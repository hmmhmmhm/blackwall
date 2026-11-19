"""Bound original MSPI0 queue setup, separate IRQ calls, and retained-sleep reads."""
import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_application_vendor_address import call
from inspect_keydb_record_load import run
from inspect_mspi0_config_profiles import inspect as verify_capture
from inspect_mspi0_initialization import state
from inspect_mspi1_config_contract import collect
from inspect_nema_blocking_wait import cpu, WORK
from prepare_vendor_startup_candidate import sha


class Bank:
    def __init__(self, metadata):
        self.values = {r['offset']: r['reset'] for r in metadata if r['selected']}
        self.values.update({o: 0 for o in (0x200, 0x204, 0x2a0, 0x2a8, 0x2b8, 0x2c0, 0x2c4)})
        self.events = []
        self.unknown = []
        self.software_flags = 0

    def fail(self, u, operation, offset, size, value=None):
        self.unknown.append(dict(operation=operation, offset=offset, size=size, value=value))
        u.emu_stop()
        return 0xffffffff

    def read(self, u, offset, size, user):
        if size != 4 or offset not in self.values:
            return self.fail(u, 'read', offset, size)
        value = self.values[offset]
        self.events.append(dict(operation='read', offset=offset, value=value))
        return value

    def write(self, u, offset, size, value, user):
        if size != 4 or (offset not in self.values and offset not in (0x208, 0x2b4)):
            self.fail(u, 'write', offset, size, value)
            return
        if offset == 0x2a0 and value & 1:
            self.fail(u, 'queue-enable', offset, size, value)
            return
        self.events.append(dict(operation='write', offset=offset, value=value))
        if offset == 0x208:
            self.values[0x204] &= ~value
        elif offset == 0x2b4:
            self.software_flags = ((self.software_flags | (value & 255)) ^ ((value >> 8) & 255)) & ~((value >> 16) & 255)
        else:
            self.values[offset] = value

    def attach(self, u):
        u.mmio_map(0x40060000, 4096, self.read, None, self.write, None)


def branch(raw, address):
    i = decode(raw, address, 4)[0]
    if i.mnemonic != 'bl':
        raise ValueError('Expected original BL')
    return i.operands[0].imm


def inspect(s, case, metadata):
    capture = verify_capture(s, case, 'mspi0-config-main-01', case, 'active')
    f = s / 'mspi0-config-main-01' / case
    raw = (f / 'main.bin').read_bytes()
    ram = (f / 'exports/sram-full.bin').read_bytes()
    observed = json.loads((f / 'report.json').read_text())['observed']
    regs = observed['register_context']
    queue = regs['r4']
    words = struct.unpack_from('<11I', ram, queue - 0x20000000)
    table = struct.unpack_from('<10I', raw, words[9] - 0x438000)
    if table != (0x400602a0, 0x400602a8, 0x400602c0, 0x400602c4, 0x400602b8, 0x4000, 0x400602ac, 1, 4, 8):
        raise ValueError('Different original MSPI0 queue table')
    if words[0] != 0x1cdcdcd or words[6:9] != (0x400, 0, 0) or words[2] - words[1] != 0x400:
        raise ValueError('Different native initialized queue state')
    instance = regs['r2'] - 0x828
    # This parent return is on the real saved stack, below the CMDQ and wrapper frames.
    stack = struct.unpack_from('<12I', ram, regs['r13'] - 0x20000000)
    parent_return = stack[7] & ~1
    parent = parent_return - 0xf6
    enable = branch(raw, parent + 0xf2)
    wrapper = branch(raw, enable + 0x36)
    entry = branch(raw, regs['r14'] - 5)
    if wrapper + 0x26 != regs['r14'] - 5 or observed['pc'] != entry + 0xaa:
        raise ValueError('Different native queue caller chain')
    gpio = branch(raw, parent + 0x13e)
    clear = branch(raw, parent + 0x148)
    enable_irq = branch(raw, parent + 0x15c)
    priority = branch(raw, parent + 0x1a8)
    nvic = branch(raw, parent + 0x1ae)
    power = branch(raw, parent + 0x1b8)
    if branch(raw, parent - 4) != power:
        raise ValueError('Different retained power caller')
    if [(i.mnemonic, i.op_str) for i in decode(raw, parent + 0x13a, 4)] != [('movs', 'r1, #0'), ('movs', 'r0, #0')]:
        raise ValueError('Different intervening GPIO setup arguments')

    def make():
        u = cpu(raw, ram, regs['r13'])
        for n in range(15):
            u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), regs['r' + str(n)])
        return u

    bank = Bank(metadata)
    u = make()
    bank.attach(u)
    trace = run(u, observed['pc'], [parent_return])
    if bank.unknown or u.reg_read(arm.UC_ARM_REG_R0) != 0:
        raise ValueError('Original controller enable did not return success')
    expected = [('write', 0x2c0, 0), ('write', 0x2c4, 0), ('read', 0x2b8, 0),
                ('write', 0x2b8, 0x4000), ('write', 0x2a8, words[1]),
                ('write', 0x2a0, 2), ('write', 0x2b4, 0x400080)]
    if [(e['operation'], e['offset'], e['value']) for e in bank.events] != expected or bank.software_flags != 0x80:
        raise ValueError('Different original disabled queue setup')
    after = bytes(u.mem_read(0x20000000, len(ram)))
    if struct.unpack_from('<I', after, instance - 0x20000000)[0] != 0x3bebebe:
        raise ValueError('MSPI handle enable bit missing')
    plain = make()
    plain.mem_map(0x40060000, 4096)
    plain_trace = run(plain, observed['pc'], [parent_return])
    if trace != plain_trace or state(u, len(ram)) != state(plain, len(ram)):
        raise ValueError('MMIO callback changed original CPU/RAM/WORK path')

    samples = []
    for status in (0, 0x1a80):
        b = Bank(metadata)
        b.values[0x200] = 0x400
        b.values[0x204] = status
        c = cpu(raw, after, WORK + 0xf000)
        b.attach(c)
        t = call(c, clear, (instance, 0x1a80))
        if b.unknown or c.reg_read(arm.UC_ARM_REG_R0) != 0 or b.values[0x204] != 0:
            raise ValueError('Original interrupt clear differs')
        # Use a fresh CPU for each hook-bearing run; carry only the declared bank state.
        c = cpu(raw, after, WORK + 0xf000)
        b.attach(c)
        e = call(c, enable_irq, (instance, 0x1a80))
        if b.unknown or b.values[0x200] != 0x1e80 or c.reg_read(arm.UC_ARM_REG_R0) != 0:
            raise ValueError('Original interrupt enable lost existing bits')
        samples.append(dict(status=status, clear=t, enable=e, events=b.events))
    c = cpu(raw, after, WORK + 0xf000)
    pt = call(c, priority, (20, 4))
    if bytes(c.mem_read(0xe000e414, 1)) != b'\x40':
        raise ValueError('Different IRQ20 priority')
    c = cpu(raw, after, WORK + 0xf000)
    nt = call(c, nvic, (20,))
    if struct.unpack('<I', c.mem_read(0xe000e100, 4))[0] != 1 << 20:
        raise ValueError('Different IRQ20 enable')

    # Independent synthetic call: selected config registers use declared source resets,
    # not alleged values from the preceding native device_configure invocation.
    retained = Bank(metadata)
    retained.values.update(bank.values)
    c = cpu(raw, after, WORK + 0xf000)
    retained.attach(c)
    try:
        call(c, power, (instance, 2, 1))
    except ValueError:
        if not retained.unknown:
            raise
    if retained.unknown != [dict(operation='read', offset=0x2b0, size=4, value=None)]:
        raise ValueError('Unexpected retained-sleep boundary: ' + repr(retained.unknown))
    return dict(case=case, capture=capture, queue_entry=entry, queue_table=list(table),
                parent=parent, instance=instance, queue=queue, queue_setup=trace,
                queue_events=bank.events, callback_plain_cpu_ram_work_exact=True,
                queue_software_flags=bank.software_flags, queue_engine_enabled=False,
                next_parent_gpio_call=gpio, irq_samples=samples,
                nvic_priority=pt, nvic_enable=nt, irq_number=20, priority=4,
                retained_sleep_events=retained.events, retained_sleep_boundary=retained.unknown,
                retained_sleep_pc=c.reg_read(arm.UC_ARM_REG_PC))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence')
    folder = a.simulator / 'mspi0-queue-sdk-01'
    pins = json.loads((folder / 'sources.json').read_text())
    tree = json.loads((folder / 'tree.json').read_text())
    if pins['commit'] != '61b293a49db34030c545f99101f7ebf6a3050314' or tree['sha'] != pins['commit'] or tree['truncated']:
        raise ValueError('Different pinned SDK tree')
    for pin in pins['files']:
        data = (folder / Path(pin['path']).name).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if sha(folder / Path(pin['path']).name) != pin['sha256'] or blob != pin['git_blob'] or not any(t['path'] == pin['path'] and t['sha'] == blob for t in tree['tree']):
            raise ValueError('Changed CMDQ SDK source')
    _, metadata = collect(a.simulator)
    svd = ET.parse(a.simulator / 'apollo-dfp-research-01/apollo510.svd').getroot()
    peripheral = next(x for x in svd.findall('./peripherals/peripheral') if x.findtext('name') == 'MSPI0')
    if [int(i.findtext('value'), 0) for i in peripheral.findall('interrupt')] != [20]:
        raise ValueError('Different public MSPI0 IRQ number')
    rows = [inspect(a.simulator, case, metadata) for case in ('stock24', 'stock23', 'cfw')]
    report = dict(passed=True, cases=rows, sdk=pins,
                  engine='Original ARM on Unicorn M7; saved native GPR/RAM plus synthetic Thumb status and passive MMIO/SCS fixtures. Separate IRQ/sleep function calls use a synthetic stack.',
                  queue_equivalence_cases=3, native_rerun=False, model_changed=False,
                  gpio_following_enable_not_executed=True, cqflags_unknown=True,
                  queue_completion_generated=False, hardware_accessed=False,
                  natural_boot_verified=False, display_verified=False)
    a.output.mkdir(mode=0o700)
    (a.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    print('Verified original3 disabled queue setup/equivalence; separate IRQ20 calls; retained sleep bounded at unknown CQFLAGS')


if __name__ == '__main__':
    main()
