"""Execute codec check from its entry, stopping before update; all I/O is synthetic."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from blackwall_package import parse_bundle
from audit_assets import PINS
from emulate_codec_query import PROFILES as QUERIES
from emulate_codec_header import PROFILES as HEADERS

BASE, RETURN, STACK, RESPONSE, HANDLE = 0x438000, 0x100000, 0x2000f000, 0x20002000, 0x1234
PROFILES = {
    'stock_base': dict(entry=0x598944, update=0x598c2c, epilogue=0x598ce8,
                       mode=0x59919e, format=0x596ea0),
    'stock_current': dict(entry=0x59b49c, update=0x59b784, epilogue=0x59b840,
                          mode=0x5ae9ee, format=0x5999f8),
}
PROFILES['cfw'] = dict(PROFILES['stock_base'])


def execute(raw, key, package_header, case):
    p, q = PROFILES[key], QUERIES[key]
    h = HEADERS['stock_base' if key == 'cfw' else key]
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x430000, 0x3d0000)
    cpu.mem_write(BASE, raw)
    cpu.mem_protect(0x430000, 0x3d0000, UC_PROT_READ | UC_PROT_EXEC)
    cpu.mem_map(0x20000000, 0x80000)
    cpu.mem_map(RETURN, 0x1000)
    cpu.mem_write(RESPONSE, case['queried'].to_bytes(4, 'big'))
    cpu.reg_write(UC_ARM_REG_SP, STACK)
    cpu.reg_write(UC_ARM_REG_LR, RETURN | 1)
    cpu.reg_write(UC_ARM_REG_R0, case['force'])
    calls, trace, stopped = [], [], []
    registers = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
    io_mode = case.get('io', 'valid')
    header = b'BAD!' + package_header[4:] if io_mode == 'bad-magic' else package_header

    def hook(uc, address, size, _):
        trace.append(address)
        if address == p['update']:
            stopped.append('upgrade-path-boundary')
            uc.emu_stop()
            return
        args = [uc.reg_read(r) for r in registers]
        result, name = 0, None
        if address == q['log']:
            name = 'logging-mask'
        elif address == p['mode']:
            if args[0] != 0:
                raise ValueError('Unexpected mode argument')
            name = 'mode-control'
        elif address == p['format']:
            name = 'version-format'
        elif address == 0x43c0e4:
            if args[1] not in (4, 26, 32) or args[2] != 0 or not 0x20000000 <= args[0] <= STACK-args[1]:
                raise ValueError('Unexpected memory initialization')
            uc.mem_write(args[0], bytes(args[1]))
            name = 'memory-initialize'
        elif address == h['open']:
            path = bytes(uc.mem_read(args[0], 80)).split(b'\0')[0]
            mode = bytes(uc.mem_read(args[1], 8)).split(b'\0')[0]
            if (path, mode) != (b'/firmware/codec.bin', b'r+'):
                raise ValueError('Unexpected filesystem request')
            name, result = 'file-open', 0 if io_mode == 'open-failure' else HANDLE
        elif address == h['read']:
            if args[1:] != [1, 16, HANDLE]:
                raise ValueError('Unexpected header read')
            uc.mem_write(args[0], header)
            name, result = 'file-read', len(header)
        elif address == h['close']:
            if args[0] != HANDLE:
                raise ValueError('Unexpected file close')
            name = 'file-close'
        elif address == q['transport']:
            extra = struct.unpack('<III', uc.mem_read(uc.reg_read(UC_ARM_REG_SP), 12))
            if args != [2, 0x100, 0, 0] or extra[0] != 0 or extra[2] != 200:
                raise ValueError('Unexpected codec query request')
            name = 'query-transport'
            if io_mode == 'query-failure':
                result = 0xfffffffb
            else:
                uc.mem_write(extra[1]+14, struct.pack('<IH', RESPONSE, 3 if io_mode == 'short-response' else 4))
        elif address == q['cleanup']:
            name = 'response-cleanup'
        elif address == q['failure']:
            if args[:2] != [2, 0xfffffffb]:
                raise ValueError('Unexpected query failure callback')
            name = 'query-failure-callback'
        elif (p['entry'] <= address <= p['epilogue']+2 or
              h['entry'] <= address < h['entry']+0x210 or
              q['entry'] <= address < q['end'] or
              q['convert'] <= address < q['convert']+40):
            return
        else:
            raise ValueError(f'Unexpected function outside bounded flow: {address:#x}')
        calls.append(name)
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.emu_start(p['entry'] | 1, RETURN, count=10000, timeout=1000000)
    outcome = stopped[0] if stopped else 'returned' if cpu.reg_read(UC_ARM_REG_PC) == RETURN else 'instruction-limit'
    expected_queries = case['queries']
    if outcome != case['outcome'] or calls.count('query-transport') != expected_queries:
        raise ValueError(f'{key}/{case["name"]}: unexpected outcome {outcome}, queries {calls.count("query-transport")}')
    result = cpu.reg_read(UC_ARM_REG_R0)
    if outcome == 'returned':
        if result != case['result'] or cpu.reg_read(UC_ARM_REG_SP) != STACK:
            raise ValueError('Unexpected return result or stack')
    elif cpu.reg_read(UC_ARM_REG_SP) != STACK-0x68:
        raise ValueError('Unexpected caller stack at update boundary')
    return dict(name=case['name'], force_argument=case['force'], io=io_mode,
                outcome=outcome, result=hex(result) if outcome == 'returned' else None,
                query_calls=expected_queries, calls=calls, trace=[hex(a) for a in trace])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    results = {}
    for key, q in QUERIES.items():
        data = (args.inputs/q['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != PINS[key]:
            raise ValueError('Bundle hash mismatch: '+key)
        parts = {c.type_id: c for c in parse_bundle(data)}
        raw, header = parts[0].payload[32:], parts[4].payload[:16]
        version = struct.unpack_from('<I', header, 4)[0]
        cases = [
            dict(name='equal', force=0, queried=version, outcome='returned', result=1, queries=1),
            dict(name='different', force=0, queried=version ^ 7, outcome='upgrade-path-boundary', queries=1),
            dict(name='force-one', force=1, queried=version, outcome='upgrade-path-boundary', queries=0),
            dict(name='force-upper-byte-only', force=256, queried=version, outcome='returned', result=1, queries=1),
            dict(name='query-failure', force=0, queried=version, io='query-failure', outcome='upgrade-path-boundary', queries=3),
            dict(name='short-response', force=0, queried=version, io='short-response', outcome='upgrade-path-boundary', queries=1),
            dict(name='open-failure', force=0, queried=version, io='open-failure', outcome='returned', result=0xffffffff, queries=0),
            dict(name='forced-open-failure', force=1, queried=version, io='open-failure', outcome='returned', result=0xffffffff, queries=0),
            dict(name='bad-magic', force=0, queried=version, io='bad-magic', outcome='returned', result=0xffffffff, queries=0),
        ]
        results[key] = [execute(raw, key, header, case) for case in cases]
    report = dict(scope='codec check entry through decision, real header/query/conversion code with synthetic I/O',
                  profiles=PROFILES, bundle_sha256={key:PINS[key] for key in PROFILES}, results=results,
                  stubs=['filesystem', 'query transport', 'cleanup', 'failure callback', 'memory initialization', 'mode control', 'version formatting', 'logging mask'],
                  caller_reachability_verified=False, upgrade_executed=False, hardware_validated=False, installable=False)
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print('27 entry-to-decision cases passed; update code never executed')


if __name__ == '__main__':
    main()
