"""Execute the exact stock boot SP predicate; isolated ARM, not whole boot."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R4,UC_ARM_REG_PC,UC_ARM_REG_SP

BOOT_SHA='ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665'
VALUES=(0,0xdead0000,0x2007fb00,0x2007fb01,0xa007fb00,0x20000000,0x20400000,0xffffffff,0x10000000)


def check(boot,value):
    if hashlib.sha256(boot).hexdigest()!=BOOT_SHA:raise ValueError('Exact stock2.4 boot required')
    uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);uc.mem_map(0x410000,0x28000);uc.mem_write(0x410000,boot);uc.mem_protect(0x410000,0x28000,UC_PROT_READ|UC_PROT_EXEC)
    uc.mem_map(0x438000,0x1000);uc.mem_write(0x438000,struct.pack('<I',value));uc.mem_protect(0x438000,0x1000,UC_PROT_READ)
    uc.mem_map(0x20000000,0x10000);uc.mem_write(0x20001014,struct.pack('<I',0x438000));uc.reg_write(UC_ARM_REG_R4,0x20001000);uc.reg_write(UC_ARM_REG_SP,0x2000f000)
    trace=[]
    def observe(c,pc,size,context):
        trace.append(pc)
        if pc in (0x42e406,0x42e1f6):c.emu_stop()
    uc.hook_add(UC_HOOK_CODE,observe);uc.emu_start(0x42e3fd,0,count=8)
    accepted=uc.reg_read(UC_ARM_REG_PC)==0x42e406
    assert trace==[0x42e3fc,0x42e3fe,0x42e400,0x42e402,0x42e406 if accepted else 0x42e1f6]
    assert accepted==bool(value&0x20000000)
    return dict(sp=hex(value),accepted=accepted,pc=hex(uc.reg_read(UC_ARM_REG_PC)),trace=[hex(x) for x in trace],whole_boot=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('boot',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Fresh output required')
    rows=[check(a.boot.read_bytes(),v) for v in VALUES]
    a.output.write_text(json.dumps(dict(cases=rows,passed=True,boot_sha256=BOOT_SHA,scope='Original LDR/LDR/LSLS/BPL only; no MMIO or handoff execution',hardware_accessed=False),indent=2)+'\n');print('predicate_cases',len(rows),'passed')

if __name__=='__main__':main()
