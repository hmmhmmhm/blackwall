"""Execute SPOT classification prefix with synthetic revision/cache fixtures only."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from blackwall_package import parse_bundle
from audit_assets import PINS

BASE, STACK = 0x438000, 0x2000f000
PROFILES = {
    'stock_base': dict(file='stock-2.3.0.24.bin', entry=0x489c34, stop=0x489d7e, literals=0x489efc),
    'stock_current': dict(file='stock-2.4.0.24.bin', entry=0x495b1c, stop=0x495c66, literals=0x495de4),
    'cfw': dict(file='faceclaw-38-research-only.bin', entry=0x489c34, stop=0x489d7e, literals=0x489efc),
}
FLAG_OFFSETS = {'pcm22_or_newer': 12, 'pcm21': 16, 'pcm10_or_11': 20,
                'b0_pcm11_or_newer': 24, 'pcm20': 28, 'pcm21_without_patch': 36}


def bindings(raw, profile):
    def word(offset):
        return struct.unpack_from('<I', raw, profile['literals']-BASE+offset)[0]
    if word(4) != 0x4002000c:
        raise ValueError('CHIPREV literal mismatch')
    result = dict(context=word(0), trim_cache=word(8), tracker_cache=word(32)+0x34,
                  flags={name:word(offset) for name,offset in FLAG_OFFSETS.items()})
    if not all(0x20000000 <= address < 0x20080000 for address in
               [result['context'], result['trim_cache'], result['tracker_cache'], *result['flags'].values()]):
        raise ValueError('Unexpected RAM bindings')
    return result


def expected_flags(revision, trim, tracker):
    pcm21 = (revision == 0x22 and trim == 2) or (revision == 0x23 and trim == 1)
    return dict(pcm22_or_newer=int((revision == 0x23 and trim >= 2) or revision >= 0x24),
                pcm21=int(pcm21),
                pcm10_or_11=int((revision == 0x21 and trim in (2, 3)) or (revision == 0x22 and trim == 0)),
                b0_pcm11_or_newer=int(revision == 0x21 and trim >= 3),
                pcm20=int((revision == 0x22 and trim == 1) or (revision == 0x23 and trim == 0)),
                pcm21_without_patch=int(pcm21 and not tracker & 1))


def execute(raw, profile, layout, revision, trim, tracker):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x430000, 0x3d0000)
    cpu.mem_write(BASE, raw)
    cpu.mem_protect(0x430000, 0x3d0000, UC_PROT_READ | UC_PROT_EXEC)
    cpu.mem_map(0x20000000, 0x80000)
    cpu.mem_write(0x20000000, b'\xa5'*0x80000)
    cpu.mem_write(layout['trim_cache'], struct.pack('<I', trim))
    cpu.mem_write(layout['tracker_cache'], struct.pack('<I', tracker))
    cpu.reg_write(UC_ARM_REG_SP, STACK)
    cpu.reg_write(UC_ARM_REG_LR, 0xffffffff)
    reads, writes, stops = [], [], []

    def read(uc, offset, size, _):
        if (offset, size) != (12, 4):
            raise ValueError('Unexpected MCUCTRL read')
        reads.append(hex(uc.reg_read(UC_ARM_REG_PC)))
        return revision

    def write(uc, offset, size, value, _):
        raise ValueError('Hardware writes are outside this probe')

    cpu.mmio_map(0x40020000, 0x1000, read, None, write, None)

    def guest_write(uc, access, address, size, value, _):
        if size == 4 and address in range(STACK-16, STACK, 4):
            return  # The function's four-register PUSH only.
        if size != 1 or address not in layout['flags'].values():
            raise ValueError('Unexpected guest memory write')
        writes.append(address)

    def step(uc, address, size, _):
        if address == profile['stop']:
            stops.append(address)
            uc.emu_stop()
        elif address == 0x43c0e4:
            args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            if args != [layout['context'], 60, 0]:
                raise ValueError('Unexpected context initialization')
            uc.mem_write(layout['context'], bytes(60))
            uc.reg_write(UC_ARM_REG_R0, 0)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif not profile['entry'] <= address < profile['stop']:
            raise ValueError(f'Unexpected code boundary: {address:#x}')

    cpu.hook_add(UC_HOOK_MEM_WRITE, guest_write)
    cpu.hook_add(UC_HOOK_CODE, step)
    cpu.emu_start(profile['entry'] | 1, 0, count=1000, timeout=1000000)
    actual = {name:cpu.mem_read(address, 1)[0] for name,address in layout['flags'].items()}
    if actual != expected_flags(revision & 255, trim, tracker):
        raise ValueError('Classification flags differ from expected predicates')
    if stops != [profile['stop']] or cpu.reg_read(UC_ARM_REG_SP) != STACK-16 or sorted(writes) != sorted(layout['flags'].values()):
        raise ValueError('Unexpected stop, stack, or flag write set')
    return dict(chiprev_fixture=hex(revision), normalized_trim_cache_fixture=trim,
                tracker_cache_fixture=hex(tracker), flags=actual, chiprev_reads=len(reads))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results, layouts, hashes = {}, {}, {}
    for key, profile in PROFILES.items():
        data = (args.inputs/profile['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != PINS[key]:
            raise ValueError('Input hash mismatch: '+key)
        raw = next(c for c in parse_bundle(data) if c.type_id == 0).payload[32:]
        layout = bindings(raw, profile)
        layouts[key] = layout
        hashes[key] = hashlib.sha256(raw[profile['entry']-BASE:profile['stop']-BASE]).hexdigest()
        results[key] = [execute(raw, profile, layout, revision, trim, tracker)
                        for revision in (0x21, 0x22, 0x23, 0x24)
                        for trim in (0, 1, 2, 3) for tracker in (0, 1)]
    if hashes['stock_base'] != hashes['cfw']:
        raise ValueError('Faceclaw classification prefix differs from stock')
    report = dict(scope='SPOT classification prefix only, no power configuration or selected handler execution',
                  profiles=PROFILES, bindings=layouts, prefix_sha256=hashes,
                  bundle_sha256={key:PINS[key] for key in PROFILES}, results=results,
                  stubs=['context initialization'], synthetic_inputs=['CHIPREV', 'normalized trim cache', 'tracker cache'],
                  hardware_validated=False, boot_verified=False, installable=False)
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print('96 SPOT classification cases passed; stopped before power configuration')


if __name__ == '__main__':
    main()
