"""Compare stock MRAM call adapters in Unicorn; ROM and hardware are mocked.

Does not emulate programming or prove physical recovery. Inputs are raw boot
images extracted by compare_boot_bindings.py; exact hashes are required.
"""
import argparse
import hashlib
import itertools
import json
import struct
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_PRIMASK)

PROFILES = {
    "2.3.2.14": ("22a2b98e606b4d296e957a3a8b600a2158497638d79485c817c2025536329ba7", 0x42e83c),
    "2.4.0.24": ("ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665", 0x42e84c),
}
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
STOP, STACK, SOURCE = 0x100000, 0x2000f000, 0x20001000


def execute(data, entry, destination, words, rom_status):
    emu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    for base, size in ((0x410000, 0x30000), (0x20000000, 0x10000),
                       (0x0200f000, 0x1000), (0x40014000, 0x1000), (STOP, 0x1000)):
        emu.mem_map(base, size)
    emu.mem_write(0x410000, data)
    emu.reg_write(UC_ARM_REG_SP, STACK)
    emu.reg_write(UC_ARM_REG_LR, STOP | 1)
    for reg, value in zip(REGS, (0x12344321, SOURCE, destination, words)):
        emu.reg_write(reg, value)
    calls, writes = [], []

    def code(uc, address, size, context):
        if address == STOP:
            uc.emu_stop()
        elif address in (0x41b8ec, 0x41bd92, 0x41bde4, 0x0200ff20):
            if address == 0x0200ff20:
                calls.append([uc.reg_read(r) for r in REGS] +
                    [struct.unpack("<I", uc.mem_read(uc.reg_read(UC_ARM_REG_SP), 4))[0]])
            uc.reg_write(UC_ARM_REG_R0, rom_status if address == 0x0200ff20 else
                         (1 if address == 0x41b8ec else 0))
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def write(uc, access, address, size, value, context):
        if not 0x20000000 <= address < 0x20010000:
            writes.append([address, size, value])

    emu.hook_add(UC_HOOK_CODE, code)
    emu.hook_add(UC_HOOK_MEM_WRITE, write)
    emu.emu_start(entry | 1, STOP, count=1000)
    if emu.reg_read(UC_ARM_REG_PC) != STOP or emu.reg_read(UC_ARM_REG_SP) != STACK:
        raise AssertionError("Did not return with restored stack")
    return {"return": emu.reg_read(UC_ARM_REG_R0), "rom_calls": calls,
            "nonstack_writes": writes, "primask": emu.reg_read(UC_ARM_REG_PRIMASK)}


def audit(directory):
    images = {}
    for version, (sha, entry) in PROFILES.items():
        raw = (directory / f"boot-{version}.bin").read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("Unexpected boot input")
        images[version] = raw
    cases = []
    for dest, words, status in itertools.product((0x438000, 0x438001, 0x438004, 0x7f7ff0),
                                                 (0, 1, 4, 64), (0, 1, 0x40)):
        results = [execute(images[v], p[1], dest, words, status) for v, p in PROFILES.items()]
        assert results[0] == results[1], (dest, words, status, results)
        observed = results[0]
        if dest & 15 or words & 3:
            assert observed["return"] == 0x08000140 and not observed["rom_calls"]
            assert observed["nonstack_writes"] == []
        else:
            assert observed["rom_calls"] == [[0x12344321, 1, SOURCE, (dest-0x400000)//4, words]]
            assert observed["return"] == (status | 0x08000100 if status else 0)
            assert observed["nonstack_writes"] == [[0x40014008, 4, 0xc3],
                [0x40014024, 4, 0], [0x40014008, 4, 0]]
            assert observed["primask"] == 1
        cases.append({"destination": hex(dest), "words": words, "mock_rom_status": status,
                      "equivalent_in_model": True})
    try:
        execute(images["2.4.0.24"], PROFILES["2.3.2.14"][1], 0x438000, 4, 0)
    except (UcError, AssertionError) as error:
        wrong_entry = {"rejected_in_model": True, "error": str(error)}
    else:
        raise AssertionError("Old entry unexpectedly returned normally in new image")
    return {"kind": "stock-mram-adapter-emulation", "hardware_accessed": False,
            "rom_programming_emulated": False, "full_recovery_verified": False,
            "mocked_entries": [hex(x) for x in (0x41b8ec, 0x41bd92, 0x41bde4, 0x0200ff20)],
            "input_hashes": {v:p[0] for v,p in PROFILES.items()}, "cases": cases,
            "old_entry_on_new_image": wrong_entry}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.directory)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(f"{len(result['cases'])} paired cases passed; ROM mocked, no hardware or programming")
