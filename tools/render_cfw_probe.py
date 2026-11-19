"""Execute pinned g2flash text drawing code in ARM emulation, not a full G2 boot."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import zlib

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

from renderer_scene import compile_scene

COMMIT = '845f665e0dfdcfd06b7d3a294388de6f17a5bd59'
WIDTH, HEIGHT = 576, 288


def png_gray(pixels, width=WIDTH, height=HEIGHT):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    scan = b''.join(b'\0'+pixels[y*width:(y+1)*width] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scan)) + chunk(b'IEND', b''))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('upstream', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--scene', type=Path, help='Bounded JSON frame sequence; host-controlled timeline')
    args = p.parse_args()
    root, out = args.upstream.resolve(), args.output.resolve()
    if out.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Generated firmware and render assets must stay outside Git')
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != COMMIT:
        raise ValueError('Unexpected upstream revision')
    names = ('draw.c', 'draw.h', 'memory.h')
    hashes = {}
    for name in names:
        blob = subprocess.check_output(['git', '-C', str(root), 'show', COMMIT+':patches/'+name])
        if blob != (root/'patches'/name).read_bytes():
            raise ValueError('Modified renderer source')
        hashes[name] = hashlib.sha256(blob).hexdigest()
    scene = json.loads(args.scene.read_text()) if args.scene else None
    compiled_scene = compile_scene(scene) if scene is not None else None
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    source = '''#include <stdint.h>
#include "draw.c"
void render(uint8_t *fb, uint32_t frame) {
 (void)frame;
 for (unsigned x=16; x<560; x++) { set_pixel4(fb,576,x,16,15); set_pixel4(fb,576,x,271,15); }
 for (unsigned y=16; y<272; y++) { set_pixel4(fb,576,16,y,15); set_pixel4(fb,576,559,y,15); }
 draw_string(fb,576,288,32,36,"BLACKWALL",15,-1);
 draw_string(fb,576,288,32,60,"CFW ARM RENDER PROBE",12,-1);
 draw_string(fb,576,288,32,84,"576 x 288 / PACKED 4BPP",9,-1);
 draw_string(fb,576,288,32,120,"ISOLATED RENDERER - NOT FULL DEVICE BOOT",15,-1);
}
'''
    if compiled_scene is not None:
        source = compiled_scene
        (out/'scene.json').write_text(json.dumps(scene, indent=2)+'\n')
    (out/'probe.c').write_text(source)
    env = os.environ.copy()
    env['PATH'] = '/opt/homebrew/opt/llvm@21/bin:/opt/homebrew/opt/lld@21/bin:'+env['PATH']
    commands = [
        ['clang', '--target=arm-none-eabi', '-mcpu=cortex-m4', '-mthumb', '-fno-trigraphs', '-Oz', '-ffreestanding', '-fno-builtin', '-ffunction-sections', '-fdata-sections', '-I'+str(root/'patches'), '-c', 'probe.c', '-o', 'probe.o'],
        ['ld.lld', '-Ttext=0x10000', '--entry=render', '--gc-sections', 'probe.o', '-o', 'probe.elf'],
        ['llvm-objcopy', '-O', 'binary', 'probe.elf', 'probe.bin'],
    ]
    with (out/'build.log').open('w') as log:
        for cmd in commands:
            subprocess.run(cmd, cwd=out, env=env, check=True, stdout=log, stderr=subprocess.STDOUT)
    symbols = subprocess.check_output(['llvm-nm', '--defined-only', 'probe.elf'], cwd=out, env=env, text=True)
    entry = int(next(line.split()[0] for line in symbols.splitlines() if line.split()[-1] == 'render'), 16)
    code = (out/'probe.bin').read_bytes()
    # Independent compiler/CPU target: same pinned renderer must produce identical pixels.
    with (out/'host-build.log').open('w') as log:
        subprocess.run(['/usr/bin/clang', '-dynamiclib', '-fno-trigraphs', '-O2', '-I'+str(root/'patches'),
                        'probe.c', '-o', 'probe-host.dylib'], cwd=out, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    library = ctypes.CDLL(str(out/'probe-host.dylib'))
    library.render.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    library.render.restype = None
    frame_reports = []
    for frame_index in range(len(scene['frames']) if scene else 1):
        stem = 'frame' if frame_index == 0 else f'frame-{frame_index:03d}'
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        cpu.mem_map(0x10000, (len(code)+4095)&~4095)
        cpu.mem_write(0x10000, code)
        cpu.mem_protect(0x10000, (len(code)+4095)&~4095, UC_PROT_READ | UC_PROT_EXEC)
        cpu.mem_map(0x20000000, 0x40000)
        cpu.mem_map(0x100000, 0x1000)
        count = WIDTH*HEIGHT//2
        fb = 0x20001000
        cpu.mem_write(fb-32, b'\xa5'*32)
        cpu.mem_write(fb+count, b'\xa5'*32)
        cpu.reg_write(UC_ARM_REG_R0, fb)
        cpu.reg_write(UC_ARM_REG_R1, frame_index)
        cpu.reg_write(UC_ARM_REG_SP, 0x2003f000)
        cpu.reg_write(UC_ARM_REG_LR, 0x100001)
        cpu.emu_start(entry | 1, 0x100000, count=3000000, timeout=5000000)
        if cpu.reg_read(UC_ARM_REG_PC) != 0x100000 or cpu.reg_read(UC_ARM_REG_SP) != 0x2003f000:
            raise ValueError('Renderer did not return correctly')
        if bytes(cpu.mem_read(fb-32, 32)) != b'\xa5'*32 or bytes(cpu.mem_read(fb+count, 32)) != b'\xa5'*32:
            raise ValueError('Framebuffer guard corrupted')
        packed = bytes(cpu.mem_read(fb, count))
        host_buffer = ctypes.create_string_buffer(b'\xa5'*32 + bytes(count) + b'\xa5'*32)
        library.render(ctypes.addressof(host_buffer)+32, frame_index)
        if host_buffer.raw[32:32+count] != packed:
            raise ValueError('ARM and native renderer framebuffer differ')
        if host_buffer.raw[:32] != b'\xa5'*32 or host_buffer.raw[32+count:64+count] != b'\xa5'*32:
            raise ValueError('Native framebuffer guard corrupted')
        pixels = bytes(v*17 for byte in packed for v in (byte>>4, byte&15))
        (out/(stem+'.4bpp')).write_bytes(packed)
        (out/(stem+'.png')).write_bytes(png_gray(pixels))
        frame_reports.append({'index': frame_index, 'image': stem+'.png', 'sha256': hashlib.sha256(packed).hexdigest()})
    report = {'scope': 'isolated-source-derived-cfw-renderer', 'upstream_commit': COMMIT,
              'source_sha256': hashes, 'probe_sha256': hashlib.sha256(code).hexdigest(),
              'frame_sha256': frame_reports[0]['sha256'], 'frames': frame_reports,
              'timeline': 'host-defined frame sequence, not firmware timing', 'width': WIDTH, 'height': HEIGHT,
              'framebuffer_guards': 'preserved', 'hardware_accessed': False,
              'native_framebuffer_byte_identical': True,
              'full_g2_boot': False, 'stock_display_driver_executed': False,
              'scene_origin': 'Blackwall test wrapper; drawing functions from pinned g2flash',
              'font_origin': 'upstream draw.c Terminus 6x12 font; upstream/font licenses apply'}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'frame': str(out/'frame.png'), 'scope': report['scope']}))


if __name__ == '__main__':
    main()
