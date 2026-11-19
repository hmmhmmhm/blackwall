"""Check pinned GPU-selection definitions and HAL sequence, without device access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from verify_mram_control_sources import PINS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    texts = {}
    for name, digest in PINS.items():
        raw = (args.sources/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Pinned source differs: '+name)
        texts[name] = raw.decode()
    header, doc, hal = (texts[k] for k in ('apollo510.h', 'pwrctrl_regs.html', 'am_hal_pwrctrl.c'))
    registers = {'GFXPWRSWSEL': (0x90, 'GFXVDDSEL', 1), 'GFXPERFREQ': (0x8c, 'GFXPERFREQ', 3)}
    for register, (offset, field, mask) in registers.items():
        begin = doc.index('<h3 id="'+register+'"')
        end = doc.find('<h3 id=', begin+1)
        body = doc[begin:end]
        if f'0x{0x40021000+offset:08X}' not in body:
            raise ValueError('Public register address differs')
        if not re.search(r'>'+field+r'\s*<br>0x0<', body):
            raise ValueError('Public reset field differs')
        for suffix, expected in (('Pos', 0), ('Msk', mask)):
            match = re.search(r'#define PWRCTRL_'+register+'_'+field+'_'+suffix+r'\s+\((0x[0-9a-fA-F]+|\d+)UL\)', header)
            if not match or int(match[1], 0) != expected:
                raise ValueError('Public field differs')
    begin = hal.index('am_hal_pwrctrl_gpu_mode_select(am_hal_pwrctrl_gpu_mode_e ePowerMode)')
    end = hal.index('} // am_hal_pwrctrl_gpu_mode_select()', begin)
    body = hal[begin:end]
    order = [body.index(s) for s in ('PWRCTRL->VRSTATUS_b.SIMOBUCKST',
             'am_hal_pwrctrl_periph_enabled(', 'PWRCTRL->GFXPWRSWSEL_b.GFXVDDSEL =',
             'am_hal_delay_us(AM_HAL_PWRCTRL_GPU_VOLTADJ_WAIT);',
             'PWRCTRL->GFXPERFREQ_b.GFXPERFREQ = ePowerMode;')]
    if order != sorted(order):
        raise ValueError('Expected HAL operation order differs')
    end = header.index('} PWRCTRL_Type;'); begin = header.rfind('typedef struct {', 0, end)
    source = '#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+header[begin:end]+'} PWRCTRL_Type;\n'
    for register, (offset, _, _) in registers.items():
        source += f'_Static_assert(offsetof(PWRCTRL_Type,{register})=={offset},"{register}");\n'
    args.output.mkdir(mode=0o700)
    (args.output/'layout.c').write_text(source)
    cmd = ['/opt/homebrew/opt/llvm@21/bin/clang', '--target=arm-none-eabi', '-mcpu=cortex-m55',
           '-mthumb', '-std=c11', '-c', str(args.output/'layout.c'), '-o', str(args.output/'layout.o')]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    (args.output/'compiler.log').write_text(p.stdout+p.stderr)
    if p.returncode: raise ValueError('Register layout assertion failed')
    report = dict(scope='pinned public source/address/reset/mask/layout and textual HAL sequence only',
        upstream_commit='61b293a49db34030c545f99101f7ebf6a3050314', source_sha256=PINS,
        registers=registers, reset_words={'GFXPWRSWSEL': 0, 'GFXPERFREQ': 0},
        modeled_requests=[0, 3], unsupported_requests=[1, 2], compiler_command=cmd,
        hardware_validated=False, gpu_execution_verified=False, boot_verified=False)
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Verified GFX selection/request public reset, fields, offsets and HAL operation order')


if __name__ == '__main__':
    main()
