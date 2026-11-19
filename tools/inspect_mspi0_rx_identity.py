"""Inspect original RX9f/diagnostic consumption and draw original packed pixel buffers."""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_mspi0_dma_profiles import inspect as verify_capture
from inspect_nema_blocking_wait import cpu, WORK, STOP
from inspect_application_vendor_address import call
from inspect_keydb_record_load import run
from prepare_vendor_startup_candidate import sha


class Receive:
    def __init__(self, data, entries=1, complete=True):
        self.data, self.entries, self.complete = data, entries, complete
        self.started = False
        self.events, self.unknown = [], []

    def read(self, u, offset, size, user):
        if size == 4 and self.started and offset in (0, 0x1c, 0x14):
            value = {0: 0x40440 | (2 if self.complete else 0),
                     0x1c: self.entries, 0x14: int.from_bytes(self.data, 'little')}[offset]
            self.events.append(dict(operation='read', offset=offset, value=value))
            return value
        self.unknown.append(dict(operation='read', offset=offset, size=size))
        u.emu_stop()
        return 0xffffffff

    def write(self, u, offset, size, value, user):
        if size == 4 and ((offset == 0 and value == 0x40441 and not self.started)
                          or (offset == 0x208 and value == 0xffffffff)
                          or (offset == 0x200 and value == 0x1a80)):
            if offset == 0:
                self.started = True
            self.events.append(dict(operation='write', offset=offset, value=value))
            return
        self.unknown.append(dict(operation='write', offset=offset, size=size, value=value))
        u.emu_stop()


def png(path, packed):
    # Decode the tested CPU memory layout; no firmware drawing is reimplemented here.
    pixels = bytes(value for byte in packed[:153600] for value in ((byte >> 4) * 17, (byte & 15) * 17))
    rows = b''.join(b'\0' + pixels[y * 640:(y + 1) * 640] for y in range(480))
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 640, 480, 8, 0, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def inspect(s, case, output):
    capture = verify_capture(s, case, 'active')
    f = s / 'mspi0-dma-main-04' / case
    v = json.loads((f / 'report.json').read_text())
    raw, ram = (f / 'main.bin').read_bytes(), (f / 'exports/sram-full.bin').read_bytes()
    regs, pc = v['observed']['register_context'], v['observed']['pc']
    sp = regs['r13']
    def word(address):
        return struct.unpack_from('<I', ram, address - 0x20000000)[0] if address >= 0x20000000 else struct.unpack_from('<I', raw, address - 0x438000)[0]
    parent = word(sp + 28) & ~1
    read_return = word(sp + 0x84) & ~1
    outer_return = word(sp + 0xd4) & ~1
    id_entry = decode(raw, outer_return - 4, 4)[0]
    null_setup = decode(raw, outer_return - 6, 2)[0]
    if id_entry.mnemonic != 'bl' or (null_setup.mnemonic, null_setup.op_str) != ('movs', 'r0, #0'):
        raise ValueError('Different native diagnostic ID caller')
    id_entry = id_entry.operands[0].imm
    if read_return != id_entry + 0x1c or word(regs['r1'] + 20) != sp + 0x94:
        raise ValueError('Different original receive caller/frame chain')
    wait = decode(raw, pc + 0x52, 4)[0]
    delay_call = decode(raw, wait.operands[0].imm + 0x1a, 4)[0]
    if wait.mnemonic != 'bl' or delay_call.mnemonic != 'bl':
        raise ValueError('Different original poll/delay calls')
    delay = delay_call.operands[0].imm
    rx_samples = []
    payloads = [bytes(4), b'\xff' * 4, bytes.fromhex('12345678'), bytes.fromhex('ff000000'),
                bytes.fromhex('000000ff'), bytes.fromhex('007fff00')]
    for name, data, entries, complete, timeout in [(data.hex(), data, 1, True, 1000000) for data in payloads] + [
            ('completion-timeout', payloads[2], 1, False, 0),
            ('fifo-timeout', payloads[2], 0, True, 0),
            ('fifo-native-pending', payloads[2], 0, True, 1000000)]:
        fixture = bytearray(ram)
        if timeout == 0:
            struct.pack_into('<I', fixture, regs['r12'] - 0x20000000 + 0x10, 0)
        u = cpu(raw, bytes(fixture), sp)
        for n in range(15):
            u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), regs['r' + str(n)])
        u.reg_write(arm.UC_ARM_REG_R8, timeout)
        bank = Receive(data, entries, complete)
        u.mmio_map(0x40060000, 0x1000, bank.read, None, bank.write, None)
        t = run(u, pc, [parent, delay])
        pending = name == 'fifo-native-pending'
        result = u.reg_read(arm.UC_ARM_REG_R0)
        expected_result = 0 if complete and entries else 4
        if bank.unknown or t['stop'] != (delay if pending else parent) or (not pending and result != expected_result):
            raise ValueError('Original receive escaped expected poll/return')
        buffer = sp + 0x94
        after = bytes(u.mem_read(buffer, 4))
        if after != (data if entries else ram[buffer - 0x20000000:buffer - 0x20000000 + 4]):
            raise ValueError('Original receive byte order/timeout buffer differs')
        if not pending and bank.events[-2:] != [dict(operation='write', offset=0x208, value=0xffffffff),
                                                dict(operation='write', offset=0x200, value=0x1a80)]:
            raise ValueError('Original IRQ cleanup differs')
        rx_samples.append(dict(name=name, input_bytes=data.hex(), entries_fixture=entries, complete_fixture=complete,
                               timeout_fixture=timeout, native_delay_boundary=pending, result=result, execution=t, events=bank.events))

    decode_samples = []
    for first in (0, 1, 127, 255):
        for second in (0, 1, 127, 255):
            for target in (0, WORK + 0x100):
                u = cpu(raw, ram, sp + 0x88)
                u.mem_write(sp + 0x94, bytes([0xa5, first, second, 0x5a]))
                u.mem_write(WORK + 0xf8, b'\xcc' * 20)
                u.reg_write(arm.UC_ARM_REG_R4, target)
                t = run(u, read_return + 0xca, [outer_return])
                if t['stop'] != outer_return or u.reg_read(arm.UC_ARM_REG_R0) != 0:
                    raise ValueError('Diagnostic decoder rejected a response value')
                expected = bytearray(b'\xcc' * 20)
                if target:
                    expected[8:10] = struct.pack('<H', (first << 8) | second)
                if bytes(u.mem_read(WORK + 0xf8, 20)) != expected:
                    raise ValueError('Diagnostic decoder output/order/neighbors differ')
                decode_samples.append(dict(first=first, second=second, output_pointer_selected=bool(target), execution=t))
    branch_samples = []
    for status in (0, 1, 4, 0xffffffff):
        u = cpu(raw, ram, sp + 0x88)
        u.reg_write(arm.UC_ARM_REG_R0, status)
        t = run(u, read_return, [read_return + 6, read_return + 0x6c])
        if t['stop'] != read_return + (0x6c if status == 0 else 6):
            raise ValueError('Diagnostic transport status branch differs')
        branch_samples.append(dict(status=status, execution=t))

    # Actual init caller links reset commands -> clear callback -> DMA submission.
    init_call = decode(raw, outer_return - 10, 4)[0]
    clear_call = decode(raw, init_call.operands[0].imm + 0x62, 4)[0]
    if init_call.mnemonic != 'bl' or clear_call.mnemonic != 'bl':
        raise ValueError('Different original initialization clear call')
    clear = clear_call.operands[0].imm
    callback_global = literal(raw, decode(raw, clear + 2, 4)[0])
    fill = word(callback_global) & ~1
    pixel_global = literal(raw, decode(raw, fill + 0xa6, 4)[0])
    pixel = word(pixel_global)
    submit_call = decode(raw, clear + 0x32, 4)[0]
    submit = submit_call.operands[0].imm
    template = literal(raw, decode(raw, submit + 0x24, 4)[0])
    transfer_count = word(template + 12)
    dma_source = word(literal(raw, decode(raw, submit + 0x2e, 4)[0]))
    stride = decode(raw, fill + 0xac, 4)[0]
    if submit_call.mnemonic != 'bl' or (stride.mnemonic, stride.op_str) != ('mov.w', 'ip, #0x140') or pixel != dma_source or pixel != 0x20094400 or transfer_count != 153602:
        raise ValueError('Different source pixel/DMA buffer binding')

    fill_samples = []
    def fill_original(data, color, left, top, right, bottom):
        u = cpu(raw, data, WORK + 0xf000)
        u.mem_write(WORK + 0xf000, struct.pack('<I', bottom))
        t = call(u, fill, (color, left, top, right))
        if t['stop'] != STOP or u.reg_read(arm.UC_ARM_REG_R0) != 0:
            raise ValueError('Original clear/fill callback failed')
        after = bytes(u.mem_read(0x20000000, len(data)))
        fill_samples.append(dict(color=color, rectangle=[left, top, right, bottom], execution=t))
        return after

    base = bytearray(ram)
    offset = pixel - 0x20000000
    base[offset - 16:offset + 153618] = b'\xaa' * 153634
    rectangles = [(left, top, right, bottom) for left in (0, 1) for right in (4, 5) for top, bottom in [(0, 0), (7, 10)]]
    rectangles += [(0, 0, 640, 480)]
    for left, top, right, bottom in rectangles:
        result = fill_original(bytes(base), 0, left, top, right, bottom)
        expected = bytearray(base)
        for y in range(top, min(bottom, 479) + 1):
            for x in range(left, min(right, 639) + 1):
                n = offset + y * 320 + x // 2
                expected[n] &= 0x0f if x % 2 == 0 else 0xf0
        if result != bytes(expected):
            raise ValueError('Original pixel nibble/stride/bounds differ')

    # A diagnostic drawing sequence, each rectangle executed by original ARM.
    state = fill_original(bytes(base), 0, 0, 0, 640, 480)
    for level in range(16):
        state = fill_original(state, level * 17, level * 40, 0, level * 40 + 39, 239)
    for y in range(4):
        for x in range(8):
            state = fill_original(state, 0xff if (x + y) % 2 else 0x44, x * 80, 240 + y * 60, x * 80 + 79, 299 + y * 60)
    packed = state[offset:offset + 153602]
    if packed[-2:] != b'\xaa\xaa' or state[:offset] != bytes(base[:offset]) or state[offset + 153602:] != bytes(base[offset + 153602:]):
        raise ValueError('Original drawing changed buffer guards/tail')
    expected_pattern = b''.join(bytes([level * 17]) * 20 for level in range(16)) * 240
    expected_pattern += b''.join(b''.join(bytes([0xff if (x + y) % 2 else 0x44]) * 40 for x in range(8)) * 60 for y in range(4))
    if packed != expected_pattern + b'\xaa\xaa':
        raise ValueError('Original drawing differs from requested diagnostic pattern')
    image = output / ('original-arm-pattern-' + case + '.png')
    png(image, packed)
    (output / ('original-arm-pattern-' + case + '.bin')).write_bytes(packed)
    return dict(case=case, capture=capture, rx_samples=rx_samples, diagnostic_decode_samples=decode_samples,
                transport_status_samples=branch_samples, diagnostic_output_pointer_in_native_call=0,
                response_value_authentication=False, identity_entry=id_entry, clear_callback=fill,
                pixel_pointer_global=pixel_global, pixel_source=pixel, pixel_bytes=153600, dma_bytes=transfer_count,
                untouched_extra_bytes='tail', pixel_memory_layout='640x480, stride320, even x high nibble, odd x low nibble',
                fill_samples=fill_samples, pattern_sha256=sha(output / ('original-arm-pattern-' + case + '.bin')),
                preview_sha256=sha(image), preview=image.name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence')
    a.output.mkdir(mode=0o700)
    rows = [inspect(a.simulator, case, a.output) for case in ('stock24', 'stock23', 'cfw')]
    if len({r['pattern_sha256'] for r in rows}) != 1 or len({r['preview_sha256'] for r in rows}) != 1:
        raise ValueError('Original images produced different diagnostic pixels')
    count = sum(len(r[k]) for r in rows for k in ('rx_samples', 'diagnostic_decode_samples', 'transport_status_samples', 'fill_samples'))
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, original_arm_scenarios=count,
        engine='Unicorn M7: saved RX frame and separate original diagnostic/drawing calls',
        preview_scope='Synthetic test scene drawn by original ARM callback; not native main UI or physical panel output',
        device_identity_verified=False, native_main_rerun=False, hardware_accessed=False,
        boot_verified=False, display_verified=False), indent=2) + '\n')
    print('Verified original RX/diagnostic/pixel buffer, ARM scenarios=' + str(count) + '; original callback previews are standalone tests')


if __name__ == '__main__':
    main()
