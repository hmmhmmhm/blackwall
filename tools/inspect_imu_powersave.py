"""Verify original power-save get/set and caller passthrough with explicit ABI stubs."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_nema_blocking_wait import cpu,WORK,STOP
from prepare_vendor_startup_candidate import sha


def wrapper(raw,ram,entry,leaves,value,en,request,status,getter):
    u=cpu(raw,ram,WORK+0xf000);p=WORK+0x200;u.mem_write(p,struct.pack('<I',value)+bytes([request,0xa5,0xa5,0xa5]))
    u.reg_write(arm.UC_ARM_REG_R0,WORK+0x100);u.reg_write(arm.UC_ARM_REG_R1,p);rows=[];trace=[]
    def code(c,pc,size,user):
        trace.append(pc)
        if pc not in leaves:return
        kind=leaves[pc];args=[c.reg_read(getattr(arm,'UC_ARM_REG_R'+str(k))) for k in range(4)];assert args[0]==WORK+0x100
        _,reg,n,ptr=args
        if kind=='read-reg':assert reg==0x2a and n==1;c.mem_write(ptr,bytes([en]))
        if kind=='read-time':assert reg==0x40 and n==4;c.mem_write(ptr,struct.pack('<I',value))
        payload=bytes(c.mem_read(ptr,n));rows.append(dict(kind=kind,register=reg,data=payload.hex()))
        c.reg_write(arm.UC_ARM_REG_R0,status);c.reg_write(arm.UC_ARM_REG_PC,c.reg_read(arm.UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(entry|1,STOP,count=10000)
    assert u.reg_read(arm.UC_ARM_REG_PC)==STOP and u.reg_read(arm.UC_ARM_REG_SP)==WORK+0xf000
    blocked=not getter and bool(en&0x40) and request!=0 and bool(en&4)
    expected=status if not blocked else 0xffffffff;assert u.reg_read(arm.UC_ARM_REG_R0)==expected
    if getter:
        assert [x['kind'] for x in rows]==['read-time','read-reg'] and bytes(u.mem_read(p,8))==struct.pack('<I',value)+bytes([(en>>2)&1,0xa5,0xa5,0xa5])
    else:
        kinds=['read-reg'] if blocked else (['read-reg','write-time','write-reg'] if en&0x40 and request else ['read-reg','write-reg','write-time'])
        assert [x['kind'] for x in rows]==kinds
        for row in rows:
            if row['kind']=='write-time':assert row['register']==0x40 and row['data']==struct.pack('<I',value).hex()
            if row['kind']=='write-reg':assert row['register']==0x2a and row['data']==bytes([(en&~4)|((request&1)<<2)]).hex()
        assert bytes(u.mem_read(p,8))==struct.pack('<I',value)+bytes([request,0xa5,0xa5,0xa5])
    return dict(value=value,enable=en,request=request,bus_status=status,returned=expected,requests=rows,instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())


def caller(raw,ram,ret,setter,configure,enable,disable,powerptr,b2sptr,power,b2s,value,status):
    u=cpu(raw,ram,WORK+0xe000);sp=WORK+0xe000;u.mem_write(powerptr,bytes([power]));u.mem_write(b2sptr,bytes([b2s]));u.mem_write(sp+0x4c,struct.pack('<I',value)+b'\xa5'*4)
    for k,v in [(0,status),(4,0),(5,WORK+0x100),(8,b2sptr)]:u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(k)),v)
    rows=[];trace=[];end=ret+0x60
    def code(c,pc,size,user):
        trace.append(pc)
        if pc==end:c.emu_stop();return
        if pc not in [setter,configure,enable,disable]:return
        args=[c.reg_read(getattr(arm,'UC_ARM_REG_R'+str(k))) for k in range(4)];assert args[0]==WORK+0x100
        if pc==setter:
            assert args[1]==sp+0x4c and bytes(c.mem_read(args[1],5))==struct.pack('<I',value)+bytes([power]);rows.append('set')
        elif pc==configure:
            assert args[1:]==[13,13,13] and bytes(c.mem_read(sp,8))==struct.pack('<II',1,0);rows.append('wom-config')
        elif pc==enable:rows.append('wom-enable')
        else:rows.append('wom-disable')
        c.reg_write(arm.UC_ARM_REG_R0,0);c.reg_write(arm.UC_ARM_REG_PC,c.reg_read(arm.UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(ret|1,STOP,count=10000)
    assert u.reg_read(arm.UC_ARM_REG_PC)==end and u.reg_read(arm.UC_ARM_REG_SP)==sp and u.reg_read(arm.UC_ARM_REG_R0)==status
    assert rows==(['wom-config','wom-enable'] if power else [])+['set']+(['wom-disable'] if not(power or b2s) else [])
    return dict(power_flag=power,b2s_flag=b2s,time=value,getter_status=status,calls=rows,parameter_time_preserved=True,instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())


def inspect(s,case):
    manifest=json.loads((s/'imu-wom-verification-01/manifest.json').read_text());assert manifest['passed'];ap=s/'imu-wom-saved-audit-01'/case/'report.json';assert sha(ap)==manifest['files'][str(ap.relative_to(s))]
    audit=json.loads(ap.read_text());f=Path(audit['capture'])
    for n,h in audit['capture_hashes'].items():assert sha(f/n)==h
    r=json.loads((f/'report.json').read_text());raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();sp=r['observed']['register_context']['r13'];word=lambda off:struct.unpack_from('<I',ram,sp+off-0x20000000)[0]&~1
    ret=word(0x114);call=decode(raw,ret-4,4)[0];assert call.mnemonic=='bl';getter=call.operands[0].imm;gb=decode(raw,getter,0x32);gc=[i for i in gb if i.mnemonic=='bl'];assert len(gc)==2 and word(0xfc)==gc[0].address+4
    ca=[i for i in decode(raw,ret,0x42) if i.mnemonic=='bl'];assert len(ca)==3;configure,enable,setter=[i.operands[0].imm for i in ca]
    disable=next(i.operands[0].imm for i in decode(raw,ret+0x42,0x1e) if i.mnemonic=='bl')
    sb=decode(raw,setter,0x98);sc=[i for i in sb if i.mnemonic=='bl'];assert len(sc)==5
    read_time=gc[0].operands[0].imm;read_reg=gc[1].operands[0].imm;write_reg=sc[1].operands[0].imm;write_time=sc[2].operands[0].imm
    assert [i.operands[0].imm for i in sc]==[read_reg,write_reg,write_time,write_time,write_reg]
    powerptr=literal(raw,decode(raw,ret+2,4)[0]);loads=[i for i in decode(raw,ret-0x200,0x200) if i.mnemonic=='ldr.w' and i.op_str.startswith('r8, [pc,')];assert len(loads)==1;b2sptr=literal(raw,loads[0])
    actual=[ram[p-0x20000000] for p in [powerptr,b2sptr]];assert actual==[0,1]
    getrows=[];setrows=[];callerrows=[]
    for value in [0,0x12345678,0xffffffff]:
        for status in [0,0xfffffffd]:
            for en in [0,4,0x40,0x44,0x8f,0xcf]:
                getrows.append(wrapper(raw,ram,getter,{read_time:'read-time',read_reg:'read-reg'},value,en,0,status,True))
                for request in [0,1]:setrows.append(wrapper(raw,ram,setter,{read_reg:'read-reg',write_reg:'write-reg',write_time:'write-time'},value,en,request,status,False))
            for power in [0,1]:
                for b2s in [0,1]:callerrows.append(caller(raw,ram,ret,setter,configure,enable,disable,powerptr,b2sptr,power,b2s,value,status))
    return dict(case=case,source_audit_sha256=sha(ap),getter=getter,setter=setter,configure_wom=configure,enable_wom=enable,disable_wom=disable,actual_power_flag=actual[0],actual_b2s_flag=actual[1],getter_samples=getrows,setter_samples=setrows,caller_samples=callerrows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists() and a.output.resolve().is_relative_to(a.simulator.resolve())
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];n=sum(len(x[k]) for x in rows for k in ['getter_samples','setter_samples','caller_samples']);a.output.mkdir(mode=0o700);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_scenarios=n,bus_abi_callees_stubbed=True,caller_feature_callees_stubbed=True,physical_rom_defaults_verified=False,native_main_rerun=False,hardware_accessed=False),indent=2)+'\n');print('Original power-save wrappers/caller scenarios',n)
if __name__=='__main__':main()
