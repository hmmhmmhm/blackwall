"""Execute source-bound original eight-field get/set wrappers with explicit ABI stubs."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_imu_power import body
from inspect_em9305_hci_framing import literal
from inspect_nema_blocking_wait import cpu,WORK,STOP
from prepare_vendor_startup_candidate import sha
FIELDS=[(0x1618,4,0),(0x161c,4,4),(0x1614,1,8),(0x1615,1,9),(0x163c,4,12),(0x1640,4,16),(0x1638,1,20),(0x1639,1,21)]


def execute(raw,ram,entry,leaves,mode,e0,e1,status,offset,is_set):
    u=cpu(raw,ram,WORK+0xf000);params=WORK+0x200;data=bytes(range(24));u.mem_write(params,data)
    for k,v in [(0,WORK+0x100),(1,params),(2,mode)]:u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(k)),v)
    requests=[];trace=[]
    def code(c,pc,size,user):
        trace.append(pc)
        if pc not in leaves:return
        kind=leaves[pc];args=[c.reg_read(getattr(arm,'UC_ARM_REG_R'+str(k))) for k in range(4)];assert args[0]==WORK+0x100
        _,address,length,pointer=args
        if kind=='reg':
            assert length==1 and address in [0x29,0x2a];payload=bytes([e0 if address==0x29 else e1]);c.mem_write(pointer,payload)
        elif kind=='get':
            payload=bytes((address+k)&255 for k in range(length));c.mem_write(pointer,payload)
        else:payload=bytes(c.mem_read(pointer,length))
        requests.append(dict(kind=kind,address=address,length=length,pointer_offset=pointer-params if kind!='reg' else None,data_hex=payload.hex()))
        c.reg_write(arm.UC_ARM_REG_R0,status);c.reg_write(arm.UC_ARM_REG_PC,c.reg_read(arm.UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(entry|1,STOP,count=10000)
    assert u.reg_read(arm.UC_ARM_REG_PC)==STOP and u.reg_read(arm.UC_ARM_REG_SP)==WORK+0xf000
    blocked=is_set and bool(e0&8) and (e1&0x60)==0x60
    actual=[x for x in requests if x['kind']!='reg'];shift=offset if mode&255 else 0
    assert [(x['address'],x['length'],x['pointer_offset']) for x in actual]==([] if blocked else [(a+shift,n,o) for a,n,o in FIELDS])
    if is_set:
        assert bytes(u.mem_read(params,24))==data
        for x,(_,n,o) in zip(actual,FIELDS):assert x['data_hex']==data[o:o+n].hex()
    else:
        expected=bytearray(data)
        for a,n,o in FIELDS:expected[o:o+n]=bytes((a+shift+k)&255 for k in range(n))
        assert bytes(u.mem_read(params,24))==expected
    returned=0xffffffff if blocked else status;assert u.reg_read(arm.UC_ARM_REG_R0)==returned
    return dict(mode=mode,enable=[e0,e1],bus_status=status,blocked=blocked,returned=returned,requests=requests,instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())


def inspect(s,case):
    manifest=json.loads((s/'imu-patch-ram-verification-02/manifest.json').read_text());assert manifest['passed'];ap=s/'imu-patch-ram-saved-audit-01'/case/'report.json';assert sha(ap)==manifest['files'][str(ap.relative_to(s))]
    audit=json.loads(ap.read_text());f=Path(audit['capture'])
    for n,pin in audit['capture_hashes'].items():assert sha(f/n)==pin
    r=json.loads((f/'report.json').read_text());raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();sp=r['observed']['register_context']['r13']
    ret=struct.unpack_from('<I',ram,sp+0x114-0x20000000)[0]&~1;call=decode(raw,ret-4,4)[0];assert call.mnemonic=='bl';setter=call.operands[0].imm;getter=setter-0xd2
    gb=body(raw,getter);gc=[i for i in gb if i.mnemonic=='bl'];sc=[i for i in body(raw,setter) if i.mnemonic=='bl'];assert len(gc)==8 and len(sc)==10
    read_sram=gc[0].operands[0].imm;write_sram=sc[2].operands[0].imm;read_reg=sc[0].operands[0].imm
    assert all(i.operands[0].imm==read_sram for i in gc) and all(i.operands[0].imm==write_sram for i in sc[2:]) and sc[1].operands[0].imm==read_reg
    assert any(i.mnemonic=='bl' and i.operands[0].imm==getter for i in decode(raw,ret-0x60,0x60))
    value=literal(raw,next(i for i in gb if i.mnemonic=='ldr' and i.op_str.startswith('r7,')));offset=struct.unpack('<h',struct.pack('<H',value&0xffff))[0];assert offset==-0xe00
    # Caller passes sp+0x68 after a six-word setter frame; bind actual argument setup.
    caller=decode(raw,ret-10,10);assert any(i.op_str=='r1, sp, #0x68' for i in caller) and any(i.op_str=='r2, #0' for i in caller)
    assert body(raw,setter)[0].op_str=='{r3, r4, r5, r6, r7, lr}'
    actual=ram[sp+0x180-0x20000000:sp+0x198-0x20000000]
    assert [struct.unpack_from('<I',actual,o)[0] for o in [0,4,12,16]]==[350,3750,50,600] and [actual[o] for o in [8,9,20,21]]==[7,1,7,1]
    rows=[]
    for mode in [0,1,256]:
        for status in [0,0xfffffffd]:
            rows.append(dict(role='get',**execute(raw,ram,getter,{read_sram:'get'},mode,0,0,status,offset,False)))
            for e0 in [0,8]:
                for e1 in [0,0x20,0x40,0x60]:rows.append(dict(role='set',**execute(raw,ram,setter,{read_reg:'reg',write_sram:'set'},mode,e0,e1,status,offset,True)))
    return dict(case=case,source_audit_sha256=sha(ap),getter=getter,setter=setter,alternate_offset=offset,fields=FIELDS,actual_struct_hex=actual.hex(),samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists() and a.output.resolve().is_relative_to(a.simulator.resolve())
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];a.output.mkdir(mode=0o700);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());n=sum(len(x['samples']) for x in rows)
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_wrapper_scenarios=n,register_and_sram_callees_stubbed=True,native_main_rerun=False,hardware_accessed=False),indent=2)+'\n');print('Original B2S get/set wrapper scenarios',n)
if __name__=='__main__':main()
