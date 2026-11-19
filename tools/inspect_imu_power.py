"""Verify original power/ODR RMW, FIFO flush and interrupt-status decoding."""
import argparse
import json
import struct
from pathlib import Path
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_iom4_command import sources
from inspect_keydb_record_load import run
from inspect_imu_edmp import frame
from inspect_nema_blocking_wait import WORK, STOP
from prepare_vendor_startup_candidate import sha


def body(raw, entry):
    result = []
    for i in decode(raw, entry, 500):
        result.append(i)
        if i.mnemonic in ('pop', 'pop.w') and 'pc' in i.op_str:
            return result
    raise ValueError('Unbounded original function')


def inspect(s, case):
    manifest = json.loads((s / 'imu-edmp-verification-01/manifest.json').read_text())
    ap = s / 'imu-edmp-saved-audit-01' / case / 'report.json'
    if not manifest['passed'] or sha(ap) != manifest['files'][str(ap.relative_to(s))]:
        raise ValueError('Changed original main source audit')
    audit = json.loads(ap.read_text())
    f = Path(audit['capture'])
    for n, pin in audit['capture_hashes'].items():
        if sha(f / n) != pin:
            raise ValueError('Changed source ' + n)
    old = json.loads((s / 'imu-configuration-verification-01/manifest.json').read_text())
    flow_path = s / 'imu-configuration-verification-01/next-flow-report.json'
    if sha(flow_path) != old['files'][str(flow_path.relative_to(s))]:
        raise ValueError('Changed original caller/field map')
    flow = next(x for x in json.loads(flow_path.read_text())['cases'] if x['case'] == case)
    raw, ram = (f / 'main.bin').read_bytes(), (f / 'exports/sram-full.bin').read_bytes()
    capture = json.loads((f / 'report.json').read_text())
    sp0 = capture['observed']['register_context']['r13']
    actual_return = struct.unpack_from('<I', ram, sp0 - 0x20000000 + 0xb4)[0] & ~1
    caller_return = struct.unpack_from('<I', ram, sp0 - 0x20000000 + 0xcc)[0] & ~1
    fields, rows = [], []
    for n, field in enumerate(flow['fields']):
        instructions = body(raw, field['entry'])
        calls = [i for i in instructions if i.mnemonic == 'bl']
        read, write = calls[-2:]
        shift, width, register = field['shift'], field['width'], field['register']
        if not any(i.mnemonic == 'bfi' and i.op_str == f'r0, r5, #{shift}, #{width}' for i in instructions):
            raise ValueError('Changed original field insertion')
        if n == 0 and (actual_return != read.address + 4 or caller_return != flow['mode_off_block'] + 8):
            raise ValueError('Current native power query not bound to original caller')
        if n < 2:
            caller = decode(raw, flow['mode_off_block'] + n * 10, 10)
            if caller[0].op_str != 'r1, #0' or next(i for i in caller if i.mnemonic == 'bl').operands[0].imm != field['entry']:
                raise ValueError('Changed natural mode-off argument')
        pairs = ((byte, value) for byte in range(256) for value in range(4)) if n < 2 else ((byte, value) for byte in [0, 0xf0, 0xff] for value in range(16))
        mask = ((1 << width) - 1) << shift
        for byte, value in pairs:
            u, sp = frame(raw, ram)
            u.mem_write(sp, bytes([byte]))
            u.reg_write(arm.UC_ARM_REG_R5, value)
            u.reg_write(arm.UC_ARM_REG_R6, 0)
            t = run(u, read.address + 4, [write.address])
            expected = (byte & ~mask) | ((value << shift) & mask)
            args = [u.reg_read(getattr(arm, 'UC_ARM_REG_R' + str(k))) for k in range(4)]
            if bytes(u.mem_read(sp, 1)) != bytes([expected]) or args != [WORK + 0x100, register, 1, sp]:
                raise ValueError('Changed original RMW byte/ABI')
            rows.append(dict(kind='field-rmw-fragment', role=field['role'], byte=byte, value=value, execution=t))
        for accumulated, status in [(0, 0), (4, 0), (0, 0xfffffffd), (4, 0xfffffffd)]:
            u, sp = frame(raw, ram)
            u.reg_write(arm.UC_ARM_REG_R6, accumulated)
            u.reg_write(arm.UC_ARM_REG_R0, status)
            t = run(u, write.address + 4, [])
            if t['stop'] != STOP or u.reg_read(arm.UC_ARM_REG_R0) != accumulated | status:
                raise ValueError('Changed field status accumulation')
            rows.append(dict(kind='field-error-return', role=field['role'], execution=t))
        fields.append(dict(field, calls=[i.operands[0].imm for i in calls]))
    caller = decode(raw, flow['mode_off_block'], 0xa0)
    calls = [i for i in caller if i.mnemonic == 'bl']
    flush = calls[2].operands[0].imm
    fb = body(raw, flush)
    fc = [i for i in fb if i.mnemonic == 'bl']
    counter = literal(raw, next(i for i in fb if i.mnemonic == 'ldr.w' and i.op_str.startswith('r6,')))
    if len(fc) != 5 or not any(i.mnemonic == 'orrs' and i.op_str == 'r0, r0, #0x80' for i in fb):
        raise ValueError('Changed flush request/loop')
    for byte in range(256):
        u, sp = frame(raw, ram)
        u.reg_write(arm.UC_ARM_REG_R4, 0)
        u.reg_write(arm.UC_ARM_REG_R5, WORK + 0x100)
        u.mem_write(sp, bytes([byte]))
        t = run(u, fc[0].address + 4, [fc[1].address])
        if bytes(u.mem_read(sp, 1)) != bytes([byte | 0x80]) or u.reg_read(arm.UC_ARM_REG_R1) != 0x20:
            raise ValueError('Changed flush bit preservation')
        rows.append(dict(kind='flush-request-fragment', byte=byte, execution=t))
    for byte in [0, 0x7f, 0x80, 0xff]:
        for status in [0, 0xfffffffd]:
            u, sp = frame(raw, ram)
            u.reg_write(arm.UC_ARM_REG_R4, 0)
            u.reg_write(arm.UC_ARM_REG_R5, WORK + 0x100)
            u.reg_write(arm.UC_ARM_REG_R0, status)
            u.mem_write(sp, bytes([byte]))
            t = run(u, fc[3].address + 4, [fc[4].address])
            if t['stop'] != (fc[4].address if byte & 0x80 else STOP):
                raise ValueError('Changed flush busy predicate')
            if byte & 0x80 and u.reg_read(arm.UC_ARM_REG_R1) != 100:
                raise ValueError('Changed flush poll delay')
            rows.append(dict(kind='flush-poll-fragment', byte=byte, status=status, execution=t))
    zero_gate = next(i for i in caller if i.mnemonic == 'beq')
    after = decode(raw, zero_gate.operands[0].imm, 24)
    status_calls = [i.operands[0].imm for i in after if i.mnemonic == 'bl']
    if len(status_calls) != 2:
        raise ValueError('Changed post-flush status readers')
    for entry, register, bits in [(status_calls[0], 0x19, list(range(15))), (status_calls[1], 0x3b, list(range(11)) + [12, 13, 14])]:
        ins = body(raw, entry)
        read = next(i for i in ins if i.mnemonic == 'bl')
        for value in [0, 1, 0x80, 0xa55a, 0xffff]:
            for status in [0, 0xfffffffd]:
                u, sp = frame(raw, ram, 16)
                out = WORK + 0x200
                u.reg_write(arm.UC_ARM_REG_R4, out)
                u.reg_write(arm.UC_ARM_REG_R5, 0)
                u.reg_write(arm.UC_ARM_REG_R0, status)
                u.mem_write(sp, struct.pack('<H', value))
                t = run(u, read.address + 4, [])
                if bytes(u.mem_read(out, len(bits))) != bytes((value >> k) & 1 for k in bits) or u.reg_read(arm.UC_ARM_REG_R0) != status:
                    raise ValueError('Changed interrupt status decoding/error return')
                rows.append(dict(kind='interrupt-status-fragment', register=register, value=value, status=status, execution=t))
    return dict(case=case, source_audit_sha256=sha(ap), fields=fields, current_native_mode=0,
                flush_entry=flush, flush_counter=counter, flush_register=0x20, flush_mask=0x80,
                flush_calls=[i.operands[0].imm for i in fc], status_entries=status_calls,
                status_registers=[0x19, 0x3b], samples=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or not a.output.resolve().is_relative_to(a.simulator.resolve()):
        raise ValueError('Fresh private output required')
    src = sources(a.simulator)
    rows = [inspect(a.simulator, case) for case in ['stock24', 'stock23', 'cfw']]
    count = sum(len(x['samples']) for x in rows)
    a.output.mkdir(mode=0o700)
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, sources=src,
        original_arm_fragment_scenarios=count, odr_native_execution_verified=False,
        full_flush_timeout_verified=False, hardware_accessed=False, boot_verified=False,
        display_verified=False), indent=2) + '\n')
    print('Verified original power/ODR fields, flush/status fragments', count)


if __name__ == '__main__':
    main()
