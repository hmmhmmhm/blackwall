"""Verify pinned firmware GPU identity comparisons at an observed read boundary."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

import capstone
from audit_assets import PINS
from blackwall_package import parse_bundle
from emulate_codec_query import PROFILES

BASE=0x438000
IDENTITY=0x86362000


def analyze(bundle, runtime):
    data=bundle.read_bytes();key=runtime['profile']
    if hashlib.sha256(data).hexdigest()!=PINS[key] or runtime['bundle_sha256']!=PINS[key]:
        raise ValueError('Pinned input differs')
    raw=next(p for p in parse_bundle(data) if p.type_id==0).payload[32:]
    if hashlib.sha256(raw).hexdigest()!=runtime['raw_main_sha256']:
        raise ValueError('Main hash differs')
    observed=runtime['observed'];guards=[g for g in observed['guards'] if g['accesses']]
    if len(guards)!=1 or guards[0]['accesses']!=1 or (guards[0]['address'],guards[0]['width'],guards[0]['operation'])!=(0x400901ec,4,'read') or observed['gpu_ring_configuration']['steps_completed']!=3:
        raise ValueError('Need observed configured GPU identity read')
    helper=observed['pc']-6
    cs=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS);cs.skipdata=True
    matches=[]
    for a,size,mn,op in cs.disasm_lite(raw,BASE):
        if mn!='bl' or op!=f'#{helper:#x}':continue
        before=[(i.mnemonic,i.op_str) for i in cs.disasm(raw[a-BASE-4:a-BASE],a-4)]
        if before!=[('mov.w','r0, #0x1ec')]:continue
        after=list(cs.disasm(raw[a-BASE+size:a-BASE+size+24],a+size))
        if len(after)<3 or after[1].mnemonic!='cmp' or after[1].op_str!='r0, r1' or after[2].mnemonic!='beq':continue
        load=after[0];match=re.fullmatch(r'r1, \[pc, #(0x[0-9a-f]+)\]',load.op_str)
        if load.mnemonic!='ldr.w' or not match:continue
        literal=((load.address+4)&~3)+int(match[1],16)
        if not BASE<=literal<=BASE+len(raw)-4:raise ValueError('Literal outside main')
        value=struct.unpack_from('<I',raw,literal-BASE)[0]
        if value!=IDENTITY:raise ValueError('Firmware identity expectation differs')
        matches.append(dict(call=hex(a),literal_address=hex(literal),expected_identity=hex(value),
            context=[f'{i.address:x}: {i.mnemonic} {i.op_str}' for i in after]))
    if len(matches)!=1:raise ValueError('Need one bounded identity compare candidate')
    return dict(profile=key,bundle_sha256=PINS[key],main_sha256=runtime['raw_main_sha256'],reader_candidate=hex(helper),matches=matches,
                scope='static compare pattern anchored to observed read PC, not function-symbol recovery or complete failure-path proof')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inputs',type=Path);p.add_argument('header',type=Path);p.add_argument('metadata',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--runtime-report',type=Path,action='append',required=True)
    p.add_argument('--with-initial-controls',action='store_true');args=p.parse_args()
    header=args.header.read_bytes();metadata=args.metadata.read_bytes()
    if hashlib.sha256(header).hexdigest()!='b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797' or hashlib.sha256(metadata).hexdigest()!='baf9354c0e017aca4c36f9c72313e4b4e7b50bb5f07ecf5a71e178597e777deb':raise ValueError('Public source pin differs')
    html=metadata.decode();a=html.index('id="IDREG"');b=html.index('id="LOADCTRL"',a)
    if '0x86362000' not in html[a:b]:raise ValueError('Public identity value differs')
    text=header.decode();end=text.index('} GPU_Type;');begin=text.rfind('typedef struct {',0,end)
    source='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+text[begin:end]+'} GPU_Type;\n_Static_assert(offsetof(GPU_Type,IDREG)==0x1ec,"GPU.IDREG");\n'
    control_offsets={}
    if args.with_initial_controls:
        control_offsets={'CMDLISTSTATUS':0xe8,'SYSCLEAR':0xfc}
        for name,offset in control_offsets.items():
            source+=f'_Static_assert(offsetof(GPU_Type,{name})=={offset},"GPU.{name}");\n'
        if 'On write, resets the GPU (CHECK address!).' not in html or 'On read, returns command list processor status; On write, resets command list processor.' not in html:
            raise ValueError('Expected reset descriptions absent')
    rows=[]
    for path in args.runtime_report:
        data=path.read_bytes();r=json.loads(data);row=analyze(args.inputs/PROFILES[r['profile']]['file'],r);row.update(runtime=str(path),runtime_sha256=hashlib.sha256(data).hexdigest());rows.append(row)
    if len(rows)!=3 or {r['profile'] for r in rows}!={'stock_base','stock_current','cfw'}:raise ValueError('Need three distinct profiles')
    args.output.mkdir(mode=0o700);(args.output/'layout.c').write_text(source)
    cmd=['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(args.output/'layout.c'),'-o',str(args.output/'layout.o')]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(args.output/'compiler.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError('Layout compile failed')
    (args.output/'report.json').write_text(json.dumps(dict(passed=True,rows=rows,public_identity=hex(IDENTITY),compiled_offset='0x1ec',initial_control_offsets=control_offsets,full_reset_semantics_verified=False,compiler_command=cmd,hardware_validated=False,boot_verified=False),indent=2)+'\n')
    print(json.dumps({'passed':True,'profiles':3,'public_identity':hex(IDENTITY)}))


if __name__=='__main__':main()
