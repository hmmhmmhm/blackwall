"""Bound original zero-data MSPI0 command, completion poll, IRQ restore and pending wait."""
import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_application_vendor_address import call
from inspect_cpu_sleep_profiles import inspect as verify_capture
from inspect_keydb_record_load import run
from inspect_mspi1_config_contract import collect
from inspect_nema_blocking_wait import cpu, WORK
from prepare_vendor_startup_candidate import sha


class Registers:
    def __init__(self, status, pending=0):
        self.status = status
        self.irq_status = pending
        self.irq_enable = 0
        self.started = False
        self.events = []
        self.unknown = []

    def read(self, u, offset, size, user):
        if size == 4 and offset == 0 and self.started:
            value = 0xc0 | self.status
            if self.status & 2:
                self.irq_status |= 1
        elif size == 4 and offset == 0x200:
            value = self.irq_enable
        else:
            self.unknown.append(dict(operation='read', offset=offset, size=size))
            u.emu_stop()
            return 0xffffffff
        self.events.append(dict(operation='read', offset=offset, value=value))
        return value

    def write(self, u, offset, size, value, user):
        if size == 4 and offset == 0x208 and value == 0xffffffff:
            self.irq_status &= ~0x3fff
        elif size == 4 and offset == 0 and value == 0xc1 and not self.started:
            self.started = True
        elif size == 4 and offset == 0x200 and value & ~0x3fff == 0:
            self.irq_enable = value
        else:
            self.unknown.append(dict(operation='write', offset=offset, size=size, value=value))
            u.emu_stop()
            return
        self.events.append(dict(operation='write', offset=offset, value=value))

    def attach(self, u):
        u.mmio_map(0x40060000, 0x1000, self.read, None, self.write, None)


class Fifo:
    def __init__(self, entries):
        self.entries = entries if isinstance(entries, tuple) else (entries,)
        self.read_index = 0
        self.events = []
        self.unknown = []

    def read(self, u, offset, size, user):
        if offset != 0x18 or size != 4:
            self.unknown.append(dict(operation='read', offset=offset, size=size))
            u.emu_stop()
            return 0xffffffff
        value = self.entries[min(self.read_index, len(self.entries) - 1)]
        self.read_index += 1
        self.events.append(dict(operation='read', offset=offset, value=value))
        return value

    def write(self, u, offset, size, value, user):
        if offset != 0x10 or size != 4:
            self.unknown.append(dict(operation='write', offset=offset, size=size))
            u.emu_stop()
            return
        self.events.append(dict(operation='write', offset=offset, value=value))

    def attach(self, u):
        u.mmio_map(0x40060000, 0x1000, self.read, None, self.write, None)


def inspect(s, case):
    capture = verify_capture(s, case)
    f = s / 'cpu-sleep-main-02' / case
    v = json.loads((f / 'report.json').read_text())
    regs = v['observed']['register_context']
    raw = (f / 'main.bin').read_bytes()
    ram = (f / 'exports/sram-full.bin').read_bytes()
    pc = v['observed']['pc']
    sp = regs['r13']
    transaction = regs['r1']
    fields = ram[transaction - 0x20000000:transaction - 0x20000000 + 24]
    count, address, buffer = struct.unpack_from('<I', fields)[0], struct.unpack_from('<I', fields, 8)[0], struct.unpack_from('<I', fields, 20)[0]
    instruction = struct.unpack_from('<H', fields, 14)[0]
    if count != 0 or fields[4:8] != b'\0\0\1\0' or address != 0 or fields[12:14] != b'\1\0' or instruction != 0x66 or fields[16:20] != bytes(4):
        raise ValueError('Different first native command transaction')
    if (regs['r0'], regs['r4'], regs['r6'], regs['r8'], regs['r14']) != (0, 0, 0x1a80, 1000000, 0xc1):
        raise ValueError('Different original blocking-control frame')
    frame = struct.unpack_from('<8I', ram, sp - 0x20000000)
    parent = frame[7] & ~1
    entry_call = decode(raw, parent - 4, 4)[0]
    entry = entry_call.operands[0].imm
    if entry_call.mnemonic != 'bl' or entry != pc - 0xfa:
        raise ValueError('Different original blocking entry')
    wait = decode(raw, pc + 0x5a, 4)[0]
    if wait.mnemonic != 'bl':
        raise ValueError('Different completion polling call')
    delay_call = decode(raw, wait.operands[0].imm + 0x1a, 4)[0]
    if delay_call.mnemonic != 'bl':
        raise ValueError('Different original one-us delay call')
    delay = delay_call.operands[0].imm
    wrapper_return = struct.unpack_from('<I', ram, sp - 0x20000000 + 0x5c)[0] & ~1
    wrapper_call = decode(raw, wrapper_return - 4, 4)[0]
    init_return = struct.unpack_from('<I', ram, sp - 0x20000000 + 0x8c)[0] & ~1
    api_call = decode(raw, init_return - 4, 4)[0]
    if wrapper_call.mnemonic != 'bl' or api_call.mnemonic != 'bl':
        raise ValueError('Different outer command caller chain')
    api = api_call.operands[0].imm
    for entry_address, expected_frame in [(api, 48), (wrapper_call.operands[0].imm, 64)]:
        prologue = decode(raw, entry_address, 8)[:2]
        if prologue[0].mnemonic not in ('push', 'push.w') or prologue[1].mnemonic != 'sub' or prologue[1].operands[0].reg != arm.UC_ARM_REG_SP:
            raise ValueError('Different original outer frame prologue')
        if len(prologue[0].operands) * 4 + prologue[1].operands[-1].imm != expected_frame:
            raise ValueError('Different original outer frame size')
    upcoming = []
    for offset, opcode, data_count in [(-4, 0x66, 0), (0xc, 0x99, 0), (0x1c, 6, 0), (0x38, 1, 1)]:
        callsite = init_return + offset
        i = decode(raw, callsite, 4)[0]
        setup = decode(raw, callsite - 2, 2)[0]
        if i.mnemonic != 'bl' or i.operands[0].imm != api or (setup.mnemonic, setup.op_str) != ('movs', 'r0, #' + (str(opcode) if opcode < 10 else hex(opcode))):
            raise ValueError('Different static initialization command sequence')
        size = decode(raw, callsite - 6, 2)[0]
        if (size.mnemonic, size.op_str) != ('movs', 'r2, #' + str(data_count)):
            raise ValueError('Different static command byte count')
        upcoming.append(dict(callsite=callsite, instruction=opcode, num_data_bytes=data_count))
    payload = decode(raw, init_return + 0x2c, 6)
    if [(i.mnemonic, i.op_str) for i in payload] != [('movs', 'r0, #0x10'), ('strb.w', 'r0, [sp, #0x14]')]:
        raise ValueError('Different static first data byte')
    upcoming[-1]['first_data_byte'] = 0x10

    def execute(status, timeout, pending=0, restore_mask=0x1a80, dead_buffer=False, pending_boundary=False):
        data = bytearray(ram)
        if dead_buffer:
            struct.pack_into('<I', data, transaction - 0x20000000 + 20, 0xdead0000)
        u = cpu(raw, bytes(data), sp)
        for n in range(15):
            u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), regs['r' + str(n)])
        u.reg_write(arm.UC_ARM_REG_R8, timeout)
        u.reg_write(arm.UC_ARM_REG_R6, restore_mask)
        bank = Registers(status, pending)
        bank.attach(u)
        trace = run(u, pc, [parent, delay])
        if bank.unknown:
            raise ValueError('Original command escaped bounded register contract: ' + repr(bank.unknown))
        if pending_boundary:
            if trace['stop'] != delay or u.reg_read(arm.UC_ARM_REG_R0) != 1 or bank.irq_enable != 0:
                raise ValueError('Pending native timeout did not request original one-us delay')
        else:
            result = 0 if status & 2 else 4
            if trace['stop'] != parent or u.reg_read(arm.UC_ARM_REG_R0) != result or bank.irq_enable != restore_mask or bank.irq_status != 0:
                raise ValueError('Original completion/timeout or IRQ restore differs')
            expected = [('write', 0x208, 0xffffffff), ('write', 0, 0xc1), ('read', 0, 0xc0 | status),
                        ('write', 0x208, 0xffffffff), ('write', 0x200, restore_mask)]
            if [(e['operation'], e['offset'], e['value']) for e in bank.events] != expected:
                raise ValueError('Different zero-data command event sequence')
            if bytes(u.mem_read(buffer, 16)) != ram[buffer - 0x20000000:buffer - 0x20000000 + 16]:
                raise ValueError('Zero-data transaction modified buffer')
        return dict(status_fixture=status, timeout=timeout, initial_irq_status=pending, restored_mask=restore_mask,
                    dead_buffer=dead_buffer, pending_boundary=pending_boundary,
                    execution=trace, result=u.reg_read(arm.UC_ARM_REG_R0), events=bank.events)

    samples = [execute(status, 0) for status in range(8)]
    samples += [execute(status, 1000000) for status in (2, 3, 6, 7)]
    samples += [execute(2, 1000000, pending=pending, restore_mask=mask, dead_buffer=True)
                for pending in (0, 0x3fff) for mask in (0, 0x1a80, 0x3fff)]
    samples += [execute(4, 1000000, pending_boundary=True)]
    tx_call = decode(raw, pc + 0x32, 4)[0]
    if tx_call.mnemonic != 'bl':
        raise ValueError('Different original FIFO helper call')
    fifo_samples = []
    for length in range(9):
        payload = bytes([0x10] + list(range(1, length))) if length else b''
        backing = payload + b'\xa5' * (16 - length)
        for entries in (0, 15, 16) + (((16, 0),) if length == 8 else ()):
            b = Fifo(entries)
            u = cpu(raw, ram, WORK + 0xf000)
            u.mem_write(WORK + 0x1000, backing)
            b.attach(u)
            t = call(u, tx_call.operands[0].imm, (0, WORK + 0x1000, length, 0))
            words = [e['value'] for e in b.events if e['operation'] == 'write']
            expected_words = list(struct.unpack('<' + 'I' * ((length + 3) // 4), backing[:((length + 3) // 4) * 4]))
            result = 4 if length and entries == 16 else 0
            if b.unknown or words != expected_words or u.reg_read(arm.UC_ARM_REG_R0) != result:
                raise ValueError('Original FIFO count/padding/timeout differs')
            if [e['operation'] for e in b.events] != ['write', 'read'] * len(words):
                raise ValueError('Original FIFO did not poll after each word')
            if bytes(u.mem_read(WORK + 0x1000, 16)) != backing:
                raise ValueError('FIFO writer modified input buffer')
            fifo_samples.append(dict(num_bytes=length, entries_fixture=entries, execution=t,
                                     words=words, result=result, events=b.events,
                                     earlier_timeout_masked=entries == (16, 0),
                                     logical_payload_hex=payload.hex()))
    return dict(case=case, capture=capture, entry=entry, parent_return=parent, original_wait=wait.operands[0].imm,
                original_delay_boundary=delay, transaction_pointer=transaction,
                num_data_bytes=count, direction='TX', send_instruction=True, instruction=instruction,
                send_address=False, control=0xc1, fifo_accesses=0, samples=samples,
                static_next_command_calls=upcoming,
                fifo_helper=tx_call.operands[0].imm, fifo_samples=fifo_samples,
                external_command_semantics='unknown; no panel/NOR reset acknowledgement claimed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence')
    s = a.simulator
    _, metadata = collect(s)
    masks = {r['name']: r['mask'] for r in metadata}
    if masks['INTCLR'] != 0x3fff:
        raise ValueError('Different published interrupt mask')
    pins = json.loads((s / 'mspi1-source-research-01/sources.json').read_text())
    if pins['commit'] != '61b293a49db34030c545f99101f7ebf6a3050314':
        raise ValueError('Different SDK version')
    sdk = []
    for name in ['am_hal_mspi.c', 'am_hal_mspi.h']:
        path = s / 'mspi1-source-research-01' / name
        pin = next(x for x in pins['files'] if x['path'].endswith('/' + name))
        if sha(path) != pin['sha256']:
            raise ValueError('Changed SDK ' + name)
        sdk.append(pin)
    rows = [inspect(s, case) for case in ('stock24', 'stock23', 'cfw')]
    header = (s / 'mspi1-source-research-01/am_hal_mspi.h').read_text()
    end = header.index('} am_hal_mspi_pio_transfer_t;') + len('} am_hal_mspi_pio_transfer_t;')
    body = header[header.rfind('typedef struct', 0, end):end]
    direction = re.search(r'typedef enum\s*\{\s*AM_HAL_MSPI_RX = 0,\s*AM_HAL_MSPI_TX = 1\s*\}\s*am_hal_mspi_dir_e;', header)
    if not direction:
        raise ValueError('Different direction enum')
    source = '#include <stdint.h>\n#include <stdbool.h>\n#include <stddef.h>\n' + direction[0] + '\n' + body
    source += '\n_Static_assert(sizeof(am_hal_mspi_pio_transfer_t)==24,"size");\n'
    for name, offset in [('ui32NumBytes', 0), ('eDirection', 6), ('ui32DeviceAddr', 8), ('bSendInstr', 12), ('ui16DeviceInstr', 14), ('pui32Buffer', 20)]:
        source += '_Static_assert(offsetof(am_hal_mspi_pio_transfer_t,' + name + ')==' + str(offset) + ',"' + name + '");\n'
    a.output.mkdir(mode=0o700)
    (a.output / 'layout.c').write_text(source)
    command = ['/opt/homebrew/opt/llvm@21/bin/clang', '--target=arm-none-eabi', '-mcpu=cortex-m55', '-mthumb', '-std=c11', '-fshort-enums', '-c', str(a.output / 'layout.c'), '-o', str(a.output / 'layout.o')]
    compile = subprocess.run(command, capture_output=True, text=True, timeout=30)
    (a.output / 'compiler.log').write_text(compile.stdout + compile.stderr)
    if compile.returncode:
        raise ValueError('SDK short-enum layout does not match raw ARM fields')
    result = dict(passed=True, cases=rows, sdk=sdk, original_arm_scenarios=sum(len(x['samples']) + len(x['fifo_samples']) for x in rows),
                  compiled_abi='ARM32 -fshort-enums matches observed 24-byte field layout; actual upstream build flags not established',
                  engine='Original ARM on Unicorn M7; saved GPR/RAM with explicit status/IRQ fixtures and caller-register/frame variants. Pending native timeout stops before original delay.',
                  actual_bus_completion_verified=False, actual_timing_verified=False,
                  native_rerun=False, model_changed=False, hardware_accessed=False,
                  boot_verified=False, display_verified=False)
    (a.output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    print('Verified original3 zero-data instruction66:', result['original_arm_scenarios'], 'scenarios; IRQ restore/status timeout; real completion unknown')


if __name__ == '__main__':
    main()
