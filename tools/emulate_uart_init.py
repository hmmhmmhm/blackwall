"""Run real data init, UART handle registration and init loop; mock peripheral callees."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from emulate_boot_data_init import initialize_machine
from emulate_mram_binding import PROFILES


def execute(data, version, power_status):
    uc, initial = initialize_machine(data, version)
    delta = 0 if version == '2.3.2.14' else 16
    stubs = {0x41f530: 'irq-priority', 0x41f512: 'irq-pending',
             0x41f4f4: 'irq-enable', 0x41d92c: 'gpio',
             0x422ef0+delta: 'power', 0x4233d6+delta: 'configure',
             0x42310e+delta: 'uart-control', 0x423a16+delta: 'uart-finalize'}
    calls = []
    def hook(emu, address, size, context):
        if address in stubs:
            name = stubs[address]
            calls.append({'name': name, 'args': [hex(emu.reg_read(reg)) for reg in
                (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]})
            emu.reg_write(UC_ARM_REG_R0, power_status if name == 'power' else 0)
            emu.reg_write(UC_ARM_REG_PC, emu.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, hook)
    uc.reg_write(UC_ARM_REG_LR, 0x100001)
    uc.emu_start(0x41f613, 0x100000, count=200000, timeout=5000000)
    assert uc.reg_read(UC_ARM_REG_PC) == 0x100000
    assert uc.reg_read(UC_ARM_REG_SP) == 0x2007f000
    slots = {address: struct.unpack('<I', uc.mem_read(address, 4))[0] for address in
             (0x20000494, 0x20000498, 0x200004a4, 0x200004a8, 0x200004f8, 0x20026e44, 0x20026e48)}
    assert slots[0x20000494] == 0x20024638
    assert slots[0x20000498] == 0x434210+delta
    assert slots[0x200004f8] == 0x42e6e5+delta
    assert slots[0x200004a4] == slots[0x200004a8] == slots[0x20026e44] == slots[0x20026e48] == 0
    assert struct.unpack('<I', uc.mem_read(0x20024638, 4))[0] & 0x1ffffff == 0x1ea9e06
    assert uc.reg_read(UC_ARM_REG_R0) == (1 if power_status else 0)
    return {'mock_power_status': power_status, 'return': uc.reg_read(UC_ARM_REG_R0),
            'slots': {hex(a):hex(v) for a,v in slots.items()}, 'stub_calls': calls}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = {}
    for version, (sha, _) in PROFILES.items():
        data = (args.directory/f'boot-{version}.bin').read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha
        results[version] = [execute(data, version, status) for status in (0, 7)]
    report = {'hardware_accessed': False, 'peripheral_callees_mocked': True,
              'full_boot_verified': False, 'input_hashes': {v:p[0] for v,p in PROFILES.items()},
              'results': results}
    with args.output.open('x') as out:
        json.dump(report, out, indent=2)
        out.write('\n')
    print('Two versions × success/failure: UART handle and guarded slots verified in model')
