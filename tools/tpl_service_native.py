"""Existing M55/RTC board and original BLE task; explicit serialized TPL API caller."""
import hashlib
import json
from pathlib import Path
import struct
import re
from datetime import datetime, timezone
from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import SRAM
from probe_display_root_ingress import packet
from probe_tpl_service_ingress import message
from sync_peer_roundtrip import bl_references
from run_native_candidate import finish_capture, validate_semantics


def prepare(s,out,case):
    proof=s/'tpl-service-source-02/report.json'
    pin=json.loads((s/'tpl-service-research-01/manifest.json').read_text())
    assert pin['passed'] and hashlib.sha256(proof.read_bytes()).hexdigest()==pin['files'][str(proof.relative_to(s))]
    row=next(r for r in json.loads(proof.read_text())['cases'] if r['case']==case)
    raw=(out/'main.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==row['main_sha256']
    root_proof=s/'display-root-source-05/report.json'
    root_pin=json.loads((s/'display-root-research-01/manifest.json').read_text())
    assert hashlib.sha256(root_proof.read_bytes()).hexdigest()==root_pin['files'][str(root_proof.relative_to(s))]
    root=next(r['contract'] for r in json.loads(root_proof.read_text())['cases'] if r['case']==case)
    c=dict(row['contract']);refs=bl_references(raw,c['consumer']);assert len(refs)==1
    assert decode(raw,refs[0],4)[0].mnemonic=='bl'
    c.update(consumer_return=refs[0]+4,clock_return=c['before_clock_apply']+4,
             ingress=root['ingress'],serialized=packet(128,message(1700000000,16),both=False).hex(),timestamp=1700000000,zone=16)
    (out/'service-source.json').write_bytes(proof.read_bytes())
    (out/'service-root-source.json').write_bytes(root_proof.read_bytes())
    observer=Path(__file__).parent/'renode-tpl-service-observer.cs'
    (out/'service-observer.cs').write_bytes(observer.read_bytes())
    with (out/'activation.cs').open('ab') as f:f.write(b'\n'+observer.read_bytes())
    board=(out/'board.repl').read_text();anchor='    halLowUpperWrites: false\n';assert board.count(anchor)==1
    (out/'board.repl').write_text(board.replace(anchor,'    halLowUpperWrites: true\n'))
    return c


def harness(code,load,call,record,c,ctx):
    load('r0',0);load('r1',0x21002000);load('r2',len(bytes.fromhex(c['serialized'])));call(c['ingress']);record(8)
    load('r0',0xc0ff3300);record(20)
    load('r0',1);load('r1',4);load('r2',0);call(ctx['queue_new']);code.append('mov r4, r0')
    load('r1',0x21000200);load('r2',0);load('r3',0xffffffff);call(ctx['ui']['get'])


def inspect(out,p,r,ram,initial_same,destination):
    c=p['service'];v=r['service'];before=r['before'];ret=v['returns'];cons=v['consumers'];applied=v['applied'];inputs=v['inputs']
    task=c['tcb'];name=ram[task+52-SRAM:task+84-SRAM].split(b'\0',1)[0].decode()
    stack,words=struct.unpack_from('<I',ram,task+48-SRAM)[0],struct.unpack_from('<I',ram,task+84-SRAM)[0]
    asm=(out/'harness.s').read_text();calls=[int(v,16) for v in re.findall(r'ldr r12, =0x([0-9a-f]+)\nblx r12',asm)]
    raw=(out/'main.bin').read_bytes()
    call_contract=len(calls)==3 and calls[0]==c['ingress']|1 and calls[2]==p['ui']['get']|1 and raw[(calls[1]&~1)-0x438000:(calls[1]&~1)-0x438000+10]==bytes.fromhex('f8b504000d0016000027')
    board=(out/'board.repl').read_text();profile=board.count('    halLowUpperWrites: true\n')==1 and '    halLowUpperWrites: false\n' not in board
    checks=dict(initial_assets_unchanged=initial_same,main_unchanged=hashlib.sha256((out/'main.bin').read_bytes()).hexdigest()==p['main_sha256'],model_unchanged=hashlib.sha256((out/'strict.cs').read_bytes()).hexdigest()==p['model_sha256'],
                stopped=v['stopped'] and r['pc']==c['consumer_return'],one_input=len(inputs)==1 and inputs[0][:3]==[0,0x21002000,len(bytes.fromhex(c['serialized']))],
                input_context=len(inputs)==1 and inputs[0][3]==before['sp'] and inputs[0][5]==before['current_tcb'] and inputs[0][6]&511==0,
                original_task=name=='ble_msgrx' and len(cons)==len(applied)==len(ret)==1 and all(x[5]==task and x[6]&511==0 for x in cons+applied+ret),
                stack_preserved=len(cons)==len(ret)==1 and cons[0][3]==ret[0][3] and all(stack<=x[3]<stack+4*words for x in cons+applied+ret),
                state=ram[c['state']-SRAM:c['state']-SRAM+5]==struct.pack('<IB',c['timestamp'],c['zone']),queue_empty=struct.unpack_from('<I',ram,c['queue']+0x38-SRAM)[0]==0,
                rtc_commit=v['rtc']['commits']==v['rtc_before']['commits']+1 and not v['rtc']['pending'] and v['rtc']['error']=='none',
                rtc_date=v['rtc']['date'].startswith(datetime.fromtimestamp(c['timestamp'],timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')),
                no_direct_consumer_clock_call=call_contract,rtc_write_profile_declared=profile,
                original_preemption_before_input_return=r['mailbox'][5]==0 and struct.unpack_from('<I',ram,task+44-SRAM)[0]>struct.unpack_from('<I',ram,before['current_tcb']+44-SRAM)[0],
                irq_context=r['bootstrap'][5:]==[0,0,0],no_fault=r['cfsr']==r['hfsr']==r['memory_violations']==0,
                no_unsupported=all(x['accesses']==0 for x in r['guards']))
    spec=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['checks','main_unchanged'],['checks','model_unchanged']]),checks=[dict(path=['checks',key],eq=True) for key in checks],allowed_differences=['Explicit TPL API stimulus in Sensor context after normal main hold; existing RTC counter-write profile enabled; original ble_msgrx scheduling/consumer/RTC apply.'],unresolved_differences=['No ATT device input, natural main completion, physical RTC fidelity, or observer neutrality proof.'])
    validate_semantics(spec)
    result=dict(schema=2,passed=all(checks.values()),case=p['case'],checks=checks,expected_frame='',observed=r,boundary_kind='bounded-capture',execution_passed=True,selected_observation=dict(events=[dict(pc=r['pc'])] if v['stopped'] else [],sequence=int(v['stopped']),dropped_events=0),natural_main_complete=False,device_att_input=False)
    result=finish_capture(result,dict(checks=dict(main_unchanged=True,model_unchanged=True)),spec);result['contract']=spec
    target=out if destination is None else destination
    if destination is not None:destination.mkdir(mode=0o700,parents=True)
    (target/'verification.json').write_text(json.dumps(result,indent=2)+'\n');return result
