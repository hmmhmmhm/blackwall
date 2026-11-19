"""Render a saved original-ARM command batch with an explicit reference profile.

Creates derived pixels outside Git. Does not submit GPU work or alter any saved
guest memory. Original CPU bitmap callbacks supply an independent coverage check.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC
import unicorn.arm_const as arm
from nema_pixel_reference import PROFILE, render_white_a4_reference
from pinned_main import load_pinned_main
from prepare_nema_state_captures import validate_region
from render_cfw_probe import png_gray


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cpu_bitmap(raw, sram, font, character):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    u.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
    u.reg_write(arm.UC_ARM_REG_C1_C0_2, 0xf00000)
    u.reg_write(arm.UC_ARM_REG_FPEXC, 0x40000000)
    extent = (len(raw) + 4095) & ~4095
    u.mem_map(0x438000, extent); u.mem_write(0x438000, raw)
    u.mem_protect(0x438000, extent, UC_PROT_READ | UC_PROT_EXEC)
    u.mem_map(0x20000000, 0x80000); u.mem_write(0x20000000, sram)
    u.mem_protect(0x20000000, 0x80000, UC_PROT_READ)
    u.mem_map(0x21000000, 0x10000)
    u.mem_map(0x10000000, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
    callbacks = struct.unpack_from('<2I', sram, font - 0x20000000)
    if not all(0x438000 <= fn < 0x438000 + len(raw) and fn & 1 for fn in callbacks):
        raise ValueError('Invalid original font callbacks')
    descriptor, draw, pixels = 0x21001000, 0x21001800, 0x21002000

    def call(entry, args):
        for n in range(4, 12): u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), 0x12340000 + n)
        for n, value in enumerate(args): u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), value)
        u.reg_write(arm.UC_ARM_REG_SP, 0x2100ff00); u.reg_write(arm.UC_ARM_REG_LR, 0x10000001)
        u.emu_start(entry, 0x10000000, count=100000)
        if (u.reg_read(arm.UC_ARM_REG_PC) != 0x10000000 or u.reg_read(arm.UC_ARM_REG_SP) != 0x2100ff00
                or any(u.reg_read(getattr(arm, 'UC_ARM_REG_R' + str(n))) != 0x12340000 + n for n in range(4, 12))):
            raise ValueError('Original bitmap callback did not preserve return/ABI')
        return u.reg_read(arm.UC_ARM_REG_R0)

    u.mem_write(descriptor, struct.pack('<I', font) + bytes(28))
    if call(callbacks[0], [font, descriptor, character, 0]) != 1:
        raise ValueError('Original descriptor rejected glyph')
    desc = bytes(u.mem_read(descriptor, 32))
    width, height = struct.unpack_from('<HH', desc, 6)
    if not 0 < width <= 64 or not 0 < height <= 32 or desc[20] & 1:
        raise ValueError('Unexpected decoded glyph dimensions/raw flag')
    u.mem_write(draw, bytes(16) + struct.pack('<I', pixels))
    u.mem_write(pixels - 32, b'\xa5' * (width * height + 64))
    before = bytes(u.mem_read(0x21000000, 0x10000))
    if call(callbacks[1], [descriptor, draw, 0, 0]) != draw:
        raise ValueError('Original bitmap did not return caller buffer')
    after = bytes(u.mem_read(0x21000000, 0x10000))
    allowed = [(0x1000, 0x1020), (0x1800, 0x1820), (0x2000, 0x2000 + width * height), (0xfc00, 0xff00)]
    if (any(not any(a <= i < b for a, b in allowed) for i, (x, y) in enumerate(zip(before, after)) if x != y)
            or bytes(u.mem_read(pixels - 32, 32)) != b'\xa5' * 32
            or bytes(u.mem_read(pixels + width * height, 32)) != b'\xa5' * 32
            or bytes(u.mem_read(0x20000000, 0x80000)) != sram):
        raise ValueError('Original bitmap output escaped caller memory')
    return bytes(u.mem_read(pixels, width * height)), dict(width=width, height=height, callbacks=list(callbacks),
                                                         glyph_id=struct.unpack_from('<I', desc, 24)[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--profile', choices=[PROFILE], required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if any((p / '.git').exists() for p in [output, *output.parents]):
        raise ValueError('Private output required')
    output.mkdir(mode=0o700)
    previous_path = args.simulator / 'builtin-font-bitmap-contract-04/report.json'
    previous = json.loads(previous_path.read_text())
    if not previous['passed']: raise ValueError('Previous CPU bitmap contract failed')
    results = {}
    for case, filename in [('stock24', 'stock-2.4.0.24.bin'), ('stock23', 'stock-2.3.0.24.bin'),
                           ('cfw', 'faceclaw-38-research-only.bin')]:
        native = args.simulator / 'nema-state-batch-m55-01' / (case + '-full-letter')
        report = json.loads((native / 'report.json').read_text())
        snapshot = json.loads((native / 'snapshot.json').read_text())
        _, raw = load_pinned_main((args.simulator / 'inputs/verified-01' / filename).read_bytes())
        if not report['passed'] or (native / 'main.bin').read_bytes() != raw:
            raise ValueError('Unverified native batch')
        sram = (native / 'sram.bin').read_bytes()
        if (sha(sram) != report['input_hashes']['sram.bin']
                or sha(sram) != snapshot['image_hashes']['sram.bin']
                or sha((native / 'snapshot.json').read_bytes()) != report['snapshot_sha256']):
            raise ValueError('Native input snapshot or SRAM changed')
        validate_region(args.simulator, case, raw, snapshot, sram)
        work = (native / 'result/final-work.bin').read_bytes()
        if sha(work) != report['final_hashes']['work']:
            raise ValueError('Native final WORK changed')
        words = report['actual']['words']
        if (words != snapshot['batch']['words'] or list(struct.unpack_from('<' + 'I' * len(words), work, 0x4000)) != words
                or list(struct.unpack_from('<2I', work, 0x4000 + len(words) * 4)) != [0x50000, 0]):
            raise ValueError('Native command stream differs')
        surface = snapshot['batch']['surface']
        initial = work[0xa000:0xa000 + surface['extent']]

        def read(address, size):
            if not 0x438000 <= address <= address + size <= 0x438000 + len(raw):
                raise ValueError('Source texture is outside pinned original ROM')
            return raw[address - 0x438000:address - 0x438000 + size]

        frame, geometry = render_white_a4_reference(words, initial, read)
        font = snapshot['registers']['R3']
        character = snapshot['batch']['calls'][3]['stack'][0]
        cpu, bitmap = cpu_bitmap(raw, sram, font, character)
        x0, y0, x1, y1 = geometry['draw']
        crop = bytes(frame[y * geometry['stride'] + x] for y in range(y0, y1) for x in range(x0, x1))
        prior_font = next(f for c in previous['cases'] if c['case'] == case for f in c['fonts'] if int(f['address'], 0) == font)
        prior_glyph = next(g for g in prior_font['glyphs'] if g['character'] == character)
        if crop != cpu or sha(cpu) != prior_glyph['sha256'] or (x1 - x0, y1 - y0) != (bitmap['width'], bitmap['height']):
            raise ValueError('Reference pixels differ from original ARM bitmap output')
        visible = bytes(frame[y * geometry['stride'] + x] for y in range(32) for x in range(64))
        (output / (case + '-reference.bin')).write_bytes(frame)
        image = png_gray(visible, 64, 32)
        (output / (case + '-reference.png')).write_bytes(image)
        results[case] = dict(geometry=geometry, bitmap=bitmap, crop_sha256=sha(crop), frame_sha256=sha(frame),
                             png_sha256=sha(image), original_cpu_bitmap_equal=True,
                             native_report_sha256=sha((native / 'report.json').read_bytes()),
                             raw_sha256=sha(raw), snapshot_sha256=sha((native / 'snapshot.json').read_bytes()))
    result = dict(passed=True, profile=args.profile, cases=results, original_cpu_callbacks=6,
                  prior_cpu_report_sha256=sha(previous_path.read_bytes()),
                  gpu_executed=False, full_main_rendered=False, hardware_validated=False,
                  assumptions=['high nibble first', 'white source maps to luminance 255',
                               'integer nearest sampling', 'half-open rectangle and clip',
                               'white-on-black L8 equals expanded A4 coverage'],
                  sources={name: sha((Path(__file__).parent / name).read_bytes()) for name in
                           ['render_nema_reference.py', 'nema_pixel_reference.py', 'render_cfw_probe.py']})
    (output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=3, original_cpu_callbacks=6, gpu_executed=False)))


if __name__ == '__main__':
    main()
