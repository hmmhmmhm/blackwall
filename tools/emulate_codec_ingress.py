"""Bounded codec callback registration and RAM-state ingress; no device I/O."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS,
                     UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC)
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
from audit_assets import PINS
from blackwall_package import parse_bundle
from emulate_codec_callers import PROFILES as CALLERS
from emulate_codec_flow import PROFILES as FLOWS
from emulate_codec_query import PROFILES as QUERIES

BASE, SRAM, SRAM_SIZE, STACK = 0x438000, 0x20000000, 0x80000, 0x2000f000
PROFILES = {
    'stock_base': dict(registration=0x5592a8, factory=0x442896, parent=0x559490,
                       after_selector=0x5594a6, prepare=0x559294, gate=0x4e3734,
                       selector_byte=0x200046e9, state_byte=0x200784db, init=0x200773f8),
    'stock_current': dict(registration=0x57d1ec, factory=0x4427f2, parent=0x57d3d4,
                          after_selector=0x57d3ea, prepare=0x57d1d8, gate=0x4ede02,
                          selector_byte=0x200069f5, state_byte=0x20077d6c, init=0x2007698c),
}
PROFILES['cfw'] = dict(PROFILES['stock_base'])


def execute(raw, key, selector=None, state=None):
    p, caller = PROFILES[key], CALLERS[key]
    registration = selector is None
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x430000, 0x3d0000)
    cpu.mem_write(BASE, raw)
    cpu.mem_protect(0x430000, 0x3d0000, UC_PROT_READ | UC_PROT_EXEC)
    cpu.mem_map(SRAM, SRAM_SIZE, UC_PROT_READ | UC_PROT_WRITE)
    cpu.mem_write(SRAM, b'\xa5' * SRAM_SIZE)
    if not registration:
        cpu.mem_write(p['selector_byte'], bytes([selector]))
        cpu.mem_write(p['state_byte'], bytes([state]))
    cpu.reg_write(UC_ARM_REG_SP, STACK)
    cpu.reg_write(UC_ARM_REG_LR, 0xffffffff)
    trace, writes, stubs, result = [], [], [], []
    ranges = [(p['registration'], p['registration'] + 20)] if registration else [
        (p['parent'], p['after_selector']), (p['prepare'], p['prepare'] + 10),
        (caller['selector'], caller['selector'] + 22),
        (caller['direct'], caller['direct'] + 10),
        (caller['state'], caller['other']),
        (caller['selector_get'], caller['selector_get'] + 6),
        (caller['state_get'], caller['state_get'] + 8), (0x43c0e4, 0x43c14a)]

    def on_write(uc, access, address, size, value, _):
        stack_write = STACK - 128 <= address and address + size <= STACK
        init_write = (not registration and p['init'] <= address
                      and address + size <= p['init'] + caller['state_bytes'])
        if not (stack_write or init_write):
            raise ValueError(f'Unexpected write at {address:#x}+{size}')
        writes.append(dict(pc=hex(uc.reg_read(UC_ARM_REG_PC)), address=hex(address), size=size))

    def step(uc, address, size, _):
        trace.append(hex(address))
        if registration and address == p['factory']:
            args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            if args[:2] != [p['parent'] | 1, 0]:
                raise ValueError('Unexpected callback/argument at factory boundary')
            result.append(dict(boundary='factory-entry', callback=hex(args[0]),
                               callback_argument=args[1], descriptor=hex(args[2])))
            uc.emu_stop()
        elif not registration and address in (FLOWS[key]['entry'], caller['other'], p['after_selector']):
            expected = FLOWS[key]['entry'] if selector == 1 or state == 2 else caller['other']
            if address != expected or (address == FLOWS[key]['entry'] and uc.reg_read(UC_ARM_REG_R0) != 0):
                raise ValueError(f'Unexpected route key={key} selector={selector} state={state}: '
                                 f'pc={address:#x}, expected={expected:#x}, '
                                 f'r0={uc.reg_read(UC_ARM_REG_R0):#x}; trace={trace}')
            result.append(dict(boundary='codec-check-entry' if address == FLOWS[key]['entry'] else 'other-state-path',
                               force_argument=0 if address == FLOWS[key]['entry'] else None))
            uc.emu_stop()
        elif not registration and address == 0x43c0e4:
            args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            if args != [p['init'], caller['state_bytes'], 0]:
                raise ValueError('Unexpected initialization arguments')
            cpu.mem_write(args[0], bytes(args[1]))
            stubs.append(dict(address=hex(address), arguments=args,
                              effects='Exact-length zero initialization; original memset not executed'))
            uc.reg_write(UC_ARM_REG_R0, args[0])
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif not registration and address == p['gate']:
            if uc.reg_read(UC_ARM_REG_R0) != 3:
                raise ValueError('Unexpected preparation gate argument')
            stubs.append(dict(address=hex(address), argument=3, return_value=0,
                              effects='No side effects modeled; real service is unknown'))
            uc.reg_write(UC_ARM_REG_R0, 0)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif not any(start <= address and address + size <= end for start, end in ranges):
            raise ValueError(f'Unexpected execution at {address:#x}')

    cpu.hook_add(UC_HOOK_MEM_WRITE, on_write)
    cpu.hook_add(UC_HOOK_CODE, step)
    cpu.emu_start((p['registration'] if registration else p['parent']) | 1,
                  0, count=500, timeout=1000000)
    if len(result) != 1:
        raise ValueError('No terminal boundary reached within execution limit')
    init = bytes(cpu.mem_read(p['init'] - 4, caller['state_bytes'] + 8))
    expected_init = b'\xa5' * 4 + (b'\xa5' if registration or selector == 1 else b'\x00') * caller['state_bytes'] + b'\xa5' * 4
    if init != expected_init:
        raise ValueError('Initialization or guard bytes mismatch')
    return dict(selector=selector, state=state, result=result[0], trace=trace,
                writes=writes, stub_calls=stubs, initialized_bytes=0 if registration or selector == 1 else caller['state_bytes'],
                initialization_and_guards_hex=init.hex())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    results = {}
    for key in PROFILES:
        data = (args.inputs / QUERIES[key]['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != PINS[key]:
            raise ValueError('Bundle hash mismatch: ' + key)
        raw = next(c for c in parse_bundle(data) if c.type_id == 0).payload[32:]
        results[key] = dict(main_sha256=hashlib.sha256(raw).hexdigest(),
                            registration=execute(raw, key),
                            states=[execute(raw, key, a, b) for a in (0, 1, 2, 255) for b in (0, 1, 2, 255)])
    report = dict(scope='Three factory-boundary probes and 48 fixture-based parent ingress probes',
                  profiles=PROFILES, bundle_sha256=PINS,
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), results=results,
                  hardware_validated=False, installable=False, full_boot_verified=False,
                  factory_executed=False, codec_check_executed=False,
                  limitations=['RAM selector/state values are fixtures, not observed boot values',
                               'Memset is an exact-length zero-fill stub; original-memset execution is unresolved',
                               'Unknown preparation service is stubbed without side effects',
                               'Factory identity and its upstream reachability are not established',
                               'Forced-check field wrapper input provenance remains unknown',
                               'No transport, file access, codec update or persistent hardware writes executed'])
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print('3 registration and 48 RAM-state ingress probes passed; stopped before factory/codec check')


if __name__ == '__main__':
    main()
