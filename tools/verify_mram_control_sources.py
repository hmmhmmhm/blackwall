"""Verify the public MRAMEXTCTRL location/reset and HAL usage, without device access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

PINS = {
    'apollo510.h':'b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797',
    'pwrctrl_regs.html':'405d102950db0ef10b9c1f446d2bc7d694835142549a3484d6c089e14f3638c9',
    'am_hal_pwrctrl.c':'84cc1da6a01dd46f29e0465074ad92602c4dd6d7a12f7f4596aef64a9a250586',
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    texts={}
    for name,digest in PINS.items():
        data=(args.sources/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Public source mismatch: '+name)
        texts[name]=data.decode()
    header=texts['apollo510.h'];doc=texts['pwrctrl_regs.html']
    start=doc.index('<h3 id="MRAMEXTCTRL"');end=doc.find('<h3 id=',start+1);block=doc[start:end]
    if '0x400211C8' not in block:raise ValueError('Unexpected register address')
    word=0;fields={}
    for name,reset in re.findall(r'colspan="\d+">([A-Z0-9_]+)\s*<br>(0x[0-9a-fA-F]+)',block):
        if name=='RSVD':
            if int(reset,16):raise ValueError('Nonzero reserved reset bits')
            continue
        prefix='PWRCTRL_MRAMEXTCTRL_'+name
        shift=int(re.search(r'#define '+prefix+r'_Pos\s+\((\d+)UL\)',header).group(1))
        mask=int(re.search(r'#define '+prefix+r'_Msk\s+\((0x[0-9a-fA-F]+)UL\)',header).group(1),16)
        value=int(reset,16)<<shift
        if value&~mask:raise ValueError('Reset bits exceed mask')
        word|=value;fields[name]=dict(reset=int(reset,16),position=shift,mask=hex(mask))
    if word!=2 or len(fields)!=4:raise ValueError('Unexpected reset derivation')
    hal=texts['am_hal_pwrctrl.c'];assignment=hal.index('PWRCTRL->MRAMEXTCTRL_b.MRAMAUTOWAKEUPCTRL = 0x3;')
    condition=hal.rfind('    if (APOLLO5_GE_B1)',0,assignment)
    if condition<0 or hal.find('\n    }',condition)<assignment:raise ValueError('Unexpected HAL condition')
    struct_end=header.index('} PWRCTRL_Type;');struct_start=header.rfind('typedef struct {',0,struct_end)
    output=args.output.resolve();output.mkdir(mode=0o700)
    source=output/'layout.c';source.write_text('#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+header[struct_start:struct_end]+'} PWRCTRL_Type;\n_Static_assert(offsetof(PWRCTRL_Type,MRAMEXTCTRL)==0x1c8,"MRAMEXTCTRL offset");\n')
    command=['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(source),'-o',str(output/'layout.o')]
    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    (output/'compiler.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError('Register layout compilation failed')
    report=dict(scope='pinned public source derivation only',upstream_commit='61b293a49db34030c545f99101f7ebf6a3050314',
        source_sha256=PINS,address='0x400211c8',offset='0x1c8',reset_word=word,fields=fields,
        hal_condition='APOLLO5_GE_B1',hal_written_field_value=3,compiler_command=command,hardware_validated=False)
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Verified MRAMEXTCTRL offset 0x1c8, public reset 2, HAL field value 3 under APOLLO5_GE_B1')


if __name__=='__main__':main()
