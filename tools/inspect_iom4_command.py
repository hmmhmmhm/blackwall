"""Bound original IOM4 polling I2C register select/read and ICM45608 identity gate."""
import argparse
import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_keydb_record_load import run
from inspect_mspi0_rx_profiles import inspect as verify_capture
from inspect_nema_blocking_wait import cpu, WORK
from prepare_vendor_startup_candidate import sha

SVD_SHA = 'a2390c3366450eaccc9d4531d26dc9d68488ec42de5795ee50ab45a266f28276'
TDK_COMMIT = '646f55a6ec119b59d9ebce47af660842b53e5506'


class Bank:
    def __init__(self, status=4, irq=1, data=0x81, fifo_bytes=4):
        self.status, self.irq, self.data, self.fifo_bytes = status, irq, data, fifo_bytes
        self.values = {0x200: 0, 0x218: 0, 0x2c0: 0x23040, 0x2c4: 0x69}
        self.events, self.unknown = [], []

    def read(self, u, offset, size, user):
        values = dict(self.values)
        values.update({0x248: self.status, 0x204: self.irq, 0x100: self.fifo_bytes << 16, 0x108: self.data})
        if size != 4 or offset not in values or offset == 0x108 and not self.fifo_bytes:
            self.unknown.append(dict(operation='read', offset=offset, size=size))
            u.emu_stop()
            return 0xffffffff
        value = values[offset]
        self.events.append(dict(operation='read', offset=offset, value=value))
        if offset == 0x108:
            self.fifo_bytes = 0
        return value

    def write(self, u, offset, size, value, user):
        valid = size == 4 and ((offset == 0x120 and value in (0x101, 0x102))
            or (offset == 0x208 and value == 0xffffffff) or (offset in (0x200, 0x218, 0x124, 0x128) and value == 0)
            or (offset == 0x2c4 and value == 0x69))
        if not valid:
            self.unknown.append(dict(operation='write', offset=offset, size=size, value=value))
            u.emu_stop()
            return
        self.events.append(dict(operation='write', offset=offset, value=value))
        if offset != 0x208:
            self.values[offset] = value

    def attach(self, u):
        u.mmio_map(0x40054000, 0x1000, self.read, None, self.write, None)


def clone(raw, ram, u):
    n = cpu(raw, bytes(u.mem_read(0x20000000, len(ram))), u.reg_read(arm.UC_ARM_REG_SP))
    for k in range(15):
        n.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(k)), u.reg_read(getattr(arm, 'UC_ARM_REG_R' + str(k))))
    for name in ['XPSR', 'PRIMASK']:
        n.reg_write(getattr(arm, 'UC_ARM_REG_' + name), u.reg_read(getattr(arm, 'UC_ARM_REG_' + name)))
    return n


def inspect(s, case):
    capture = verify_capture(s, case, 'active')
    f = s / 'mspi0-rx-main-01' / case
    v = json.loads((f / 'report.json').read_text())
    raw, ram = (f / 'main.bin').read_bytes(), (f / 'exports/sram-full.bin').read_bytes()
    r, pc = v['observed']['register_context'], v['observed']['pc']
    sp = r['r13']
    word = lambda address: struct.unpack_from('<I', ram, address - 0x20000000)[0]
    parent = word(sp + 0x4c) & ~1
    whoami_return = word(sp + 0xbc) & ~1
    getter_return = word(sp + 0xb4) & ~1
    getter = decode(raw, whoami_return - 4, 4)[0]
    if getter.mnemonic != 'bl' or getter_return != getter.operands[0].imm + 12:
        raise ValueError('Different actual WHOAMI getter stack chain')
    setup = decode(raw, getter_return - 8, 8)
    if [(i.mnemonic, i.op_str) for i in setup] != [('movs', 'r2, #1'), ('movs', 'r1, #0x72'), ('bl', setup[-1].op_str)]:
        raise ValueError('Different actual WHOAMI register/length')
    descriptor = struct.unpack_from('<12I', ram, sp + 0x50 - 0x20000000)
    if descriptor[0] != 0x69 or descriptor[4:6] != (1, 0) or ram[descriptor[6] - 0x20000000] != 0x72:
        raise ValueError('Different native I2C register-select descriptor')
    iom = next(x for x in v['observed']['ioms'] if x['module'] == 4)
    if iom['peer_attached'] or iom['commands'] != 0 or iom['cq']['pairs'] != 0 or iom['cq']['configuration'] != 2:
        raise ValueError('Not the unexecuted polling command frontier')
    core = (f / 'strict.cs').read_text()
    if core.count('public uint BytesCount => Count * 4;') != 1:
        raise ValueError('Changed captured runtime word-backed FIFO accounting')
    wait_call = decode(raw, pc - 0xc4, 4)[0]
    delay_call = decode(raw, wait_call.operands[0].imm + 0x1a, 4)[0]
    if wait_call.mnemonic != 'bl' or delay_call.mnemonic != 'bl':
        raise ValueError('Different original status poll/delay')
    delay = delay_call.operands[0].imm
    rows = []
    normal = None
    for status, irq in [(4, 0), (4, 1), (4, 0x10), (2, 1)]:
        u = cpu(raw, ram, sp)
        for n in range(15):
            u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), r['r' + str(n)])
        bank = Bank(status=status, irq=irq)
        bank.attach(u)
        stop = delay if status == 2 else pc - 0xa0 if irq == 0x10 else parent
        t = run(u, pc, [parent, delay, pc - 0xa0])
        if bank.unknown or t['stop'] != stop:
            raise ValueError('Original write continuation escaped fixture')
        if status == 4 and irq != 0x10 and u.reg_read(arm.UC_ARM_REG_R0) != 0:
            raise ValueError('Completed polling write did not return success')
        if irq == 0x10 and u.reg_read(arm.UC_ARM_REG_R4) == 0:
            raise ValueError('NAK fixture did not report an error before cleanup')
        rows.append(dict(kind='select-write', status_fixture=status, irq_fixture=irq, execution=t, events=bank.events))
        if status == 4 and irq == 1:
            normal = u
    n = clone(raw, ram, normal)
    bank = Bank()
    bank.attach(n)
    read_call = decode(raw, parent + 0x42, 4)[0]
    entry = read_call.operands[0].imm
    t = run(n, parent, [entry])
    pointer = n.reg_read(arm.UC_ARM_REG_R1)
    read_desc = struct.unpack('<12I', n.mem_read(pointer, 48))
    if bank.unknown or t['stop'] != entry or read_desc[0] != 0x69 or read_desc[4:6] != (1, 1) or read_desc[7] != sp + 0xc0:
        raise ValueError('Original wrapper did not prepare the one-byte I2C read')
    rows.append(dict(kind='read-preparation', execution=t, descriptor=list(read_desc)))
    for data, size in [(0x81, 4), (0, 4), (0xff, 4), (0x81, 8), (0x81, 1), (0x81, 0)]:
        u = clone(raw, ram, n)
        bank = Bank(data=data, fifo_bytes=size)
        bank.attach(u)
        t = run(u, entry, [read_call.address + 4, delay])
        if bank.unknown or t['stop'] != (read_call.address + 4 if size >= 4 else delay):
            raise ValueError('Original read escaped data-ready/delay contract')
        if size >= 4:
            if u.reg_read(arm.UC_ARM_REG_R0) != 0 or bytes(u.mem_read(sp + 0xc0, 1)) != bytes([data]):
                raise ValueError('Original read delivered different WHOAMI byte')
            if len([x for x in bank.events if x['operation'] == 'read' and x['offset'] == 0x108]) != 1:
                raise ValueError('Original one-byte read did not pop one FIFO word')
        rows.append(dict(kind='read', data_fixture=data, fifo_byte_count_fixture=size,
                         delay_before_execution=size < 4, execution=t, events=bank.events))
    gate_samples = []
    reset_call = decode(raw, whoami_return + 0x12, 4)[0]
    reset_entry = reset_call.operands[0].imm
    return_pc = whoami_return + 0x1a
    if reset_call.mnemonic != 'bl' or (decode(raw, whoami_return + 6, 2)[0].mnemonic,
        decode(raw, whoami_return + 6, 2)[0].op_str) != ('cmp', 'r0, #0x81'):
        raise ValueError('Different actual WHOAMI identity constant')
    for byte, read_status in [(value, 0) for value in range(256)] + [(0x81, 4)]:
        u = cpu(raw, ram, sp + 0xc0)
        u.mem_write(sp + 0xc0, bytes([byte]))
        u.reg_write(arm.UC_ARM_REG_R0, read_status)
        u.reg_write(arm.UC_ARM_REG_R4, 0)
        u.reg_write(arm.UC_ARM_REG_R5, word(sp + 0xc8))
        t = run(u, whoami_return, [reset_entry, return_pc])
        if t['stop'] != (reset_entry if byte == 0x81 else return_pc):
            raise ValueError('Original identity gate selected a different branch')
        if byte != 0x81 and u.reg_read(arm.UC_ARM_REG_R0) != 0xffffffff:
            raise ValueError('Mismatching WHOAMI did not return failure')
        gate_samples.append(dict(byte=byte, read_status_fixture=read_status, reset_entry_reached=byte == 0x81, execution=t))
    return dict(case=case, capture=capture, frontier_register='IOM4.CMD', command=0x101,
                bus_address=0x69, selected_register=0x72, transfer_bytes=1,
                command_queue_executed=False, samples=rows, identity_samples=gate_samples,
                expected_whoami=0x81, reset_entry=reset_entry, hardware_part_verified=False,
                captured_runtime_fifo_bytes_are_word_count_times_four=True)


def sources(s):
    svd = s / 'apollo-dfp-research-01/apollo510.svd'
    if sha(svd) != SVD_SHA:
        raise ValueError('Changed SVD')
    root = ET.parse(svd).getroot()
    iom = next(x for x in root.findall('.//peripheral') if x.findtext('name') == 'IOM0')
    offsets = {x.findtext('name'): int(x.findtext('addressOffset'), 0) for x in iom.findall('.//register')}
    if (offsets['CMD'], offsets['CQCFG']) != (0x120, 0x228):
        raise ValueError('IOM command and queue register definitions changed')
    folder = s / 'iom4-command-source-research-01'
    commit = json.loads((folder / 'tdk-commit.json').read_text())
    tree = json.loads((folder / 'tdk-canonical-tree.json').read_text())
    if commit['sha'] != TDK_COMMIT or tree['sha'] != commit['commit']['tree']['sha'] or tree.get('truncated'):
        raise ValueError('Changed TDK commit')
    blobs = {x['path']: x['sha'] for x in tree['tree'] if x['type'] == 'blob'}
    files = {}
    for p in (folder / 'tdk').rglob('*'):
        if p.is_file():
            name = str(p.relative_to(folder / 'tdk'))
            data = p.read_bytes()
            if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != blobs[name]:
                raise ValueError('Changed TDK blob ' + name)
            files[name] = sha(p)
    header = (folder / 'tdk/src/imu/inv_imu.h').read_text()
    regmap = (folder / 'tdk/src/imu/inv_imu_regmap_le.h').read_text()
    if '#define INV_IMU_WHOAMI               0x81' not in header or not re.search(r'^#define WHO_AM_I\s+0x72\s*$', regmap, re.M):
        raise ValueError('Changed TDK identity definition')
    return dict(svd_sha256=SVD_SHA, offsets={k: offsets[k] for k in ['CMD', 'CQCFG']},
                tdk_commit=TDK_COMMIT, tdk_files=files, tdk_license='BSD-3-Clause')



def inspect_nak_cleanup(s, case):
    """Run original polling error cleanup; only its timing leaf is an ABI stub."""
    from unicorn import UC_HOOK_CODE
    capture = verify_capture(s, case, 'active')
    folder = s / 'mspi0-rx-main-01' / case
    report = json.loads((folder / 'report.json').read_text())
    raw, ram = (folder / 'main.bin').read_bytes(), (folder / 'exports/sram-full.bin').read_bytes()
    regs = report['observed']['register_context']
    pc, sp = report['observed']['pc'], regs['r13']
    parent = struct.unpack_from('<I', ram, sp + 0x4c - 0x20000000)[0] & ~1
    wait = decode(raw, pc - 0xc4, 4)[0].operands[0].imm
    delay = decode(raw, wait + 0x1a, 4)[0].operands[0].imm
    cleanup = decode(raw, pc - 0x96, 4)[0]
    if cleanup.mnemonic != 'bl':
        raise ValueError('Changed original error-cleanup call')
    rows = []
    for debug in (0, 4):
        for fifo in (2, 3):
            for enables in (0, 0x10, 0x20):
                class ErrorBank(Bank):
                    def __init__(self):
                        super().__init__(status=4, irq=0x10, fifo_bytes=0)
                        self.values.update({0x110: fifo, 0x11c: 0x30, 0x388: debug, 0x200: enables})

                    def read(self, u, off, size, user):
                        return super().read(u, off, size, user)

                    def write(self, u, off, size, value, user):
                        if size != 4:
                            raise ValueError('Unexpected MMIO width')
                        if off in (0x110, 0x11c, 0x388, 0x200):
                            self.events.append(dict(operation='write', offset=off, value=value))
                            self.values[off] = value
                        else:
                            super().write(u, off, size, value, user)
                        if off == 0x208:
                            self.irq &= ~value

                u = cpu(raw, ram, sp)
                for n in range(15):
                    u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), regs['r' + str(n)])
                u.mem_write(sp + 0x14, struct.pack('<I', enables))
                bank = ErrorBank()
                bank.attach(u)
                delays = []
                def sleep(c, address, size, user):
                    if address == delay:
                        delays.append(c.reg_read(arm.UC_ARM_REG_R0))
                        c.reg_write(arm.UC_ARM_REG_PC, c.reg_read(arm.UC_ARM_REG_LR))
                u.hook_add(UC_HOOK_CODE, sleep)
                execution = run(u, pc, [parent])
                writes = [(x['offset'], x['value']) for x in bank.events if x['operation'] == 'write']
                expected = [(0x120, 0x101), (0x200, 0), (0x11c, 0x20),
                            (0x110, fifo & ~2), (0x388, debug | 2), (0x388, debug),
                            (0x110, fifo), (0x11c, 0x30), (0x208, 0xffffffff),
                            (0x200, enables), (0x208, 0xffffffff), (0x200, enables)]
                if bank.unknown or execution['stop'] != parent or writes != expected:
                    raise ValueError('Different original NAK cleanup sequence: ' + str(writes))
                handle = regs['r10']
                clock = struct.unpack_from('<I', ram, handle + 0x864 - 0x20000000)[0]
                if delays != [6 * clock] or not delays[0]:
                    raise ValueError('Different original recovery delay argument')
                returned = u.reg_read(arm.UC_ARM_REG_R0)
                if returned != 0x08000002 or bank.irq != 0 or any(bank.values[o] != v for o, v in [(0x110, fifo), (0x11c, 0x30), (0x388, debug), (0x200, enables)]):
                    raise ValueError('Different original NAK return/restoration: ' + hex(returned))
                # Follow the real caller branch; stop before its release helper.
                release = decode(raw, parent + 10, 4)[0]
                if release.mnemonic != 'bl':
                    raise ValueError('Changed original transport error branch')
                caller = clone(raw, ram, u)
                branch = run(caller, parent, [release.operands[0].imm, parent + 0x42])
                if branch['stop'] != release.operands[0].imm:
                    raise ValueError('Failed select incorrectly started data read')
                rows.append(dict(debug_fixture=debug, fifo_fixture=fifo, interrupt_enable_fixture=enables,
                                 returned=returned, recovery_delay_argument=delays[0], execution=execution,
                                 caller_error_branch=branch, events=bank.events, read_command_started=False))
    return dict(case=case, capture=capture, main_sha256=sha(folder / 'main.bin'),
                sram_sha256=sha(folder / 'exports/sram-full.bin'), cleanup_entry=cleanup.operands[0].imm,
                source_return=parent, runs=rows)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--nak-cleanup', action='store_true')
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Fresh private evidence required')
    source = sources(a.simulator)
    if a.nak_cleanup:
        svd = ET.parse(a.simulator / 'apollo-dfp-research-01/apollo510.svd').getroot()
        iom = next(x for x in svd.findall('.//peripheral') if x.findtext('name') == 'IOM0')
        dbg = next(x for x in iom.findall('.//register') if x.findtext('name') == 'IOMDBG')
        field = next(x for x in dbg.findall('.//field') if x.findtext('name') == 'IOCLKON')
        assert int(dbg.findtext('addressOffset'), 0) == 0x388 and field.findtext('bitRange') == '[1:1]'
        rows = [inspect_nak_cleanup(a.simulator, case) for case in ('stock24', 'stock23', 'cfw')]
        a.output.mkdir(mode=0o700)
        (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
        (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, sources=source, original_arm_scenarios=sum(len(x['runs']) for x in rows), engine='Unicorn M7 original polling HAL and caller error branch', mmio_state_fixture=True, delay_abi_stubbed=True, native_main=False, upper_initializer_return_verified=False, gaf_computation_verified=False, hardware_accessed=False), indent=2) + '\n')
        print('Verified original NAK cleanup/return/caller branch scenarios=36; timing ABI stubbed; no native main')
        return
    rows = [inspect(a.simulator, case) for case in ('stock24', 'stock23', 'cfw')]
    count = sum(len(r['samples']) + len(r['identity_samples']) for r in rows)
    a.output.mkdir(mode=0o700)
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, sources=source,
        original_arm_scenarios=count, engine='Unicorn M7 saved frame and explicit IOM idle/error/FIFO fixtures',
        native_main_rerun=False, physical_fifo_behavior_verified=False, sensor_reset_executed=False,
        hardware_accessed=False, boot_verified=False, display_verified=False), indent=2) + '\n')
    print('Verified IOM4 CMD polling select72/read1@69 and WHOAMI81, ARM scenarios=' + str(count) + '; no CQ execution or sensor reset')


if __name__ == '__main__':
    main()
