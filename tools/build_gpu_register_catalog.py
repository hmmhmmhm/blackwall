"""Build a diagnostic register-name catalog from one pinned official SDK header."""
import argparse
import hashlib
import json
from pathlib import Path
import re

SOURCE_SHA256='7ac2f2ad9bda610df64ca02ab4974ca93fada09898f3cbfdb3466ed2a4cf957c'
COMMIT='d3278ec49a534728384537557dd44b205ec72129'
SOURCE_PATH='components/graphics/NemaGFX_SDK/headers/NemaGFX/Nema/nema_regs.h'


def build(header):
    data=header.read_bytes()
    if hashlib.sha256(data).hexdigest()!=SOURCE_SHA256:
        raise ValueError('Pinned Nema register header differs')
    registers={};constants={}
    for name,value in re.findall(r'^#define\s+(NEMA_[A-Z0-9_]+)\s+\((0x[0-9a-fA-F]+)U\)',data.decode(),re.M):
        offset=int(value,16)
        if name=='NEMA_HOLDCMD' and offset==0xff000000:
            constants[name]=offset;continue
        if not 0<=offset<0x1000 or offset%4:
            raise ValueError('Non-register literal needs review: '+name)
        if name in registers:raise ValueError('Duplicate name: '+name)
        registers[name]=offset
    required={'NEMA_RAST_BYPASS':0x388,'NEMA_CLID':0x148,'NEMA_STATUS':0xfc,'NEMA_CMDSTATUS':0xe8,
              'NEMA_CONFIG':0x1f0,'NEMA_CONFIGH':0x1f4,'NEMA_CMDADDR':0xf0,'NEMA_CMDSIZE':0xf4}
    if any(registers.get(k)!=v for k,v in required.items()):
        raise ValueError('Required SDK mapping differs')
    return dict(schema_version=1,repo='AmbiqMicro/ambiqhal_ambiq',commit=COMMIT,path=SOURCE_PATH,
                source_sha256=SOURCE_SHA256,license='licenses/think-silicon-nema-headers.txt',
                scope='diagnostic byte offsets only; no read/write semantics, reset values, capability or GPU execution model',
                register_name_count=len(registers),distinct_offset_count=len(set(registers.values())),
                aliases={hex(offset):sorted(name for name,value in registers.items() if value==offset)
                         for offset in sorted(set(registers.values())) if sum(value==offset for value in registers.values())>1},
                command_constants=constants,registers=dict(sorted(registers.items())))


def lookup(catalog,address):
    if 0x40090000<=address<0x40091000:offset=address-0x40090000
    elif 0<=address<0x1000:offset=address
    else:raise ValueError('Outside catalog query range')
    return dict(offset=hex(offset),names=[name for name,value in catalog['registers'].items() if value==offset],
                modeled_behavior=False,hardware_verified=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('header',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--address',type=lambda v:int(v,0));args=p.parse_args()
    catalog=build(args.header)
    query=lookup(catalog,args.address) if args.address is not None else None
    with args.output.open('x') as f:f.write(json.dumps(catalog,indent=2)+'\n')
    print(json.dumps(dict(register_names=catalog['register_name_count'],distinct_offsets=catalog['distinct_offset_count'],query=query)))


if __name__=='__main__':main()
