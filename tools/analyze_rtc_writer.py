"""Resolve the original RTC counter write sequence statically; this does not execute it."""
import argparse,json,hashlib,struct
from pathlib import Path
import capstone
from capstone.arm import ARM_OP_MEM,ARM_OP_REG,ARM_REG_PC
from pinned_main import load_pinned_main

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();o=a.output.resolve()
    if o.exists():raise ValueError('Use a fresh evidence directory')
    cs=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS);cs.detail=True
    results=[]
    for name,file in [('stock24-xt','stock-2.4.0.24.bin'),('stock23-xt','stock-2.3.0.24.bin'),('cfw-xt','faceclaw-38-research-only.bin')]:
        s=a.simulator/'rtc-osel-main-comparison-01'/name;r=json.loads((s/'report.json').read_text())
        _,raw=load_pinned_main((a.simulator/'inputs/verified-01'/file).read_bytes())
        if raw!=(s/'main.bin').read_bytes():raise ValueError('Original main differs')
        # The adjacent writer is only a candidate function identity. Check actual bytes/instructions.
        start=r['observed']['pc']+12;base=0x438000
        ins=list(cs.disasm(raw[start-base:start-base+0xc0],start))
        if ins[0].mnemonic!='push':raise ValueError('Candidate writer entry differs')
        stores=[]
        for current,next_ins in zip(ins,ins[1:]):
            if current.mnemonic not in ('ldr','ldr.w') or len(current.operands)!=2 or current.operands[1].type!=ARM_OP_MEM or current.operands[1].mem.base!=ARM_REG_PC:continue
            pool=((current.address+4)&~3)+current.operands[1].mem.disp
            target=struct.unpack_from('<I',raw,pool-base)[0]
            if target not in (0x40004820,0x40004824):continue
            if next_ins.mnemonic!='str' or next_ins.operands[1].type!=ARM_OP_MEM or next_ins.operands[1].mem.base!=current.operands[0].reg:raise ValueError('Literal is not followed by the expected store')
            stores.append(dict(instruction=hex(next_ins.address),literal_pool=hex(pool),register=cs.reg_name(next_ins.operands[0].reg),target=hex(target),mnemonic=next_ins.mnemonic,operands=next_ins.op_str))
        if [x['target'] for x in stores]!=['0x40004820','0x40004824']:raise ValueError('Original writer order differs')
        results.append(dict(name=name,raw_sha256=hashlib.sha256(raw).hexdigest(),candidate_entry=hex(start),stores=stores,executed=False))
    o.mkdir(mode=0o700)
    report=dict(source_supported_order='CTRLOW then CTRUP',cases=results,hardware_write_order_verified=False,candidate_function_identity='inferred from adjacent RTC instruction sequence and HAL shape; no symbols',scope='static original code/literal verification, not successful counter update or hardware behavior')
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
