"""Verify source-derived zone/record/CRC/log-stack effects in saved ARM runs."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct

from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import cpu, WORK, STOP
from pinned_main import MAIN_LAYOUT
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm


STATE, RECORD = 0x200076b4, 0x2000690c
POINTS = [0x4fad8e, 0x4fad92, 0x4fadd2, 0x4fadd4]


def record_bytes(initial, timestamp, zone):
    result = bytearray(initial)
    result[0] = 3
    struct.pack_into('<I', result, 4, timestamp)
    result[8] = zone
    struct.pack_into('<H', result, 10, binascii.crc_hqx(result[:10], 0xffff))
    return bytes(result)


def producer_scenarios(raw, ram, initial, timestamp):
    samples = []
    for zone in [0, 16, 24, 255]:
        for store_status in [0, 7]:
            machine = cpu(raw, ram, WORK + 0xf000)
            machine.mem_write(RECORD, initial)
            machine.reg_write(arm.UC_ARM_REG_R0, timestamp)
            machine.reg_write(arm.UC_ARM_REG_R1, zone if zone < 128 else zone - 256)
            stores = []

            def abi(core, pc, size, user):
                if pc not in (0x43d62a, 0x50bd7a):
                    return
                if pc == 0x50bd7a:
                    assert core.reg_read(arm.UC_ARM_REG_R1) == RECORD
                    assert core.reg_read(arm.UC_ARM_REG_R2) == 12
                    stores.append(bytes(core.mem_read(RECORD, 12)).hex())
                core.reg_write(arm.UC_ARM_REG_R0, store_status if pc == 0x50bd7a else 0)
                core.reg_write(arm.UC_ARM_REG_PC, core.reg_read(arm.UC_ARM_REG_LR))

            machine.hook_add(UC_HOOK_CODE, abi)
            machine.emu_start(0x57a39d, STOP, count=10000)
            expected = record_bytes(initial, timestamp, zone)
            assert machine.reg_read(arm.UC_ARM_REG_PC) == STOP
            assert machine.reg_read(arm.UC_ARM_REG_SP) == WORK + 0xf000
            assert machine.reg_read(arm.UC_ARM_REG_R0) == store_status
            assert stores == [expected.hex()]
            assert bytes(machine.mem_read(RECORD, 12)) == expected
            samples.append(dict(zone=zone, store_status=store_status, record=expected.hex(),
                                returned=store_status, crc_executed_in_original_arm=True))
    return samples


def verify(simulator):
    files = {}

    def pin(path):
        files[str(path.relative_to(simulator))] = hashlib.sha256(path.read_bytes()).hexdigest()

    def load_capture(path):
        pin(path / 'capture-files.json')
        for name, expected in json.loads((path / 'capture-files.json').read_text())['files'].items():
            child = path / name
            assert child.resolve().is_relative_to(path.resolve())
            assert hashlib.sha256(child.read_bytes()).hexdigest() == expected
        return json.loads((path / 'connection-profile.json').read_text())

    original = simulator / 'runtime-candidate-control-01/stock24'
    raw = (original / 'main.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MAIN_LAYOUT['stock_current'][3]
    # Verify the actual producer and stores, not an address-only attribution.
    assert struct.unpack_from('<I', raw, 0x4fb0b0 - 0x438000)[0] == STATE
    assert struct.unpack_from('<I', raw, 0x57a44c - 0x438000)[0] == RECORD
    for pc, operands in {0x4fad88: 'r1, [r4, #4]', 0x4fad8c: 'r0, [r4]',
                         0x57a3a0: 'r1, [r4, #8]', 0x57a3a2: 'r0, [r4, #4]',
                         0x57a3a6: 'r0, [r4]', 0x57a3b2: 'r0, [r4, #0xa]',
                         0x4fadce: 'r0, [r4, #4]', 0x4fadd2: 'r0, [sp]'}.items():
        assert decode(raw, pc, 4)[0].op_str == operands
    assert decode(raw, 0x57a3ae, 4)[0].operands[0].imm == 0x4d0888
    assert decode(raw, 0x4fad8e, 4)[0].operands[0].imm == 0x57a39c
    cases = []
    predicted = []
    stack_address = None
    initial = None
    for name, source, zone in [('original', original, 16),
                               ('regression', simulator / 'runtime-candidate-regression-native-01/stock24', 0)]:
        observed = simulator / 'runtime-state-lineage-native-01' / name
        profile = load_capture(source)
        observed_profile = load_capture(observed)
        assert profile == observed_profile
        assert (source / 'main.bin').read_bytes() == (observed / 'main.bin').read_bytes()
        if name == 'regression':
            candidate = (source / 'main.bin').read_bytes()
            offset = 0x4fab34 - 0x438000
            assert raw[offset:offset + 2] == bytes.fromhex('2079')
            assert candidate[offset:offset + 2] == bytes.fromhex('0020')
            assert candidate[:offset] == raw[:offset] and candidate[offset + 2:len(raw)] == raw[offset + 2:]
        rows = json.loads((observed / 'exports/lineage.json').read_text())
        log_rows = [json.loads(line.split(' ', 1)[1]) for line in (observed / 'renode.log').read_text().splitlines()
                    if line.startswith('BLACKWALL_RUNTIME_LINEAGE ')]
        assert log_rows == [rows] and len(rows) == 4
        assert [row[0] for row in rows] == POINTS
        assert all(len(row) == 14 and row[5] == profile['service']['tcb'] and row[6] & 511 == 0 for row in rows)
        assert all(row[7:9] == [1700000000, zone] for row in rows)
        assert rows[0][1:3] == [1700000000, zone]
        assert rows[2][1] == zone and rows[2][3] == rows[3][3] == 0x20052be0
        assert rows[3][13] == zone and rows[2][13] == rows[0][13]
        stack_address = rows[2][3]
        pre = (source / 'exports/connected-sram.bin').read_bytes()
        ram = (source / 'exports/connection-sram.bin').read_bytes()
        seed = pre[RECORD - 0x20000000:RECORD - 0x20000000 + 12]
        if initial is None:
            initial = seed
        assert seed == initial
        assert rows[0][9:13] == [struct.unpack_from('<I', seed)[0],
                                  struct.unpack_from('<I', seed, 4)[0], seed[8],
                                  struct.unpack_from('<H', seed, 10)[0]]
        expected = record_bytes(seed, 1700000000, zone)
        assert ram[RECORD - 0x20000000:RECORD - 0x20000000 + 12] == expected
        crc = struct.unpack_from('<H', expected, 10)[0]
        assert all(row[9:13] == [3, 1700000000, zone, crc] for row in rows[1:])
        assert struct.unpack_from('<I', ram, stack_address - 0x20000000)[0] == zone
        for filename in ['sram-full.bin', 'connected-sram.bin', 'connection-sram.bin']:
            assert (source / 'exports' / filename).read_bytes() == (observed / 'exports' / filename).read_bytes()
        assert json.loads((source / 'exports/connection.json').read_text()) == json.loads((observed / 'exports/connection.json').read_text())
        cases.append(dict(case=name, zone=zone, crc=crc, rows=rows,
                          observer_connection_report_json_equal=True, observer_whole_sram_exact=True))
        predicted.append(expected)
    changes = []
    for address, before, after in [(STATE + 4, bytes([16]), bytes([0])),
                                   (RECORD, predicted[0], predicted[1]),
                                   (stack_address, struct.pack('<I', 16), struct.pack('<I', 0))]:
        changes += [dict(address=address + index, before=x, after=y)
                    for index, (x, y) in enumerate(zip(before, after)) if x != y]
    expectation = dict(schema=1, failed_checks=['app_state'],
                       sram_changes=sorted(changes, key=lambda change: change['address']),
                       connection_report_equal=True)
    samples = producer_scenarios(raw, (original / 'exports/connected-sram.bin').read_bytes(), initial, 1700000000)
    return dict(passed=True, cases=cases, expectation=expectation, producer_samples=samples,
                producer_engine='isolated Unicorn M7; original ARM function and CRC',
                producer_logging_and_storage_leaves_stubbed=True,
                persistent_storage_committed=False, native_observed_runs=2,
                observer_neutrality_scope='these fixed report values and full SRAM at three checkpoints only',
                files=files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new evidence output directory')
    report = verify(args.simulator)
    args.output.mkdir(mode=0o700, parents=True)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.output / 'derived-expectation.json').write_text(json.dumps(report['expectation'], indent=2) + '\n')
    print('native producer/CRC/log-stack verified; original ARM producer scenarios8')


if __name__ == '__main__':
    main()
