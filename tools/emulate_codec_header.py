"""Run stock codec header readers with explicit filesystem/logging stubs only."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from blackwall_package import parse_bundle
from audit_assets import PINS

BASE, RETURN, OUTPUT, HANDLE = 0x438000, 0x100000, 0x20001000, 0x1234
PROFILES = {
    'stock_base': {'file': 'stock-2.3.0.24.bin', 'entry': 0x596efe,
                   'log': 0x43d74e, 'open': 0x457dd0, 'read': 0x457ec2, 'close': 0x457e82},
    'stock_current': {'file': 'stock-2.4.0.24.bin', 'entry': 0x599a56,
                      'log': 0x43d62a, 'open': 0x480144, 'read': 0x480236, 'close': 0x4801f6},
}


def execute(raw, profile, header, mode):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x430000, 0x3d0000)
    cpu.mem_write(BASE, raw)
    cpu.mem_protect(0x430000, 0x3d0000, UC_PROT_READ | UC_PROT_EXEC)
    cpu.mem_map(0x20000000, 0x10000)
    cpu.mem_map(RETURN, 0x1000)
    cpu.mem_write(OUTPUT, b'\xa5'*4)
    cpu.reg_write(UC_ARM_REG_SP, 0x2000f000)
    cpu.reg_write(UC_ARM_REG_LR, RETURN | 1)
    cpu.reg_write(UC_ARM_REG_R0, 0 if mode == 'null-output' else OUTPUT)
    calls = []

    def cstring(address):
        return bytes(cpu.mem_read(address, 80)).split(b'\0')[0]

    def instruction(uc, address, size, _):
        matches = [name for name in ('log', 'open', 'read', 'close') if profile[name] == address]
        if not matches:
            return
        name = matches[0]
        args = [uc.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        result = 0
        if name == 'open':
            if cstring(args[0]) != b'/firmware/codec.bin' or cstring(args[1]) != b'r+':
                raise ValueError('Unexpected filesystem open request')
            result = 0 if mode == 'open-failure' else HANDLE
        elif name == 'read':
            if args[1:] != [1, 16, HANDLE]:
                raise ValueError('Unexpected filesystem read request')
            contents = header[:8] if mode == 'short-read' else header
            uc.mem_write(args[0], contents)
            result = len(contents)
        elif name == 'close' and args[0] != HANDLE:
            raise ValueError('Unexpected close handle')
        calls.append(name)
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.emu_start(profile['entry'] | 1, RETURN, count=1000, timeout=1000000)
    if cpu.reg_read(UC_ARM_REG_PC) != RETURN or cpu.reg_read(UC_ARM_REG_SP) != 0x2000f000:
        raise ValueError('Header reader did not return with balanced stack')
    result = cpu.reg_read(UC_ARM_REG_R0)
    output = struct.unpack('<I', cpu.mem_read(OUTPUT, 4))[0]
    expected_result = 0 if mode == 'valid' else 0xffffffff
    expected_output = struct.unpack_from('<I', header, 4)[0] if mode == 'valid' else 0xa5a5a5a5
    if (result, output) != (expected_result, expected_output):
        raise ValueError(f'Unexpected reader result: {result:#x}, {output:#x}')
    nonlog = [call for call in calls if call != 'log']
    expected_calls = [] if mode == 'null-output' else ['open'] if mode == 'open-failure' else ['open', 'read', 'close']
    if nonlog != expected_calls:
        raise ValueError('Unexpected filesystem call sequence')
    return {'mode': mode, 'return': hex(result), 'output_word': hex(output), 'filesystem_calls': nonlog}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    images, headers = {}, {}
    for key, profile in PROFILES.items():
        data = (args.inputs / profile['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != PINS[key]:
            raise ValueError('Input hash mismatch')
        parts = {part.type_id: part for part in parse_bundle(data)}
        images[key], headers[key] = parts[0].payload[32:], parts[4].payload[:16]
    results = {}
    for key, profile in PROFILES.items():
        results[key] = {}
        for header_key, header in headers.items():
            cases = []
            for mode in ('valid', 'bad-magic', 'short-read', 'open-failure', 'null-output'):
                fixture = b'BAD!' + header[4:] if mode == 'bad-magic' else header
                cases.append(execute(images[key], profile, fixture, mode))
            results[key][header_key] = cases
    report = {'scope': 'codec package header reader only', 'results': results,
              'profiles': PROFILES, 'bundle_sha256': {key: PINS[key] for key in PROFILES},
              'stubbed_functions': ['filesystem open/read/close', 'logging enabled mask returns zero'],
              'codec_execution_emulated': False, 'hardware_validated': False, 'installable': False}
    with args.output.open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
    print('20 header reader cases passed; codec compatibility is not established')


if __name__ == '__main__':
    main()
