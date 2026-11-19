"""Run original IRQ20 dispatch, CQ completion callbacks and semaphore release on declared fixtures."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_mspi0_cq_submit import inspect as verify_capture, SOURCE_PINS
from inspect_nema_blocking_wait import cpu, WORK, STOP
from prepare_vendor_startup_candidate import sha


def inspect(s, case):
    source = verify_capture(s, case)
    f = s / 'mspi0-tx-main-01' / case
    v = json.loads((f / 'report.json').read_text())
    raw = (f / 'main.bin').read_bytes()
    original = (f / 'exports/sram-full.bin').read_bytes()
    regs = v['observed']['register_context']

    def word(address):
        return struct.unpack_from('<I', original, address - 0x20000000)[0] if address >= 0x20000000 else struct.unpack_from('<I', raw, address - 0x438000)[0]

    irq = struct.unpack_from('<I', raw, 4 * (16 + 20))[0] & ~1
    global_pointer = literal(raw, decode(raw, irq + 2, 4)[0])
    dispatch_object = word(global_pointer)
    dispatch_callback = word(dispatch_object) & ~1
    mspi_global = literal(raw, decode(raw, dispatch_callback + 2, 4)[0])
    mspi_handle = word(mspi_global)
    callback = regs['r6'] & ~1
    if mspi_handle != regs['r4'] or word(mspi_handle + 0x2c) & ~1 != callback:
        raise ValueError('Different registered MSPI dispatch/callback chain')
    context = word(mspi_handle + 0x42c)
    if not 0x20000000 <= context < 0x20380000:
        raise ValueError('Callback context outside captured SRAM')
    instructions = decode(raw, callback, 18)
    if (instructions[1].mnemonic, instructions[1].op_str) != ('str', 'r1, [r0]'):
        raise ValueError('Different callback status store')
    semaphore_global = literal(raw, decode(raw, callback + 4, 4)[0])
    semaphore = word(semaphore_global)
    if word(semaphore + 0x38) != 0 or word(mspi_handle + 0x20) != 1:
        raise ValueError('Different initial pending transaction/semaphore state')
    give_call = decode(raw, callback + 10, 4)[0]
    if give_call.mnemonic != 'bl':
        raise ValueError('Different callback semaphore give call')

    scenarios = [
        ('no-status', 0, 0, 9, None),
        ('raw-dma-complete-index-pending', 0x40, 0, 9, None),
        ('queue-update-index-pending', 0x200, 0, 9, None),
        ('paused-index-pending', 0x400, 0, 9, None),
        ('queue-update-index-complete', 0x200, 1, 9, 0),
        ('combined-completion-index-complete', 0x640, 1, 9, 0),
        ('dma-error-index-pending', 0x80, 0, 9, 1),
        ('queue-error-index-pending', 0x800, 0, 9, 1),
        ('scramble-error-index-pending', 0x1000, 0, 9, 1),
        ('apb-error-not-in-this-error-mask', 0x2000, 0, 9, None),
        ('queue-status-error', 0x200, 0, 5, 1),
    ]

    def execute(status, index, queue_status, result, observe):
        ram = bytearray(original)
        # Declared post-enable fixture; original main stopped before committing CQEN.
        struct.pack_into('<I', ram, source['handle'] - 0x20000000,
                         word(source['handle']) | 0x2000000)
        u = cpu(raw, bytes(ram), WORK + 0xf000)
        u.reg_write(arm.UC_ARM_REG_XPSR, 0x1000024)
        if u.reg_read(arm.UC_ARM_REG_IPSR) != 36:
            raise ValueError('Missing explicit passive IRQ20 context')
        values = {0x200: 0x1a80, 0x204: status, 0x2c0: index, 0x2c4: 1,
                  0x2ac: queue_status, 0x2a0: 3, 0x2a8: source['queue_start'] + (72 if index else 0),
                  0x100: 0, 0x104: 2, 0x30: 0xc00000f1, 0x2b4: 0x80}
        events, unknown, trace, callbacks = [], [], [], []

        def read(c, offset, size, user):
            if size != 4 or offset not in values:
                unknown.append(dict(operation='read', offset=offset, size=size))
                c.emu_stop()
                return 0xffffffff
            value = values[offset]
            events.append(dict(operation='read', offset=offset, value=value))
            return value

        def write(c, offset, size, value, user):
            if size != 4 or offset not in (0x208, 0x2a0, 0x100):
                unknown.append(dict(operation='write', offset=offset, size=size, value=value))
                c.emu_stop()
                return
            if offset == 0x208:
                values[0x204] &= ~value
            else:
                values[offset] = value
            events.append(dict(operation='write', offset=offset, value=value))

        u.mmio_map(0x40060000, 0x1000, read, None, write, None)

        def hook(c, pc, size, user):
            trace.append(pc)
            if pc == callback:
                if observe:
                    callbacks.append((c.reg_read(arm.UC_ARM_REG_R0), c.reg_read(arm.UC_ARM_REG_R1)))
                # Error cleanup is a separate boundary; do not skip or stub it.
                if result == 1:
                    c.emu_stop()

        u.hook_add(UC_HOOK_CODE, hook)
        u.emu_start(irq | 1, STOP, count=5000)
        end = u.reg_read(arm.UC_ARM_REG_PC)
        if unknown or end != (callback if result == 1 else STOP):
            raise ValueError('Original IRQ escaped contract: ' + repr(unknown))
        after = bytes(u.mem_read(0x20000000, len(ram)))
        pending = struct.unpack_from('<I', after, mspi_handle - 0x20000000 + 0x20)[0]
        count = struct.unpack_from('<I', after, semaphore - 0x20000000 + 0x38)[0]
        if pending != (1 if result is None else 0) or count != (1 if result == 0 else 0):
            raise ValueError('Different pending/semaphore state')
        if observe and callbacks != ([] if result is None else [(context, result)]):
            raise ValueError('Different original completion callback status/context')
        if result == 0:
            if values[0x2a0] != 2 or values[0x100] != 0 or struct.unpack_from('<I', after, context - 0x20000000)[0] != 0:
                raise ValueError('Success did not clear queue/DMA and store callback status')
            if struct.unpack_from('<I', after, mspi_handle - 0x20000000 + 0x2c)[0] != 0 or struct.unpack_from('<I', after, source['handle'] - 0x20000000)[0] & 0x2000000:
                raise ValueError('Success did not retire callback/disable software CQ handle')
        return dict(stop=end, instructions=len(trace),
                    trace_sha256=hashlib.sha256(struct.pack('<' + 'I' * len(trace), *trace)).hexdigest(),
                    sram_sha256=hashlib.sha256(after).hexdigest(),
                    work_sha256=hashlib.sha256(bytes(u.mem_read(WORK, 0x10000))).hexdigest(),
                    registers=[u.reg_read(getattr(arm, 'UC_ARM_REG_R' + str(n))) for n in range(16)],
                    xpsr=u.reg_read(arm.UC_ARM_REG_XPSR), primask=u.reg_read(arm.UC_ARM_REG_PRIMASK),
                    events=events, pending=pending, semaphore_count=count, callbacks=callbacks)

    samples = []
    for name, status, index, queue_status, result in scenarios:
        observed = execute(status, index, queue_status, result, True)
        control = execute(status, index, queue_status, result, False)
        callbacks = observed.pop('callbacks')
        control.pop('callbacks')
        if observed != control:
            raise ValueError('Callback observation changed original execution')
        samples.append(dict(name=name, status_fixture=status, index_fixture=index, cqstat_fixture=queue_status,
                            hardware_irq_mask_would_assert=bool(status & 0x1a80),
                            callback_result=result, callbacks=callbacks, execution=observed,
                            error_cleanup_executed=False if result == 1 else None))
    return dict(case=case, irq20=irq, dispatch_object=dispatch_object, registered_dispatch=dispatch_callback,
                mspi_handle=mspi_handle, callback=callback, context=context, semaphore=semaphore,
                semaphore_give_function=give_call.operands[0].imm, source=source,
                observer_on_off_equal=True, samples=samples)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence')
    for name, expected in SOURCE_PINS.items():
        if sha(a.simulator / name) != expected:
            raise ValueError('Changed pinned source ' + name)
    header = (a.simulator / 'mspi1-source-research-01/apollo510.h').read_text()
    irq_masks = dict(DCMP=0x40, DERR=0x80, CQUPD=0x200, CQPAUSED=0x400,
                     CQERR=0x800, SCRERR=0x1000, APBDMAERR=0x2000)
    for name, expected in irq_masks.items():
        m = re.search(r'^#define MSPI0_INTSTAT_' + name + r'_Msk\s+\((0x[0-9a-fA-F]+)UL\)', header, re.M)
        if not m or int(m.group(1), 16) != expected:
            raise ValueError('Different MSPI0 IRQ bit mapping ' + name)
    rows = [inspect(a.simulator, case) for case in ('stock24', 'stock23', 'cfw')]
    a.output.mkdir(mode=0o700)
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows,
        irq_arm_scenarios=66, prerequisite_enable_arm_scenarios=12, irq_masks=irq_masks,
        engine='Unicorn M7 passive IRQ20 context and declared completed/failed CQ registers',
        dma_executed=False, native_irq_verified=False, error_cleanup_verified=False,
        hardware_accessed=False, boot_verified=False, display_verified=False), indent=2) + '\n')
    print('Verified original3 IRQ dispatch/CQ index/callback/semaphore, 66 paired IRQ scenarios; no native DMA/IRQ')


if __name__ == '__main__':
    main()
