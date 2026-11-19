"""Original phone transport bytes to sync schedule queue; isolated ARM, no BLE I/O."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct
from unicorn import UcError, UC_HOOK_MEM_INVALID
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import cpu, BASE, SRAM, WORK, STOP
from probe_display_queue_producer import literal
from sync_peer_roundtrip import bl_references

SIGNATURE=bytes.fromhex('2de9f04385b007000d00002d')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packet(app, payload, both=True):
    if not 0<=app<=255 or len(payload)>253:
        raise ValueError('Single TPL frame requires byte application ID and payload <=253')
    return bytes([0xaa,0,1,len(payload)+2,1,1,app,0x20 if both else 0])+payload+struct.pack('<H',binascii.crc_hqx(payload,0xffff))


def discover(raw, ram, stock_reference=None):
    assert raw.count(SIGNATURE)==1
    tpl=BASE+raw.index(SIGNATURE);body=decode(raw,tpl,0x500)
    table_candidates=[]
    for i in body:
        if not i.mnemonic.startswith('ldr'):continue
        try:value=literal(raw,i)
        except ValueError:continue
        after=decode(raw,i.address+i.size,2)
        if not after or after[0].op_str!='r0, [r7, #4]':continue
        assert SRAM<=value<SRAM+len(ram)-20
        table_candidates.append((i.address,value))
    assert len(table_candidates)==1
    table_load,table=table_candidates[0]
    both,peer=struct.unpack_from('<II',ram,table+4-SRAM)
    assert both&1 and peer&1
    calls=[i for i in decode(raw,table_load,0x24) if i.mnemonic=='blx']
    assert len(calls)==1 and calls[0].op_str=='r4'
    sender_completion=literal(raw,next(i for i in decode(raw,table_load,0x24) if i.mnemonic.startswith('ldr') and i.op_str.startswith('r3,')))
    crc_candidates=[]
    for i in body[:100]:
        if i.mnemonic=='bl':
            target=i.operands[0].imm
            if raw[target-BASE:target-BASE+8]==bytes.fromhex('70b40300002a02d1'):crc_candidates.append(target)
    assert len(crc_candidates)==1
    comparison=next(k for k,i in enumerate(body) if i.mnemonic=='cmp' and i.op_str=='sb, r8')
    assert body[comparison+1].mnemonic=='bne'
    queue_load=decode(raw,(both&~1)+0xe,4)[0]
    queue_slot=literal(raw,queue_load);queue=struct.unpack_from('<I',ram,queue_slot-SRAM)[0]
    assert SRAM<=queue<SRAM+len(ram)-80
    assert struct.unpack_from('<II',ram,queue+0x3c-SRAM)==(150,4)
    all_refs=bl_references(raw,tpl)
    expected=['r1, [sp, #0x1c]','r2, [sp, #0x18]','r2, r2','r0, #0']
    refs=[pc for pc in all_refs if [i.op_str for i in decode(raw,pc-8,12)[:4]]==expected]
    hook=None
    if not refs:
        assert stock_reference is not None and stock_reference['tpl']==tpl
        pc=stock_reference['eus_tpl_call'];ins=decode(raw,pc,4)[0]
        assert ins.mnemonic=='bl';hook=ins.operands[0].imm
        assert bl_references(raw,hook)==[pc]
        code=decode(raw,hook,0xc0)
        marker=next(k for k,i in enumerate(code) if i.mnemonic=='cmp' and i.op_str=='r3, #0xf0')
        assert code[marker+1].mnemonic=='bne'
        fallback=code[marker+1].operands[0].imm
        sequence=decode(raw,fallback,10)
        assert [i.mnemonic for i in sequence]==['movw','movt','bx'] and sequence[-1].op_str=='r3'
        address=sequence[0].operands[1].imm|(sequence[1].operands[1].imm<<16)
        assert address==tpl|1
        refs=[pc]
    assert len(refs)==1
    eus_candidates=[]
    for pc in range(refs[0]-0x80,refs[0],2):
        ins=decode(raw,pc,2)
        if ins and (ins[0].mnemonic,ins[0].op_str)==('push','{r0, r1, r2, r3, r4, lr}'):eus_candidates.append(pc)
    assert len(eus_candidates)==1
    # The callback's original stack arguments, not a fabricated protobuf API.
    prefix=decode(raw,refs[0]-8,12)
    assert [i.op_str for i in prefix[:4]]==['r1, [sp, #0x1c]','r2, [sp, #0x18]','r2, r2','r0, #0']
    return dict(tpl=tpl,ingress=hook or tpl,faceclaw_hook=hook,eus_callback=eus_candidates[0],eus_tpl_call=refs[0],callback_table=table,both=both&~1,peer=peer&~1,callback_return=calls[0].address+calls[0].size,sender_completion=sender_completion,crc=crc_candidates[0],crc_failure=body[comparison+1].operands[0].imm,queue_slot=queue_slot,queue=queue)


def invoke(raw, ram, c, data, *, end, size=None, entry=None, args=None):
    u=cpu(raw,ram,WORK+0xf000);u.mem_write(WORK+0x100,data)
    values=[0,WORK+0x100,len(data) if size is None else size] if args is None else args
    for k,value in enumerate(values):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(k)),value)
    u.reg_write(arm.UC_ARM_REG_LR,STOP|1);invalid=[]
    def reject(m,access,address,size,value,user):
        invalid.append(dict(address=address,access=access,pc=m.reg_read(arm.UC_ARM_REG_PC)));return False
    u.hook_add(UC_HOOK_MEM_INVALID,reject)
    error=None
    try:u.emu_start((c['ingress'] if entry is None else entry)|1,end,count=400000)
    except UcError as exc:error=str(exc)
    return u,dict(pc=u.reg_read(arm.UC_ARM_REG_PC),r0=u.reg_read(arm.UC_ARM_REG_R0),invalid=invalid,error=error)


def inspect_case(raw, ram, c):
    rows=[];q=c['queue'];before=struct.unpack_from('<I',ram,q+0x38-SRAM)[0];write_slot=struct.unpack_from('<I',ram,q+4-SRAM)[0]
    for app in (0x0b,6):
        for length in (0,4,16,253):
            payload=bytes((k*37+11)&255 for k in range(length));data=packet(app,payload)
            # Verify the independent CCITT encoder against the actual ARM helper.
            u,crc=invoke(raw,ram,c,payload,end=STOP,entry=c['crc'],args=[WORK+0x100,length,0])
            assert crc['pc']==STOP and not crc['invalid'] and crc['error'] is None and crc['r0']==binascii.crc_hqx(payload,0xffff)
            u,r=invoke(raw,ram,c,data,end=c['callback_return'])
            assert r['pc']==c['callback_return'] and not r['invalid'] and r['error'] is None and r['r0']==0,r
            node=struct.unpack('<I',u.mem_read(write_slot,4))[0]
            callback,kind,size,pointer=struct.unpack('<IHHI',u.mem_read(node,12))
            expected=struct.pack('<4H',0x901,app,0,length)+payload
            assert callback==c['sender_completion'] and kind==1 and size==8+length
            assert bytes(u.mem_read(pointer,len(expected)))==expected
            assert struct.unpack('<I',u.mem_read(q+0x38,4))[0]==before+1
            rows.append(dict(kind='valid',app=app,length=length,pc=r['pc'],queue_delta=1,node=node,packet=expected.hex(),crc=crc['r0']))
            if length:
                bad=bytearray(data);bad[-1]^=1
                u,r=invoke(raw,ram,c,bytes(bad),end=c['crc_failure'])
                assert r['pc']==c['crc_failure'] and not r['invalid'] and r['error'] is None,r
                assert struct.unpack('<I',u.mem_read(q+0x38,4))[0]==before
                rows.append(dict(kind='bad-crc-boundary',app=app,length=length,pc=r['pc'],queue_delta=0,error_handler_return_verified=False))
    # The route bit selects the already registered peer callback instead of Both.
    u,r=invoke(raw,ram,c,packet(11,b'1234',False),end=c['peer'])
    assert r['pc']==c['peer'] and not r['invalid'] and r['error'] is None
    assert struct.unpack('<I',u.mem_read(q+0x38,4))[0]==before
    rows.append(dict(kind='peer-route-entry-only',pc=r['pc'],queue_delta=0,peer_handler_executed=False))
    for kind,data,size,wanted in [('bad-marker',b'\x00'+packet(11,b'')[1:],None,10),('short-size',packet(11,b''),7,11)]:
        u,r=invoke(raw,ram,c,data,end=STOP,size=size)
        assert r['pc']==STOP and r['r0']==wanted and not r['invalid'] and r['error'] is None,r
        assert struct.unpack('<I',u.mem_read(q+0x38,4))[0]==before
        rows.append(dict(kind=kind,pc=r['pc'],returned=wanted,queue_delta=0))
    if c.get('faceclaw_hook'):
        code=decode(raw,c['faceclaw_hook'],0x24)
        marker=next(k for k,i in enumerate(code) if i.mnemonic=='cmp' and i.op_str=='r3, #0xf0')
        stop=code[marker+2].address
        u,r=invoke(raw,ram,c,packet(0xf0,b'1234'),end=stop)
        assert r['pc']==stop and not r['invalid'] and r['error'] is None
        assert struct.unpack('<I',u.mem_read(q+0x38,4))[0]==before
        rows.append(dict(kind='faceclaw-custom-route-boundary',service=0xf0,pc=r['pc'],queue_delta=0,custom_command_completed=False))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(s) or s.is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Fresh private output required')
    out.mkdir(mode=0o700,parents=True);(out/'inspector.py').write_bytes(Path(__file__).read_bytes());rows=[]
    pin=json.loads((s/'uart0-rx-jbd-research-01/manifest.json').read_text())
    for case in ('stock24','stock23','cfw'):
        src=s/'uart0-rx-jbd-native-01'/case;capture=src/'capture-files.json';assert sha(capture)==pin['files'][str(capture.relative_to(s))]
        files=json.loads(capture.read_text())['files']
        for name in ('main.bin','exports/sync-after-sram.bin'):assert sha(src/name)==files[name]
        raw=(src/'main.bin').read_bytes();ram=(src/'exports/sync-after-sram.bin').read_bytes();c=discover(raw,ram,rows[1]['contract'] if case=='cfw' else None)
        cases=inspect_case(raw,ram,c)
        if case=='stock23':
            data=packet(0xf0,b'1234');u,r=invoke(raw,ram,c,data,end=c['callback_return'])
            assert r['pc']==c['callback_return'] and r['r0']==0 and not r['invalid'] and r['error'] is None
            q=c['queue'];before=struct.unpack_from('<I',ram,q+0x38-SRAM)[0]
            assert struct.unpack('<I',u.mem_read(q+0x38,4))[0]==before+1
            cases.append(dict(kind='stock-custom-service-generic-route',service=0xf0,pc=r['pc'],queue_delta=1))
        rows.append(dict(case=case,main_sha256=sha(src/'main.bin'),ram_sha256=sha(src/'exports/sync-after-sram.bin'),contract=c,rows=cases))
        (out/'partial.json').write_text(json.dumps(dict(cases=rows,complete=False),indent=2)+'\n')
    result=dict(passed=True,cases=rows,scenarios=sum(len(r['rows']) for r in rows),layer='isolated original ARM TPL/API; source SRAM from native captures',natural_main_complete=False,physical_ble=False,root_device_input_proven=False,request_id_generation_executed=False,shell_candidate_rejected=True)
    (out/'inspector.py').write_bytes(Path(__file__).read_bytes());(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,scenarios=result['scenarios'])))


if __name__=='__main__':main()
