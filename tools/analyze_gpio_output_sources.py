"""Check pinned GPIO output-latch sources and compile public register offsets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

HEADER_SHA='b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797'
METADATA_SHA='94134fb630f47634e6b39cde05bcc20529009e3201350fe88b873b0e4c7a3158'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('header','metadata','output'):parser.add_argument(name,type=Path)
    args=parser.parse_args()
    header=args.header.read_bytes();metadata=args.metadata.read_bytes()
    if hashlib.sha256(header).hexdigest()!=HEADER_SHA or hashlib.sha256(metadata).hexdigest()!=METADATA_SHA:
        raise ValueError('Pinned GPIO source differs')
    text=header.decode();page=metadata.decode();end=text.index('} GPIO_Type;');start=text.rfind('typedef struct {',0,end)
    source='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+text[start:end]+'} GPIO_Type;\n'
    registers=[]
    for kind,base in [('WT',0x420),('WTS',0x43c),('WTC',0x458)]:
        for group in range(7):
            name=kind+str(group);offset=base+group*4
            a=page.index('id="'+name+'"');z=page.find('<h3 id="',a+10);body=page[a:z if z!=-1 else len(page)]
            if hex(0x40010000+offset).lower() not in body.lower():raise ValueError('Register address differs: '+name)
            cells=re.findall(r'<td align="center" colspan="(\d+)">(.*?)</td>',body,re.S)
            if len(cells)!=1 or cells[0][0]!='32' or not re.search(r'<br>0x0\s*$',cells[0][1].strip()):
                raise ValueError('Expected one 32-bit zero field: '+name)
            if not re.search(r'#define GPIO_'+name+'_'+name+r'_Msk\s+\(0xffffffffUL\)',text):raise ValueError('Mask differs: '+name)
            source+=f'_Static_assert(offsetof(GPIO_Type,{name})==0x{offset:x},"{name}");\n'
            registers.append(dict(name=name,group=group,kind=kind,offset=hex(offset),initial_field_diagram='0x0',mask='0xffffffff'))
    supported=[];reserved=[]
    for pin in range(224):
        gpio=re.search(f'GPIO_PINCFG{pin}_FNCSEL{pin}_GPIO'+r'\s*= (\d+),',text)
        if gpio:
            if int(gpio.group(1))!=3:raise ValueError('Review different GPIO encoding: '+str(pin))
            if not re.search(f'GPIO_PINCFG{pin}_OUTCFG{pin}_PUSHPULL'+r'\s*= 1,',text):raise ValueError('Push-pull encoding differs: '+str(pin))
            supported.append(pin)
        else:
            end_enum=text.index(f'}} GPIO_PINCFG{pin}_FNCSEL{pin}_Enum;')
            begin_enum=text.rfind('typedef enum {',0,end_enum)
            entries=re.findall(f'GPIO_PINCFG{pin}_FNCSEL{pin}_([A-Z0-9_]+)'+r'\s*= (\d+),',text[begin_enum:end_enum])
            if len(entries)!=16 or not all(name.startswith('RESERVED') for name,value in entries):raise ValueError('Unknown non-GPIO pin schema: '+str(pin))
            reserved.append(pin)
    args.output.mkdir(mode=0o700,exist_ok=False);(args.output/'layout.c').write_text(source)
    command=['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(args.output/'layout.c'),'-o',str(args.output/'layout.o')]
    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    (args.output/'compiler.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError('Output register layout compile failed')
    report=dict(passed=True,commit='61b293a49db34030c545f99101f7ebf6a3050314',header_sha256=HEADER_SHA,metadata_sha256=METADATA_SHA,compiled_offsets=21,inspected_pin_encodings=224,gpio_pushpull_pins=supported,reserved_only_pins=reserved,registers=registers,scope='public latch fields and config encodings; physical pad and initial G2 state unverified',hardware_validated=False)
    (args.output/'source-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'compiled_offsets':21,'pushpull_pins':len(supported),'reserved_only_pins':len(reserved)}))


if __name__=='__main__':main()
