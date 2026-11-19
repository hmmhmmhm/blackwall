"""Execute stock init-table copy/sort/dispatch; initializer bodies are mocked."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from emulate_mram_binding import PROFILES


def execute(data, version, initializer_status=0):
    delta = 0 if version == '2.3.2.14' else 16
    table = 0x433880 + delta
    entries = [struct.unpack_from('<II', data, table-0x410000+i*8) for i in range(4)]
    names = ('board-init', 'second-priority-one-init', 'priority-25-init', 'priority-26-init')
    identities = {address & ~1: (names[i], priority) for i, (address, priority) in enumerate(entries)}
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    for base, size in ((0x410000, 0x30000), (0x20000000, 0x30000), (0x100000, 0x1000)):
        uc.mem_map(base, size)
    uc.mem_write(0x410000, data)
    uc.mem_write(0x20022dfc, b'\xa5'*40)
    uc.reg_write(UC_ARM_REG_SP, 0x2000f000)
    uc.reg_write(UC_ARM_REG_LR, 0x100001)
    calls = []

    def code(emu, address, size, context):
        if address in identities:
            name, priority = identities[address]
            calls.append({'name': name, 'priority': priority})
            emu.reg_write(UC_ARM_REG_R0, initializer_status)
            emu.reg_write(UC_ARM_REG_PC, emu.reg_read(UC_ARM_REG_LR))

    uc.hook_add(UC_HOOK_CODE, code)
    uc.emu_start((0x41f9f8+delta) | 1, 0x100000, count=20000)
    assert uc.reg_read(UC_ARM_REG_PC) == 0x100000
    assert uc.reg_read(UC_ARM_REG_SP) == 0x2000f000
    assert len(calls) == 4 and sorted(c['name'] for c in calls) == sorted(names)
    assert [c['priority'] for c in calls] == [1, 1, 25, 26]
    memory = bytes(uc.mem_read(0x20022dfc, 40))
    assert memory[:4] == memory[-4:] == b'\xa5'*4
    sorted_entries = [struct.unpack_from('<II', memory, 4+i*8) for i in range(4)]
    assert sorted(sorted_entries) == sorted(entries)
    return {'calls': calls, 'mock_initializer_status': initializer_status, 'entry': hex(0x41f9f8+delta),
            'table': hex(table), 'table_count': 4,
            'sorted_table': [{'pointer': hex(a), 'priority': p} for a, p in sorted_entries]}


def audit(directory):
    results = {}
    for version, (sha, _) in PROFILES.items():
        data = (directory/f'boot-{version}.bin').read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha
        results[version] = [execute(data, version, status) for status in (0, 7)]
    for index in range(2):
        assert results['2.3.2.14'][index]['calls'] == results['2.4.0.24'][index]['calls']
    assert results['2.3.2.14'][0]['calls'] == results['2.3.2.14'][1]['calls']
    return {'scope': 'init-table-dispatch-with-mocked-initializers',
            'hardware_accessed': False, 'full_boot_order_proven': False,
            'input_hashes': {v:p[0] for v,p in PROFILES.items()}, 'results': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.directory)
    with args.output.open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(json.dumps(result['results'], indent=2))
