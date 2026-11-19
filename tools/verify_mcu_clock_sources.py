"""Audit pinned public clock/performance definitions; no firmware or device access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

PINS = {
    'apollo510.h': 'b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797',
    'am_hal_pwrctrl.c': '84cc1da6a01dd46f29e0465074ad92602c4dd6d7a12f7f4596aef64a9a250586',
}
FIELDS = {'CLKGEN_MISC_FRCHFRC2': (5, 0x20),
          'CLKGEN_CLOCKENSTAT_HFRC2CLKEN': (31, 0x80000000),
          'CLKGEN_CLOCKENSTAT_HFRC2READY': (24, 0x1000000),
          'PWRCTRL_MCUPERFREQ_MCUPERFREQ': (0, 3),
          'PWRCTRL_MCUPERFREQ_MCUPERFACK': (2, 4),
          'PWRCTRL_MCUPERFREQ_MCUPERFSTATUS': (3, 0x18)}
LAYOUT = {'CLKGEN': {'MISC': 0x44, 'CLOCKENSTAT': 0x30, 'CLKCTRL': 0x120},
          'PWRCTRL': {'MCUPERFREQ': 0, 'GFXPWRSWSEL': 0x90}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--with-hfrc-force-control', action='store_true')
    args = parser.parse_args()
    pins=dict(PINS);fields=dict(FIELDS)
    if args.with_hfrc_force_control:
        pins['am_hal_clkgen.c']='fd1d50990a9a62e699c9bed05ec2983f2c766e62c5a9eb9e08387e2bcc39bddf'
        fields.update(CLKGEN_MISC_FRCHFRC=(0,1),CLKGEN_CLOCKENSTAT_HFRCCLKEN=(30,0x40000000))
    texts = {}
    for name, digest in pins.items():
        data = (args.sources/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Pinned public source changed: '+name)
        texts[name] = data.decode()
    header = texts['apollo510.h']
    for name, (shift, mask) in fields.items():
        for suffix, expected in (('Pos', shift), ('Msk', mask)):
            match = re.search(r'#define '+name+'_'+suffix+r'\s+\((0x[0-9a-fA-F]+|\d+)UL\)', header)
            if not match or int(match[1], 0) != expected:
                raise ValueError('Field definition differs: '+name+'_'+suffix)
    hal = texts['am_hal_pwrctrl.c']
    begin = hal.index('mcu_hp_lp_switch_sequence(am_hal_pwrctrl_mcu_mode_e ePowerMode)')
    end = hal.index('} // mcu_hp_lp_switch_sequence()', begin)
    body = hal[begin:end]
    for required in ('CLKGEN->MISC_b.FRCHFRC2 = CLKGEN_MISC_FRCHFRC2_FRC;',
                     'CLKGEN->CLOCKENSTAT_b.HFRC2READY',
                     'PWRCTRL->MCUPERFREQ_b.MCUPERFREQ = ePowerMode;',
                     'PWRCTRL->MCUPERFREQ_b.MCUPERFACK > 0',
                     'CLKGEN->MISC_b.FRCHFRC2 = CLKGEN_MISC_FRCHFRC2_NOFRC;'):
        if required not in body:
            raise ValueError('Expected HAL operation absent: '+required)
    if args.with_hfrc_force_control:
        clk=texts['am_hal_clkgen.c']
        begin=clk.index('am_hal_clkgen_private_hfrc_force_on(bool bForceOn)')
        end=clk.index('return AM_HAL_STATUS_SUCCESS;',begin)
        if 'CLKGEN->MISC_b.FRCHFRC = bForceOn ? CLKGEN_MISC_FRCHFRC_FRC: CLKGEN_MISC_FRCHFRC_NOFRC;' not in clk[begin:end]:
            raise ValueError('Expected private HFRC control operation absent')
    source = '#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'
    for prefix, registers in LAYOUT.items():
        end = header.index('} '+prefix+'_Type;')
        begin = header.rfind('typedef struct {', 0, end)
        source += header[begin:end]+'} '+prefix+'_Type;\n'
        for name, offset in registers.items():
            source += f'_Static_assert(offsetof({prefix}_Type,{name})=={offset},"{prefix}.{name}");\n'
    args.output.mkdir(mode=0o700)
    (args.output/'layout.c').write_text(source)
    command = ['/opt/homebrew/opt/llvm@21/bin/clang', '--target=arm-none-eabi', '-mcpu=cortex-m55',
               '-mthumb', '-std=c11', '-c', str(args.output/'layout.c'), '-o', str(args.output/'layout.o')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    (args.output/'compiler.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise ValueError('Public register layout assertions failed')
    report = dict(scope='pinned public field/layout assertions and HAL operation presence; not hardware behavior',
                  upstream_commit='61b293a49db34030c545f99101f7ebf6a3050314', source_sha256=pins,
                  fields=fields, layout=LAYOUT, hfrc_force_control=args.with_hfrc_force_control, compiler_command=command,
                  hardware_validated=False, boot_verified=False)
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Verified public clock fields and compiled CLKGEN/PWRCTRL offsets')


if __name__ == '__main__':
    main()
