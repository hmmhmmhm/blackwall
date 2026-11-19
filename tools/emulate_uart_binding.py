"""Execute stock UART wake/sleep wrappers; GPIO and power callee are stubs.

This is a RAM-layout and call-contract experiment, not physical UART validation.
"""
import argparse
import hashlib
import itertools
import json
import struct
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from emulate_mram_binding import PROFILES

BASE, STATE, STACK, STOP = 0x410000, 0x20000458, 0x2000f000, 0x100000
HANDLE, CALLBACK = 0x20002000, 0x20003001


def execute(data, version, operation, module, awake, status):
    pin = 0x434210 if version == "2.3.2.14" else 0x434220
    power = 0x422ef0 if version == "2.3.2.14" else 0x422f00
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    for base, size in ((BASE, 0x30000), (0x20000000, 0x10000), (STOP, 0x1000)):
        uc.mem_map(base, size)
    uc.mem_write(BASE, data)
    uc.mem_write(STATE, bytes([0xa5])*112)
    for address, value in ((0x20000494, HANDLE), (0x20000498, pin), (0x200004a4, CALLBACK)):
        uc.mem_write(address, struct.pack("<I", value))
    uc.mem_write(0x200004a8, bytes([awake]))
    before = bytes(uc.mem_read(STATE, 112))
    uc.reg_write(UC_ARM_REG_R0, module)
    uc.reg_write(UC_ARM_REG_SP, STACK)
    uc.reg_write(UC_ARM_REG_LR, STOP | 1)
    trace = []

    def code(emu, address, size, context):
        if address in (power, 0x41d92c):
            args = [emu.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            trace.append({"call": "power" if address == power else "gpio", "args": args if address == power else args[:2]})
            emu.reg_write(UC_ARM_REG_R0, status if address == power else 0)
            emu.reg_write(UC_ARM_REG_PC, emu.reg_read(UC_ARM_REG_LR))

    def write(emu, access, address, size, value, context):
        if STATE <= address < STATE + 112:
            trace.append({"write": hex(address), "size": size, "value": value})
        elif not STACK-128 <= address < STACK:
            raise AssertionError(f"Unexpected write {address:x}")

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_WRITE, write)
    uc.emu_start((0x41f846 if operation == "wake" else 0x41f8ba) | 1, STOP, count=1000)
    assert uc.reg_read(UC_ARM_REG_PC) == STOP
    assert uc.reg_read(UC_ARM_REG_SP) == STACK
    after = bytes(uc.mem_read(STATE, 112))
    expected = bytearray(before)
    if module == 2:
        expected[0x50] = 1 if operation == "wake" else 0
    assert after == expected, "Driver RAM changed beyond the awake byte"
    result = {"return": uc.reg_read(UC_ARM_REG_R0), "trace": trace}
    assert result["return"] == (status if module == 2 else 1)
    if module == 4:
        assert trace == []
    else:
        power_call = {"call": "power", "args": [HANDLE, 0 if operation == "wake" else 2, 1]}
        state_write = {"write": "0x200004a8", "size": 1, "value": 1 if operation == "wake" else 0}
        assert trace[0 if operation == "wake" else -1] == power_call
        assert trace[-1 if operation == "wake" else 0] == state_write
        assert sum(row.get("call") == "gpio" for row in trace) == 2
    return result


def audit(directory):
    images = {}
    for version, (sha, _) in PROFILES.items():
        data = (directory/f"boot-{version}.bin").read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha
        images[version] = data
    cases = []
    for operation, module, awake, status in itertools.product(("wake", "sleep"), (2, 4), (0, 1, 255), (0, 7)):
        results = [execute(data, version, operation, module, awake, status) for version, data in images.items()]
        assert results[0] == results[1], (operation, module, awake, status, results)
        cases.append({"operation": operation, "module": module, "initial_awake": awake,
                      "stub_power_status": status, "result": results[0]})
    return {"kind": "uart-wrapper-comparison", "hardware_accessed": False,
            "gpio_and_power_mocked": True, "initialization_and_lifetime_verified": False,
            "input_hashes": {v:p[0] for v,p in PROFILES.items()}, "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.directory)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(f"{len(result['cases'])} paired UART wrapper cases passed; power/GPIO mocked")
