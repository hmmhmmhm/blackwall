"""Bind original soft-reset call order, restore arguments and reset-done branch.

Independent ARM fragments only; does not execute a reset or bypass delay in main.
"""
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
    manifest = json.loads((s / 'iom4-imu-verification-01/manifest.json').read_text())
    audit_path = s / 'iom4-imu-saved-audit-01' / case / 'report.json'
    if not manifest['passed'] or sha(audit_path) != manifest['files'][str(audit_path.relative_to(s))]:
        raise ValueError('Changed verified native capture audit')
    audit = json.loads(audit_path.read_text())
    f = Path(audit['capture'])
    for name, value in audit['capture_hashes'].items():
        if sha(f / name) != value:
            raise ValueError('Changed native input ' + name)
    old_manifest = json.loads((s / 'iom4-command-verification-01/manifest.json').read_text())
    old_report = s / 'iom4-command-source-04/report.json'
    if sha(old_report) != old_manifest['files'][str(old_report.relative_to(s))]:
        raise ValueError('Changed original reset caller contract')
    original = next(x for x in json.loads(old_report.read_text())['cases'] if x['case'] == case)
    raw, ram = (f / 'main.bin').read_bytes(), (f / 'exports/sram-full.bin').read_bytes()
    adv_call = next(i for i in decode(raw, original['reset_entry'], 24) if i.mnemonic == 'bl')
    entry = adv_call.operands[0].imm
    ins = decode(raw, entry, 0x9c)
    calls = [i for i in ins if i.mnemonic == 'bl']
    if len(calls) != 8 or ins[-1].mnemonic != 'pop' or ins[-1].op_str != '{r1, r2, r4, r5, r6, pc}':
        raise ValueError('Different bounded soft-reset body')
    clear, read, read2, write, sleep, restore_drive, restore_interface, status = calls
    if read.operands[0].imm != read2.operands[0].imm or status.operands[0].imm != read.operands[0].imm or len({x.operands[0].imm for x in [write, restore_drive, restore_interface]}) != 1:
        raise ValueError('Changed register read/write helpers')
    wanted = [(0x18, 'movs', 'r1, #0x2d'), (0x28, 'movs', 'r1, #0x32'),
              (0x36, 'orrs', 'r0, r0, #2'), (0x42, 'movs', 'r1, #0x7f'),
              (0x4c, 'mov.w', 'r1, #0x3e8'), (0x5c, 'movs', 'r1, #0x32'),
              (0x6c, 'movs', 'r1, #0x2d'), (0x7c, 'movs', 'r1, #0x19')]
    by_offset = {i.address - entry: i for i in ins}
    for offset, mnemonic, operands in wanted:
        i = by_offset[offset]
        if (i.mnemonic, i.op_str) != (mnemonic, operands):
            raise ValueError('Changed original reset field at ' + hex(offset))
    sp = WORK + 0xf000
    rows = []
    for value in range(256):
        for accumulated, last in [(0, 0), (4, 0), (0, 0xfffffffd)]:
            u = cpu(raw, ram, sp)
            u.mem_write(sp, struct.pack('<6I', 0, 0, 0x11111111, 0x22222222, 0x33333333, STOP | 1))
            u.mem_write(sp + 1, bytes([value]))
            u.reg_write(arm.UC_ARM_REG_R5, accumulated)
            u.reg_write(arm.UC_ARM_REG_R0, last)
            t = run(u, status.address + 4, [])
            result = u.reg_read(arm.UC_ARM_REG_R0)
            if result != ((accumulated | last) if value & 0x80 else 0xffffffff) or u.reg_read(arm.UC_ARM_REG_SP) != sp + 24:
                raise ValueError('Changed original reset-done/error return')
            rows.append(dict(kind='reset-done-return-fragment', status_byte=value, accumulated_status=accumulated,
                             last_read_status=last, returned=result, execution=t))
        for start, end, register, offset in [(sleep.address + 4, restore_drive, 0x32, 2), (restore_drive.address + 4, restore_interface, 0x2d, 3)]:
            u = cpu(raw, ram, sp)
            u.mem_write(sp, bytes([0, 0x80, value, value ^ 0xff]))
            u.reg_write(arm.UC_ARM_REG_R4, WORK + 0x100)
            u.reg_write(arm.UC_ARM_REG_R5, 0)
            u.reg_write(arm.UC_ARM_REG_R0, 0)
            t = run(u, start, [end.address])
            args = [u.reg_read(getattr(arm, 'UC_ARM_REG_R' + str(k))) for k in range(4)]
            expected = [WORK + 0x100, register, 1, sp + offset]
            if args != expected or bytes(u.mem_read(sp + offset, 1)) != bytes([value if offset == 2 else value ^ 0xff]):
                raise ValueError('Changed restore argument fragment')
            rows.append(dict(kind='restore-argument-fragment', register=register, saved_value=value if offset == 2 else value ^ 0xff,
                             arguments=args, callee_not_executed=True, execution=t))
    return dict(case=case, source_audit_sha256=sha(audit_path), main_sha256=sha(f / 'main.bin'), soft_reset_entry=entry,
                instruction_count=len(ins), original_call_order=[dict(offset=i.address - entry, target=i.operands[0].imm) for i in calls],
                register_sequence=[0x2d, 0x32, 0x7f, 0x32, 0x2d, 0x19], reset_write_mask=2, delay_argument_us=1000,
                reset_done_mask=0x80, samples=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or not a.output.resolve().is_relative_to(a.simulator.resolve()):
        raise ValueError('Fresh private evidence required')
    src = sources(a.simulator)
    rows = [inspect(a.simulator, case) for case in ['stock24', 'stock23', 'cfw']]
    a.output.mkdir(mode=0o700)
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    result = dict(passed=True, cases=rows, sources=src, original_arm_fragment_scenarios=sum(len(x['samples']) for x in rows),
                  native_main_rerun=False, hardware_accessed=False, continuous_reset_execution_verified=False,
                  reset_delay_executed=False, sensor_reset_executed=False, physical_register_defaults_verified=False,
                  boot_verified=False, display_verified=False)
    (a.output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Verified reset call order and original ARM fragments', result['original_arm_fragment_scenarios'])


if __name__ == '__main__':
    main()
