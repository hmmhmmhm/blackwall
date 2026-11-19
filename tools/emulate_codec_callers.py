"""Run small codec caller wrappers with explicit selector/state fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from blackwall_package import parse_bundle
from audit_assets import PINS
from emulate_codec_flow import PROFILES as FLOWS
from emulate_codec_query import PROFILES as QUERIES

BASE, STACK, STRUCT = 0x438000, 0x2000f000, 0x20001000
PROFILES = {
    'stock_base': dict(direct=0x55946e, field=0x5599b6, selector=0x559478,
                       selector_get=0x4bff34, state=0x56e666, state_get=0x465d4c, other=0x56e694, state_bytes=8),
    'stock_current': dict(direct=0x57d3b2, field=0x57d8fe, selector=0x57d3bc,
                          selector_get=0x4cd8e4, state=0x52af6a, state_get=0x465a5c, other=0x52af98, state_bytes=9),
}
PROFILES['cfw'] = dict(PROFILES['stock_base'])


def execute(raw, key, case):
    p, target = PROFILES[key], FLOWS[key]['entry']
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x430000, 0x3d0000)
    cpu.mem_write(BASE, raw)
    cpu.mem_protect(0x430000, 0x3d0000, UC_PROT_READ | UC_PROT_EXEC)
    cpu.mem_map(0x20000000, 0x80000)
    cpu.mem_write(STRUCT+8, struct.pack('<I', case.get('field', 0)))
    cpu.reg_write(UC_ARM_REG_SP, STACK)
    cpu.reg_write(UC_ARM_REG_LR, 0xffffffff)
    cpu.reg_write(UC_ARM_REG_R0, STRUCT)
    trace, result, stubs = [], [], []

    def step(uc, address, size, _):
        trace.append(hex(address))
        if address == target:
            result.append(dict(boundary='codec-check-entry', force_argument=uc.reg_read(UC_ARM_REG_R0)))
            uc.emu_stop()
        elif address == p['other']:
            result.append(dict(boundary='other-state-path', force_argument=None))
            uc.emu_stop()
        elif address in (p['selector_get'], p['state_get'], 0x43c0e4):
            if address == 0x43c0e4:
                start, length, value = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
                if length != p['state_bytes'] or value != 0 or not 0x20000000 <= start <= 0x20080000-length:
                    raise ValueError(f'Unexpected caller initialization: {start:#x}, {length}, {value}')
                uc.mem_write(start, bytes(length))
                value = 0
            else:
                value = case.get('selector', 0) if address == p['selector_get'] else case.get('state', 0)
            stubs.append(hex(address))
            uc.reg_write(UC_ARM_REG_R0, value)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif not any(start <= address < end for start, end in
                     ((p['direct'], p['direct']+10), (p['field'], p['field']+22),
                      (p['selector'], p['selector']+22), (p['state'], p['other']))):
            raise ValueError(f'Unexpected caller execution: {address:#x}')

    cpu.hook_add(UC_HOOK_CODE, step)
    cpu.emu_start(p[case['entry']] | 1, 0, count=300, timeout=1000000)
    expected = dict(boundary='other-state-path', force_argument=None) if case.get('other') else dict(boundary='codec-check-entry', force_argument=case['force'])
    if result != [expected]:
        raise ValueError('Unexpected wrapper outcome: '+case['name'])
    return dict(case=case, result=result[0], trace=trace, stub_calls=stubs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = [dict(name='direct', entry='direct', force=0),
             dict(name='field-zero', entry='field', field=0, force=0),
             dict(name='field-one', entry='field', field=1, force=1),
             dict(name='field-erased', entry='field', field=0xffffffff, force=1),
             dict(name='selector-one', entry='selector', selector=1, force=0),
             dict(name='selector-other-state-two', entry='selector', selector=0, state=2, force=0),
             dict(name='selector-other-state-one', entry='selector', selector=0, state=1, other=True)]
    results = {}
    for key in PROFILES:
        data = (args.inputs/QUERIES[key]['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != PINS[key]:
            raise ValueError('Bundle hash mismatch: '+key)
        raw = next(c for c in parse_bundle(data) if c.type_id == 0).payload[32:]
        results[key] = [execute(raw, key, case) for case in cases]
    report = dict(scope='small upper caller wrappers; all selector/state values are fixtures',
                  profiles=PROFILES, bundle_sha256={key:PINS[key] for key in PROFILES}, results=results,
                  codec_check_executed=False, hardware_validated=False, boot_reachability_verified=False,
                  limitations=['Selector and state getters are stubbed; their real meaning is unknown',
                               'Input structure field provenance is unknown', 'Stop before codec check or other-state side effects'])
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print('21 caller wrapper cases passed; stopped before codec check')


if __name__ == '__main__':
    main()
