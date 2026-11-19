"""Verify bounded public GPU CONFIG evidence; CONFIGH reset value stays unknown."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

PINS={'header':'b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797',
      'metadata':'baf9354c0e017aca4c36f9c72313e4b4e7b50bb5f07ecf5a71e178597e777deb',
      'sdk':'7ac2f2ad9bda610df64ca02ab4974ca93fada09898f3cbfdb3466ed2a4cf957c'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('header','metadata','sdk','output'):p.add_argument(name,type=Path)
    args=p.parse_args();texts={}
    for name,digest in PINS.items():
        data=getattr(args,name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Public source differs: '+name)
        texts[name]=data.decode()
    html=texts['metadata'];a=html.index('id="LOADCTRL"');tail=html[a:];m=re.search(r'id="[A-Z][A-Z0-9]+" class="panel-title"',tail[10:]);body=tail[:m.start()+10] if m else tail
    if '0xf4030105' not in body:raise ValueError('CONFIG low initial word differs')
    if '0x400901F4' in html.upper().replace('X','x'):raise ValueError('Review newly documented high word')
    header=texts['header'];end=header.index('} GPU_Type;');begin=header.rfind('typedef struct {',0,end)
    source='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+header[begin:end]+'} GPU_Type;\n'
    source+='#include "'+str(args.sdk.resolve())+'"\n_Static_assert(NEMA_CONFIG==0x1f0,"NEMA_CONFIG");\n_Static_assert(offsetof(GPU_Type,LOADCTRL)==NEMA_CONFIG,"CONFIG alias");\n_Static_assert(NEMA_CONFIGH==0x1f4,"CONFIGH");\n_Static_assert(offsetof(GPU_Type,RESERVED12)==NEMA_CONFIGH,"public reserved slot");\n'
    args.output.mkdir(mode=0o700);(args.output/'layout.c').write_text(source)
    cmd=['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(args.output/'layout.c'),'-o',str(args.output/'layout.o')]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(args.output/'compiler.log').write_text(r.stdout+r.stderr)
    if r.returncode:raise ValueError('Layout compile failed')
    report=dict(passed=True,source_sha256=PINS,low_word=hex(0xf4030105),config_low_offset='0x1f0',config_high_offset='0x1f4',config_high_reset_value=None,
                high_hypotheses={'zero':0,'bit9':512},high_hypotheses_are_hardware_evidence=False,
                compiled_offsets_only=True,compiler_command=cmd,hardware_validated=False,implemented_gpu_features=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'low_word':report['low_word'],'high_reset_value':None}))


if __name__=='__main__':main()
