"""Audit current linked display waits and large IMU getter without inventing ROM data."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_nema_irq_contract import discover_irq
from inspect_nema_blocking_wait import cpu,WORK,STOP
from inspect_em9305_hci_framing import literal
from prepare_vendor_startup_candidate import sha

SRAM=0x20000000


def linked_graph(data,current):
    valid=lambda p,n=4:p%4==0 and SRAM<=p<=SRAM+len(data)-n
    def word(p):
        assert valid(p);return struct.unpack_from('<I',data,p-SRAM)[0]
    candidates=[];excluded=[]
    for offset in range(0,len(data)-112,4):
        a=SRAM+offset
        if word(a+16)!=a or word(a+36)!=a:continue
        saved,stack,priority,depth=word(a),word(a+48),word(a+44),word(a+84)
        if not(priority<256 and valid(stack) and valid(saved,40) and 0<depth<=0x100000 and stack<=saved<stack+depth*4<=SRAM+len(data)):continue
        row=dict(tcb=a,name=data[offset+52:offset+84].split(b'\0',1)[0].decode('ascii',errors='replace'),saved_sp=saved,stack_base=stack,priority=priority,state_container=word(a+20),current=a==current)
        if row['state_container']==0:
            assert a!=current;excluded.append(dict(**row,reason='No linked state-list membership; not treated as an active task'))
        else:candidates.append(row)
    by_tcb={x['tcb']:x for x in candidates};assert current in by_tcb
    containers={}
    for t in candidates:
        co=t['state_container'];assert valid(co,20)
        if co not in containers:
            count=word(co);assert 1<=count<=128 and word(co+8)==0xffffffff
            sentinel=co+8;node=word(co+12);nodes=[];owners=[]
            while node!=sentinel:
                assert node not in nodes and len(nodes)<count
                nxt,prev,owner=word(node+4),word(node+8),word(node+12)
                assert word(nxt+8)==node and word(prev+4)==node and owner in by_tcb and node==owner+4 and word(node+16)==co
                nodes.append(node);owners.append(owner);node=nxt
            assert len(nodes)==count and word(co+4) in nodes+[sentinel];containers[co]=dict(count=count,owners=owners)
        assert t['tcb'] in containers[co]['owners']
        if not t['current']:assert word(t['saved_sp'])==t['stack_base'] and word(t['saved_sp']+4)&0xffffff00==0xffffff00
    return dict(tasks=candidates,excluded_unlinked_candidates=excluded,containers=containers,current=by_tcb[current])


def display_waits(raw,data,graph):
    w=lambda p:struct.unpack_from('<I',data,p-SRAM)[0];rows=[]
    for t in graph['tasks']:
        name=t['name']
        if name not in ['ui_task','displaydrv_mgr_task','ambiqdraw']:continue
        assert not t['current'];sp=t['saved_sp'];exc=w(sp+4);extended=exc&16==0;core=sp+40+(64 if extended else 0)
        hardware=[w(core+4*k) for k in range(8)];assert hardware[7]&0x01000000 and hardware[7]&0x1ff==0 and 0x438000<=hardware[6]<0x438000+len(raw)
        saved=[w(sp+8+4*k) for k in range(8)];event=w(t['tcb']+40)
        row=dict(name=name,tcb=t['tcb'],saved_pc=hardware[6],saved_lr=hardware[5],event_container=event,notify_value=w(t['tcb']+0x68),notify_state=data[t['tcb']+0x6c-SRAM])
        if name in ['ui_task','displaydrv_mgr_task']:
            item=12 if name=='ui_task' else 36
            q=event-0x24;assert saved[2]==q and w(q+0x24)==1 and w(q+0x38)==0 and w(q+0x3c)==96 and w(q+0x40)==item
            row.update(kind='queue receive',queue=q,messages=0,receivers=1,capacity=96,item_bytes=item)
        else:
            assert event==0 and row['notify_state']==1 and row['notify_value']==0 and saved[0]==0
            caller=core+32+(72 if extended else 0)+(4 if hardware[7]&0x200 else 0);matches=[]
            for k in range(16):
                ret=w(caller+4*k)
                if ret&1==0 or not 0x438004<=ret<0x438000+len(raw):continue
                ins=decode(raw,(ret&~1)-4,4)
                if len(ins)!=1 or ins[0].mnemonic!='bl':continue
                target=ins[0].operands[0].imm;ops=[i.op_str for i in decode(raw,target,20)]
                if name=='ambiqdraw' and all(x in ops for x in ['r4, r0','r5, r1','r6, r2']):
                    assert saved[1:3]==[1,0xffffffff];matches.append(dict(kind='notification counter',index=0,clear_on_exit=1,ticks=0xffffffff,call=(ret&~1)-4,target=target))
                if name=='displaydrv_mgr_task' and all(x in ops for x in ['r4, r0','r8, r1','r7, r2','r5, r3']):
                    assert saved[3]==0x800000;matches.append(dict(kind='notification bits',index=0,mask=0x800000,call=(ret&~1)-4,target=target))
            assert len(matches)==1;row.update(matches[0])
        rows.append(row)
    assert len(rows)==3;return rows


def getter_run(raw,ram,entry,read,seed,status):
    u=cpu(raw,ram,WORK+0xf000);p=WORK+0x200;size=0xa8;u.mem_write(p,b'\xa5'*size);u.reg_write(arm.UC_ARM_REG_R0,WORK+0x100);u.reg_write(arm.UC_ARM_REG_R1,p);fields=[];trace=[];expected=bytearray(b'\xa5'*size)
    def code(c,pc,n,user):
        trace.append(pc)
        if pc!=read:return
        args=[c.reg_read(getattr(arm,'UC_ARM_REG_R'+str(k))) for k in range(4)];assert args[0]==WORK+0x100
        _,address,length,ptr=args;off=ptr-p;assert 1<=length<=12 and 0<=off<=size-length
        payload=bytes(((address+k)^seed)&255 for k in range(length));c.mem_write(ptr,payload);expected[off:off+length]=payload;fields.append(dict(address=address,length=length,offset=off))
        c.reg_write(arm.UC_ARM_REG_R0,status);c.reg_write(arm.UC_ARM_REG_PC,c.reg_read(arm.UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(entry|1,STOP,count=20000)
    expected[0xa0:0xa8]=struct.pack('<II',5000,2500);after=bytes(u.mem_read(p,size))
    assert u.reg_read(arm.UC_ARM_REG_PC)==STOP and u.reg_read(arm.UC_ARM_REG_SP)==WORK+0xf000 and u.reg_read(arm.UC_ARM_REG_R0)==status and len(fields)==41 and after==expected
    return dict(seed=seed,status=status,fields=fields,buffer_hex=after.hex(),instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())


def caller_prefix(raw,ram,ret,helper,initial,status,gyro):
    sp=WORK+0xe000;p=sp+0x8c;u=cpu(raw,ram,sp);u.mem_write(p,initial)
    for k,v in [(0,status),(4,0),(5,WORK+0x100),(6,gyro)]:u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(k)),v)
    # First call is the helper boundary; all preceding stores execute as original.
    instructions=decode(raw,ret,0x38);call=next(i for i in instructions if i.mnemonic=='bl');assert call.operands[0].imm==helper
    word_load=next(i for i in instructions if i.mnemonic.startswith('ldr') and i.op_str.startswith('r0, [pc,'));slot=literal(raw,word_load);global_value=struct.unpack_from('<I',ram,slot-SRAM)[0]
    trace=[]
    def code(c,pc,n,user):
        trace.append(pc)
        if pc==helper:c.emu_stop()
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(ret|1,STOP,count=10000)
    assert u.reg_read(arm.UC_ARM_REG_PC)==helper
    expected=bytearray(initial);expected[0]=1;expected[4:8]=struct.pack('<I',global_value);expected[8:12]=struct.pack('<I',40000 if gyro&255 else 0)
    assert bytes(u.mem_read(p,len(initial)))==expected
    return dict(status=status,gyro=gyro,overlaid_ranges=[[0,1],[4,4],[8,4]],global_value=global_value,remaining_buffer_preserved=True,instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())


def wrapper_run(raw,ram,entry,root,status,mode):
    # Actual initializer wrapper; root device init and locking helpers are ABI stubs.
    b=decode(raw,entry,0x46);calls=[i for i in b if i.mnemonic=='bl'];assert len(calls)==5 and calls[3].operands[0].imm==root
    targets={i.operands[0].imm for i in calls};u=cpu(raw,ram,WORK+0xf000);u.reg_write(arm.UC_ARM_REG_R0,mode);requests=[]
    def code(c,pc,n,user):
        if pc not in targets:return
        requests.append(pc);c.reg_write(arm.UC_ARM_REG_R0,status if pc==root else 0);c.reg_write(arm.UC_ARM_REG_PC,c.reg_read(arm.UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(entry|1,STOP,count=10000)
    valid=(mode&255)<5;assert u.reg_read(arm.UC_ARM_REG_PC)==STOP and u.reg_read(arm.UC_ARM_REG_SP)==WORK+0xf000
    assert requests==([i.operands[0].imm for i in calls] if valid else [])
    returned=u.reg_read(arm.UC_ARM_REG_R0);assert returned==(0 if valid else 0xffffffff)
    return dict(mode=mode,root_status=status,returned=returned,root_status_not_propagated=valid,calls=requests)


def inspect(s,case):
    manifest=json.loads((s/'imu-powersave-verification-01/manifest.json').read_text());assert manifest['passed'];ap=s/'imu-powersave-saved-audit-01'/case/'report.json';assert sha(ap)==manifest['files'][str(ap.relative_to(s))]
    audit=json.loads(ap.read_text());f=Path(audit['capture'])
    for n,pin in audit['capture_hashes'].items():assert sha(f/n)==pin
    r=json.loads((f/'report.json').read_text());raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();sp=r['observed']['register_context']['r13'];word=lambda off:struct.unpack_from('<I',ram,sp+off-SRAM)[0]&~1
    ret=word(0x10c);get_call=decode(raw,ret-4,4)[0];assert get_call.mnemonic=='bl';entry=get_call.operands[0].imm
    decoded=decode(raw,entry,0x1000);end=next(i.address for i in decoded if i.mnemonic in ['pop','pop.w'] and 'pc' in i.op_str);b=[i for i in decoded if i.address<=end];assert b[0].op_str=='{r4, r5, r6, lr}'
    calls=[i for i in b if i.mnemonic=='bl'];assert len(calls)==41 and word(0xfc)==calls[0].address+4 and len({i.operands[0].imm for i in calls})==1
    runs=[getter_run(raw,ram,entry,calls[0].operands[0].imm,seed,status) for seed in [0,0x5a,0xff] for status in [0,0xfffffffd]]
    helper=next(i.operands[0].imm for i in decode(raw,ret,0x38) if i.mnemonic=='bl')
    prefixes=[caller_prefix(raw,ram,ret,helper,bytes.fromhex(row['buffer_hex']),row['status'],gyro) for row in runs for gyro in [0,1]]
    root_return=word(0x264);root_call=decode(raw,root_return-4,4)[0];assert root_call.mnemonic=='bl';root=root_call.operands[0].imm;prologue=decode(raw,root,6)
    assert prologue[0].op_str=='{r4, r5, r6, r7, r8, sb, sl, fp, lr}' and prologue[1].op_str=='sp, #0x134'
    outer_return=word(0x274);outer_call=decode(raw,outer_return-4,4)[0];assert outer_call.mnemonic=='bl';wrapper=outer_call.operands[0].imm;assert decode(raw,wrapper,2)[0].op_str=='{r3, r4, r5, lr}'
    wrapper_cases=[wrapper_run(raw,ram,wrapper,root,status,mode) for status in [0,0xfffffffd,0xffffffff] for mode in [0,4,5,255,256]]
    root_body=decode(raw,root,0x1800);footer=next(k for k,i in enumerate(root_body[:-1]) if i.op_str=='sp, #0x134' and i.mnemonic=='add' and root_body[k+1].mnemonic in ['pop','pop.w']);root_end=root_body[footer+1].address
    remaining_calls=[dict(pc=i.address,target=i.operands[0].imm) for i in root_body if ret<=i.address<=root_end and i.mnemonic=='bl']
    contract=discover_irq(raw);current=struct.unpack_from('<I',ram,contract['current_tcb_slot']-SRAM)[0];graph=linked_graph(ram,current);assert graph['current']['name']=='sensor_hub';waits=display_waits(raw,ram,graph)
    return dict(case=case,source_audit_sha256=sha(ap),current_task=graph['current'],graph=graph,display_waits=waits,getter=entry,getter_end=end,fields=runs[0]['fields'],getter_runs=runs,caller_prefixes=prefixes,
                active_stack_binding=dict(getter_caller_return=ret,root_initializer=root,root_return=root_return,wrapper=wrapper,wrapper_return=outer_return),wrapper_cases=wrapper_cases,remaining_static_call_sites=remaining_calls,
                ui_start_requires_successful_imu_init_proven=False,imu_completion_alone_starts_ui_proven=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists() and a.output.resolve().is_relative_to(a.simulator.resolve())
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];a.output.mkdir(mode=0o700);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());n=sum(len(x[k]) for x in rows for k in ['getter_runs','caller_prefixes','wrapper_cases'])
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_scenarios=n,display_tasks_inspected=9,source_callees_stubbed=True,native_rerun=False,hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n');print('Startup/UI audit: original ARM scenarios',n,'display waits9; no native rerun')
if __name__=='__main__':main()
