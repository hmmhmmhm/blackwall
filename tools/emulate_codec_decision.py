"""Execute the codec version decision slice; stop before any update code."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0
from blackwall_package import parse_bundle
from audit_assets import PINS

BASE, STACK = 0x438000, 0x20008000
PROFILES = {
    'stock_base': ('stock-2.3.0.24.bin', 0x598b70, 0x598c2c, 0x598ce8, 0x43d74e),
    'stock_current': ('stock-2.4.0.24.bin', 0x59b6c8, 0x59b784, 0x59b840, 0x43d62a),
    'cfw': ('faceclaw-38-research-only.bin', 0x598b70, 0x598c2c, 0x598ce8, 0x43d74e),
}


def execute(raw, profile, package_word, queried_word):
    _, start, update, epilogue, logging = profile
    # These four instructions load the two caller locals, compare, and branch.
    if raw[start-BASE:start-BASE+8] != bytes.fromhex('0598049988421ed1'):
        raise ValueError('Codec decision instruction guard mismatch')
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x430000, 0x3d0000)
    cpu.mem_write(BASE, raw)
    cpu.mem_protect(0x430000, 0x3d0000, UC_PROT_READ | UC_PROT_EXEC)
    cpu.mem_map(0x20000000, 0x10000)
    cpu.mem_write(STACK+0x10, struct.pack('<II', package_word, queried_word))
    cpu.reg_write(UC_ARM_REG_SP, STACK)
    trace, boundary = [], []

    def step(uc, address, size, _):
        trace.append(address)
        if address == logging:
            uc.reg_write(UC_ARM_REG_R0, 0)  # Disable both logging paths only.
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif address in (update, epilogue):
            boundary.append(address)
            uc.emu_stop()
        elif not start <= address < update:
            raise ValueError(f'Unexpected execution outside decision slice: {address:#x}')

    cpu.hook_add(UC_HOOK_CODE, step)
    cpu.emu_start(start | 1, 0, count=200, timeout=1000000)
    expected = epilogue if package_word == queried_word else update
    if boundary != [expected] or cpu.reg_read(UC_ARM_REG_SP) != STACK:
        raise ValueError('Unexpected decision boundary or unbalanced stack')
    if expected == epilogue and cpu.reg_read(UC_ARM_REG_R0) != 1:
        raise ValueError('Equal versions did not select no-upgrade result')
    if bytes(cpu.mem_read(STACK+0x10, 8)) != struct.pack('<II', package_word, queried_word):
        raise ValueError('Version inputs were modified')
    return {'package_word': hex(package_word), 'queried_word': hex(queried_word),
            'decision': 'no-upgrade' if expected == epilogue else 'upgrade-path-boundary',
            'stopped_before_instruction': hex(expected), 'trace': [hex(a) for a in trace]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    images, hashes = {}, {}
    for key, profile in PROFILES.items():
        data = (args.inputs / profile[0]).read_bytes()
        if hashlib.sha256(data).hexdigest() != PINS[key]:
            raise ValueError('Input bundle hash mismatch: '+key)
        images[key] = next(c for c in parse_bundle(data) if c.type_id == 0).payload[32:]
        start, stop = profile[1], profile[2]
        hashes[key] = hashlib.sha256(images[key][start-BASE:stop-BASE]).hexdigest()
    if hashes['cfw'] != hashes['stock_base']:
        raise ValueError('Faceclaw decision slice differs from stock 2.3')
    cases = [(0x203, 0x203), (0x204, 0x204), (0x203, 0x204),
             (0x204, 0x203), (0x203, 0), (0x203, 0xffffffff)]
    results = {key: [execute(images[key], profile, *case) for case in cases]
               for key, profile in PROFILES.items()}
    rejected = 0
    for key, profile in PROFILES.items():
        damaged = bytearray(images[key])
        damaged[profile[1]-BASE+7] ^= 1
        try:
            execute(bytes(damaged), profile, 0x203, 0x204)
        except ValueError as error:
            if str(error) != 'Codec decision instruction guard mismatch':
                raise
            rejected += 1
        else:
            raise ValueError('Changed decision instruction was accepted')
    report = {'scope': 'caller version comparison slice only; locals are supplied fixtures',
              'bundle_sha256': {key: PINS[key] for key in PROFILES},
              'slice_sha256': hashes, 'profiles': PROFILES, 'results': results,
              'changed_instruction_rejections': rejected,
              'stubs': ['logging enabled mask returns zero'],
              'version_query_executed': False, 'upgrade_executed': False,
              'hardware_validated': False, 'installable': False}
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print('18 codec decision cases passed; all update paths stopped before execution')


if __name__ == '__main__':
    main()
