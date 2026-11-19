"""Bound original MSPI0 flag save/restore; no power transition or completion model."""
import argparse
import json
import struct
from pathlib import Path

import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_application_vendor_address import call
from inspect_keydb_record_load import run
from inspect_mspi0_queue_contract import Bank, branch
from inspect_mspi0_queue_profiles import inspect as verify_capture
from inspect_mspi0_initialization import Registers
from inspect_mspi1_config_contract import collect
from inspect_nema_blocking_wait import cpu, WORK
from prepare_vendor_startup_candidate import sha


OFFSETS = [0x80, 0x84, 0x88, 0x8c, 0x90, 0x94, 0x98, 0x9c, 0xa0, 0xa4,
           0xa8, 0x30, 0x44, 0x48, 0x4c, 0x2a8, 0x2b8, 0x2c0, 0x2c4, 0x200]


class Power:
    def __init__(self, enabled):
        self.values = {4: enabled, 8: enabled}
        self.events = []
        self.unknown = []

    def read(self, u, offset, size, user):
        if offset not in self.values or size != 4:
            self.unknown.append(dict(operation='read', offset=offset, size=size))
            u.emu_stop()
            return 0xffffffff
        self.events.append(dict(operation='read', offset=offset, value=self.values[offset]))
        return self.values[offset]

    def write(self, u, offset, size, value, user):
        if offset != 4 or size != 4:
            self.unknown.append(dict(operation='write', offset=offset, size=size, value=value))
            u.emu_stop()
            return
        self.events.append(dict(operation='write', offset=offset, value=value))
        self.values[offset] = value
        # Explicit immediate status response for this synthetic fixture only.
        self.values[8] = value

    def attach(self, u):
        u.mmio_map(0x40021000, 4096, self.read, None, self.write, None)


def word(data, address):
    return struct.unpack_from('<I', data, address - 0x20000000)[0]


def changed(data, address, value):
    b = bytearray(data)
    struct.pack_into('<I', b, address - 0x20000000, value)
    return bytes(b)


def inspect(s, case, metadata):
    capture = verify_capture(s, case)
    f = s / 'mspi0-queue-main-01' / case
    raw = (f / 'main.bin').read_bytes()
    ram = (f / 'exports/sram-full.bin').read_bytes()
    v = json.loads((f / 'report.json').read_text())
    regs = v['observed']['register_context']
    pc, instance = v['observed']['pc'], regs['r5']
    if regs['r4'] != instance or regs['r6'] != 1 or word(ram, instance + 0x20) or word(ram, instance + 0x840):
        raise ValueError('Different native idle retained-power context')
    # The preceding twenty reads have already populated this full native SRAM shadow.
    vals = {offset: word(ram, instance + 0x864 + 4 * (n if n < 15 else n + 1)) for n, offset in enumerate(OFFSETS)}
    if vals[0x90] & 1 or vals[0x200] != 0x1a80:
        raise ValueError('Different native XIP/IRQ state')
    suspend = pc + 0x80
    suspend_cq = pc + 0x4e
    resume = pc - 0x2ce
    resume_end = pc - 0x15a
    resume_cq = pc - 0x164
    power_entry = pc - 0x350
    disable = branch(raw, suspend)
    if decode(raw, resume, 4)[0].mnemonic != 'ldr.w' or branch(raw, suspend_cq) == branch(raw, resume_cq):
        raise ValueError('Different original power/CQ boundaries')

    def bank(flags, cfg=2):
        b = Bank(metadata)
        b.values.update(vals)
        b.values[0x2b0] = flags
        b.values[0x2a0] = cfg
        return b

    def saved(flags, cfg=2):
        b = bank(flags, cfg)
        u = cpu(raw, ram, regs['r13'])
        for n in range(15):
            u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), regs['r' + str(n)])
        b.attach(u)
        t = run(u, pc, [suspend, suspend_cq])
        data = bytes(u.mem_read(0x20000000, len(ram)))
        if b.unknown or word(data, instance + 0x8b8) != flags or word(data, instance + 0x8a0) != cfg:
            raise ValueError('Original shadow save differs')
        expected = suspend_cq if cfg & 1 else suspend
        if t['stop'] != expected:
            raise ValueError('Active queue was not separated before power off')
        if cfg == 2 and (b.values[0x200] != 0 or data[instance - 0x20000000 + 0x860] != 1 or u.reg_read(arm.UC_ARM_REG_R0) != 16):
            raise ValueError('Different saved-state marker/IRQ/off argument')
        return b, t, data

    def restored(data, cfg=2):
        # Explicit bounded restoration block, after the original power/clock calls.
        # This synthetic block entry does not claim those calls succeeded.
        b = Bank(metadata)
        c = cpu(raw, data, WORK + 0xf000)
        c.reg_write(arm.UC_ARM_REG_R4, instance)
        c.reg_write(arm.UC_ARM_REG_R5, instance)
        b.attach(c)
        t = run(c, resume, [resume_end, resume_cq])
        events = [x for x in b.events if x['operation'] == 'write']
        if b.unknown or t['stop'] != (resume_cq if cfg & 1 else resume_end):
            raise ValueError('Original restore escaped disabled queue boundary')
        if b.values[0x2a0] != cfg & ~1:
            raise ValueError('Original restore enabled CQ too early')
        expected = [(offset, word(data, instance + 0x864 + 4 * (n if n < 15 else n + 1))) for n, offset in enumerate(OFFSETS)]
        expected += [(0x2b4, word(data, instance + 0x8b8) & 255),
                     (0x114, word(data, instance + 0x8bc)),
                     (0x118, word(data, instance + 0x8c0)),
                     (0x20, word(data, instance + 0x8c4)), (0x2a0, cfg & ~1)]
        if [(e['offset'], e['value']) for e in events] != expected:
            raise ValueError('Original restore register ordering/value differs from shadow')
        if cfg == 2 and bytes(c.mem_read(instance + 0x860, 1)) != b'\0':
            raise ValueError('Saved-state marker not cleared')
        return b, t, events

    samples = []
    baseline = None
    for high in range(256):
        flags = (high << 8) | 0x80
        b, t, data = saved(flags)
        restored_bank, rt, writes = restored(data)
        if restored_bank.software_flags != 0x80:
            raise ValueError('Hardware flag bits leaked into software restoration')
        signature = (t, rt, writes)
        if baseline is None:
            baseline = signature
        elif signature != baseline:
            raise ValueError('Hardware flag bits changed bounded path or restore writes')
        samples.append(dict(flags=flags, save=t, restore=rt))
    active, active_save, active_data = saved(0x80, 3)
    active_restore, active_rt, _ = restored(active_data, 3)
    busy = []
    for offset in (0x20, 0x840):
        b = Bank(metadata)
        u = cpu(raw, changed(ram, instance + offset, 1), WORK + 0xf000)
        b.attach(u)
        t = call(u, power_entry, (instance, 2, 1))
        if b.events or b.unknown or u.reg_read(arm.UC_ARM_REG_R0) != 3:
            raise ValueError('Pending transaction did not reject suspend')
        busy.append(dict(nonzero_offset=offset, execution=t, result=3, mmio_events=0))
    hal = []
    for initial in (0x4e00, 0xe00):
        b = Power(initial)
        u = cpu(raw, ram, WORK + 0xf000)
        b.attach(u)
        t = call(u, disable, (16,))
        writes = [e for e in b.events if e['operation'] == 'write']
        if b.unknown or u.reg_read(arm.UC_ARM_REG_R0) != 0 or b.values[4] != 0xe00 or len(writes) != (1 if initial & 0x4000 else 0):
            raise ValueError('Original HAL power-off clear/idempotence differs')
        hal.append(dict(initial_enable=initial, execution=t, events=b.events, result=0))

    # Integrated original tail: successful peripheral-off response is a declared
    # virtual input. The guest executes every HAL/clock/release call itself.
    b = bank(0x80)
    power = Power(0x4e00)
    clock_state = v['observed']['mcu_clock_response']
    if clock_state['profile'] != 'nominal' or clock_state['mode_word'] != 22:
        raise ValueError('Different native nominal clock fixture')
    clock = Registers({}, clock_state['misc_word'], 22, 0xa4215)
    u = cpu(raw, ram, regs['r13'])
    for n in range(15):
        u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), regs['r' + str(n)])
    b.attach(u)
    power.attach(u)
    u.mmio_map(0x40004000, 4096, clock.cread, None, clock.cwrite, None)
    tail = run(u, pc, [regs['r14'] & ~1])
    if b.unknown or power.unknown or clock.unknown or u.reg_read(arm.UC_ARM_REG_R0) != 0 or power.values[4] != 0xe00 or clock.clock[0x110] != 0xa4214:
        raise ValueError('Original suspend tail failed declared off/clock fixture')
    return dict(case=case, capture=capture, instance=instance, native_saved_registers=vals,
                source_reset_only_offsets=[0x114, 0x118, 0x20],
                save_entry=pc, restore_block_entry=resume, off_call_site=suspend,
                off_callee=disable, off_argument=16, samples=samples,
                bounded_paths_equal_for_all_hardware_flag_bytes=True,
                restore_write_sequence=baseline[2], active_queue_save_boundary=active_save,
                active_queue_restore_boundary=active_rt, pending_transaction_rejections=busy,
                synthetic_hal_off=hal, integrated_suspend_tail=tail,
                suspend_power_events=power.events, suspend_clock_events=clock.events)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence')
    _, metadata = collect(a.simulator)
    flags = next(r for r in metadata if r['name'] == 'CQFLAGS')
    if flags['mask'] != 0xffff:
        raise ValueError('Different public CQFLAGS bit range')
    pins = json.loads((a.simulator / 'mspi1-source-research-01/sources.json').read_text())
    source = next(x for x in pins['files'] if x['path'].endswith('/am_hal_mspi.c'))
    path = a.simulator / 'mspi1-source-research-01/am_hal_mspi.c'
    if pins['commit'] != '61b293a49db34030c545f99101f7ebf6a3050314' or sha(path) != source['sha256']:
        raise ValueError('Changed pinned MSPI SDK')
    rows = [inspect(a.simulator, c, metadata) for c in ('stock24', 'stock23', 'cfw')]
    report = dict(passed=True, cases=rows, sdk=source,
                  hardware_flag_variants_per_case=256, original_arm_executions=1557,
                  engine='Unicorn M7 original ARM, saved GPR/RAM plus synthetic Thumb/MMIO; separate restore block and busy calls have synthetic entries/stacks.',
                  natural_power_transition_executed=False, synthetic_hal_power_off_calls=6,
                  integrated_suspend_tail_cases=3, restore_power_clock_calls_executed=False,
                  native_rerun=False, model_changed=False, hardware_accessed=False,
                  natural_boot_verified=False, display_verified=False)
    a.output.mkdir(mode=0o700)
    (a.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    print('Verified original3 flags upper-byte256 paths, active/busy guards and synthetic off/clock tail; no native rerun')


if __name__ == '__main__':
    main()
