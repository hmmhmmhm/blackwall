"""Inspect original posted DMA queue and run CQ-enable tail to caller wait boundary."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_keydb_record_load import run
from inspect_mspi0_tx_profiles import inspect as verify_capture
from inspect_nema_blocking_wait import cpu, WORK
from prepare_vendor_startup_candidate import sha

SOURCE_PINS = {
    'mspi0-queue-sdk-01/am_hal_cmdq.c': '60aa2126ca01cd72f746a92d6f34a13e909fdab24ebfab6d6b0a70b026d8fa83',
    'mspi0-queue-sdk-01/am_hal_cmdq.h': '0113aed2f109c5f022d38055b83a75c2cf141e8621177296757fc8315926762f',
    'mspi1-source-research-01/am_hal_mspi.c': '5a91ab0c67bda4bd61c7d436b94b5a7c81693b948a331d282ae10e88cc5bf85f',
    'mspi1-source-research-01/am_hal_mspi.h': '2a682bb7c1618982d6a802f3220a38696cd594c89d90e64b1a698d226b0a557b',
    'mspi1-source-research-01/apollo510.h': 'b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797',
    'apollo-dfp-research-01/apollo510.svd': 'a2390c3366450eaccc9d4531d26dc9d68488ec42de5795ee50ab45a266f28276',
}


def word(data, address):
    return struct.unpack_from('<I', data, address - 0x20000000)[0]


class EnableRegister:
    def __init__(self):
        self.events = []
        self.unknown = []

    def read(self, u, offset, size, user):
        self.unknown.append(dict(operation='read', offset=offset, size=size))
        u.emu_stop()
        return 0xffffffff

    def write(self, u, offset, size, value, user):
        event = dict(offset=offset, size=size, value=value)
        if event != dict(offset=0x2a0, size=4, value=3):
            self.unknown.append(event)
            u.emu_stop()
        else:
            self.events.append(event)


def inspect(s, case):
    source = verify_capture(s, case, 'active')
    folder = s / 'mspi0-tx-main-01' / case
    v = json.loads((folder / 'report.json').read_text())
    r = v['observed']['register_context']
    raw = (folder / 'main.bin').read_bytes()
    ram = (folder / 'exports/sram-full.bin').read_bytes()
    pc, sp, handle = v['observed']['pc'], r['r13'], r['r1']
    fields = struct.unpack_from('<11I', ram, handle - 0x20000000)
    prefix, start, end, head, tail, next_tail, length, current, posted, table, extra = fields
    if (prefix, end - start, head, tail - start, next_tail, length, current, posted, extra) != (
            0x1cdcdcd, 1024, start, 72, tail, 1024, 0, 1, 0):
        raise ValueError('Different posted command queue state')
    register_table = struct.unpack_from('<7I', raw, table - 0x438000)
    if register_table != (0x400602a0, 0x400602a8, 0x400602c0, 0x400602c4, 0x400602b8, 0x4000, 0x400602ac):
        raise ValueError('Different queue register table')
    descriptors = list(struct.iter_unpack('<II', ram[start - 0x20000000:tail - 0x20000000]))
    expected = [(0x400602b8, 0x4080), (0x400602b8, 0x4000),
                (0x40060108, 0x20094400), (0x4006010c, 0),
                (0x40060110, 0x25802), (0x40060100, 0x17),
                (0x40060100, 0), (0x400602b4, 0), (0x400602c1, 1)]
    if descriptors != expected:
        raise ValueError('Different actual DMA descriptor list')
    dma = ram[sp - 0x20000000 + 0x44:sp - 0x20000000 + 0x5c]
    if dma != bytes([1, 1, 0, 0]) + struct.pack('<5I', 0x25802, 0, 0x20094400, 0, 0):
        raise ValueError('Different original caller DMA parameters')
    buffer = ram[0x94400:0x94400 + 0x25802]
    if len(buffer) != 153602 or any(buffer):
        raise ValueError('Different initial zero-filled DMA buffer')
    caller_return = word(ram, sp + 0x2c) & ~1
    api = decode(raw, caller_return - 4, 4)[0]
    if api.mnemonic != 'bl':
        raise ValueError('Different nonblocking DMA API call')
    wait = caller_return + 0xa
    before_wait = decode(raw, caller_return, 14)
    if [(i.mnemonic, i.op_str) for i in before_wait[:2]] != [('mov', 'r8, r0'), ('movw', 'r1, #0xbb8')]:
        raise ValueError('Different caller status and wait setup')
    load = decode(raw, caller_return + 6, 4)[0]
    semaphore_global = literal(raw, load)
    semaphore = word(ram, semaphore_global)
    wait_call = decode(raw, wait, 4)[0]
    if wait_call.mnemonic != 'bl' or not 0x20000000 <= semaphore < 0x20380000:
        raise ValueError('Different caller semaphore wait')

    def execute(callback, end_pc):
        u = cpu(raw, ram, sp)
        for n in range(15):
            u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), r['r' + str(n)])
        bank = EnableRegister()
        if callback:
            u.mmio_map(0x40060000, 0x1000, bank.read, None, bank.write, None)
        else:
            u.mem_map(0x40060000, 0x1000)
            u.mem_write(0x400602a0, struct.pack('<I', 2))
        trace = run(u, pc, [end_pc])
        if trace['stop'] != end_pc or bank.unknown:
            raise ValueError('Original enable tail escaped contract')
        after = bytes(u.mem_read(0x20000000, len(ram)))
        if word(after, handle) != prefix | 0x2000000:
            raise ValueError('Original enable did not set handle enabled bit')
        if bytes(u.mem_read(start, 72)) != ram[start - 0x20000000:tail - 0x20000000]:
            raise ValueError('CPU enable mutated DMA descriptors')
        regs = [u.reg_read(getattr(arm, 'UC_ARM_REG_R' + str(n))) for n in range(16)]
        if end_pc == wait and (regs[0], regs[1], regs[8]) != (semaphore, 3000, 0):
            raise ValueError('Different returned DMA status or caller wait args')
        if end_pc == r['r14'] & ~1 and regs[0] != 0:
            raise ValueError('Different CQ enable return')
        if callback and bank.events != [dict(offset=0x2a0, size=4, value=3)]:
            raise ValueError('Different CQ enable effects')
        return dict(execution=trace, registers=regs, sram_sha256=hashlib.sha256(after).hexdigest(),
                    work_sha256=hashlib.sha256(bytes(u.mem_read(WORK, 0x10000))).hexdigest(),
                    xpsr=u.reg_read(arm.UC_ARM_REG_XPSR), primask=u.reg_read(arm.UC_ARM_REG_PRIMASK))

    samples = []
    for end_pc in [r['r14'] & ~1, wait]:
        observed, passive = execute(True, end_pc), execute(False, end_pc)
        if observed != passive:
            raise ValueError('MMIO observer changed original enable tail')
        samples.append(observed)
    return dict(case=case, source=source, handle=handle, queue_start=start, queue_bytes=1024,
                prepared_descriptors=[dict(address=a, value=b) for a, b in descriptors],
                software_current_index=current, software_posted_index=posted,
                index_update_interrupt_bit=descriptors[-1][0] & 1,
                dma_source=0x20094400, dma_bytes=len(buffer), dma_buffer_sha256=hashlib.sha256(buffer).hexdigest(),
                dma_buffer_all_zero=True, nonblocking_api=api.operands[0].imm,
                wait_call=wait, wait_function=wait_call.operands[0].imm, wait_argument=3000,
                callback_and_passive_equal=True, samples=samples)


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
    rows = [inspect(a.simulator, case) for case in ('stock24', 'stock23', 'cfw')]
    a.output.mkdir(mode=0o700)
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows,
        original_arm_scenarios=12, source_pins=SOURCE_PINS,
        engine='Unicorn M7, saved main SRAM/GPR, explicit CQ-enable register',
        dma_executed=False, queue_executed=False, panel_format_verified=False, hardware_accessed=False,
        boot_verified=False, display_verified=False), indent=2) + '\n')
    print('Verified original3 posted9-descriptor DMA queue and enable/caller wait tails, 12 ARM scenarios; no DMA/pixels')


if __name__ == '__main__':
    main()
