"""Execute the pinned recovery worker through UART authentication and RAM-call entry.

Isolated Unicorn fixture: main is corrupt and never executed. Tick, delay, GPIO,
UART readiness and cache registers are modeled. Scheduler/case/ROM are not tested.
The fixture stops BEFORE boot_ram_invoke; it does not perform a firmware write.
"""
from collections import deque
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import struct
import sys
from unittest.mock import patch

import unicorn as u
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_SP

BOOT_SHA = '5ac1b02d337b57e0d25886a06296df2d5932af1f31168c416e64b50c5417a91d'
SESSION = 0x20001000


class RamInvocationBoundary(RuntimeError):
    pass


class RecoveryWorker:
    sha = staticmethod(lambda data: hashlib.sha256(data).hexdigest())

    def __init__(self, candidate):
        self.candidate = Path(candidate).resolve()
        root = self.candidate / 'source'
        boot = (root / 'build/bootloader.bin').read_bytes()
        meta = json.loads((root / 'build/patch.json').read_text())
        code = (root / 'build/patch.bin').read_bytes()
        if (self.sha(boot) != BOOT_SHA or meta['base'] != 0x434910
            or self.sha(code) != meta['sha256'] or len(code) != meta['bytes']
            or boot[meta['base'] - 0x410000:meta['base'] - 0x410000 + len(code)] != code):
            raise ValueError('Unknown recovery candidate')
        self.functions = {name: meta['base'] + data['offset'] for name, data in meta['functions'].items()}
        for name in ('uart2_worker', 'boot_ram_invoke'):
            if not meta['base'] <= self.functions[name] < meta['base'] + len(code):
                raise ValueError('Invalid worker symbol')
        sys.path.insert(0, str(root / 'tools'))
        self.protocol = importlib.import_module('g2patch.protocol')
        self.handshake = importlib.import_module('g2patch.handshake')
        if not Path(self.protocol.__file__).resolve().is_relative_to(root):
            raise ValueError('Recovery protocol imported from another build')
        self.client = self.protocol.Client(self.exchange)
        self.cpu = u.Uc(u.UC_ARCH_ARM, u.UC_MODE_THUMB | u.UC_MODE_MCLASS)
        for address, size in ((0x400000, 0x400000), (0x20000000, 0x80000),
                              (0x4003b000, 0x1000), (0xe000e000, 0x1000)):
            self.cpu.mem_map(address, size)
        self.cpu.mem_write(0x410000, boot)
        self.cpu.mem_write(0x20000498, struct.pack('<I', 0x434220))
        self.cpu.reg_write(UC_ARM_REG_R0, SESSION)
        self.cpu.reg_write(UC_ARM_REG_SP, 0x2007b000)
        self.cpu.reg_write(UC_ARM_REG_LR, 0x20010001)
        self.cpu.reg_write(UC_ARM_REG_PC, self.functions['uart2_worker'] | 1)
        self.incoming = deque()
        self.outgoing = bytearray()
        self.frame = None
        self.boundary = None
        self.main_instructions = self.mram_writes = self.instructions = 0
        self.ram_calls = self.frames = self.ticks = 0
        self.upload_length = 0
        self.uploaded_sha = None
        self.api_version = None
        self.stubs = {'tick': 0, 'delay': 0, 'gpio': 0}
        self.cache_writes = 0
        self.cpu.hook_add(u.UC_HOOK_CODE, self._instruction)
        self.cpu.hook_add(u.UC_HOOK_MEM_READ, self._read)
        self.cpu.hook_add(u.UC_HOOK_MEM_WRITE, self._write)

    def _instruction(self, cpu, pc, size, _):
        self.instructions += 1
        if self.frame is not None:
            cpu.emu_stop()
            return
        if 0x438000 <= pc < 0x800000:
            self.main_instructions += 1
            raise ValueError('Corrupt main must never execute')
        if pc == self.functions['boot_ram_invoke']:
            self.ram_calls += 1
            entry, api, arg0, arg1, _result = struct.unpack('<5I', cpu.mem_read(cpu.reg_read(UC_ARM_REG_R0), 20))
            if not (0x20000000 <= (entry & ~1) < 0x20080000) or not self.upload_length:
                raise ValueError('Invalid resident RAM program')
            self.uploaded_sha = self.sha(cpu.mem_read(entry & ~1, self.upload_length))
            version, send, context, recv = struct.unpack('<4I', cpu.mem_read(api, 16))
            if version != 3 or (send & ~1) != self.functions['send_output'] or (recv & ~1) != self.functions['recv_input']:
                raise ValueError('RAM API does not use the compiled worker callbacks')
            if struct.unpack('<2I', cpu.mem_read(context, 8)) != (0, SESSION):
                raise ValueError('RAM API is not owned by this held session')
            self.api_version = version
            self.boundary = dict(pc=pc, entry=entry, api=api, destination=arg0, length=arg1)
            cpu.emu_stop()
            return
        if pc == 0x4160e8:
            name, result = 'tick', self.ticks
        elif pc == 0x416378:
            self.ticks += cpu.reg_read(UC_ARM_REG_R0)
            name, result = 'delay', 0
        elif pc == 0x41d92c:
            name, result = 'gpio', 0
        else:
            return
        self.stubs[name] += 1
        cpu.reg_write(UC_ARM_REG_R0, result)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    def _read(self, cpu, access, address, size, value, _):
        if address == 0x4003b018:
            cpu.mem_write(address, struct.pack('<I', 0 if self.incoming else 0x10))
        elif address == 0x4003b000:
            if not self.incoming:
                raise ValueError('UART underflow')
            cpu.mem_write(address, struct.pack('<I', self.incoming.popleft()))
        elif 0x40000000 <= address < 0x60000000:
            raise ValueError('Unsupported worker MMIO read')
        elif 0xe000e000 <= address < 0xe000f000:
            raise ValueError('Unsupported worker system register read')

    def _write(self, cpu, access, address, size, value, _):
        if 0x400000 <= address < 0x800000:
            self.mram_writes += 1
            raise ValueError('This fixture must stop before MRAM writing')
        if address == 0x4003b000:
            self.outgoing.append(value & 255)
            data = self.outgoing
            length = None
            if len(data) >= 4 and data[:2] == b'\x5a\xa5':
                length = data[3] + 5
            elif len(data) >= 8 and data[:4] == b'BLK2':
                length = int.from_bytes(data[6:8], 'little') + 12
            if length is not None and len(data) == length:
                self.frame = bytes(data)
                self.outgoing.clear()
                self.frames += 1
        elif 0x40000000 <= address < 0x60000000 and address != 0x4003b004:
            raise ValueError('Unsupported worker MMIO write')
        elif 0xe000e000 <= address < 0xe000f000:
            if size != 4 or address not in (0xe000ef64, 0xe000ef50):
                raise ValueError('Unsupported worker system register write')
            self.cache_writes += 1

    def exchange(self, packet=b''):
        if self.boundary is not None:
            raise RamInvocationBoundary('RAM invocation is already paused')
        if self.incoming:
            raise ValueError('Previous request was not consumed')
        if len(packet) == 32 and packet[8] == self.protocol.LOAD:
            self.upload_length = int.from_bytes(packet[9:11], 'little')
        self.incoming.extend(packet)
        self.frame = None
        self.cpu.emu_start(self.cpu.reg_read(UC_ARM_REG_PC) | 1, 0, count=2_000_000, timeout=5_000_000)
        if self.boundary is not None:
            raise RamInvocationBoundary('Stopped before compiled boot_ram_invoke')
        if self.frame is None:
            raise TimeoutError('No complete UART reply within fixture budget')
        return self.frame

    def claim(self):
        hello = self.exchange()
        challenge = self.handshake.decode_hello(hello)
        # The private key stays in this process; never put raw handshake frames in reports.
        with patch.dict(os.environ, {'G2_BOOT_KEY': (self.candidate / 'recovery.key').read_text().strip()}):
            answer = self.exchange(self.handshake.hold(challenge))
            self.handshake.check_okay(answer, challenge)

    def report(self):
        return dict(scope='isolated compiled worker to RAM-call entry; platform stubs; not scheduler/case/ROM/recovery completion',
                    main_instructions=self.main_instructions, mram_writes=self.mram_writes,
                    held=struct.unpack('<I', self.cpu.mem_read(SESSION, 4))[0],
                    ram_invocations_reached=self.ram_calls, uploaded_code_sha256=self.uploaded_sha,
                    api_version=self.api_version, api_callbacks_from_patch=self.api_version == 3,
                    boundary=self.boundary, uart_frames=self.frames, instructions=self.instructions,
                    modeled_platform_calls=self.stubs, cache_maintenance_stores=self.cache_writes, hardware_accessed=False,
                    ram_payload_executed=False, full_boot_verified=False, recovery_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[1]) or output.exists():
        raise ValueError('Use a new report outside the repository')
    worker = RecoveryWorker(args.candidate)
    worker.claim()
    writer = (worker.candidate / 'source/build/recover.bin').read_bytes()
    if worker.sha(writer) != '9abc30c98bec432981d0c40ded3159085f273700e6c3b54716e37360df8cb8b2':
        raise ValueError('Unknown resident recovery writer')
    worker.client.upload(writer, arg0=0x438010, arg1=512)
    try:
        worker.client.execute(source=lambda n: bytes(n))
    except RamInvocationBoundary:
        pass
    else:
        raise ValueError('Worker did not stop at RAM invocation')
    report = worker.report()
    if report['main_instructions'] or report['mram_writes'] or report['held'] != 1 or report['uploaded_code_sha256'] != worker.sha(writer):
        raise ValueError('Worker ownership contract failed')
    report['passed'] = True
    report['source_sha256'] = {name: worker.sha((worker.candidate / 'source' / name).read_bytes()) for name in (
        'src/bootloader.c', 'src/ram_invoke.h', 'src/examples/recover.c',
        'tools/g2patch/recovery.py', 'tools/g2patch/protocol.py', 'build/patch.json',
        'build/patch.bin', 'build/bootloader.bin', 'build/recover.bin')}
    report['harness_sha256'] = worker.sha(Path(__file__).read_bytes())
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('passed', 'held', 'main_instructions', 'mram_writes', 'ram_invocations_reached', 'ram_payload_executed')}))


if __name__ == '__main__':
    main()
