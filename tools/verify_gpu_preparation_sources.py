"""Audit pinned public GPU preparation fields/layout and rail macro ordering."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

PINS = {
    'apollo510.h': 'b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797',
    'am_hal_spotmgr_pcm2_0.c': '85cf17f69d6b8eefe90ad0c1e60468a1e4183841c1cb6d579857902174cc4f4a',
    'am_hal_pwrctrl.h': '54ce1a2242e3d48ca14ad6f49c14e28667975314f7ef06f071f362404afb073f',
}
FIELDS = {'LDOREG1_CORELDOACTIVETRIM': (0, 1023), 'LDOREG2_MEMLDOACTIVETRIM': (0, 63),
    'PWRSW1_SHORTVDDCVDDCLVORVAL': (29, 1<<29), 'PWRSW1_SHORTVDDCVDDCLVOREN': (28, 1<<28),
    'PWRSW1_SHORTVDDFVDDSORVAL': (31, 1<<31), 'PWRSW1_SHORTVDDFVDDSOREN': (30, 1<<30),
    'SIMOBUCK2_VDDCACTLOWTONTRIM': (25, 0x3e000000), 'SIMOBUCK2_VDDCACTHIGHTONTRIM': (11, 0xf800),
    'SIMOBUCK4_VDDCLVACTLOWTONTRIM': (25, 0x3e000000), 'SIMOBUCK4_VDDCLVACTHIGHTONTRIM': (11, 0xf800),
    'SIMOBUCK7_VDDFACTLOWTONTRIM': (8, 0x1f00), 'SIMOBUCK6_VDDFACTHIGHTONTRIM': (17, 0x3e0000)}
LAYOUT = {'LDOREG1': 0x80, 'LDOREG2': 0x88, 'PWRSW1': 0x380,
          'SIMOBUCK2': 0x344, 'SIMOBUCK4': 0x34c, 'SIMOBUCK7': 0x358, 'SIMOBUCK6': 0x354}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('sources', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--with-power-response', action='store_true')
    args = p.parse_args(); texts = {};pins=dict(PINS)
    if args.with_power_response:pins['am_hal_pwrctrl.c']='84cc1da6a01dd46f29e0465074ad92602c4dd6d7a12f7f4596aef64a9a250586'
    for name, digest in pins.items():
        raw = (args.sources/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest: raise ValueError('Pinned source differs: '+name)
        texts[name] = raw.decode()
    header = texts['apollo510.h']
    definitions = {'MCUCTRL_'+k: v for k, v in FIELDS.items()}
    definitions['PWRCTRL_DEVPWREN_PWRENGFX'] = (18, 0x40000)
    if args.with_power_response:definitions['PWRCTRL_DEVPWRSTATUS_PWRSTGFX']=(18,0x40000)
    for field, (shift, mask) in definitions.items():
        for suffix, expected in (('Pos', shift), ('Msk', mask)):
            match = re.search(r'#define '+field+'_'+suffix+r'\s+\((0x[0-9a-fA-F]+|\d+)UL\)', header)
            if not match or int(match[1], 0) != expected: raise ValueError('Field differs: '+field)
    hal = texts['am_hal_spotmgr_pcm2_0.c']
    if not re.search(r'#define CORELDOTRIM_BOOST_CODE_FOR_GPU\s+\(12\)', hal):
        raise ValueError('Unexpected boost constant')
    macro = texts['am_hal_pwrctrl.h']; begin = macro.index('#define vddc_to_vddclv_and_vdds_to_vddf_short(')
    end = macro.index('while (0);', begin)
    writes = re.findall(r'PWRSW1_b\.(\w+)\s*=\s*([01]);', macro[begin:end])
    names = ['SHORTVDDCVDDCLVORVAL','SHORTVDDCVDDCLVOREN','SHORTVDDFVDDSORVAL','SHORTVDDFVDDSOREN']
    if writes != [(n, v) for v in ('1','0') for n in names]: raise ValueError('Rail macro order differs')
    end = header.index('} MCUCTRL_Type;'); begin = header.rfind('typedef struct {', 0, end)
    source = '#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+header[begin:end]+'} MCUCTRL_Type;\n'
    for name, offset in LAYOUT.items():
        source += f'_Static_assert(offsetof(MCUCTRL_Type,{name})=={offset},"{name}");\n'
    if args.with_power_response:
        extra_layout={'PWRCTRL':{'DEVPWREN':4,'DEVPWRSTATUS':8},'GPU':{'INTERRUPTCTRL':0xf8}}
        for prefix,registers in extra_layout.items():
            end=header.index('} '+prefix+'_Type;');begin=header.rfind('typedef struct {',0,end)
            source+=header[begin:end]+'} '+prefix+'_Type;\n'
            for name,offset in registers.items():
                source+=f'_Static_assert(offsetof({prefix}_Type,{name})=={offset},"{prefix}.{name}");\n'
        power=texts['am_hal_pwrctrl.c'];begin=power.index('am_hal_pwrctrl_periph_enable(am_hal_pwrctrl_periph_e ePeripheral)');end=power.index('} // am_hal_pwrctrl_periph_enable()',begin)
        body=power[begin:end]
        for operation in ('AM_REGVAL(pwr_ctrl.ui32PwrEnRegAddr) |=','am_hal_delay_us_status_check(AM_HAL_PWRCTRL_MAX_WAIT_US,','return ui32Status;'):
            if operation not in body:raise ValueError('Expected enable/poll/error operation absent')
    args.output.mkdir(mode=0o700); (args.output/'layout.c').write_text(source)
    cmd = ['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb',
           '-std=c11','-c',str(args.output/'layout.c'),'-o',str(args.output/'layout.o')]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    (args.output/'compiler.log').write_text(result.stdout+result.stderr)
    if result.returncode: raise ValueError('Layout compilation failed')
    (args.output/'report.json').write_text(json.dumps(dict(scope='public source hash, field masks, compiled offsets, boost constant and rail macro ordering only',
        upstream_commit='61b293a49db34030c545f99101f7ebf6a3050314', source_sha256=pins, fields=definitions, power_response=args.with_power_response,
        layout=LAYOUT, macro_writes=writes, compiler_command=cmd, hardware_validated=False,
        saturation_edge_runtime_verified=False, gpu_execution_verified=False),indent=2)+'\n')
    print('Verified public GPU preparation fields/layout and rail macro order')


if __name__ == '__main__':
    main()
