"""Run codec response handling with a synthetic transport, never a device."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from blackwall_package import parse_bundle
from audit_assets import PINS

BASE, RETURN, OUTPUT, WORD, RESPONSE, STACK = 0x438000, 0x100000, 0x20001000, 0x20001100, 0x20002000, 0x2000f000
PROFILES = {
    'stock_base': dict(file='stock-2.3.0.24.bin', entry=0x59b094, end=0x59b252,
                       transport=0x59af0a, cleanup=0x59b070, failure=0x59b018,
                       log=0x43d74e, convert=0x596ed6),
    'stock_current': dict(file='stock-2.4.0.24.bin', entry=0x50361c, end=0x5037da,
                          transport=0x503492, cleanup=0x5035f8, failure=0x5035a0,
                          log=0x43d62a, convert=0x599a2e),
    'cfw': dict(file='faceclaw-38-research-only.bin', entry=0x59b094, end=0x59b252,
                transport=0x59af0a, cleanup=0x59b070, failure=0x59b018,
                log=0x43d74e, convert=0x596ed6),
}


def execute(raw, profile, mode, response=b'\x00\x00\x02\x04'):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x430000, 0x3d0000)
    cpu.mem_write(BASE, raw)
    cpu.mem_protect(0x430000, 0x3d0000, UC_PROT_READ | UC_PROT_EXEC)
    cpu.mem_map(0x20000000, 0x80000)
    cpu.mem_map(RETURN, 0x1000)
    cpu.mem_write(OUTPUT, b'\xa5'*4)
    cpu.mem_write(WORD, b'\xa5'*4)
    cpu.mem_write(RESPONSE, response)
    cpu.reg_write(UC_ARM_REG_SP, STACK)
    cpu.reg_write(UC_ARM_REG_LR, RETURN | 1)
    cpu.reg_write(UC_ARM_REG_R0, 0 if mode == 'null-output' else OUTPUT)
    cpu.reg_write(UC_ARM_REG_R1, 200)
    calls, cleanups, failures = [], [], []
    registers = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)

    def hook(uc, address, size, _):
        args = [uc.reg_read(r) for r in registers]
        result = 0
        if address == profile['log']:
            pass
        elif address == 0x43c0e4:
            if args[1:3] != [26, 0] or not 0x20000000 <= args[0] <= STACK-26:
                raise ValueError('Unexpected descriptor initialization')
            uc.mem_write(args[0], bytes(26))
        elif address == profile['transport']:
            extra = struct.unpack('<III', uc.mem_read(uc.reg_read(UC_ARM_REG_SP), 12))
            if args != [2, 0x100, 0, 0] or extra[0] != 0 or extra[2] != 200:
                raise ValueError('Unexpected codec transport request')
            descriptor = extra[1]
            calls.append({'command': args[1], 'timeout_argument': extra[2]})
            failed = mode == 'transport-failure' or (mode == 'retry-success' and len(calls) < 3)
            if failed:
                result = 0xfffffffb
            else:
                length = 3 if mode == 'short-response' else 0 if mode == 'empty-response' else 4
                uc.mem_write(descriptor+14, struct.pack('<IH', RESPONSE, length))
        elif address == profile['cleanup']:
            cleanups.append(args[0])  # Free/cleanup implementation is stubbed.
        elif address == profile['failure']:
            if args[:2] != [2, 0xfffffffb]:
                raise ValueError('Unexpected failure callback arguments')
            failures.append(args[:2])
        elif profile['entry'] <= address < profile['end'] or profile['convert'] <= address < profile['convert']+40:
            return
        else:
            raise ValueError(f'Unexpected code outside query/conversion: {address:#x}')
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.emu_start(profile['entry'] | 1, RETURN, count=3000, timeout=1000000)
    success = mode in ('valid', 'retry-success')
    expected_result = 0 if success else 0xfffffffb if mode == 'transport-failure' else 0xffffffff
    output = bytes(cpu.mem_read(OUTPUT, 4))
    if cpu.reg_read(UC_ARM_REG_PC) != RETURN or cpu.reg_read(UC_ARM_REG_SP) != STACK:
        raise ValueError('Query did not return with balanced stack')
    if cpu.reg_read(UC_ARM_REG_R0) != expected_result or output != (response if success else b'\xa5'*4):
        raise ValueError('Unexpected query return or response bytes')
    expected_attempts = 0 if mode == 'null-output' else 3 if mode in ('retry-success', 'transport-failure') else 1
    if len(calls) != expected_attempts or len(cleanups) != expected_attempts:
        raise ValueError('Unexpected retry/cleanup count')
    if len(failures) != (1 if mode == 'transport-failure' else 0):
        raise ValueError('Unexpected failure callback count')
    word = None
    if success:
        cpu.reg_write(UC_ARM_REG_R0, OUTPUT)
        cpu.reg_write(UC_ARM_REG_R1, WORD)
        cpu.reg_write(UC_ARM_REG_LR, RETURN | 1)
        cpu.emu_start(profile['convert'] | 1, RETURN, count=100, timeout=1000000)
        word = struct.unpack('<I', cpu.mem_read(WORD, 4))[0]
        if cpu.reg_read(UC_ARM_REG_PC) != RETURN or cpu.reg_read(UC_ARM_REG_SP) != STACK or word != int.from_bytes(response, 'big'):
            raise ValueError('Unexpected version conversion')
    return dict(mode=mode, response_hex=response.hex(), result=hex(expected_result),
                converted_word=None if word is None else hex(word), transport_calls=calls,
                cleanup_calls=len(cleanups), failure_callbacks=len(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results, hashes = {}, {}
    for key, profile in PROFILES.items():
        data = (args.inputs/profile['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != PINS[key]:
            raise ValueError('Bundle hash mismatch: '+key)
        raw = next(c for c in parse_bundle(data) if c.type_id == 0).payload[32:]
        hashes[key] = hashlib.sha256(raw[profile['entry']-BASE:profile['end']-BASE]).hexdigest()
        results[key] = [execute(raw, profile, mode) for mode in
                        ('valid', 'retry-success', 'transport-failure', 'short-response', 'empty-response', 'null-output')]
        results[key] += [execute(raw, profile, 'valid', fixture) for fixture in (b'\x00\x00\x02\x03', b'\x01\x02\x03\x04')]
    if hashes['cfw'] != hashes['stock_base']:
        raise ValueError('Faceclaw query body differs from stock 2.3')
    report = dict(scope='codec query wrapper and four-byte conversion, synthetic transport',
                  profiles=PROFILES, bundle_sha256={key: PINS[key] for key in PROFILES},
                  query_body_sha256=hashes, results=results,
                  stubs=['transport request', 'descriptor initialization', 'cleanup', 'failure callback', 'logging mask'],
                  hardware_validated=False, transport_executed=False, installable=False)
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print('24 codec query/conversion cases passed with synthetic transport only')


if __name__ == '__main__':
    main()
