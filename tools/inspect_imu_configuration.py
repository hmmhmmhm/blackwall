"""Bind actual INT1 caller arguments and original pin configuration RMW/error ABI."""
import argparse
import json
import struct
from pathlib import Path
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_iom4_command import sources
from inspect_keydb_record_load import run
from inspect_nema_blocking_wait import cpu, WORK, STOP
from prepare_vendor_startup_candidate import sha


def inspect(s, case):
    m = json.loads((s / 'imu-tags-verification-01/manifest.json').read_text())
    path = s / 'imu-tags-saved-audit-01' / case / 'report.json'
    if not m['passed'] or sha(path) != m['files'][str(path.relative_to(s))]:
        raise ValueError('Changed native INT1 frontier')
    a = json.loads(path.read_text())
    if not a['passed']:
        raise ValueError('Unverified INT1 frontier')
    f = Path(a['capture'])
    for n, value in a['capture_hashes'].items():
        if sha(f / n) != value:
            raise ValueError('Changed source ' + n)
    d = json.loads((f / 'report.json').read_text())
    raw, ram = (f / 'main.bin').read_bytes(), (f / 'exports/sram-full.bin').read_bytes()
    sp0 = d['observed']['register_context']['r13']
    word = lambda off: struct.unpack_from('<I', ram, sp0 + off - 0x20000000)[0]
    read_return = word(0xb4) & ~1
    entry = read_return - 0x22
    body = decode(raw, entry, 0x70)
    calls = [i for i in body if i.mnemonic == 'bl']
    if len(calls) != 2 or calls[0].address + 4 != read_return or (body[0].mnemonic, body[0].op_str) != ('push', '{r3, r4, r5, r6, r7, lr}'):
        raise ValueError('Different pin-config stack frame')
    conf = word(0xb0)
    actual_conf = list(ram[conf - 0x20000000:conf + 3 - 0x20000000])
    caller_return = word(0xcc) & ~1
    caller = decode(raw, caller_return - 4, 4)[0]
    if conf != sp0 + 0xd0 or actual_conf != [1, 0, 0] or caller.mnemonic != 'bl' or caller.operands[0].imm != entry:
        raise ValueError('Changed original caller/config bytes')
    rows = []
    sp, context, config = WORK + 0xf000, WORK + 0x100, WORK + 0x200
    for number in [0, 1, 2, 255, 256]:
        u = cpu(raw, ram, sp)
        u.reg_write(arm.UC_ARM_REG_R0, context)
        u.reg_write(arm.UC_ARM_REG_R1, number)
        u.reg_write(arm.UC_ARM_REG_R2, config)
        t = run(u, entry, [calls[0].operands[0].imm])
        if number & 255 in (0, 1):
            if t['stop'] != calls[0].operands[0].imm or u.reg_read(arm.UC_ARM_REG_R1) != (0x18 if number & 255 == 0 else 0x58):
                raise ValueError('Changed interrupt selector')
        elif u.reg_read(arm.UC_ARM_REG_R0) != 0xfffffff5 or u.reg_read(arm.UC_ARM_REG_SP) != sp:
            raise ValueError('Changed invalid selector return')
        rows.append(dict(kind='selector', number=number, execution=t))
    for initial in range(256):
        for bits in range(8):
            u = cpu(raw, ram, sp)
            u.mem_write(sp, bytes([initial, 0, 0, 0]))
            values = [(bits >> k) & 1 for k in range(3)]
            u.mem_write(config, bytes(values))
            for reg, value in [(0, 0), (4, context), (5, 0), (6, 0x18), (7, config)]:
                u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(reg)), value)
            t = run(u, read_return, [calls[1].address])
            args = [u.reg_read(getattr(arm, 'UC_ARM_REG_R' + str(k))) for k in range(4)]
            prepared = bytes(u.mem_read(sp, 1))[0]
            if args != [context, 0x18, 1, sp] or prepared != ((initial & 0xf8) | bits):
                raise ValueError('Original RMW failed to preserve upper bits')
            rows.append(dict(kind='rmw-argument-fragment', initial=initial, fields=values, prepared=prepared, callee_executed=False, execution=t))
    for read_status in [4]:
        u = cpu(raw, ram, sp)
        u.mem_write(sp, b'\xa6\x00\x00\x00')
        u.mem_write(config, b'\x01\x00\x00')
        for reg, value in [(0, read_status), (4, context), (5, 0), (6, 0x18), (7, config)]:
            u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(reg)), value)
        t = run(u, read_return, [calls[1].address])
        if u.reg_read(arm.UC_ARM_REG_R5) != read_status or bytes(u.mem_read(sp, 1)) != b'\xa1':
            raise ValueError('Original read error preparation differs')
        rows.append(dict(kind='read-error-still-prepares-write', status=read_status, execution=t))
    for accumulated, last in [(0, 0), (4, 0), (0, 0xfffffffd), (4, 0xfffffffd)]:
        u = cpu(raw, ram, sp)
        u.mem_write(sp, struct.pack('<6I', 0, 1, 2, 3, 4, STOP | 1))
        u.reg_write(arm.UC_ARM_REG_R5, accumulated)
        u.reg_write(arm.UC_ARM_REG_R0, last)
        t = run(u, calls[1].address + 4, [])
        if u.reg_read(arm.UC_ARM_REG_R0) != (accumulated | last) or u.reg_read(arm.UC_ARM_REG_SP) != sp + 24:
            raise ValueError('Original write error return differs')
        rows.append(dict(kind='status-or-return-fragment', accumulated=accumulated, last=last, execution=t))
    return dict(case=case, source_audit_sha256=sha(path), raw_sha256=sha(f / 'main.bin'), entry=entry,
                caller_return=caller_return, actual_config=actual_conf, actual_low_bits=1,
                register=0x18, preserved_mask=0xf8, writable_mask=7, samples=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or not a.output.resolve().is_relative_to(a.simulator.resolve()):
        raise ValueError('Fresh private output required')
    src = sources(a.simulator)
    rows = [inspect(a.simulator, case) for case in ['stock24', 'stock23', 'cfw']]
    a.output.mkdir(mode=0o700)
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    n = sum(len(x['samples']) for x in rows)
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, sources=src,
        original_arm_fragment_scenarios=n, native_main_rerun=False, interrupt_generation_verified=False,
        power_odr_configuration_verified=False, hardware_accessed=False, boot_verified=False, display_verified=False), indent=2) + '\n')
    print('Verified original INT1 caller/RMW/error fragments', n)


if __name__ == '__main__':
    main()
