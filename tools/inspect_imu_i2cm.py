"""Verify original I2CM encoding and completion/error consumers with ABI stubs."""
import argparse,json,struct
from pathlib import Path
import unicorn.arm_const as arm
from inspect_imu_power import body
from inspect_imu_edmp import frame
from inspect_keydb_record_load import run
from inspect_nema_blocking_wait import cpu,WORK,STOP
from prepare_vendor_startup_candidate import sha

def inspect(s,case):
    m=json.loads((s/'imu-aux-verification-01/manifest.json').read_text());ap=s/'imu-aux-saved-audit-01'/case/'report.json'
    assert m['passed'] and sha(ap)==m['files'][str(ap.relative_to(s))]
    a=json.loads(ap.read_text());f=Path(a['capture'])
    for n,pin in a['capture_hashes'].items():assert sha(f/n)==pin
    old=json.loads((s/'imu-aux-source-02/report.json').read_text());c=next(x for x in old['cases'] if x['case']==case)
    assert sha(s/'imu-aux-source-02/report.json')==m['files']['imu-aux-source-02/report.json']
    raw,ram=(f/'main.bin').read_bytes(),(f/'exports/sram-full.bin').read_bytes()
    cb=body(raw,c['secondary_callbacks'][0]);calls=[i for i in cb if i.mnemonic=='bl']
    configure,start,wait=calls[1].operands[0].imm,calls[2].operands[0].imm,calls[3].operands[0].imm
    start_calls=[i for i in body(raw,start) if i.mnemonic=='bl'];read_reg=start_calls[0].operands[0].imm;write_reg=start_calls[1].operands[0].imm
    rows=[]
    for register,data in [(0x7f,b'\xca'),(0x7c,b'\x80'),(0x7f,b'\x00'),(4,b'\x03'),(4,b'\x00'),(1,None),(0x7c,None),(5,None),(4,None),(6,None)]:
        sp=WORK+0xf000;u=cpu(raw,ram,sp);cfg=WORK+0x200;payload=WORK+0x300
        conf=bytearray(36);conf[0]=1;conf[1]=0x1e;conf[4]=int(data is None);conf[5]=register;conf[6]=1
        struct.pack_into('<I',conf,8,payload);u.mem_write(cfg,bytes(conf))
        if data is not None:u.mem_write(payload,data)
        for n,value in [(0,WORK+0x100),(1,cfg),(2,0)]:u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),value)
        current=configure;writes=[];fragments=[]
        for k in range(10):
            t=run(u,current,[write_reg]);fragments.append(t)
            if t['stop']==STOP:break
            assert t['stop']==write_reg
            reg=u.reg_read(arm.UC_ARM_REG_R1);length=u.reg_read(arm.UC_ARM_REG_R2);ptr=u.reg_read(arm.UC_ARM_REG_R3)
            writes.append([reg,bytes(u.mem_read(ptr,length)).hex()])
            current=u.reg_read(arm.UC_ARM_REG_LR)&~1;u.reg_write(arm.UC_ARM_REG_R0,0)
        else:raise ValueError('Unbounded encoder')
        expected=[[0xa20f,'1e']]
        if data is None:expected += [[0xa20e,bytes([register]).hex()],[0xa206,'91']]
        else:expected += [[0xa233,bytes([register]).hex()],[0xa234,data.hex()],[0xa206,'82']]
        assert writes==expected and u.reg_read(arm.UC_ARM_REG_R0)==0
        rows.append(dict(kind='original-encoder-with-write-reg-ABI-stub',register=register,read=data is None,writes=writes,fragments=fragments))
    for byte in range(256):
        for fast in [0,1]:
            u,sp=frame(raw,ram);u.mem_write(sp,bytes([byte]));u.reg_write(arm.UC_ARM_REG_R4,WORK+0x100)
            u.reg_write(arm.UC_ARM_REG_R5,0xa216);u.reg_write(arm.UC_ARM_REG_R6,0);u.reg_write(arm.UC_ARM_REG_R7,fast)
            t=run(u,start_calls[0].address+4,[start_calls[1].address])
            assert bytes(u.mem_read(sp,1))==bytes([(byte&0xf6)|1|((1-fast)<<3)])
            assert u.reg_read(arm.UC_ARM_REG_R1)==0xa216
            rows.append(dict(kind='start-control-RMW',byte=byte,fast=fast,execution=t))
    wb=body(raw,wait);wc=[i for i in wb if i.mnemonic=='bl'];assert any(i.mnemonic=='tst.w' and i.op_str=='r0, #0x3d' for i in wb)
    # Status register processing after read; frame is push3 words + 0x14 locals.
    for byte in range(256):
        u,sp=frame(raw,ram,32);u.mem_write(sp,bytes([byte]));u.reg_write(arm.UC_ARM_REG_R4,0)
        t=run(u,wc[-1].address+4,[])
        assert u.reg_read(arm.UC_ARM_REG_R0)==(0xffffffff if byte&0x3d else 0)
        rows.append(dict(kind='completion-error-status',byte=byte,execution=t))
    return dict(case=case,source_audit_sha256=sha(ap),configure_entry=configure,start_entry=start,wait_entry=wait,
                read_reg=read_reg,write_reg=write_reg,completion_mask=0x2000,error_mask=0x3d,samples=rows)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    assert not a.output.exists() and a.output.resolve().is_relative_to(a.simulator.resolve())
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];a.output.mkdir(mode=0o700)
    (a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());n=sum(len(x['samples']) for x in rows)
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_scenarios=n,
        encoder_bus_callees_stubbed=True,native_main_execution=False,hardware_accessed=False),indent=2)+'\n');print('Verified original I2CM encoder/control/error scenarios',n)
if __name__=='__main__':main()
