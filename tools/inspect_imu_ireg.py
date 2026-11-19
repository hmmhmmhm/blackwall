"""Bind indirect read transport and original endian cache branch to pinned images."""
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
    m = json.loads((s / 'imu-reset-model-verification-01/manifest.json').read_text())
    p = s / 'imu-reset-model-saved-audit-01' / case / 'report.json'
    if not m['passed'] or sha(p) != m['files'][str(p.relative_to(s))]:
        raise ValueError('Changed native source audit')
    audit = json.loads(p.read_text())
    f = Path(audit['capture'])
    for name, value in audit['capture_hashes'].items():
        if sha(f / name) != value:
            raise ValueError('Changed native source ' + name)
    prior = s / 'iom4-command-source-04/report.json'
    pm = json.loads((s / 'iom4-command-verification-01/manifest.json').read_text())
    if sha(prior) != pm['files'][str(prior.relative_to(s))]:
        raise ValueError('Changed original advanced-reset caller contract')
    outer = next(x['reset_entry'] for x in json.loads(prior.read_text())['cases'] if x['case'] == case)
    raw, ram = (f / 'main.bin').read_bytes(), (f / 'exports/sram-full.bin').read_bytes()
    entry = [i for i in decode(raw, outer, 0x30) if i.mnemonic == 'bl'][1].operands[0].imm
    getter = decode(raw, entry, 0x28)
    call = next(i for i in getter if i.mnemonic == 'bl')
    readreg = call.operands[0].imm
    transport = next(i for i in decode(raw, readreg, 0x18) if i.mnemonic == 'bl').operands[0].imm
    ins = decode(raw, transport, 0x72)
    by = {i.address - transport: i for i in ins}
    expected = [(0x22, 'lsrs', 'r0, r0, #8'), (0x24, 'strb.w', 'r0, [sp]'),
                (0x28, 'strb.w', 'r8, [sp, #1]'), (0x2c, 'movs', 'r0, #4'),
                (0x30, 'blx', 'r1'), (0x34, 'movs', 'r2, #2'), (0x36, 'movs', 'r1, #0x7c'),
                (0x4e, 'movs', 'r0, #4'), (0x52, 'blx', 'r1'),
                (0x58, 'movs', 'r2, #1'), (0x5a, 'movs', 'r1, #0x7e')]
    for off, op, args in expected:
        if (by[off].mnemonic, by[off].op_str) != (op, args):
            raise ValueError('Changed original indirect protocol at ' + hex(off))
    if [(i.mnemonic, i.op_str) for i in getter[:1]] != [('push', '{r3, r4, r5, lr}')]:
        raise ValueError('Changed endian frame')
    samples = []
    sp, context = WORK + 0xf000, WORK + 0x100
    for byte in range(256):
        for status in [0, 4, 0xfffffffd]:
            u = cpu(raw, ram, sp)
            u.mem_write(sp, struct.pack('<4I', byte, 0x11111111, 0x22222222, STOP | 1))
            u.mem_write(context + 0x11, b'\x5a')
            u.reg_write(arm.UC_ARM_REG_R4, 0)
            u.reg_write(arm.UC_ARM_REG_R5, context)
            u.reg_write(arm.UC_ARM_REG_R0, status)
            t = run(u, call.address + 4, [])
            cached = bytes(u.mem_read(context + 0x11, 1))[0]
            if cached != ((byte >> 1) & 1 if status == 0 else 0x5a) or u.reg_read(arm.UC_ARM_REG_R0) != status or u.reg_read(arm.UC_ARM_REG_SP) != sp + 16:
                raise ValueError('Changed original endian/error cache branch')
            samples.append(dict(byte=byte, status=status, cache=cached, execution=t))
    return dict(case=case, source_audit_sha256=sha(p), raw_sha256=sha(f / 'main.bin'), getter=entry,
                readreg=readreg, indirect_transport=transport, address_register=0x7c, data_register=0x7e,
                address=0xa267, address_byte_order='high then low', sleep_arguments_us=[4, 4],
                ready_register_poll_executed=False, cache_offset=0x11, cache_bit=1, samples=samples)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or not a.output.resolve().is_relative_to(a.simulator.resolve()):
        raise ValueError('Fresh private output required')
    src = sources(a.simulator)
    rows = [inspect(a.simulator, case) for case in ['stock24', 'stock23', 'cfw']]
    a.output.mkdir(mode=0o700)
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, sources=src,
        original_arm_fragment_scenarios=sum(len(x['samples']) for x in rows), native_main_rerun=False,
        physical_access_time_verified=False, continuous_transport_executed=False, hardware_accessed=False,
        boot_verified=False, display_verified=False), indent=2) + '\n')
    print('Verified original indirect protocol and endian cache fragments', sum(len(x['samples']) for x in rows))


if __name__ == '__main__':
    main()
