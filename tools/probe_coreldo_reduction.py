"""Exhaust a pinned firmware helper's 10-bit trim inputs; no boot or device access."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import capstone
import unicorn as u
from unicorn import arm_const as arm
from audit_assets import PINS
from blackwall_package import parse_bundle

BASE=0x438000
RAM=0x20000000
RETURN=RAM
PROFILES={
    'stock_base':('stock-2.3.0.24.bin',0x5bad14),
    'stock_current':('stock-2.4.0.24.bin',0x5c22bc),
    'cfw':('faceclaw-38-research-only.bin',0x5bad14),
}


def probe(raw,start):
    cs=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS)
    cs.detail=True
    instructions={i.address:i for i in cs.disasm(raw[start-BASE:start-BASE+38],start)}
    def literal(pc):
        ins=instructions[pc]
        if ins.mnemonic!='ldr' or ins.operands[1].mem.base!=capstone.arm.ARM_REG_PC:
            raise ValueError('Expected PC-relative literal missing')
        address=((pc+4)&~3)+ins.operands[1].mem.disp
        return struct.unpack_from('<I',raw,address-BASE)[0]
    flag_address,cached_address,register_address=literal(start),literal(start+8),literal(start+24)
    if not (RAM<=flag_address<RAM+0x80000 and RAM<=cached_address<=RAM+0x80000-4
            and cached_address%4==0 and register_address==0x40020080):
        raise ValueError('Helper data ABI differs from selected image')
    if instructions[start+18].mnemonic!='subs' or instructions[start+18].operands[-1].imm!=7:
        raise ValueError('Observed reduction instruction changed')
    if instructions[start+28].mnemonic!='bfi' or instructions[start+28].op_str!='r2, r0, #0, #0xa':
        raise ValueError('Observed 10-bit field insertion changed')
    cpu=u.Uc(u.UC_ARCH_ARM,u.UC_MODE_THUMB|u.UC_MODE_MCLASS)
    cpu.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M4)
    cpu.mem_map(BASE,(len(raw)+0xfff)&~0xfff)
    cpu.mem_write(BASE,raw)
    cpu.mem_protect(BASE,(len(raw)+0xfff)&~0xfff,u.UC_PROT_READ|u.UC_PROT_EXEC)
    cpu.mem_map(RAM,0x80000)
    state={}
    def read(uc,offset,size,_):
        if offset!=0x80 or size!=4:raise ValueError('Unexpected peripheral read')
        state['reads']+=1
        return state['word']
    def write(uc,offset,size,value,_):
        if offset!=0x80 or size!=4:raise ValueError('Unexpected peripheral write')
        state['writes']+=1;state['word']=value
    cpu.mmio_map(0x40020000,0x1000,read,None,write,None)
    def code(uc,address,size,_):
        if not start<=address<start+38:raise ValueError('Execution left isolated helper')
    cpu.hook_add(u.UC_HOOK_CODE,code)
    count=0;boundaries=[]
    for stored in (True,False):
        for cached in (range(1024) if stored else (0,7,8,980,1023)):
            for current in (0,0x6d3d4):
                state.update(word=current,reads=0,writes=0)
                cpu.mem_write(flag_address,bytes((int(stored),)))
                cpu.mem_write(cached_address,struct.pack('<I',cached))
                cpu.reg_write(arm.UC_ARM_REG_SP,RAM+0x7fb00)
                cpu.reg_write(arm.UC_ARM_REG_LR,RETURN|1)
                cpu.reg_write(arm.UC_ARM_REG_XPSR,0x01000000)
                cpu.emu_start(start|1,RETURN,count=128)
                expected=(current&~0x3ff)|max(cached-7,0) if stored else current
                if (state['word']!=expected or state['writes']!=int(stored) or state['reads']!=int(stored)
                        or cpu.reg_read(arm.UC_ARM_REG_PC)!=RETURN or cpu.reg_read(arm.UC_ARM_REG_R0)!=0):
                    raise ValueError('Helper result mismatch: '+repr((stored,cached,current,state)))
                count+=1
                if cached in (0,7,8,980,1023):
                    boundaries.append(dict(stored=stored,cached=cached,current=hex(current),result=hex(expected),writes=state['writes']))
    return dict(cases=count,passed=True,flag_address=hex(flag_address),cached_address=hex(cached_address),
        register_address=hex(register_address),function_start=hex(start),boundaries=boundaries)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(mode=0o700)
    rows={}
    for profile,(filename,start) in PROFILES.items():
        data=(args.inputs/filename).read_bytes()
        if hashlib.sha256(data).hexdigest()!=PINS[profile]:raise ValueError('Input bundle SHA256 mismatch')
        raw=next(c for c in parse_bundle(data) if c.type_id==0).payload[32:]
        rows[profile]=dict(probe(raw,start),raw_main_sha256=hashlib.sha256(raw).hexdigest())
        print(profile,rows[profile]['cases'],'passed',flush=True)
    report=dict(scope='isolated real ARM helper with synthetic flag/cached/current values; no full boot or valid calibration',
        cpu_model='Unicorn Cortex-M4 approximation',profiles=rows,cases=sum(r['cases'] for r in rows.values()),
        hardware_validated=False,boot_verified=False,installable=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
