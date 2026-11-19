"""Run original WOM configuration/enable wrappers with explicit register bus ABI stubs."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_imu_power import body
from inspect_nema_blocking_wait import cpu,WORK,STOP
from prepare_vendor_startup_candidate import sha


def execute(raw,ram,entry,read,write,initial,mode,duration,status,enable):
    sp=WORK+0xf000;u=cpu(raw,ram,sp);u.mem_write(sp,struct.pack('<II',mode,duration))
    for k,v in [(0,WORK+0x100),(1,2),(2,0x103),(3,0x204)]:u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(k)),v)
    requests=[];trace=[];value=initial
    def code(c,pc,size,user):
        nonlocal value
        trace.append(pc)
        if pc not in [read,write]:return
        args=[c.reg_read(getattr(arm,'UC_ARM_REG_R'+str(k))) for k in range(4)];assert args[0]==WORK+0x100
        _,reg,length,pointer=args
        if pc==read:assert reg==0x23 and length==1;c.mem_write(pointer,bytes([value]));data=bytes([value])
        else:
            data=bytes(c.mem_read(pointer,length))
            if reg==0x23:assert length==1;value=data[0]
            else:assert reg==0xa27e and data==bytes([2,3,4])
        requests.append(dict(kind='read' if pc==read else 'write',register=reg,data=data.hex()))
        c.reg_write(arm.UC_ARM_REG_R0,status);c.reg_write(arm.UC_ARM_REG_PC,c.reg_read(arm.UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(entry|1,STOP,count=10000)
    assert u.reg_read(arm.UC_ARM_REG_PC)==STOP and u.reg_read(arm.UC_ARM_REG_SP)==sp and u.reg_read(arm.UC_ARM_REG_R0)==status
    expected=initial|0x10 if enable else ((initial|8)&~7)|((mode&1)<<2)|(duration&3)
    assert value==expected and len(requests)==(2 if enable else 3)
    return dict(initial=initial,mode=mode,duration=duration,status=status,enabled=enable,final=value,requests=requests,instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())


def inspect(s,case):
    manifest=json.loads((s/'imu-b2s-verification-01/manifest.json').read_text());assert manifest['passed'];ap=s/'imu-b2s-saved-audit-01'/case/'report.json';assert sha(ap)==manifest['files'][str(ap.relative_to(s))]
    audit=json.loads(ap.read_text());f=Path(audit['capture'])
    for n,h in audit['capture_hashes'].items():assert sha(f/n)==h
    r=json.loads((f/'report.json').read_text());raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();sp=r['observed']['register_context']['r13'];ret=lambda off:struct.unpack_from('<I',ram,sp+off-0x20000000)[0]&~1
    call=decode(raw,ret(0x114)-4,4)[0];assert call.mnemonic=='bl';configure=call.operands[0].imm;cb=body(raw,configure);cc=[i for i in cb if i.mnemonic=='bl'];assert len(cc)==3 and ret(0xfc)==cc[0].address+4
    write=cc[0].operands[0].imm;read=cc[1].operands[0].imm;assert cc[2].operands[0].imm==write
    after=decode(raw,ret(0x114),16);enable=next(i.operands[0].imm for i in after if i.mnemonic=='bl');ec=[i for i in body(raw,enable) if i.mnemonic=='bl'];assert [i.operands[0].imm for i in ec]==[read,write]
    caller=decode(raw,ret(0x114)-0x14,0x14);assert [i.op_str for i in caller if i.mnemonic=='movs']==['r0, #1','r0, #0','r3, #2','r2, #2','r1, #2','r0, r5']
    assert ram[sp+0x118-0x20000000:sp+0x120-0x20000000]==struct.pack('<II',0,1)
    rows=[]
    for initial in [0,0xff,0xa5,0x5a]:
        for status in [0,0xfffffffd]:
            rows.append(execute(raw,ram,enable,read,write,initial,0,0,status,True))
            for mode in [0,1,2,255]:
                for duration in [0,1,2,3,255]:rows.append(execute(raw,ram,configure,read,write,initial,mode,duration,status,False))
    return dict(case=case,source_audit_sha256=sha(ap),configure=configure,enable=enable,read=read,write=write,actual_thresholds=[2,2,2],actual_mode=0,actual_duration=1,samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists() and a.output.resolve().is_relative_to(a.simulator.resolve())
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];a.output.mkdir(mode=0o700);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());n=sum(len(x['samples']) for x in rows)
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_wrapper_scenarios=n,register_callees_stubbed=True,native_main_rerun=False,hardware_accessed=False),indent=2)+'\n');print('Original WOM config/enable scenarios',n)
if __name__=='__main__':main()
