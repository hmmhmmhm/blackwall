"""Original ATT group/permission/connection contracts, no connection-state fabrication."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import uuid
from unicorn import UcError,UC_HOOK_MEM_INVALID
import unicorn.arm_const as arm
from inspect_nema_blocking_wait import cpu,BASE,SRAM,WORK,STOP
from inspect_ambiq_target import decode
from probe_display_queue_producer import literal
from probe_display_root_ingress import packet


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def unique(raw,signature):
    assert raw.count(signature)==1
    return BASE+raw.index(signature)


def discover(raw,ram,root):
    callback=root['eus_callback']|1;needle=struct.pack('<I',callback)
    candidates=[]
    for k in range(16,0x80000-4,4):
        if ram[k:k+4]!=struct.pack('<HH',0x840,0x847):continue
        group=SRAM+k-16
        nxt,attrs,read,write,start,end=struct.unpack_from('<IIIIHH',ram,group-SRAM)
        if start<=0x842<=end and BASE<=attrs<BASE+len(raw)-16*(end-start+1):candidates.append((group,attrs,start,end,write))
    assert len(candidates)==1
    group,attrs,first,last,registered=candidates[0]
    wrapper_fallback=None
    if registered!=callback:
        body=decode(raw,registered&~1,0x80)
        pairs=[(x,y,z) for x,y,z in zip(body,body[1:],body[2:]) if x.mnemonic=='movw' and y.mnemonic=='movt' and z.mnemonic=='blx' and x.operands[0].reg==y.operands[0].reg==z.operands[0].reg]
        matches=[z.address for x,y,z in pairs if x.operands[1].imm|(y.operands[1].imm<<16)==callback]
        assert len(matches)==1
        wrapper_fallback=matches[0]
    lookup=unique(raw,bytes.fromhex('d2f8582200e0'))-6
    code=decode(raw,lookup,10);assert code[0].op_str=='{r4}'
    att_global=literal(raw,code[1]);head_slot=att_global+0x258
    head=struct.unpack_from('<I',ram,head_slot-SRAM)[0];groups=[]
    while head:
        assert SRAM<=head<SRAM+len(ram)-20 and head not in [g['address'] for g in groups]
        nxt,ptr,rd,wr,lo,hi=struct.unpack_from('<IIIIHH',ram,head-SRAM)
        assert lo<=hi and len(groups)<100
        groups.append(dict(address=head,first=lo,last=hi,attributes=ptr,write_callback=wr));head=nxt
    assert group in [g['address'] for g in groups]
    attributes=[]
    for handle in range(first,last+1):
        address=attrs+16*(handle-first);up,value,length,word=struct.unpack_from('<4I',raw,address-BASE)
        max_length=word&0xffff;settings=word>>16&255;permissions=word>>24
        uid=raw[up-BASE:up-BASE+(16 if settings&1 else 2)]
        attributes.append(dict(handle=handle,address=address,uuid_bytes=uid.hex(),uuid=str(uuid.UUID(bytes=uid[::-1])) if len(uid)==16 else uid[::-1].hex(),max_length=max_length,settings=settings,permissions=permissions))
    write=unique(raw,bytes.fromhex('2de9ff470500002012f10800'))
    dispatch=unique(raw,bytes.fromhex('2de9f8430c001500002180b2'))
    permission=unique(raw,bytes.fromhex('f8b504000e0015001f003800'))
    ccb=next(i.operands[0].imm for i in decode(raw,dispatch,24) if i.mnemonic=='bl')
    dm=next(i.operands[0].imm for i in decode(raw,ccb,16) if i.mnemonic=='bl')
    dm_body=decode(raw,dm,24);dm_global=literal(raw,dm_body[1]);assert dm_body[2].op_str=='r3, #3'
    slots=[dict(address=dm_global+48*k,active=ram[dm_global+48*k+0x16-SRAM],handle=struct.unpack_from('<H',ram,dm_global+48*k+0xc-SRAM)[0],connection_id=ram[dm_global+48*k+0x10-SRAM]) for k in range(3)]
    # The live dispatch vector points to the original write processor.
    needles=struct.pack('<II',write|1,write|1);positions=[SRAM+k for k in range(0,len(ram)-8,4) if ram[k:k+8]==needles]
    assert len(positions)==1
    dispatch_body=decode(raw,dispatch,0x120)
    assert any(i.mnemonic=='cmp' and i.op_str=='r0, #0x52' for i in dispatch_body)
    assert any(i.op_str=='r8, #0xa' for i in dispatch_body)
    tables=[]
    for i in dispatch_body:
        if not i.mnemonic.startswith('ldr') or not i.op_str.startswith('r0,'):continue
        try:value=literal(raw,i)
        except ValueError:continue
        if value==positions[0]-9*4:tables.append(value)
    assert len(tables)==1
    return dict(group=group,first=first,last=last,attributes=attributes,groups=groups,head_slot=head_slot,lookup=lookup,permission=permission,write_processor=write,dispatch=dispatch,write_request_slot=positions[0],write_command_slot=positions[0]+4,dispatch_vector=tables[0],ccb_lookup=ccb,dm_lookup=dm,dm_global=dm_global,connection_slots=slots,eus_callback=root['eus_callback'],registered_write_callback=registered&~1,wrapper_fallback_call=wrapper_fallback)


def run(raw,ram,entry,args,data=b''):
    u=cpu(raw,ram,WORK+0xf000);u.mem_write(WORK+0x100,data)
    for k,value in enumerate(args):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(k)),value)
    u.reg_write(arm.UC_ARM_REG_LR,STOP|1);invalid=[]
    def reject(m,access,address,size,value,user):
        invalid.append(dict(address=address,pc=m.reg_read(arm.UC_ARM_REG_PC)));return False
    u.hook_add(UC_HOOK_MEM_INVALID,reject)
    error=None
    try:u.emu_start(entry|1,STOP,count=400000)
    except UcError as exc:error=str(exc)
    result=dict(pc=u.reg_read(arm.UC_ARM_REG_PC),r0=u.reg_read(arm.UC_ARM_REG_R0),invalid=invalid,error=error)
    assert result['pc']==STOP and not invalid and error is None,result
    return u,result


def inspect(raw,ram,c,root):
    rows=[]
    for attr in c['attributes']:
        u,r=run(raw,ram,c['lookup'],[attr['handle'],WORK+0x20])
        assert r['r0']==attr['address'] and struct.unpack('<I',u.mem_read(WORK+0x20,4))[0]==c['group']
        rows.append(dict(kind='original-attribute-lookup',handle=attr['handle'],attribute=r['r0'],group=c['group']))
    by={a['handle']:a for a in c['attributes']}
    assert by[0x842]['uuid_bytes'].startswith('0154') and by[0x842]['settings']==0x0b and by[0x842]['permissions']==0x10 and by[0x842]['max_length']==512
    assert by[0x844]['uuid_bytes'].startswith('0254') and by[0x844]['permissions']==1
    assert by[0x847]['uuid_bytes'].startswith('0354') and by[0x847]['permissions']==0x90 and by[0x847]['max_length']==1
    for handle,wanted in [(0x842,0),(0x844,3),(0x847,5)]:
        u,r=run(raw,ram,c['permission'],[1,0x10,handle,by[handle]['permissions']])
        assert r['r0']==wanted,r
        rows.append(dict(kind='permission-helper-ABI',handle=handle,connection_id_argument=1,connection_active=False,returned=wanted,live_session_authorized=False))
    assert all(s['active']==0 for s in c['connection_slots'])
    tpl=packet(11,bytes([1,2,3,4]));pdu=bytes([0x52])+struct.pack('<H',0x842)+tpl
    hci_l2cap_prefix=bytes(8)
    for handle in (0x40,0x41):
        u,r=run(raw,ram,c['dm_lookup'],[handle]);assert r['r0']==0
        u,r=run(raw,ram,c['dispatch'],[handle,len(pdu),WORK+0x100],hci_l2cap_prefix+pdu)
        q=root['queue'];before=struct.unpack_from('<I',ram,q+0x38-SRAM)[0]
        assert struct.unpack('<I',u.mem_read(q+0x38,4))[0]==before
        assert bytes(u.mem_read(c['dm_global'],144))==ram[c['dm_global']-SRAM:c['dm_global']-SRAM+144]
        rows.append(dict(kind='no-active-connection-drop',hci_handle=handle,queue_delta=0,connection_state_unchanged=True,dispatcher_return_verified=True,eus_delivery_verified=False))
    if c['wrapper_fallback_call'] is not None:
        # Explicit callback ABI probe; connection admission is not exercised here.
        address=c['registered_write_callback'];payload=packet(11,bytes([1,2,3,4]));sp=WORK+0xf000
        u=cpu(raw,ram,sp);u.mem_write(WORK+0x100,payload)
        for k,v in enumerate([1,0x842,0x52,0]):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(k)),v)
        u.reg_write(arm.UC_ARM_REG_LR,STOP|1);u.mem_write(sp,struct.pack('<III',len(payload),WORK+0x100,by[0x842]['address']))
        u.emu_start(address|1,c['eus_callback'],count=400000)
        assert u.reg_read(arm.UC_ARM_REG_PC)==c['eus_callback']
        args=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(k))) for k in range(4)]+list(struct.unpack('<III',u.mem_read(u.reg_read(arm.UC_ARM_REG_SP),12)))
        assert args==[1,0x842,0x52,0,len(payload),WORK+0x100,by[0x842]['address']]
        rows.append(dict(kind='cfw-registered-wrapper-normal-fallback',args=args,connection_admission_tested=False,old_eus_body_executed=False))
        code=decode(raw,address,0x70)
        cmp=next(k for k,i in enumerate(code) if i.mnemonic=='cmp' and i.op_str=='r0, #0x12')
        target=next(i.operands[0].imm for i in code[cmp:cmp+8] if i.mnemonic=='beq')
        u=cpu(raw,ram,sp);payload=b'AN'+bytes(12);u.mem_write(WORK+0x100,payload)
        for k,v in enumerate([1,0x842,0x52,0]):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(k)),v)
        u.reg_write(arm.UC_ARM_REG_LR,STOP|1);u.mem_write(sp,struct.pack('<III',len(payload),WORK+0x100,by[0x842]['address']))
        u.emu_start(address|1,target,count=400000);assert u.reg_read(arm.UC_ARM_REG_PC)==target
        rows.append(dict(kind='cfw-AN-prefix-boundary',pc=target,connection_admission_tested=False,custom_command_completed=False))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
    if o.exists() or not o.is_relative_to(s) or s.is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Fresh private output required')
    o.mkdir(mode=0o700,parents=True);(o/'inspector.py').write_bytes(Path(__file__).read_bytes())
    proof=s/'display-root-source-05/report.json';pin=json.loads((s/'display-root-research-01/manifest.json').read_text());assert sha(proof)==pin['files'][str(proof.relative_to(s))]
    source=json.loads(proof.read_text());pins=json.loads((s/'tpl-request-research-01/manifest.json').read_text());rows=[]
    for case in ['stock24','stock23','cfw']:
        folder=s/'tpl-request-native-02'/case;capture=folder/'capture-files.json';assert sha(capture)==pins['files'][str(capture.relative_to(s))];files=json.loads(capture.read_text())['files']
        for n in ['main.bin','exports/sync-after-sram.bin']:assert sha(folder/n)==files[n]
        raw=(folder/'main.bin').read_bytes();ram=(folder/'exports/sync-after-sram.bin').read_bytes();root=next(r['contract'] for r in source['cases'] if r['case']==case)
        c=discover(raw,ram,root);tests=inspect(raw,ram,c,root);rows.append(dict(case=case,contract=c,rows=tests,main_sha256=sha(folder/'main.bin'),ram_sha256=sha(folder/'exports/sync-after-sram.bin')))
        (o/'partial.json').write_text(json.dumps(dict(cases=rows,complete=False),indent=2)+'\n')
    report=dict(passed=True,cases=rows,scenarios=sum(len(r['rows']) for r in rows),layer='isolated original ARM plus source/live snapshot analysis',active_connection_fabricated=False,security_state_changed=False,positive_att_delivery_verified=False,controller_runtime_event_supported=False,natural_main_complete=False,physical_hardware_access=False)
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,scenarios=report['scenarios'])))


if __name__=='__main__':main()
