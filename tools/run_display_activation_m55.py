"""API-driven original M55 UI/display activation diagnostic, not complete main boot."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(simulator, capture, destination):
    """Inspect real captures and original task ownership, without rerunning firmware."""
    from inspect_nema_irq_contract import discover_irq
    assert not destination.exists(), 'Preserve prior evidence'
    p = json.loads((capture/'profile.json').read_text())
    case = p['case']
    assert case in ['stock24', 'stock23', 'cfw'] and p['message_type'] in [2, 3]
    parent = simulator/'imu-powersave-main-01'/case
    assert sha(parent/'derived-inputs.json') == p['source_meta_sha256']
    meta = json.loads((parent/'derived-inputs.json').read_text())
    from run_native_candidate import validate_assets
    validate_assets(parent, meta['derived'])
    original_raw = (parent/'main.bin').read_bytes()
    is_original = 'firmware_candidate' not in p
    candidate_checks = {}
    if is_original:
        assert not (capture/'firmware-candidate.json').exists(), 'Missing candidate profile'
        assert (capture/'main.bin').read_bytes() == original_raw
    else:
        from display_firmware_candidate import inspect as inspect_candidate
        candidate_checks = inspect_candidate(capture, p, original_raw)
    if p.get('jbd_status_hex'):
        component=p['status_component']
        baseline=simulator/component['baseline']
        candidate=capture/'mspi0-status-component.cs'
        proof=capture/'status-source.json'
        assert sha(baseline)==component['baseline_sha256'] and sha(candidate)==component['candidate_sha256']
        assert sha(proof)==p['status_source_sha256']
        original=(parent/'strict.cs').read_bytes();old=baseline.read_bytes()
        assert original.count(old)==1
        expected_strict=original.replace(old,candidate.read_bytes())
        if p.get('gpu_runtime_component'):
            runtime=p['gpu_runtime_component'];old_gpu=simulator/runtime['baseline'];new_gpu=capture/'gpu-runtime-component.cs'
            assert sha(old_gpu)==runtime['baseline_sha256'] and sha(new_gpu)==runtime['candidate_sha256']
            assert expected_strict.count(old_gpu.read_bytes())==1
            expected_strict=expected_strict.replace(old_gpu.read_bytes(),new_gpu.read_bytes())
        for extra in p.get('gpu_ring_components',[]):
            component_file=capture/extra['file'];assert sha(component_file)==extra['sha256']
            expected_strict+=b'\n'+component_file.read_bytes()
        assert (capture/'strict.cs').read_bytes()==expected_strict
        assert sha(capture/'strict.cs')==component['derived_strict_sha256']
        status_proof=json.loads(proof.read_text());assert status_proof['passed']
        status_row=next(x for x in status_proof['cases'] if x['case']==case)
        assert status_row['raw_sha256']==sha(parent/'main.bin')
    else:
        assert sha(capture/'strict.cs') == sha(parent/'strict.cs')
    ui = p['contract']
    d = p['display']
    raw = (capture/'main.bin').read_bytes()
    slot = discover_irq(raw)['current_tcb_slot']
    before = (capture/'exports/sram-full.bin').read_bytes()
    after = (capture/'exports/ui-after-sram.bin').read_bytes()
    first = json.loads((capture/'exports/activation.json').read_text())
    word = lambda data, address: struct.unpack_from('<I', data, address-0x20000000)[0]
    display_tcb = word(before, d['context']+8)
    def role(data, tcb, name, point):
        start = word(before, tcb+48)
        end = start+4*word(before, tcb+84)
        assert before[tcb+52-0x20000000:tcb+84-0x20000000].split(b'\0', 1)[0].decode() == name
        return (point['current_tcb'] == tcb == word(data, slot)
                and start <= point['sp'] < end and point['sp'] % 8 == 0
                and point['xpsr'] & 0x1ff == 0 and bool(point['xpsr'] & 0x1000000))
    kind = p['message_type']
    expected_pc = ui['display_on_producer']+0x24 if kind == 2 else p['negative_stop']
    expected_state = 1 if kind == 2 else 0
    bootstrap = first['bootstrap']
    sensor_tcb = word(before, slot)
    sensor_base = word(before, sensor_tcb+48)
    sensor_end = sensor_base+4*word(before, sensor_tcb+84)
    checks = dict(
        stopped_at_original_boundary=first['stopped'] and first['pc'] == expected_pc,
        real_ui_task=role(after, ui['ui_tcb'], 'ui_task', first),
        original_ui_state_transition=before[ui['state_slot']-0x20000000] == 0 and after[ui['state_slot']-0x20000000] == expected_state == first['ui_state'],
        original_message=after[ui['message_buffer']-0x20000000:ui['message_buffer']-0x20000000+12] == struct.pack('<III', kind, 0x10b, 0),
        source_thread_irq_context=len(bootstrap) >= 10 and bootstrap[7:10] == [0, 0, 0] and bootstrap[4] & 2 != 0,
        source_stack_not_replaced=len(bootstrap) >= 10 and sensor_base <= bootstrap[2] < sensor_end and bootstrap[5] == sensor_base,
        no_cpu_fault=first['cfsr'] == first['hfsr'] == first['memory_policy_violations'] == 0,
        no_unsupported_peripheral=all(x['accesses'] == 0 for x in first['guards']),
        display_queue_matches=word(after, d['queue']+0x38) == first['display_messages'] == (1 if kind == 2 else 0),
        mode_before=word(before, d['mode_slot']) == word(after, d['mode_slot']) == 0,
    )
    checks.update(candidate_checks)
    assembly = (capture/'harness.s').read_text().lower()
    checks['caller_has_no_ui_jump_or_context_override'] = ('msr ' not in assembly and 'cpsid' not in assembly
        and 'cpsie' not in assembly and 'bx r12' not in assembly and assembly.count('blx r12') == 3)
    if kind == 2:
        on = json.loads((capture/'exports/display-on.json').read_text())
        on_ram = (capture/'exports/display-after-sram.bin').read_bytes()
        checks.update(real_display_task=role(on_ram, display_tcb, 'displaydrv_mgr_task', on),
                      stopped_after_original_mode_write=on['stopped'] and on['pc'] == d['consumer_return']+0x7c,
                      original_display_mode_on=word(on_ram, d['mode_slot']) == on['mode'] == 1,
                      display_no_cpu_fault=on['cfsr'] == on['hfsr'] == on['memory_policy_violations'] == 0)
        checks['original_preparation_helpers'] = all(pc in first['events'] for pc in ui['preparation_helpers'])
    else:
        checks['no_activation_helpers'] = not any(pc in first['events'] for pc in ui['preparation_helpers'][1:])
        checks['display_receiver_still_waiting'] = word(after, d['queue']+0x24) == 1
    report = dict(passed=all(checks.values()), case=case, message_type=kind, checks=checks,
                  source_models_and_main_unchanged=is_original and not bool(p.get('jbd_status_hex')), main_bytes_unmodified=is_original, changed_model_components=(1+bool(p.get('gpu_runtime_component'))+len(p.get('gpu_ring_components',[]))) if p.get('jbd_status_hex') else 0, original_tasks_resumed=checks['real_ui_task'] and checks.get('real_display_task',True),
                  synthetic_api_stimulus=True, sensor_initialization_complete=False,
                  natural_main_complete=False, frame_pixels_verified=False, hardware_accessed=False,
                  files={str(f.relative_to(capture)): sha(f) for f in capture.rglob('*') if f.is_file()})
    if not is_original:
        report.update(firmware_candidate=p['firmware_candidate'], selected_image_unchanged=True)
    if 'content' in p:
        content=discover_content_contract(raw,ui,before)
        assert content==p['content'], 'Changed source content contract'
        trace=json.loads((capture/'exports/content-trace.json').read_text())
        final=(capture/'exports/content-after-sram.bin').read_bytes()
        from inspect_ambiq_target import discover as draw_entries
        from inspect_nema_submission import discover_submission
        draw=draw_entries(raw);gpu=discover_submission(raw)
        expected_watches={name:content[name] for name in ['dispatch','callback','return_site']}
        expected_watches.update(draw=draw['dispatch'],target=draw['target'],submit=gpu['submit'],ring_submit=gpu['ring_submit'],display_producer=d['producer'],frame_wrapper=d['wrapper'])
        if p.get('jbd_status_hex'):
            expected_watches.update(display_status=status_row['entry'],display_status_return=status_row['return_checkpoint'])
        assert p['content_watches']==expected_watches
        assert all(trace['points'][name]['pc']==pc for name,pc in expected_watches.items())
        points=trace['points'];dispatch=points['dispatch']['first'];callback=points['callback']['first'];returned=points['return_site']['first']
        valid_samples=all(len(sample)==7 for sample in [dispatch,callback,returned])
        context=word(on_ram,content['context_slot'])
        ui_stack=word(before,ui['ui_tcb']+48);ui_end=ui_stack+4*word(before,ui['ui_tcb']+84)
        content_checks=dict(
            ui_stack_at_content_points=valid_samples and all(ui_stack<=sample[4]<ui_end for sample in [dispatch,callback,returned]),
            original_ui_dispatch=valid_samples and dispatch[:4]==[content['app_id'],2,content['payload_buffer'],0],
            original_callback_arguments=valid_samples and callback[:4]==[2,content['payload_buffer'],0,word(on_ram,context+0x1c)],
            callback_return_order=valid_samples and dispatch[6]<=callback[6]<returned[6],
            registered_callback=points['callback']['pc']==content['callback'] and points['callback']['hits']>=1,
            original_root_published=0x20000000<=word(final,content['descriptor']+4)<0x20380000,
            no_cpu_or_memory_fault=trace['cfsr']==trace['hfsr']==trace['memory_policy_violations']==0)
        report['content']=dict(checks=content_checks,ui_dispatch_verified=all(content_checks.values()),
            frame_wrapper_observed=points['frame_wrapper']['hits']>0,submit_completed=False,gpu_work_consumed=False,
            draw_observed=points['draw']['hits']>0,submit_observed=points['submit']['hits']>0,
            unsupported=[g for g in trace['guards'] if g['accesses']>0],
            post_mode1_supported=not any(g['accesses']>0 for g in trace['guards']),
            observer_neutrality_proven=False,frame_pixels_verified=False)
        report['passed']=report['passed'] and report['content']['ui_dispatch_verified']
        renderer=prepare_context(simulator,case,2)['renderer_task']
        renderer_tcb=renderer['tcb'];renderer_base=word(before,renderer_tcb+48)
        renderer_end=renderer_base+4*word(before,renderer_tcb+84)
        draw_sample=points['draw']['first'];target_sample=points['target']['first']
        task_name=before[renderer_tcb+52-0x20000000:renderer_tcb+84-0x20000000].split(b'\0',1)[0].decode()
        renderer_checks=dict(captured_original_task=task_name=='ambiqdraw' and renderer_base==renderer['stack_base'],
            real_current_renderer=trace['current_tcb']==word(final,slot)==renderer_tcb,
            draw_and_target_called=len(draw_sample)==len(target_sample)==7 and points['draw']['hits']>=1 and points['target']['hits']>=1,
            original_task_stack=len(draw_sample)==len(target_sample)==7 and all(renderer_base<=v[4]<renderer_end and v[4]%8==0 for v in [draw_sample,target_sample]),
            original_draw_order=len(draw_sample)==len(target_sample)==7 and draw_sample[6]<target_sample[6])
        if p.get('content_observer_version')==2:
            del renderer_checks['real_current_renderer']
            renderer_checks['renderer_at_sample_points']=all(points[name].get('tcb')==renderer_tcb for name in ['draw','target'])
        report['renderer']=dict(verified=all(renderer_checks.values()),checks=renderer_checks,tcb=renderer_tcb,name=task_name,
            stack_base=renderer_base,stack_end=renderer_end,full_frame_verified=False)
        report['pending_submission']=dict(verified=False,gpu_work_consumed=False)
        if p.get('gpu_ring_components'):
            consumed=trace.get('gpu_ring',{})
            if 'gpu_quad_coverage' in p:assert consumed.get('coverage_profile')==p['gpu_quad_coverage']
            report['gpu_ring']=dict(observed=consumed,work_consumed=consumed.get('lists_consumed',0)>0 and consumed.get('pixels_written',0)>0,
                live_completion_id_observed=consumed.get('completion_events',0)>0,full_frame_verified=False)
            report['gpu_ring'].update(coverage_profile=p.get('gpu_quad_coverage','strict'),physical_msaa_verified=False)
            report['content']['gpu_work_consumed']=report['gpu_ring']['work_consumed']
            report['content']['post_mode1_supported']=report['content']['post_mode1_supported'] and not consumed.get('rejections',0)
            if consumed.get('frame_width',0):
                frame_path=capture/'exports/gpu-last-frame.bin';frame_data=frame_path.read_bytes()
                assert len(frame_data)==consumed['frame_stride']*consumed['frame_height']
                assert 0<consumed['frame_width']<=consumed['frame_stride']<=4096 and 0<consumed['frame_height']<=1024
                report['gpu_ring']['captured_surface']=dict(address=consumed['frame_address'],width=consumed['frame_width'],height=consumed['frame_height'],stride=consumed['frame_stride'],sha256=sha(frame_path),nonzero_bytes=sum(v!=0 for v in frame_data),full_ui_verified=False)
        doorbells=[g for g in trace['guards'] if g['accesses'] and g['address']==0x400900ec and g['operation']=='write']
        ring_sample=points['ring_submit']['first']
        if len(doorbells)==1 and len(ring_sample)==7:
            doorbell=doorbells[0]['value'];packet=(doorbell&~7)-16
            if doorbell&7==4 and 0x20000000<=packet<=0x20380000-16:
                header=[word(final,packet+4*k) for k in range(4)]
                address,length=ring_sample[:2]
                if header==[0xf0,address,0x200f4,length] and 0<length<=65536 and 0x20000000<=address and address+4*length<=0x20380000:
                    commands=final[address-0x20000000:address-0x20000000+4*length]
                    report['pending_submission']=dict(verified=True,packet_address=packet,doorbell=doorbell,header=header,
                        list_address=address,word_count=length,commands_sha256=hashlib.sha256(commands).hexdigest(),
                        command_words=list(struct.unpack('<'+'I'*length,commands)),gpu_work_consumed=False,submit_completed=False)
        if p.get('jbd_status_hex'):
            from run_native_candidate import finish_capture,validate_semantics
            selected=trace.get('jbd_status',{})
            replies=bytes.fromhex(p['jbd_status_hex'])
            expected_frames=[dict(instruction=5,control=0x10441,payload=replies[:1].hex())]
            if replies[0]!=0x90:expected_frames.append(dict(instruction=0x35,control=0x10441,payload=replies[1:].hex()))
            frames=selected.get('frames',[])
            returned=points['display_status_return']['first']
            expected_return=0xffffffff if replies[0]==0x90 or replies[1]==0 else 0
            report['status_diagnostics']=dict(profile=selected.get('profile'),
                sequence_matches=frames[:len(expected_frames)]==expected_frames,
                source_return_matches=len(returned)==7 and returned[0]==expected_return,
                expected_return=expected_return,observed_return=returned[0] if returned else None,
                expected_frames=expected_frames,frames=frames)
            report['boundary_kind']='bounded-capture';report['observed']=trace
            events=[dict(name=name,pc=v['pc'],first=v['first'],hits=v['hits']) for name,v in points.items() if v['hits']]
            report['selected_observation']=dict(events=events,sequence=len(events),
                dropped_events=sum(len(v['first'])!=7 for v in points.values() if v['hits']),policy='first-sample-per-declared-PC-plus-hit-count')
            if p.get('gpu_runtime_component'):
                wake=trace.get('gpu_runtime',{});response=p['gpu_runtime_component']['response']
                expected_state=(wake.get('phase')=='on') if response==1 else wake.get('phase') in ['stuck-off','cancelled']
                report['runtime_diagnostics']=dict(wake_verified=wake.get('response')==response and wake.get('cycles',0)>=1 and wake.get('prep_steps')==18 and expected_state,observed=wake)
            spec=p['status_semantics'];validate_semantics(spec)
            invariants=dict(main_bytes_unmodified=is_original,original_tasks_resumed=True)
            if not is_original:invariants['selected_image_unchanged']=True
            report=finish_capture(report,invariants,spec)
            report['passed']=report['passed'] and all(checks.values())

    destination.mkdir(mode=0o700,parents=True)
    (destination/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (destination/'auditor.py').write_bytes(Path(__file__).read_bytes())
    return report


def prepare_context(s, case, kind):
    from inspect_nema_irq_contract import discover_irq
    from inspect_ambiq_target import decode
    from probe_ui_queue_producer import discover
    from probe_display_queue_producer import UI_PREFIX
    proof_path = s/'display-activation-source-04/report.json'
    verification = json.loads((s/'display-activation-verification-01/manifest.json').read_text())
    assert verification['passed'] and sha(proof_path) == verification['files'][str(proof_path.relative_to(s))]
    proof = json.loads(proof_path.read_text())
    row = next(x for x in proof['cases'] if x['case'] == case)
    wait_path = s/'imu-ui-dependency-source-02/report.json'
    assert sha(wait_path) == proof['wait_map_sha256']
    mapped = next(x for x in json.loads(wait_path.read_text())['cases'] if x['case'] == case)
    raw = (s/'imu-powersave-main-01'/case/'main.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['raw_sha256']
    api = discover(raw)
    c = row['activation']['contract']
    candidates = []
    start = 0
    while True:
        offset = raw.find(UI_PREFIX, start)
        if offset < 0:
            break
        start = offset+1
        body = {i.address-0x438000-offset: i for i in decode(raw, 0x438000+offset, 0xb4)}
        if body.get(0x7a) and body[0x7a].op_str == 'r0, #3':
            assert body[0xac].mnemonic == 'bl' and body[0xac].operands[0].imm == api['put']
            candidates.append(0x438000+offset)
    assert len(candidates) == 1
    branch = decode(raw, c['return_pc']+0x72, 2)[0]
    assert branch.mnemonic == 'bne'
    new = api['put']-0x8c
    assert raw[new-0x438000:new-0x438000+10] == bytes.fromhex('f8b504000d0016000027')
    copy_signature = bytes.fromhex('103a07d330b4b1e83810103aa0e83810f9d230bc')
    assert raw.count(copy_signature) == 1
    display_path = s/'display-queue-producer-05/report.json'
    display_manifest = json.loads((s/'display-queue-verification-02/manifest.json').read_text())
    assert display_manifest['passed'] and sha(display_path) == display_manifest['files'][str(display_path.relative_to(s))]
    return dict(ui=c, display=next(x['contract'] for x in json.loads(display_path.read_text())['cases'] if x['case'] == case),
                getter=mapped['getter'], tcb_slot=discover_irq(raw)['current_tcb_slot'], queue_new=new,
                copy=0x438000+raw.index(copy_signature), negative_stop=branch.operands[0].imm,
                sender=c['ui_producer'] if kind == 2 else candidates[0],
                task=next(t for t in mapped['graph']['tasks'] if t['name'] == 'ui_task'),
                renderer_task=next(t for t in mapped['graph']['tasks'] if t['name']=='ambiqdraw'))



def discover_content_contract(raw, ui, data, app_id=0x10b):
    """Recover the original UI dispatch and registered callback from captured RAM."""
    from inspect_ambiq_target import decode
    from probe_ui_queue_producer import literal, word
    site = ui['return_pc']+0x128
    caller = decode(raw, site-10, 14)
    expected = [('ldr', 'r3, [r7, #8]'), ('ldr.w', None),
                ('movs', 'r1, #2'), ('ldr', 'r0, [r7, #4]'), ('bl', None)]
    if len(caller) != len(expected) or any(i.mnemonic != m or (op is not None and i.op_str != op)
            for i, (m, op) in zip(caller, expected)):
        raise ValueError('Unknown UI content dispatch caller')
    payload_buffer=literal(raw,caller[1])
    word(data,payload_buffer)
    entry = caller[-1].operands[0].imm
    body = {i.address-entry:i for i in decode(raw, entry, 0x54)}
    guards = {0:('push','{r1, r2, r3, r4, r5, r6, r7, lr}'),
              0x20:('lsls','r0, r4, #4'), 0x22:('ldr','r0, [r5, r0]'),
              0x24:('cmp','r0, r7'), 0x26:('bne',None),
              0x28:('lsls','r0, r4, #4'), 0x2a:('add','r0, r5'),
              0x2c:('ldr','r0, [r0, #8]'), 0x2e:('cmp','r0, #0'),
              0x30:('beq',None), 0x3e:('ldr.w',None),
              0x42:('ldr','r0, [r7]'), 0x44:('ldr','r3, [r0, #0x1c]'),
              0x46:('movs','r0, r6'), 0x4e:('ldr.w','ip, [ip, #8]'),
              0x52:('blx','ip')}
    for offset,(mnemonic, operands) in guards.items():
        i = body.get(offset)
        if i is None or i.mnemonic != mnemonic or (operands is not None and i.op_str != operands):
            raise ValueError('Unknown original app registry dispatch')
    count_slot=literal(raw,body[0x10]);table=literal(raw,body[0x1c])
    context_slot=literal(raw,body[0x3e]);count=word(data,count_slot)
    if not 0 < count <= 256:raise ValueError('Invalid captured app registry count')
    matches=[]
    for index in range(count):
        row=[word(data,table+16*index+4*k) for k in range(4)]
        if row[0]==app_id:matches.append((index,row))
    if len(matches)!=1:raise ValueError('App is missing or ambiguous in captured registry')
    index,row=matches[0];callback=row[2]&~1
    if not row[2]&1 or not 0x438000 <= callback < 0x438000+len(raw):
        raise ValueError('Registered app callback is outside original Thumb code')
    descriptor=row[3]
    word(data,descriptor+8)
    if data[descriptor-0x20000000+11] != 0:raise ValueError('Unsupported app descriptor dispatch branch')
    return dict(dispatch=entry,call_site=site,return_site=site+4,callback=callback,
                app_id=app_id,registry_count=count,registry_count_slot=count_slot,
                registry_table=table,registry_index=index,descriptor=descriptor,
                context_slot=context_slot,payload_buffer=payload_buffer,
                callback_arguments=['2','payload-buffer','payload-length','context[0x1c]'])



CONTENT_TRACE_POST = """if not next_diag.Stopped:raise ValueError('Missing original mode1 checkpoint')
frame=BlackwallUiActivationDiagnostic(m,cpu,d['wrapper'])
start_ins=int(cpu.ExecutedInstructions)
EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+30
while not frame.Stopped and not m.IsPaused and time.time()<deadline:time.sleep(0.01)
m.Pause()
points={}
for name,pc in p['content_watches'].items():
    points[name]=dict(pc=pc,hits=int(diag.ContentHits(pc)),first=[int(v) for v in diag.ContentSample(pc)],tcb=int(diag.ContentTcb(pc)))
guards=[]
for name in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail'):
    node=m['sysbus.'+name]
    guards.append(dict(name=name,accesses=int(node.AccessCount),address=int(node.LastAddress),value=int(node.LastValue),operation=str(node.LastOperation)))
content_result=dict(stopped_at_frame=bool(frame.Stopped),pc=int(cpu.PC.RawValue),registers=[int(cpu.GetRegister(i).RawValue) for i in range(16)],current_tcb=int(b.ReadDoubleWord(p['tcb_slot'])),instructions_since_mode1=int(cpu.ExecutedInstructions)-start_ins,points=points,guards=guards,cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_policy_violations=int(memory_policy.Violations),synthetic_api_stimulus=True,natural_main_complete=False,frame_pixels_verified=False,observer_neutrality_proven=False)
File.WriteAllBytes('/work-output/content-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
File.WriteAllText('/work-output/content-trace.json',json.dumps(content_result))
if p.get('jbd_status_hex'):
    rx=m['sysbus.guard'].Mspi0Config.Pio
    content_result['jbd_status']=dict(profile=str(rx.JbdStatusHex),rx_starts=int(rx.RxStarts),rx_completions=int(rx.RxCompletions),rx_reads=int(rx.RxReads),rx_bytes=int(rx.RxBytesDelivered),frames=[dict(instruction=int(f.Instruction),control=int(f.Control),payload=str(f.PayloadHex)) for f in rx.ReceiveFrames if int(f.Instruction) in (5,0x35)],tx_frames=[dict(instruction=int(f.Instruction),control=int(f.Control),payload_prefix=str(f.PayloadHex)[:32],payload_bytes=len(str(f.PayloadHex))//2) for f in rx.Frames][-64:])
if p.get('gpu_runtime_component'):
    g=m['sysbus.guard']
    content_result['gpu_runtime']=dict(response=int(g.GpuRuntimeWakeResponse),cycles=int(g.GpuRuntimeWakeCycles),phase=str(g.GpuPower.Phase),request=int(g.GpuPower.RequestWord),status=int(g.GpuPower.StatusWord),prep_steps=int(g.GpuPreparation.StepsCompleted),off_steps=int(g.GpuOffSequence.StepsCompleted),ring_steps=int(g.GpuRing.StepsCompleted),ring_base=int(g.GpuRing.BaseAddress),ring_bytes=int(g.GpuRing.ByteLength),ring_request=int(g.GpuRing.RequestWord),reset_steps=int(g.GpuReset.StepsCompleted),epoch_identity_reads=int(g.GpuEpochIdentityReads),epoch_interrupt_clears=int(g.GpuEpochInterruptClears))
if p.get('gpu_ring_components'):
    gpu=m['sysbus.guard'].GpuCommandDevice
    content_result['gpu_ring']=dict(doorbells=int(gpu.Doorbells),last_doorbell=int(gpu.LastDoorbell),lists_consumed=int(gpu.ListsConsumed),words_consumed=int(gpu.ConsumedWords),pixels_written=int(gpu.PixelsWritten),completed_id=int(gpu.CompletedId),completion_events=int(gpu.CompletionEvents),last_completed_id=int(gpu.LastCompletedId),irq_assertions=int(gpu.IrqAssertions),irq_acks=int(gpu.IrqAcks),epochs=int(gpu.Epochs),interrupt_pending=bool(gpu.InterruptPending),rejections=int(gpu.Rejections),fault=str(gpu.Fault))
    content_result['gpu_ring'].update(draws=int(gpu.Draws),frame_address=int(gpu.FrameAddress),frame_stride=int(gpu.FrameStride),frame_width=int(gpu.FrameWidth),frame_height=int(gpu.FrameHeight))
    content_result['gpu_ring']['coverage_profile']=str(gpu.CoverageProfile)
    File.WriteAllBytes('/work-output/gpu-last-frame.bin',gpu.FrameBytes)
File.WriteAllBytes('/work-output/content-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
File.WriteAllText('/work-output/content-trace.json',json.dumps(content_result))
Console.WriteLine('BLACKWALL_CONTENT_TRACE '+json.dumps(content_result))
"""


def run_native(args):
    from run_native_candidate import FILES,validate_assets
    from run_renode_m55_probe import execute
    from native_replay import IMAGE
    from run_recovery_m55_writer import is_git_output
    import shutil
    root=ROOT;s=args.simulator.resolve();case=args.case;kind=args.message_type;out=args.output.resolve()
    assert not out.exists(), 'Preserve prior evidence'
    if is_git_output(out):raise ValueError('Proprietary capture output must remain outside Git')
    out.mkdir(mode=0o700,parents=True);(out/'exports').mkdir(mode=0o700)
    ctx=prepare_context(s,case,kind);c=ctx['ui'];task=ctx['task'];display=ctx['display']
    trace_content=getattr(args,'trace_content',False)
    status_hex=getattr(args,'jbd_status_hex','').lower()
    if status_hex:
        if len(status_hex)!=4 or any(x not in '0123456789abcdef' for x in status_hex):raise ValueError('Explicit two-byte JBD status hex required')
        if not trace_content:raise ValueError('JBD status profile requires --trace-content')
    if trace_content and kind!=2:raise ValueError('Content trace requires type2 activation')
    gpu_runtime=getattr(args,'gpu_runtime_wake_response',-1)
    if gpu_runtime!=-1 and not status_hex:raise ValueError('GPU runtime diagnostic requires explicit JBD status profile')
    ring_consumer=getattr(args,'gpu_ring_consumer',False)
    if ring_consumer and gpu_runtime!=1:raise ValueError('GPU consumer requires explicit runtime wake response1')
    quad_coverage=getattr(args,'gpu_quad_coverage','strict')
    if quad_coverage!='strict' and not ring_consumer:raise ValueError('Quad reference profile requires ring consumer')

    src=s/'imu-powersave-main-01'/case
    meta=json.loads((src/'derived-inputs.json').read_text());validate_assets(src,meta['derived'])
    for name in FILES:shutil.copyfile(src/name,out/name)
    status_component=None
    if status_hex:
        baseline=s/'display-status-research-01/base-config.cs'
        candidate=ROOT/'tools/renode-mspi1-config.cs'
        old=baseline.read_bytes();original=(out/'strict.cs').read_bytes()
        if original.count(old)!=1:raise ValueError('Unknown source MSPI0 component')
        shutil.copyfile(candidate,out/'mspi0-status-component.cs')
        (out/'strict.cs').write_bytes(original.replace(old,candidate.read_bytes()))
        board=(out/'board.repl').read_text();anchor='mspi0_tx: Miscellaneous.BlackwallMspi0Tx @ none\n'
        assert board.count(anchor)==1
        (out/'board.repl').write_text(board.replace(anchor,anchor+'    jbdStatusHex: "'+status_hex+'"\n'))
        proof=s/'jbd-status-consumer-source-02/report.json'
        shutil.copyfile(proof,out/'status-source.json')
        status_component=dict(baseline=str(baseline.relative_to(s)),baseline_sha256=sha(baseline),candidate_sha256=sha(candidate),derived_strict_sha256=sha(out/'strict.cs'))

    runtime_component=None
    if gpu_runtime!=-1:
        old=s/'gpu-runtime-wake-research-01/base-renode-strict-mmio.cs';candidate=ROOT/'tools/renode-strict-mmio.cs'
        model=(out/'strict.cs').read_bytes();assert model.count(old.read_bytes())==1
        shutil.copyfile(candidate,out/'gpu-runtime-component.cs')
        (out/'strict.cs').write_bytes(model.replace(old.read_bytes(),candidate.read_bytes()))
        status_component['derived_strict_sha256']=sha(out/'strict.cs')
        board=(out/'board.repl').read_text();anchor='    gpuOffSequenceStorage: true\n';assert board.count(anchor)==1
        (out/'board.repl').write_text(board.replace(anchor,anchor+'    gpuRuntimeWakeResponse: '+str(gpu_runtime)+'\n'))
        runtime_component=dict(baseline=str(old.relative_to(s)),baseline_sha256=sha(old),candidate_sha256=sha(candidate),response=gpu_runtime)
    ring_components=[]
    if ring_consumer:
        for name in ['nema-ring-consumer.cs','renode-nema-ring-device.cs']:
            shutil.copyfile(ROOT/'tools'/name,out/name)
            with (out/'strict.cs').open('ab') as f:f.write(b'\n'+(out/name).read_bytes())
            ring_components.append(dict(file=name,sha256=sha(out/name)))
        status_component['derived_strict_sha256']=sha(out/'strict.cs')
        with (out/'board.repl').open('a') as f:f.write('\ngpuRing: Miscellaneous.BlackwallNemaRingDevice @ none\n    cpu: cpu\n    owner: guard\n'+('    referenceCoverage: true\n' if quad_coverage=='area-reference' else '')+'    IRQ -> nvic@28\n')
    code=['.syntax unified','.cpu cortex-m55','.thumb','.section .text','.global entry','.thumb_func','entry:']
    def load(r,v):code.append('ldr '+r+', =0x%x'%v)
    def record(off):load('r12',0x21000040);code.append('str r0, [r12, #%d]'%off)
    # Preserve the real Thread/IRQ/stack context. Block with original kernel APIs,
    # allowing the original scheduler to resume UI on its own captured stack.
    load('r12',0x21000048)
    for k,reg in enumerate(['psp','msp','control','psplim','msplim','primask','basepri','ipsr']):code += ['mrs r1, '+reg,'str r1, [r12, #%d]'%(4*k)]
    for r,v in [('r0',1),('r1',4),('r2',0),('r12',ctx['queue_new']|1)]:load(r,v)
    code += ['blx r12','mov r4, r0'];record(4)
    for r,v in [('r0',0x10b),('r1',0),('r2',0),('r12',ctx['sender']|1)]:load(r,v)
    code.append('blx r12');record(0)
    code.append('mov r0, r4')
    for r,v in [('r1',0x21000200),('r2',0),('r3',0xffffffff),('r12',c['get']|1)]:load(r,v)
    code.append('blx r12');record(0x30)
    code += ['unexpected_return:','wfi','b unexpected_return','.balign 4','.ltorg']
    (out/'harness.s').write_text('\n'.join(code)+'\n')
    clang='/opt/homebrew/opt/llvm@21/bin/clang';lld='/opt/homebrew/opt/lld@21/bin/ld.lld';objcopy='/opt/homebrew/opt/llvm@21/bin/llvm-objcopy'
    execute([clang,'--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-mfloat-abi=hard','-nostdlib','-fuse-ld='+lld,'-Wl,-Ttext=0x3fe00','-Wl,-e,entry',str(out/'harness.s'),'-o',str(out/'harness.elf')],out,'compiler')
    execute([objcopy,'-O','binary',str(out/'harness.elf'),str(out/'harness.bin')],out,'objcopy')
    harness=(out/'harness.bin').read_bytes();assert 0<len(harness)<=512
    cs='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
    using System; using System.Collections.Generic; using Antmicro.Renode.Core; using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallUiActivationHold {
    public BlackwallUiActivationHold(IMachine machine,CortexM cpu,uint pc) { cpu.AddHook(pc,(c,a)=>{if(!Held){Held=true;machine.Pause();}}); }
    public bool Held {get;private set;}
    }
    public sealed class BlackwallUiActivationDiagnostic {
    public BlackwallUiActivationDiagnostic(IMachine machine,CortexM cpu,uint stop) { this.cpu=cpu; this.machine=machine;cpu.AddHook(stop,(c,a)=>{if(!Stopped){Events.Add((uint)a);Stopped=true;machine.Pause();}}); }
    public void Seed(int index,uint value) { if(index!=0 && index!=1 && index!=2 && index!=14 && index!=15)throw new ArgumentException("Unreviewed seed");if(index==15)cpu.PC=value;else cpu.SetRegister(index,value); }
    public void AddStop(uint pc,IMachine machine) { cpu.AddHook(pc,(c,a)=>{if(!Stopped){Events.Add((uint)a);Stopped=true;machine.Pause();}}); }
    public void WatchContent(uint pc,uint tcbSlot) { cpu.AddHook(pc,(c,a)=>{uint count;ContentCounts.TryGetValue(pc,out count);ContentCounts[pc]=count+1;if(!ContentSamples.ContainsKey(pc)){var values=new List<uint>();for(int i=0;i<4;i++)values.Add((uint)cpu.GetRegister(i).RawValue);values.Add((uint)cpu.GetRegister(13).RawValue);values.Add((uint)cpu.GetRegister(14).RawValue);values.Add((uint)cpu.ExecutedInstructions);ContentSamples.Add(pc,values);ContentTcbs.Add(pc,machine.SystemBus.ReadDoubleWord(tcbSlot));}}); }
    public uint ContentTcb(uint pc) {uint tcb;return ContentTcbs.TryGetValue(pc,out tcb)?tcb:0;}
    private readonly IMachine machine; private readonly Dictionary<uint,uint> ContentTcbs=new Dictionary<uint,uint>();
    public uint ContentHits(uint pc) {uint count;return ContentCounts.TryGetValue(pc,out count)?count:0;}
    public List<uint> ContentSample(uint pc) {List<uint> values;return ContentSamples.TryGetValue(pc,out values)?values:new List<uint>();}
    private readonly Dictionary<uint,uint> ContentCounts=new Dictionary<uint,uint>();private readonly Dictionary<uint,List<uint>> ContentSamples=new Dictionary<uint,List<uint>>();
    public void Watch(uint pc) { cpu.AddHook(pc,(c,a)=>{if(Events.Count<64)Events.Add((uint)a);}); }
    public bool Stopped {get;private set;} public List<uint> Events {get;}=new List<uint>(); private readonly CortexM cpu;
    }}
    '''
    (out/'activation.cs').write_text(cs)
    board=(out/'board.repl').read_text();assert '0x21000000' not in board
    (out/'board.repl').write_text(board+'\nactivationWork: Memory.MappedMemory @ sysbus 0x21000000\n    size: 0x10000\n')
    resc=(out/'probe.resc').read_text().replace('include @/work/strict.cs\n','include @/work/strict.cs\ninclude @/work/activation.cs\n');(out/'probe.resc').write_text(resc)
    profile=dict(message_type=kind,negative_stop=ctx['negative_stop'],getter=ctx['getter'],copy=ctx['copy'],tcb_slot=ctx['tcb_slot'],display=display,case=case,contract=c,ui_stack_base=task['stack_base'],harness_bytes=len(harness),source_meta_sha256=hashlib.sha256((src/'derived-inputs.json').read_bytes()).hexdigest(),synthetic_api_stimulus=True,irq_masked=False,natural_main_completion=False)
    if ring_components:profile.update(gpu_ring_components=ring_components,gpu_quad_coverage=quad_coverage)
    if trace_content:
        profile['content_observer_version']=2
        from inspect_ambiq_target import discover as draw_entries
        from inspect_nema_submission import discover_submission
        raw=(out/'main.bin').read_bytes()
        content=discover_content_contract(raw,c,(src/'exports/sram-full.bin').read_bytes())
        gpu=discover_submission(raw);draw=draw_entries(raw)
        profile['content']=content
        profile['content_watches']={name:content[name] for name in ['dispatch','callback','return_site']}
        profile['content_watches'].update(draw=draw['dispatch'],target=draw['target'],submit=gpu['submit'],ring_submit=gpu['ring_submit'],display_producer=display['producer'],frame_wrapper=display['wrapper'])
        if status_hex:
            status_proof=json.loads((out/'status-source.json').read_text());assert status_proof['passed']
            status_row=next(x for x in status_proof['cases'] if x['case']==case)
            assert status_row['raw_sha256']==sha(out/'main.bin')
            profile.update(jbd_status_hex=status_hex,status_component=status_component,status_source_sha256=sha(out/'status-source.json'))
            profile['content_watches'].update(display_status=status_row['entry'],display_status_return=status_row['return_checkpoint'])
            spec=dict(boundary=dict(kind='bounded-capture'),
                comparison=dict(policy='bounded-invariants',paths=[['main_bytes_unmodified'],['original_tasks_resumed']]),
                checks=[dict(path=['content','ui_dispatch_verified'],eq=True),dict(path=['status_diagnostics','profile'],eq=status_hex),dict(path=['status_diagnostics','sequence_matches'],eq=True),dict(path=['status_diagnostics','source_return_matches'],eq=True)],
                allowed_differences=['One pinned MSPI0 component; explicit virtual JBD replies; post-status frontier may differ.'],
                unresolved_differences=['Synthetic API stimulus, first-sample observation; no natural boot, hardware defaults, observer neutrality or full frame claim.'])
            from run_native_candidate import validate_semantics
            validate_semantics(spec)
            if runtime_component is not None:
                profile['gpu_runtime_component']=runtime_component
                spec['checks'].append(dict(path=['runtime_diagnostics','wake_verified'],eq=True))
                spec['allowed_differences'].append('GPU runtime epoch rearm and volatile GPU reinitialization; one further pinned component.')
            if ring_components:
                spec['checks'].append(dict(path=['gpu_ring','work_consumed'],eq=True))
                spec['allowed_differences'].append('Opt-in binary-solid L8 ring consumer; validated guest DMA and work-derived completion only.')
                spec['checks'].append(dict(path=['gpu_ring','coverage_profile'],eq=quad_coverage))
                if quad_coverage=='area-reference':spec['unresolved_differences'].append('Analytical per-edge area coverage; hardware MSAA sample positions and rounding are unverified.')
            spec['checks'].append(dict(path=['renderer','verified'],eq=True))
            profile.update(schema=2,status_semantics=spec)
            (out/'status-plan.json').write_text(json.dumps(dict(schema=2,case=case,component=status_component,replies=status_hex,semantics=spec),indent=2)+'\n')


    firmware_manifest=getattr(args,'firmware_manifest',None)
    if firmware_manifest is not None:
        from display_firmware_candidate import select,snapshot,stimulus_entries,candidate_semantics
        from firmware_candidate import candidate_runtime
        profile['stimulus_entries']=stimulus_entries((out/'harness.s').read_text())
        original=(out/'main.bin').read_bytes()
        selected,record,anchors=select(s,firmware_manifest,args.firmware_baseline,original,profile)
        profile['firmware_candidate']=snapshot(out,firmware_manifest,args.firmware_baseline,record,anchors)
        (out/'main.bin').write_bytes(selected)
        (out/'run.py').write_text(candidate_runtime((out/'run.py').read_text(),len(original),len(selected)))
        if 'status_semantics' in profile:
            spec=candidate_semantics(profile['status_semantics'])
            profile['status_semantics']=spec
            (out/'status-plan.json').write_text(json.dumps(dict(schema=2,case=case,component=status_component,replies=status_hex,semantics=spec),indent=2)+'\n')
    (out/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    post='''
    try:
        import clr,time,json
        from System.IO import File
        from System import Console
        from Antmicro.Renode.Utilities import TypeManager
        clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallUiActivationDiagnostic').Assembly)
        from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallUiActivationDiagnostic
        m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu']
        p=json.loads(File.ReadAllText('/work/profile.json'));q=p['contract']
        if not m.IsPaused:raise ValueError('Diagnostic requires original stop')
        prior_pc=int(cpu.PC.RawValue);prior_instructions=int(cpu.ExecutedInstructions);prior_time=str(m.ElapsedVirtualTime.TimeElapsed);time.sleep(0.2)
        if str(m.ElapsedVirtualTime.TimeElapsed)!=prior_time:raise ValueError('Machine time advanced while paused')
        if prior_pc!=0x58236c:raise ValueError('Unexpected original frontier')
        if int(b.ReadByte(q['state_slot']))!=0 or int(b.ReadDoubleWord(q['queue']+0x38))!=0:raise ValueError('Unexpected UI initial state')
        tail=b.ReadBytes(0x3fe00,512,True)
        if any(int(v)!=0xa5 for v in tail):raise ValueError('ITCM diagnostic range is already occupied')
        data=File.ReadAllBytes('/work/harness.bin')
        for n in range(data.Length):b.WriteByte(0x2100e000+n,data[n])
        for n,v in enumerate([0x12,0x34,0x56,0x78]):b.WriteByte(0x21000100+n,v)
        diag=BlackwallUiActivationDiagnostic(m,cpu,q['display_on_producer']+0x24)
        diag.AddStop(p['negative_stop'],m)
        for pc in q['preparation_helpers']+[q['display_on_producer'],q['return_pc'],q['ui_producer'],0x439c04,0x3fe00]:diag.Watch(pc)
        diag.Seed(0,0x3fe00);diag.Seed(1,0x2100e000);diag.Seed(2,data.Length);diag.Seed(14,0x3fe01)
        diag.Seed(15,p['copy']|1);cpu.IsHalted=False
        EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+30
        while not diag.Stopped and not m.IsPaused and time.time()<deadline:time.sleep(0.01)
        m.Pause()
        diag_guards=[]
        for name in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail'):
            node=m['sysbus.'+name]
            diag_guards.append(dict(name=name,accesses=int(node.AccessCount),address=int(node.LastAddress),pc=int(cpu.PC.RawValue),operation=str(node.LastOperation)))
        values=[int(b.ReadDoubleWord(0x21000040+4*n)) for n in range(10)]
        result=dict(stopped=bool(diag.Stopped),pc=int(cpu.PC.RawValue),instructions=int(cpu.ExecutedInstructions)-prior_instructions,events=[int(v) for v in diag.Events],bootstrap=values,ui_state=int(b.ReadByte(q['state_slot'])),display_messages=int(b.ReadDoubleWord(p['display']['queue']+0x38)),display_waiters=int(b.ReadDoubleWord(p['display']['queue']+0x24)),guards=diag_guards,memory_policy_violations=int(memory_policy.Violations),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),natural_main_completion=False,synthetic_api_stimulus=True,irq_masked=False)
        File.WriteAllBytes('/work-output/ui-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
        File.WriteAllText('/work-output/activation.json',json.dumps(result))
        result['current_tcb']=int(b.ReadDoubleWord(p['tcb_slot']));result['sp']=int(cpu.GetRegister(13).RawValue);result['xpsr']=int(cpu.GetRegister(25).RawValue)
        File.WriteAllText('/work-output/activation.json',json.dumps(result))
        Console.WriteLine('BLACKWALL_UI_ACTIVATION '+json.dumps(result))
        if not diag.Stopped:raise ValueError('UI activation did not reach first checkpoint')
        d=p['display'];next_diag=BlackwallUiActivationDiagnostic(m,cpu,d['consumer_return']+0x7c)
        for pc in d['consumer_helpers']:next_diag.Watch(pc)
        EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+30
        while not next_diag.Stopped and not m.IsPaused and time.time()<deadline:time.sleep(0.01)
        m.Pause()
        follow=dict(stopped=bool(next_diag.Stopped),pc=int(cpu.PC.RawValue),events=[int(v) for v in next_diag.Events],mode=int(b.ReadDoubleWord(d['mode_slot'])),current_tcb=int(b.ReadDoubleWord(p['tcb_slot'])),sp=int(cpu.GetRegister(13).RawValue),xpsr=int(cpu.GetRegister(25).RawValue),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_policy_violations=int(memory_policy.Violations))
        File.WriteAllBytes('/work-output/display-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
        File.WriteAllText('/work-output/display-on.json',json.dumps(follow))
        Console.WriteLine('BLACKWALL_DISPLAY_ON '+json.dumps(follow))
    except Exception as diagnostic_error:
        Console.WriteLine('BLACKWALL_UI_ACTIVATION_ERROR '+str(diagnostic_error))
    '''
    base_runtime=(out/'run.py').read_text()
    anchor='    e.StartAll()\n'
    assert base_runtime.count(anchor)==1
    setup="    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallUiActivationHold').Assembly)\n    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallUiActivationHold\n    activation_hold=BlackwallUiActivationHold(m,m['sysbus.cpu'],0x5542c6)\n"
    base_runtime=base_runtime.replace(anchor,setup.replace('0x5542c6',str(ctx['getter']))+anchor).replace('while not m.IsPaused and live_seconds<120:', 'while not m.IsPaused and not activation_hold.Held and live_seconds<120:')
    post=post.replace("prior_pc!=0x58236c", "prior_pc!=p['getter']")
    if trace_content:
        install="        for name,pc in p['content_watches'].items():diag.WatchContent(pc,p['tcb_slot'])\n"
        post=post.replace("        diag.Seed(0,0x3fe00);",install+"        diag.Seed(0,0x3fe00);")
        # Avoid the broad memcpy watch in this explicitly separate observer recipe.
        post=post.replace("q['ui_producer'],0x439c04,0x3fe00]", "q['ui_producer'],0x3fe00]")
        anchor="        Console.WriteLine('BLACKWALL_DISPLAY_ON '+json.dumps(follow))"
        post=post.replace(anchor,anchor+'\n'+textwrap.indent(CONTENT_TRACE_POST,'        '))
    post=textwrap.dedent(post)
    if kind==3:
        begin=post.index("    d=p['display'];next_diag=")
        end=post.index('\nexcept Exception as diagnostic_error:',begin)
        post=post[:begin]+"    if p['message_type']==2:\n"+'\n'.join('    '+line if line else line for line in post[begin:end].splitlines())+post[end:]
    (out/'run.py').write_text(base_runtime+textwrap.dedent(post))
    (out/'runner-source.py').write_bytes(Path(__file__).read_bytes())
    if firmware_manifest is not None:
        from display_firmware_candidate import inspect as inspect_candidate
        inspect_candidate(out,profile,original)
    comparison_preflight(args)
    print('native-start',flush=True)
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=bind,source='+str(out)+',target=/work,readonly','--mount','type=bind,source='+str(out/'exports')+',target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode',timeout=240,stream=True)
    for copied in out.iterdir():
        if copied.is_file():copied.chmod(0o600)
    return audit(s,out,out/'verification')


def comparison_preflight(args):
    if getattr(args,'compare_baseline',None) is None:
        return
    if any(not path.resolve().is_relative_to(args.simulator.resolve())
           for path in (args.compare_baseline,args.output,args.comparison_output)):
        raise ValueError('Display comparison assets must remain in the private simulator')
    from compare_display_firmware import preflight
    preflight(args.compare_baseline,args.output,args.comparison_output,args.comparison_expectation)


def finish_display_cli(args,result,summary):
    if args.compare_baseline is not None:
        from compare_display_firmware import compare
        comparison=compare(args.simulator,args.compare_baseline,args.output,args.comparison_output,args.comparison_expectation)
        summary.update(candidate_passed=result['passed'],comparison_passed=comparison['passed'],
                       comparison_output=str(args.comparison_output),
                       changed_surface_bytes=comparison['surface']['changed_bytes'])
        summary['passed']=result['passed'] and comparison['passed']
    print(json.dumps(summary))
    if not summary['passed']:raise SystemExit(1)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--case',choices=['stock24','stock23','cfw'],required=True)
    p.add_argument('--message-type',type=int,choices=[2,3],default=2)
    p.add_argument('--gpu-runtime-wake-response',type=int,choices=[-1,0,1],default=-1,help='Opt-in runtime GPU wake response; 0 stuck, 1 powered')
    p.add_argument('--gpu-ring-consumer',action='store_true',help='Opt-in bounded binary-solid L8 GPU consumer; not complete shader ISA')
    p.add_argument('--gpu-quad-coverage',choices=['strict','area-reference'],default='strict',help='Explicit analytical coverage reference; not hardware MSAA equivalence')
    p.add_argument('--jbd-status-hex',default='',help='Explicit virtual replies for JBD commands05/35 (two bytes); not physical defaults')
    p.add_argument('--trace-content',action='store_true',help='Observe original app dispatch and bounded post-mode1 execution; API diagnostic only')
    p.add_argument('--audit-existing',action='store_true');p.add_argument('--audit-output',type=Path)
    p.add_argument('--firmware-manifest',type=Path);p.add_argument('--firmware-baseline',type=Path)
    p.add_argument('--compare-baseline',type=Path);p.add_argument('--comparison-output',type=Path);p.add_argument('--comparison-expectation',type=Path)
    a=p.parse_args()
    if (a.compare_baseline is None)!=(a.comparison_output is None):p.error('Comparison requires --compare-baseline and --comparison-output together')
    if a.comparison_expectation is not None and a.compare_baseline is None:p.error('Comparison expectation requires --compare-baseline')
    if a.compare_baseline is not None and not (a.firmware_manifest is not None or a.audit_existing):p.error('Comparison requires a registered candidate or its saved audit')
    if (a.firmware_manifest is None)!=(a.firmware_baseline is None):p.error('Candidate selection requires --firmware-manifest and --firmware-baseline')
    if a.audit_existing and a.firmware_manifest is not None:p.error('Saved audit uses the captured registration snapshot; omit candidate selection')
    from simulator_cli_readiness import python_packages,native_tools
    python_packages()
    if not a.audit_existing:native_tools(compiler=True)
    if a.audit_existing:
        if a.audit_output is None:p.error('Saved audit requires --audit-output')
        saved=json.loads((a.output/'profile.json').read_text())
        if saved['case']!=a.case or saved['message_type']!=a.message_type:p.error('Audit arguments differ from capture')
        try:comparison_preflight(a)
        except (OSError,ValueError) as error:p.error(str(error))
        result=audit(a.simulator,a.output,a.audit_output)
    else:
        if a.audit_output is not None:p.error('--audit-output requires --audit-existing')
        result=run_native(a)
    summary=dict(passed=result['passed'],case=result['case'],message_type=result['message_type'],
        checks=len(result['checks']),synthetic_api_stimulus=True,natural_main_complete=False)
    if 'content' in result:
        summary.update(ui_dispatch_verified=result['content']['ui_dispatch_verified'],
                       frame_wrapper_observed=result['content']['frame_wrapper_observed'],
                       post_mode1_supported=result['content']['post_mode1_supported'],frame_pixels_verified=False)
    if 'pending_submission' in result:summary['pending_ring_packet_verified']=result['pending_submission']['verified']
    if 'runtime_diagnostics' in result:summary.update(gpu_phase=result['runtime_diagnostics']['observed'].get('phase'),gpu_wake_contract_matched=result['runtime_diagnostics']['wake_verified'])
    if 'status_diagnostics' in result:
        summary.update(submit_completed=False,gpu_work_consumed=False,renderer_task_verified=result['renderer']['verified'],draw_observed=result['content']['draw_observed'],submit_observed=result['content']['submit_observed'],status_sequence_matches=result['status_diagnostics']['sequence_matches'],status_return=result['status_diagnostics']['observed_return'],execution_passed=result['execution_passed'],semantic_validation_passed=result['semantic_validation']['passed'])
    if 'gpu_ring' in result:
        summary.update(gpu_work_consumed=result['gpu_ring']['work_consumed'],gpu_ring=result['gpu_ring']['observed'])
    finish_display_cli(a,result,summary)


if __name__=='__main__':
    from simulator_cli_readiness import run_cli
    run_cli(main)
