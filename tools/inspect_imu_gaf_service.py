"""Run original GAF request code with declared I/O ABI responses, never EDMP code."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import cpu, WORK, STOP
from pinned_main import load_pinned_main


def run(raw, ram, entry, leaves, request, seed, pending_polls, error_at):
    machine = cpu(raw, ram, WORK + 0xf000)
    device = WORK + 0x100
    machine.reg_write(arm.UC_ARM_REG_R0, device)
    machine.reg_write(arm.UC_ARM_REG_R1, request)
    registers = {0xa272: seed, 0x2a: seed ^ 0xa5, 0x73: seed ^ 0x5a}
    initial = dict(registers)
    transactions = []
    polls = 0
    calls = [i.operands[0].imm for i in decode(raw, entry, 0x32) if i.mnemonic == 'bl']
    assert len(calls) == 4 and leaves[calls[0]] == 'write-sram'
    sleep_entry = calls[2]
    sleep_arguments = []

    def observe(core, pc, size, user):
        nonlocal polls
        if pc == sleep_entry:
            sleep_arguments.append(core.reg_read(arm.UC_ARM_REG_R1))
        if pc not in leaves:
            return
        kind = leaves[pc]
        dev, address, length, pointer = [core.reg_read(getattr(arm, 'UC_ARM_REG_R' + str(k))) for k in range(4)]
        assert dev == device and length == 1
        if kind == 'read-reg':
            if address == 0xa297:
                polls += 1
                value = 0 if polls <= pending_polls else 2
            else:
                value = registers[address]
            data = bytes([value])
            core.mem_write(pointer, data)
        else:
            data = bytes(core.mem_read(pointer, length))
            if kind == 'write-reg':
                registers[address] = data[0]
            else:
                assert kind == 'write-sram' and address == 4 and data == bytes([request])
        status = 0xfffffffd if error_at == (kind, address) else 0
        transactions.append(dict(kind=kind, address=address, data=data.hex(), status=status))
        core.reg_write(arm.UC_ARM_REG_R0, status)
        core.reg_write(arm.UC_ARM_REG_PC, core.reg_read(arm.UC_ARM_REG_LR))

    machine.hook_add(UC_HOOK_CODE, observe)
    machine.emu_start(entry | 1, STOP, count=200000)
    assert machine.reg_read(arm.UC_ARM_REG_PC) == STOP
    assert machine.reg_read(arm.UC_ARM_REG_SP) == WORK + 0xf000
    returned = machine.reg_read(arm.UC_ARM_REG_R0)
    assert returned == (0xfffffffd if error_at is not None else 0)
    assert registers == {0xa272: initial[0xa272] & ~0x20,
                         0x2a: initial[0x2a] | 0x40, 0x73: initial[0x73] | 0x20}
    assert sleep_arguments[0] == 200
    sleeps = polls if error_at == ('read-reg', 0xa297) and pending_polls > 0 else polls - 1
    assert sleep_arguments == [200] + [5] * sleeps
    assert polls == (1 if error_at == ('read-reg', 0xa297) else pending_polls + 1)
    expected_prefix = [('write-sram', 4), ('read-reg', 0xa272), ('write-reg', 0xa272),
                       ('read-reg', 0x2a), ('write-reg', 0x2a), ('read-reg', 0x73), ('write-reg', 0x73)]
    assert [(x['kind'], x['address']) for x in transactions[:7]] == expected_prefix
    assert all(x['kind'] == 'read-reg' and x['address'] == 0xa297 for x in transactions[7:])
    assert bytes(machine.mem_read(0x20000000, len(ram))) == ram
    return dict(request=request, seed=seed, pending_polls=pending_polls, polls=polls,
                error_at=error_at, returned=returned, sleep_arguments=sleep_arguments,
                transactions=transactions, register_bits_preserved=True, guest_sram_unchanged=True)


def inspect(simulator):
    source_path = simulator / 'imu-parameter-full-setter-01/report.json'
    verification = json.loads((simulator / 'imu-parameter-full-setter-01/verification-report.json').read_text())
    pins = [digest for name, digest in verification['source_files'].items()
            if Path(name).name == 'report.json' and Path(name).parent.name == 'imu-parameter-full-setter-01']
    assert verification['passed'] and pins == [hashlib.sha256(source_path.read_bytes()).hexdigest()]
    source = json.loads(source_path.read_text())
    results = []
    for case, bundle in [('stock24', 'stock-2.4.0.24.bin'), ('stock23', 'stock-2.3.0.24.bin'), ('cfw', 'faceclaw-38-research-only.bin')]:
        folder = simulator / 'imu-clock-variation-main-01' / case
        raw = (folder / 'main.bin').read_bytes()
        _, pinned = load_pinned_main((simulator / 'inputs/verified-01' / bundle).read_bytes())
        assert raw == pinned
        ram = (folder / 'exports/sram-full.bin').read_bytes()
        original = next(x for x in source['cases'] if x['case'] == case)
        assert hashlib.sha256(raw).hexdigest() == original['main_sha256']
        leaves = {int(address): kind for address, kind in original['leaves'].items()}
        entry = 0x55405c if case == 'stock24' else 0x520204
        targets = [i.operands[0].imm for i in decode(raw, original['entry'], 0x710) if i.mnemonic == 'bl']
        assert targets.count(entry) == 2
        runs = []
        for request in [2, 4]:
            for seed in [0, 255, 0x5a, 0xa5, 0x8b, 0x40]:
                for pending in [0, 1, 3]:
                    runs.append(run(raw, ram, entry, leaves, request, seed, pending, None))
            for error in [('write-sram', 4), ('read-reg', 0xa272), ('write-reg', 0x2a), ('read-reg', 0xa297)]:
                runs.append(run(raw, ram, entry, leaves, request, 0xa5, 3, error))
        timeout = original['not_ready_case']
        assert timeout['returned'] == 0xfffffffc and timeout['polls'] == [200000] * 3
        requests = timeout['requests']
        service_writes = [x for x in requests if x['kind'] == 'write-sram' and x['address'] == 4]
        assert [x['data'] for x in service_writes] == ['02', '04']
        assert any(x['kind'] == 'write-sram' and x['address'] == 0xc80 for x in requests)
        results.append(dict(case=case, entry=entry, main_sha256=original['main_sha256'], runs=runs,
                            reused_timeout_polls=timeout['polls'], continues_after_timeout=True))
        print(case, len(runs), 'original helper scenarios; prior timeout evidence reused', flush=True)
    return dict(passed=True, cases=results, original_arm_scenarios=sum(len(x['runs']) for x in results),
                original_source_executed=True, io_abi_stubbed=True, synthetic_registers=True,
                sleep_callback_absent=True, io_errors_still_supply_read_data=True,
                io_writes_recorded_even_on_error=True, physical_timing_verified=False, edmp_algorithm_executed=False,
                native_main=False, hardware_accessed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output')
    result = inspect(args.simulator)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('passed', result['original_arm_scenarios'])
