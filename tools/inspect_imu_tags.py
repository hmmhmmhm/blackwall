"""Bind advanced reset flags, FIFO baselines and FSYNC/error tag fragments."""
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
    manifest = json.loads((s / 'imu-ireg-verification-01/manifest.json').read_text())
    audit_path = s / 'imu-ireg-saved-audit-01' / case / 'report.json'
    if sha(audit_path) != manifest['files'][str(audit_path.relative_to(s))]:
        raise ValueError('Changed verified advanced-reset capture')
    a = json.loads(audit_path.read_text())
    if not manifest['passed'] or not a['passed']:
        raise ValueError('Unverified capture')
    f = Path(a['capture'])
    for n, value in a['capture_hashes'].items():
        if sha(f / n) != value:
            raise ValueError('Changed original input ' + n)
    prior = s / 'iom4-command-source-04/report.json'
    pin = json.loads((s / 'iom4-command-verification-01/manifest.json').read_text())
    if sha(prior) != pin['files'][str(prior.relative_to(s))]:
        raise ValueError('Changed reset caller contract')
    outer = next(x['reset_entry'] for x in json.loads(prior.read_text())['cases'] if x['case'] == case)
    raw, ram = (f / 'main.bin').read_bytes(), (f / 'exports/sram-full.bin').read_bytes()
    adv = decode(raw, outer, 0x3a)
    calls = [i for i in adv if i.mnemonic == 'bl']
    if len(calls) != 4:
        raise ValueError('Changed advanced reset call order')
    for operands in ['r0, [r6, #4]', 'r0, [r6, #5]', 'r0, [r4, #0x10]']:
        if not any(i.mnemonic == 'strb' and i.op_str == operands for i in adv):
            raise ValueError('Changed default FIFO flags')
    compression, tag = [x.operands[0].imm for x in calls[2:]]
    body = decode(raw, tag, 0x22)
    call = next(i for i in body if i.mnemonic == 'bl')
    wanted = {4: ('adds.w', 'r5, r0, #0x18'), 0xc: ('movs', 'r1, #0x24'),
              0x18: ('ands', 'r0, r0, #7'), 0x1c: ('strb', 'r0, [r5, #0x17]')}
    by = {i.address - tag: i for i in body}
    for offset, pair in wanted.items():
        if (by[offset].mnemonic, by[offset].op_str) != pair:
            raise ValueError('Changed original FSYNC operation')
    rows = []
    sp, context = WORK + 0xf000, WORK + 0x100
    for value in [0xa5, 0x5a]:
        u = cpu(raw, ram, sp)
        before = bytes([value]) * 0x80
        u.mem_write(context, before)
        u.reg_write(arm.UC_ARM_REG_R0, context)
        t = run(u, compression, [])
        expected = bytearray(before)
        expected[0x1e:0x2c] = struct.pack('<7H', *([0x8000] * 7))
        expected[0x2c:0x2f] = bytes(3)
        if bytes(u.mem_read(context, len(before))) != expected or u.reg_read(arm.UC_ARM_REG_R0) != 0 or u.reg_read(arm.UC_ARM_REG_SP) != sp:
            raise ValueError('Original FIFO baselines/neighbors differ')
        rows.append(dict(kind='compression-baselines', sentinel=value, execution=t))
    for byte in range(256):
        for status in [0, 4, 0xfffffffd]:
            u = cpu(raw, ram, sp)
            before = b'\xa5' * 0x80
            u.mem_write(context, before)
            u.mem_write(sp, struct.pack('<4I', byte, 0x11111111, 0x22222222, STOP | 1))
            u.reg_write(arm.UC_ARM_REG_R5, context + 0x18)
            u.reg_write(arm.UC_ARM_REG_R4, 0)
            u.reg_write(arm.UC_ARM_REG_R0, status)
            t = run(u, call.address + 4, [])
            expected = bytearray(before)
            expected[0x2f] = byte & 7
            if bytes(u.mem_read(context, len(before))) != expected or u.reg_read(arm.UC_ARM_REG_R0) != status or u.reg_read(arm.UC_ARM_REG_SP) != sp + 16:
                raise ValueError('Original FSYNC tag/error behavior differs')
            rows.append(dict(kind='fsync-tag-return-fragment', byte=byte, read_status=status, stored_tag=byte & 7, execution=t))
    return dict(case=case, source_audit_sha256=sha(audit_path), main_sha256=sha(f / 'main.bin'),
                advanced_reset=outer, calls=[x.operands[0].imm for x in calls], compression=compression,
                fsync=tag, fsync_register=0x24, tag_offset=0x2f, fifo_baseline_offset=0x1e,
                fifo_baseline_count=7, fifo_baseline_value=0x8000, tag_written_even_with_read_error=True, samples=rows)


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
    n = sum(len(x['samples']) for x in rows)
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, sources=src,
        original_arm_fragment_scenarios=n, native_main_rerun=False, complete_advanced_init_verified=False,
        physical_defaults_verified=False, hardware_accessed=False, boot_verified=False, display_verified=False), indent=2) + '\n')
    print('Verified original FIFO/FSYNC fragments', n, '; read error still updates tag')


if __name__ == '__main__':
    main()
