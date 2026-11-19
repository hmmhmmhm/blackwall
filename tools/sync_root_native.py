"""Native TPL diagnostic support; saved auditing never calls the candidate builder."""
import hashlib
import json
from pathlib import Path
import re
import struct
from probe_display_root_ingress import packet
from probe_display_queue_producer import literal
from inspect_ambiq_target import decode
from sync_peer_roundtrip import bl_references,frame
from inspect_nema_blocking_wait import SRAM
from run_native_candidate import validate_semantics,finish_capture


def prepare(s,out,case,raw,c):
    proof=s/'display-root-source-05/report.json';pin=json.loads((s/'display-root-research-01/manifest.json').read_text())
    assert pin['passed'] and hashlib.sha256(proof.read_bytes()).hexdigest()==pin['files'][str(proof.relative_to(s))]
    row=next(r for r in json.loads(proof.read_text())['cases'] if r['case']==case)
    assert row['main_sha256']==hashlib.sha256(raw).hexdigest()
    root=dict(row['contract']);starts=bl_references(raw,c['start']);finishes=bl_references(raw,c['finish']);assert len(starts)==len(finishes)==1
    code=decode(raw,starts[0]-0x2a,0x2e)
    branches=[i.operands[0].imm for n,i in enumerate(code) if n>=2 and i.mnemonic=='blo' and code[n-1].mnemonic=='beq' and code[n-2].op_str=='r0, #2']
    assert len(branches)==1
    load=decode(raw,branches[0],4)[0];assert load.op_str.startswith('r2,')
    root.update(reply_callback=literal(raw,load),finish_return=finishes[0]+4,serialized=packet(11,bytes([1,2,3,4])).hex())
    (out/'tpl-source.json').write_bytes(proof.read_bytes())
    (out/'root-observer.cs').write_bytes((Path(__file__).parent/'renode-sync-root-observer.cs').read_bytes())
    with (out/'activation.cs').open('ab') as handle:handle.write(b'\n'+(out/'root-observer.cs').read_bytes())
    return root


def harness(code,load,call,record,c,ctx,root):
    load('r0',0);load('r1',0x21002000);load('r2',len(bytes.fromhex(root['serialized'])));call(root['ingress']);record(8)
    load('r0',0xc0ff3300);record(20)
    code.extend(['.global input_done','input_done:','nop'])
    load('r0',1);load('r1',4);load('r2',0);call(ctx['queue_new']);code.append('mov r4, r0')
    load('r1',0x21000200);load('r2',0);load('r3',0xffffffff);call(ctx['ui']['get'])


def inspect_root(s,out,p,r,ram,initial_same,destination):
    root=r['root'];source=p['root'];before=r['before'];context=root.get('context',[]);producers=root.get('producers',[]);inputs=root.get('inputs',[])
    descriptor=bytes(root.get('descriptor',[]));identifier=int.from_bytes(descriptor[:2],'little') if len(descriptor)==24 else -1
    body=struct.pack('<4H',0x901,11,0,4)+bytes([1,2,3,4]);expected=frame(identifier&0xffff,1,body).hex()
    new=r['dma']['transfers'][before['transfers']:];matching=[x for x in new if x['data']==expected]
    finish=root.get('finish_context',[]);owner=finish[1] if len(finish)==3 else r['current_tcb'];name=ram[owner+52-SRAM:owner+84-SRAM].split(b'\0',1)[0].decode()
    start=struct.unpack_from('<I',ram,owner+48-SRAM)[0];words=struct.unpack_from('<I',ram,owner+84-SRAM)[0]
    slot=struct.unpack_from('<I',ram,p['sync']['context_slot']-SRAM)[0];count=ram[slot+0x7158-SRAM];records=[slot+0x6430+24*k for k in range(count)]
    pending=[a for a in records if struct.unpack_from('<H',ram,a-SRAM)[0]==identifier]
    asm=(out/'harness.s').read_text();calls=[int(v,16) for v in re.findall(r'ldr r12, =0x([0-9a-f]+)\nblx r12',asm)]
    raw=(out/'main.bin').read_bytes()
    no_manual_calls=len(calls)==3 and calls[0]==(source['ingress']|1) and calls[-1]==(p['ui']['get']|1) and raw[(calls[1]&~1)-0x438000:(calls[1]&~1)-0x438000+10]==bytes.fromhex('f8b504000d0016000027')
    points=root.get('points',[]);finish_point=[x for x in points if x['kind']=='request-finished'];input_point=[x for x in points if x['kind']=='input-returned']
    point_bindings=len(finish_point)==len(input_point)==1 and finish_point[0]['pc']==source['finish_return'] and finish_point[0]['sp']==context[4] and finish_point[0]['tcb']==owner and input_point[0]['pc']==source['input_stop'] and input_point[0]['sp']==before['sp'] and input_point[0]['tcb']==before['current_tcb']
    node=struct.unpack_from('<I',descriptor,16)[0] if len(descriptor)==24 else 0
    packet_address=struct.unpack_from('<I',descriptor,8)[0] if len(descriptor)==24 else 0
    node_bound=SRAM<=node<SRAM+len(ram)-12 and SRAM<=packet_address<SRAM+len(ram)-12
    node_matches=node_bound and struct.unpack_from('<IHHI',ram,node-SRAM)==(source['sender_completion'],1,12,packet_address) and ram[packet_address-SRAM:packet_address-SRAM+12]==body
    checks=dict(initial_assets_unchanged=initial_same,main_unchanged=hashlib.sha256((out/'main.bin').read_bytes()).hexdigest()==p['main_sha256'],model_unchanged=hashlib.sha256((out/'strict.cs').read_bytes()).hexdigest()==p['model_sha256'],stopped=root['stopped'] and r['stopped'] and set(x['kind'] for x in points)=={'request-finished','input-returned'},input_return=r['mailbox'][2]==0 and r['mailbox'][5]==0xc0ff3300,input_caller_resumed=r['current_tcb']==before['current_tcb'] and r['sp']==before['sp'] and r['xpsr']&0x1ff==0,irq_context=r['bootstrap'][5:]==[0,0,0],input_entry=len(inputs)==1 and inputs[0][:3]==[0,0x21002000,len(bytes.fromhex(source['serialized']))],input_caller=len(inputs)==1 and inputs[0][3:5]==[before['sp'],before['current_tcb']] and inputs[0][5]&0x1ff==0,producer=len(producers)==1 and producers[0][:4]==[11,0x21002008,4,source['sender_completion']],one_selected_request=root['matches']==1,original_uart_thread=len(context)==7 and context[5]==owner and name=='uart_sync_thread' and context[6]&0x1ff==0,original_stack=len(context)==7 and len(finish)==3 and finish[0]==context[4] and start<=finish[0]<start+4*words and finish[2]&0x1ff==0,original_context=len(context)==7 and context[0]==slot and context[2]==source['reply_callback'],original_packet=bytes(root.get('packet',[]))==body,request_id=len(descriptor)==24 and identifier!=0 and len(pending)==1,pending_callback=len(pending)==1 and struct.unpack_from('<I',ram,pending[0]+4-SRAM)[0]==source['reply_callback'],dma_payload=len(matching)==1,dma_completed=r['dma']['completions']>=before['completions']+1 and r['dma']['phase']=='completed',uart_irq=r['uart_irq_entries']>before['irq_entries'] and r['uart_irq_vector']==31,no_fault=r['cfsr']==r['hfsr']==r['memory_violations']==0,no_unsupported=all(g['accesses']==0 for g in r['guards']),no_ui_input=r['ui_messages']==0)
    checks.update(no_manual_request_calls=no_manual_calls,phase_bindings=point_bindings,original_node_packet=node_matches,descriptor_header=len(descriptor)==24 and struct.unpack_from('<H',descriptor,4)[0]==1 and struct.unpack_from('<I',descriptor,12)[0]==12)
    spec=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['checks','main_unchanged'],['checks','model_unchanged'],['checks','initial_assets_unchanged']]),checks=[dict(path=['checks',key],eq=True) for key in checks],allowed_differences=['Serialized TPL input API caller in original Sensor context; original producer and UART task create heap/descriptor/ID/frame, no direct start/chunk/finish calls by harness.'],unresolved_differences=['No virtual BLE/ATT/security, reply cleanup, natural main completion or full UI. Observer neutrality unproven.'])
    validate_semantics(spec)
    result=dict(passed=all(checks.values()),case=p['case'],checks=checks,expected_frame=expected,observed_new_transfers=new,synthetic_api_stimulus=True,physical_transport=False,natural_main_complete=False,receive_tested=False,observed=r,boundary_kind='bounded-capture',execution_passed=True,selected_observation=dict(events=[dict(pc=r['pc'])] if root['stopped'] else [],sequence=1 if root['stopped'] else 0,dropped_events=0),schema=2)
    result=finish_capture(result,dict(checks=dict(main_unchanged=True,model_unchanged=True,initial_assets_unchanged=True)),spec);result['contract']=spec
    target=out if destination is None else destination
    if destination is not None:destination.mkdir(mode=0o700,parents=True)
    (target/'verification.json').write_text(json.dumps(result,indent=2)+'\n');return result
