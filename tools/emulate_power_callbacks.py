"""Check power callback table clearing and dispatch in pinned stock boot code.

Only an initialization prefix is executed; no MMIO or full boot is emulated.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from emulate_mram_binding import PROFILES

TABLE, STACK, STOP, CALLBACK = 0x20026e38, 0x2000f000, 0x100000, 0x100100


def run(data, mode, slot=None, callback_status=0):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    for base, size in ((0x410000, 0x30000), (0x20000000, 0x30000), (STOP, 0x1000)):
        uc.mem_map(base, size)
    uc.mem_write(0x410000, data)
    uc.mem_write(TABLE-4, b'\xa5'*68)
    if slot is not None:
        uc.mem_write(slot, struct.pack('<I', (CALLBACK | 1) if mode == 'present' else 0))
    before = bytes(uc.mem_read(TABLE-4, 68))
    ram_before = bytearray(uc.mem_read(0x20000000, 0x30000))
    uc.reg_write(UC_ARM_REG_SP, STACK)
    uc.reg_write(UC_ARM_REG_LR, STOP | 1)
    trace = []

    def hook(emu, address, size, context):
        if address == CALLBACK:
            trace.append('callback')
            emu.reg_write(UC_ARM_REG_R0, callback_status)
            emu.reg_write(UC_ARM_REG_PC, emu.reg_read(UC_ARM_REG_LR))

    uc.hook_add(UC_HOOK_CODE, hook)
    entry = 0x41ce52 if mode == 'clear' else (0x41cd34 if slot == TABLE+12 else 0x41cd4a)
    end = 0x41ce66 if mode == 'clear' else STOP
    uc.emu_start(entry | 1, end, count=2000)
    assert uc.reg_read(UC_ARM_REG_PC) == end
    after = bytes(uc.mem_read(TABLE-4, 68))
    ram_after = bytearray(uc.mem_read(0x20000000, 0x30000))
    stack_offset = STACK-0x20000000
    ram_before[stack_offset-128:stack_offset] = bytes(128)
    ram_after[stack_offset-128:stack_offset] = bytes(128)
    if mode == 'clear':
        offset = TABLE-0x20000000
        ram_before[offset:offset+60] = bytes(60)
    assert ram_after == ram_before, 'Unexpected final RAM change'
    if mode == 'clear':
        assert after == b'\xa5'*4 + b'\0'*60 + b'\xa5'*4
        assert uc.reg_read(UC_ARM_REG_SP) == STACK-16
    else:
        assert after == before
        assert uc.reg_read(UC_ARM_REG_SP) == STACK
        assert trace == (['callback'] if mode == 'present' else [])
        assert uc.reg_read(UC_ARM_REG_R0) == (callback_status if mode == 'present' else 0)
    return {"mode": mode, "slot": hex(slot) if slot else None,
            "callback_status": callback_status, "trace": trace,
            "return": uc.reg_read(UC_ARM_REG_R0) if mode != 'clear' else None}


def audit(directory):
    images = []
    for v, (sha, _) in PROFILES.items():
        data = (directory/f'boot-{v}.bin').read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha
        images.append(data)
    cases = []
    specs = [('clear', None, 0)] + [(mode, TABLE+offset, status)
        for offset in (12, 16) for mode in ('absent', 'present') for status in (0, 7)]
    for mode, slot, status in specs:
        results = [run(data, mode, slot, status) for data in images]
        assert results[0] == results[1]
        cases.append(results[0])
    return {"scope": "power-table-init-prefix-and-two-dispatch-wrappers",
            "hardware_accessed": False, "full_boot_or_callback_lifetime_verified": False,
            "input_hashes": {v:p[0] for v,p in PROFILES.items()}, "cases": cases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.directory)
    with args.output.open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(f"{len(result['cases'])} paired cases passed; init stops before MMIO")
