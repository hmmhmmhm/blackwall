"""Run pinned stock data initialization without hardware mappings or stubs."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from emulate_mram_binding import PROFILES


def initialize_machine(data, version):
    delta = 0 if version == '2.3.2.14' else 16
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    for base, size in ((0x410000, 0x30000), (0x20000000, 0x400000),
                       (0, 0x40000), (0x100000, 0x1000)):
        uc.mem_map(base, size)
    uc.mem_write(0x410000, data)
    uc.mem_protect(0x410000, 0x30000, UC_PROT_READ | UC_PROT_EXEC)
    uc.mem_write(0x20000000, b'\xa5'*0x400000)
    uc.mem_write(0, b'\xa5'*0x40000)
    uc.reg_write(UC_ARM_REG_SP, 0x2007f000)
    uc.reg_write(UC_ARM_REG_LR, 0x100001)
    uc.emu_start((0x432d24+delta) | 1, 0x100000, count=2000000, timeout=5000000)
    assert uc.reg_read(UC_ARM_REG_PC) == 0x100000
    assert uc.reg_read(UC_ARM_REG_SP) == 0x2007f000
    expected = {0x20000494: 0, 0x20000498: 0x434210+delta,
                0x200004a4: 0, 0x200004a8: 0, 0x200004f8: 0x42e6e5+delta,
                0x20026e44: 0, 0x20026e48: 0}
    observed = {address: struct.unpack('<I', uc.mem_read(address, 4))[0] for address in expected}
    assert observed == expected, observed
    return uc, {'entry': hex(0x432d24+delta), 'initial_ram_fill': '0xa5',
            'slots': {hex(a): hex(v) for a, v in observed.items()},
            'uart_state_sha256': hashlib.sha256(uc.mem_read(0x20000458, 112)).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = {}
    for version, (sha, _) in PROFILES.items():
        data = (args.directory/f'boot-{version}.bin').read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha
        _, results[version] = initialize_machine(data, version)
    report = {'scope': 'stock-data-init-only', 'hardware_accessed': False,
              'full_reset_or_boot_verified': False, 'stubbed_functions': [],
              'input_hashes': {v:p[0] for v,p in PROFILES.items()}, 'results': results}
    with args.output.open('x') as out:
        json.dump(report, out, indent=2)
        out.write('\n')
    print(json.dumps(results, indent=2))
