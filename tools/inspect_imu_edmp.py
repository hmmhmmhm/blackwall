"""Bind the five original EDMP clears, legacy conditional bits and idle/error loop."""
import argparse
import json
import struct
import re
from pathlib import Path
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_iom4_command import sources
from inspect_keydb_record_load import run
from inspect_nema_blocking_wait import cpu, WORK, STOP
from prepare_vendor_startup_candidate import sha


def frame(raw, ram, size=24):
    sp = WORK + 0xf000
    u = cpu(raw, ram, sp)
    u.mem_write(sp, struct.pack('<' + 'I' * (size // 4), *([0] * (size // 4 - 1) + [STOP | 1])))
    for n, value in [(0, 0), (4, WORK + 0x100), (5, 0), (6, 10)]:
        u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), value)
    return u, sp


def inspect(s, case):
    manifest = json.loads((s / 'imu-configuration-verification-01/manifest.json').read_text())
    p = s / 'imu-configuration-saved-audit-01' / case / 'report.json'
    if not manifest['passed'] or sha(p) != manifest['files'][str(p.relative_to(s))]:
        raise ValueError('Changed EDMP source audit')
    a = json.loads(p.read_text())
    f = Path(a['capture'])
    for name, value in a['capture_hashes'].items():
        if sha(f / name) != value:
            raise ValueError('Changed source ' + name)
    flow_path = s / 'imu-configuration-verification-01/next-flow-report.json'
    if sha(flow_path) != manifest['files'][str(flow_path.relative_to(s))]:
        raise ValueError('Changed five-call/gate contract')
    flow = next(x for x in json.loads(flow_path.read_text())['cases'] if x['case'] == case)
    raw, ram = (f / 'main.bin').read_bytes(), (f / 'exports/sram-full.bin').read_bytes()
    rows, functions = [], []
    for n, (entry, reg, mask) in enumerate(zip(flow['prerequisite_calls'], [0x2a, 0x29, 0x29, 0x29, 0x2a], [0xef, 0xfb, 0xf7, 0xfe, 0xbf])):
        body = []
        for i in decode(raw, entry, 380):
            body.append(i)
            if i.mnemonic in ('pop', 'pop.w') and 'pc' in i.op_str:
                break
        calls = [i for i in body if i.mnemonic == 'bl']
        if not any(i.mnemonic == 'ands' and i.op_str == 'r0, r0, #' + hex(mask) for i in body):
            raise ValueError('Changed original clear mask')
        for byte in range(256):
            u, sp = frame(raw, ram)
            u.mem_write(sp, bytes([byte]))
            t = run(u, calls[0].address + 4, [calls[1].address])
            args = [u.reg_read(getattr(arm, 'UC_ARM_REG_R' + str(k))) for k in range(4)]
            if args != [WORK + 0x100, reg, 1, sp] or bytes(u.mem_read(sp, 1)) != bytes([byte & mask]):
                raise ValueError('Original primary RMW differs')
            rows.append(dict(kind='primary-rmw-fragment', function=n, byte=byte, mask=mask, execution=t))
        u, sp = frame(raw, ram)
        u.mem_write(sp, b'\xff')
        u.reg_write(arm.UC_ARM_REG_R0, 0xfffffffd)
        t = run(u, calls[0].address + 4, [calls[1].address])
        if u.reg_read(arm.UC_ARM_REG_R5) != 0xfffffffd or bytes(u.mem_read(sp, 1)) != bytes([mask]):
            raise ValueError('Read error no longer prepares clear')
        rows.append(dict(kind='read-error-fragment', function=n, execution=t))
        if n in (1, 2):
            bit = 3 if n == 1 else 2
            if len(calls) != 4:
                raise ValueError('Changed conditional secondary clear')
            for byte in range(256):
                u, sp = frame(raw, ram)
                u.mem_write(sp, bytes([byte]))
                t = run(u, calls[1].address + 4, [calls[2].address])
                expected = calls[2].address if not byte & (1 << bit) else STOP
                if t['stop'] != expected:
                    raise ValueError('Changed legacy bit predicate')
                rows.append(dict(kind='legacy-bit-predicate', function=n, byte=byte, secondary=expected != STOP, execution=t))
            for byte in [0, 0xff, 0xa5, 0x5a, 0xcf]:
                u, sp = frame(raw, ram)
                u.mem_write(sp + 1, bytes([byte]))
                t = run(u, calls[2].address + 4, [calls[3].address])
                if bytes(u.mem_read(sp + 1, 1)) != bytes([byte & 0xdf]) or u.reg_read(arm.UC_ARM_REG_R1) != 0x2a:
                    raise ValueError('Changed feature3 clear')
                rows.append(dict(kind='secondary-rmw-fragment', function=n, byte=byte, execution=t))
        functions.append(dict(entry=entry, register=reg, clear_mask=mask, calls=[i.operands[0].imm for i in calls]))
    idle = functions[-1]['calls'][2]
    ibody = decode(raw, idle, 0x44)
    icalls = [i for i in ibody if i.mnemonic == 'bl']
    counter = literal(raw, next(i for i in ibody if i.mnemonic == 'ldr' and i.op_str.startswith('r6,')))
    if counter != 1000000 or len(icalls) != 2 or not any(i.mnemonic == 'movw' and i.op_str == 'r1, #0xa297' for i in ibody):
        raise ValueError('Changed idle address/counter')
    for byte in [0, 1, 2, 3, 255]:
        for status in [0, 0xfffffffd]:
            u, sp = frame(raw, ram)
            u.mem_write(sp, bytes([byte]))
            u.reg_write(arm.UC_ARM_REG_R0, status)
            u.reg_write(arm.UC_ARM_REG_R4, 0)
            u.reg_write(arm.UC_ARM_REG_R5, WORK + 0x100)
            t = run(u, icalls[0].address + 4, [icalls[1].address])
            if t['stop'] != (STOP if byte & 2 else icalls[1].address):
                raise ValueError('Changed idle return/delay predicate')
            if byte & 2 and u.reg_read(arm.UC_ARM_REG_R0) != status or not byte & 2 and u.reg_read(arm.UC_ARM_REG_R1) != 5:
                raise ValueError('Changed idle status or sleep argument')
            rows.append(dict(kind='idle-predicate-fragment', byte=byte, status=status, execution=t))
    for remaining in [5, 10]:
        for status in [0, 4, 0xfffffffd]:
            u, sp = frame(raw, ram)
            u.reg_write(arm.UC_ARM_REG_R4, status)
            u.reg_write(arm.UC_ARM_REG_R5, WORK + 0x100)
            u.reg_write(arm.UC_ARM_REG_R6, remaining)
            t = run(u, icalls[1].address + 4, [icalls[0].address])
            expected = 0xfffffffc if remaining == 5 else status
            if remaining == 10 and status == 0:
                if t['stop'] != icalls[0].address:
                    raise ValueError('Changed repeat-poll edge')
            elif t['stop'] != STOP or u.reg_read(arm.UC_ARM_REG_R0) != expected:
                raise ValueError('Changed timeout/error return')
            rows.append(dict(kind='counter-edge-fragment', remaining=remaining, status=status, expected=expected, execution=t))
    return dict(case=case, source_audit_sha256=sha(p), functions=functions, idle_entry=idle,
                idle_register=0xa297, idle_mask=2, counter_initial=counter, counter_decrement=5,
                full_timeout_executed=False, samples=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or not a.output.resolve().is_relative_to(a.simulator.resolve()):
        raise ValueError('Fresh private evidence required')
    src = sources(a.simulator)
    text = (a.simulator / 'iom4-command-source-research-01/tdk/src/imu/inv_imu_regmap_le.h').read_text()
    block = text.split('#define EDMP_APEX_EN0', 1)[1].split('} edmp_apex_en0_t;', 1)[0]
    names = re.findall(r'uint8_t\s+(\w+)\s*:\s*1', block)
    if names[:4] != ['tap_en', 'sif_en', 'reserved0', 'reserved1']:
        raise ValueError('Changed public EDMP layout drift reference')
    rows = [inspect(a.simulator, case) for case in ['stock24', 'stock23', 'cfw']]
    n = sum(len(x['samples']) for x in rows)
    a.output.mkdir(mode=0o700)
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, sources=src,
        original_arm_fragment_scenarios=n, public_reserved_bits_used_by_original=[2, 3],
        native_main_rerun=False, full_timeout_executed=False, physical_idle_timing_verified=False,
        hardware_accessed=False, boot_verified=False, display_verified=False), indent=2) + '\n')
    print('Verified original five clears/legacy branches/idle fragments', n)


if __name__ == '__main__':
    main()
