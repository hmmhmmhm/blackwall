"""Extend the frozen first-screen recipe; shared native-candidate schema2 semantics.
The generic candidate CLI owns a single main observation loop; this recipe has
reset/touch/UI phases, so it reuses its semantic validator rather than claiming
that a generic single-boundary capture represents the whole UI lifecycle.
"""
import argparse,hashlib,json,shutil,re
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from run_native_candidate import semantic_spec,finish_capture
R=Path(__file__).resolve().parents[1];S=Path.home()/'Library/Application Support/Blackwall/simulator'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
POST='''                    if final_draw.Stopped:
                        File.WriteAllBytes('/work-output/first-screen.bin',gpu.CompleteScreenFrameBytes)
                        from Antmicro.Renode.Utilities import TypeManager
                        clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallSleepTransitionObserver').Assembly)
                        from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallSleepTransitionObserver
                        sleep_watch=BlackwallSleepTransitionObserver(m,cpu,m['sysbus.nvic'],0)
                        frame_samples=[];skipped_frames=0
                        def sample_frame():
                            global skipped_frames
                            serial=int(gpu.CompleteScreenCaptures);data=gpu.CompleteScreenFrameBytes
                            if serial!=int(gpu.CompleteScreenCaptures):return
                            if frame_samples and serial==frame_samples[-1]['serial']:return
                            if frame_samples:skipped_frames+=max(0,serial-frame_samples[-1]['serial']-1)
                            name='boot-frame-%04d.bin'%len(frame_samples)
                            File.WriteAllBytes('/work-output/'+name,data)
                            frame_samples.append(dict(file=name,serial=serial,observed_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pc=int(cpu.PC.RawValue),tcb=int(b.ReadDoubleWord(p['tcb_slot'])),instructions=int(cpu.ExecutedInstructions),gpu_lists=int(gpu.ListsConsumed),gpu_draws=int(gpu.Draws),nonzero=int(gpu.CompleteScreenNonzero)))
                        def boot_state():
                            return dict(ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pc=int(cpu.PC.RawValue),instructions=int(cpu.ExecutedInstructions),registers=registers(),tcb=int(b.ReadDoubleWord(p['tcb_slot'])),frames=int(gpu.CompleteScreenCaptures),gpu_rejections=int(gpu.Rejections),gpu_fault=str(gpu.Fault),fifo_ready=bool(m['sysbus.iom4.imu_fifo'].Configuration.Ready),retention_stages=int(g.CpuNormalSleep.RetentionStages),retention_flushes=int(g.CpuNormalSleep.RetentionFlushes),cpd=int(g.CpuNormalSleep.CpdValue),uart_rx=int(g.Uarts[0].RxBytesRead),imu_wrapper_gate=int(b.ReadDoubleWord(0x200774f4)))
                        File.WriteAllBytes('/work-output/boot-before-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
                        before_boot=boot_state();sample_frame();boot_started=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
                        EmulationManager.Instance.CurrentEmulation.StartAll();boot_deadline=time.time()+180
                        while not m.IsPaused and time.time()<boot_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-boot_started<100*int(TimeInterval.TicksPerMillisecond):
                            if bool(cpu.IsHalted) or int(gpu.Rejections)>0:break
                            if len(frame_samples)>=32:break
                            sample_frame();time.sleep(0.02)
                        boot_reason='cpu-halted' if cpu.IsHalted else ('gpu-rejected' if gpu.Rejections else ('machine-paused' if m.IsPaused else ('sample-limit' if len(frame_samples)>=32 else ('host-limit' if time.time()>=boot_deadline else 'virtual-limit'))))
                        m.Pause();sample_frame();after_boot=boot_state()
                        lifecycle=dict(before=before_boot,after=after_boot,stop_reason=boot_reason,target_ms=100,ticks_per_ms=int(TimeInterval.TicksPerMillisecond),elapsed_ticks=after_boot['ticks']-boot_started,frames=frame_samples,skipped_frames=skipped_frames,sleep_events=[[int(v) for v in row] for row in sleep_watch.Events],sleep_overflow=bool(sleep_watch.Overflow),hardware_accessed=False,host_pc_tcb_or_branch_seed=False)
                        sleep_watch.Detach()
                        File.WriteAllText('/work-output/boot-lifecycle.json',json.dumps(lifecycle))
                        File.WriteAllBytes('/work-output/boot-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
                        File.WriteAllText('/work-output/firmware-uarts.txt','\\n'.join('UART'+str(n)+'\\n'+''.join(chr(int(v)) for v in g.Uarts[n].TxBytes) for n in range(4)))
'''
def with_task_wait_probe(post):
 setup="""                        task_wait_probe=None
                        def pause_for_task_wait():
                            m.Pause();return True
                        task_wait_timer=BlackwallRuntimeInputDelay(m,10,Func[bool](pause_for_task_wait))
"""
 old="                        EmulationManager.Instance.CurrentEmulation.StartAll();boot_deadline=time.time()+180"
 if post.count(old)!=1:raise ValueError('Changed lifecycle start')
 post=post.replace(old,setup+old,1)
 old="                        while not m.IsPaused and time.time()<boot_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-boot_started<100*int(TimeInterval.TicksPerMillisecond):"
 new="""                        while time.time()<boot_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-boot_started<100*int(TimeInterval.TicksPerMillisecond):
                            if m.IsPaused:
                                if task_wait_timer.Fired and task_wait_probe is None:
                                    wait_before_read=boot_state()
                                    File.WriteAllBytes('/work-output/boot-wait-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
                                    wait_after_read=boot_state()
                                    task_wait_probe=dict(before_read=wait_before_read,after_read=wait_after_read,whole_machine_paused=bool(m.IsPaused),timer_fired=bool(task_wait_timer.Fired),timer_accepted=bool(task_wait_timer.Accepted),timer_started=int(task_wait_timer.StartedAt),timer_fired_at=int(task_wait_timer.FiredAt))
                                    File.WriteAllText('/work-output/boot-wait-state.json',json.dumps(task_wait_probe))
                                    sample_frame()
                                    EmulationManager.Instance.CurrentEmulation.StartAll()
                                    continue
                                break"""
 if post.count(old)!=1:raise ValueError('Changed lifecycle loop')
 return post.replace(old,new,1)

def task_wait_witness(folder,life,touch,case,export_subdir='exports'):
 import struct
 ex=folder/export_subdir;state_path=ex/'boot-wait-state.json';ram_path=ex/'boot-wait-sram.bin'
 if not state_path.exists() or not ram_path.exists():return dict(passed=False,error='Missing actual wait-state capture')
 try:
  state=json.loads(state_path.read_text());raw=ram_path.read_bytes();expected_pc={'stock24':0x4b7a58,'stock23':0x4ad7e4,'cfw':0x4ad7e4}[case]
  entries=[r for r in touch['rows'] if r[0]==56]
  if not entries or touch['overflow'] or any(r[1]!=expected_pc or (r[9]&0x1ff)!=0 for r in entries):raise ValueError('Incomplete or incompatible UI trace')
  owners={r[8] for r in entries}
  if len(owners)!=1:raise ValueError('UI task changed unexpectedly')
  tcb=next(iter(owners))
  def word(address):
   offset=address-0x20000000
   if address%4 or offset<0 or offset+4>len(raw):raise ValueError('Pointer outside complete captured SRAM')
   return struct.unpack_from('<I',raw,offset)[0]
  if len(raw)!=0x380000:raise ValueError('Incomplete wait SRAM')
  offset=tcb-0x20000000;name=raw[offset+52:offset+84].split(b'\0')[0].decode('ascii')
  if name!='ui_task' or word(tcb+16)!=tcb or word(tcb+36)!=tcb or word(tcb+44)>=256:raise ValueError('TCB layout/owner mismatch')
  container=word(tcb+40);node=tcb+24;count=word(container)
  # Tie the event list to the actual original UI producer's queue handle.
  # This excludes a pending-ready list that also uses a TCB event-list item.
  main=(folder/'main.bin').read_bytes();load_pc=0x445f1c if case=='stock24' else 0x445ec0
  opcode=struct.unpack_from('<H',main,load_pc-0x438000)[0]
  if opcode!=(0x484b if case=='stock24' else 0x484a):raise ValueError('Changed original UI queue handle load')
  literal=((load_pc+4)&~3)+(opcode&255)*4
  queue_slot=struct.unpack_from('<I',main,literal-0x438000)[0];queue=word(queue_slot)
  if container!=queue+0x24 or word(queue+0x38)!=0 or word(queue+0x40)!=12 or not 0<word(queue+0x3c)<=65536:raise ValueError('Not an empty original UI queue receive-wait list')
  if not 1<=count<=128 or word(container+8)!=0xffffffff:raise ValueError('Not a bounded original event list')
  sentinel=container+8;current=word(container+12);nodes=[]
  while current!=sentinel:
   if current in nodes or len(nodes)>=count:raise ValueError('Invalid event-list cycle')
   nodes.append(current);nxt=word(current+4);prev=word(current+8)
   if word(nxt+8)!=current or word(prev+4)!=current or word(current+16)!=container:raise ValueError('Invalid original event-list links')
   current=nxt
  if len(nodes)!=count or node not in nodes or word(node+12)!=tcb:raise ValueError('UI task is not an original event waiter')
  stamp=state['before_read']['ticks']
  later=[r for r in entries if r[10]>stamp and r[8]==tcb and r[2]==4]
  checks=dict(whole_machine_paused=state['whole_machine_paused'],read_preserved_state=state['before_read']==state['after_read'],timer_fired=state['timer_fired'] and state['timer_accepted'],ten_ms_boundary=state['timer_fired_at']==state['timer_started']+10000000 and state['timer_started']==life['before']['ticks'] and state['timer_fired_at']<=stamp<life['after']['ticks'],original_event_waiter=True,same_task_later_callback=bool(later),instructions_progressed=life['after']['instructions']>state['before_read']['instructions'])
  return dict(passed=all(checks.values()),checks=checks,tcb=tcb,name=name,queue_handle_load_pc=load_pc,queue_slot=queue_slot,queue=queue,queue_messages=word(queue+0x38),queue_capacity=word(queue+0x3c),queue_item_bytes=word(queue+0x40),event_container=container,event_nodes=nodes,wait_ticks=stamp,later_callback_rows=later,wait_sram_sha256=sha(ram_path),wait_state_sha256=sha(state_path))
 except (KeyError,ValueError,UnicodeError,struct.error) as e:return dict(passed=False,error=type(e).__name__+': '+str(e))

def specification():
 checks=['target_reached','fault_free','multiple_frames','ordered_without_gaps','content_changed','sleep_wake_pair','fifo_ready','first_frame_matches','main_unmodified','source_model_unchanged','init_wrapper_returned']
 return dict(boundary={'kind':'bounded-capture'},comparison={'policy':'bounded-invariants','paths':[['model_sha256'],['main_sha256']]},checks=[{'path':['diagnostics',k],'eq':True} for k in checks],allowed_differences=['Same frozen board/model/main; observation extends by 100 virtual ms after first detail frame.','NVIC signal observer is installed only after first frame; no CPU hook is added.'],unresolved_differences=['Functional sensor/GPU/power profiles are not physical timing or numerical validation.','Sleep signal history is bounded; overflow is disclosed, never a claim of all IRQ events.','One stock24 case; other firmware/reset/sensor sample acceptance remains separate.'])
def derive(o,case='stock24',task_wait_probe=False):
 if case=='stock24':
  source_root='screen-first-native-23';manifest_path=S/'screen-first-functional-manifest.json';manifest_pin='0ba154614177b0620b5204aaecaec5167ffdfd64e3ef16034eabcb41e1a10d22'
 else:
  source_root='boot-family-functional-native-01/'+case;manifest_path=S/'boot-family-functional-manifest.json';manifest_pin='41115592cbfc9916d8547d440dcd68b2571b58a60c5c677ceec34d0bc955a095'
 if sha(manifest_path)!=manifest_pin:raise ValueError('Changed accepted first-screen manifest')
 manifest=json.loads(manifest_path.read_text());b=S/source_root
 if o.exists() or not o.is_relative_to(S) or o.is_relative_to(R):raise ValueError('New private output required')
 o.mkdir(mode=0o700,parents=True);(o/'exports').mkdir(mode=0o700)
 pins={}
 for p in b.iterdir():
  if p.is_file() and p.suffix in ['.cs','.bin','.json','.py','.resc','.repl'] and p.name!='renode.process.json':
   expected=manifest['files'][str(p.relative_to(S))]['sha256']
   if sha(p)!=expected:raise ValueError('Changed frozen input '+p.name)
   shutil.copyfile(p,o/p.name);pins[p.name]=expected
 observer=R/'tools/renode-sleep-transition-observer.cs';activation=(o/'activation.cs').read_text()
 if 'class BlackwallSleepTransitionObserver' in activation:raise ValueError('Duplicate observer')
 (o/'activation.cs').write_text(activation+'\n'+observer.read_text())
 runtime=(o/'run.py').read_text()
 post=with_task_wait_probe(POST) if task_wait_probe else POST;prefix_pins={};gate_contract=None
 if case=='stock24':anchor="                File.WriteAllText('/work-output/after-broadcast.json',json.dumps(after_broadcast))"
 else:
  # Derive the actual gate slot from the original Thumb LDR.W literal.
  import struct
  raw=(o/'main.bin').read_bytes();pc=0x4baae6;offset=pc-0x438000
  if raw[offset:offset+4]!=bytes.fromhex('dff8bc58'):raise ValueError('Changed original mode gate load')
  gate=struct.unpack_from('<I',raw,((pc+4)&~3)+0x8bc-0x438000)[0]
  if gate!=0x20077d00 or raw[0x4bab40-0x438000:0x4bab44-0x438000]!=bytes.fromhex('01202860'):raise ValueError('Changed original wrapper-return gate store')
  gate_contract=dict(load_pc=pc,load_bytes='dff8bc58',gate=gate,store_pc=0x4bab42,main_sha256=sha(o/'main.bin'))
  post='\n'.join(line[4:] if line.startswith('    ') else line for line in post.split('\n'))
  post=post.replace('if final_draw.Stopped:','if gpu.CompleteScreenHasDetail:').replace('0x200774f4',hex(gate))
  post+="                File.WriteAllText('/work-output/gpu.json',json.dumps(dict(rejections=int(gpu.Rejections),fault=str(gpu.Fault))))\n"
  anchor="                File.WriteAllText('/work-output/family-boot.json',json.dumps(boot))"
  for name in ['before-input-sram.bin','after-input-sram.bin','before-reply-sram.bin','after-reply-sram.bin','app-request-sram.bin','ui-dispatch-sram.bin']:
   source=b/'exports'/name;digest=manifest['files'][str(source.relative_to(S))]['sha256']
   if sha(source)!=digest:raise ValueError('Changed original startup capture')
   prefix_pins[name]=digest
 if case=='stock24':
  for name in ['before-input-sram.bin','after-input-sram.bin','before-reply-sram.bin','after-reply-sram.bin','app-request-sram.bin','ui-dispatch-sram.bin']:
   source=b/'exports'/name;digest=manifest['files'][str(source.relative_to(S))]['sha256']
   if sha(source)!=digest:raise ValueError('Changed original startup capture')
   prefix_pins[name]=digest
 if runtime.count(anchor)!=1:raise ValueError('Changed first-screen phase boundary')
 runtime=runtime.replace(anchor,post+anchor if case=='stock24' else anchor+'\n'+post,1);(o/'run.py').write_text(runtime)
 source={'model_sha256':sha(b/'strict.cs'),'main_sha256':sha(b/'main.bin')}
 contract=specification()
 if task_wait_probe:
  contract['checks'].append({'path':['diagnostics','task_wait_resume'],'eq':True})
  contract['allowed_differences'].append('Whole-machine pause at first-screen +10ms captures the original task event list, then execution resumes without CPU/TCB writes.')
 if case!='stock24':contract['unresolved_differences'][-1]='One '+case+' case; reset/sensor sample acceptance remains separate.'
 plan=dict(schema=2,id='post-screen-lifecycle-'+case+'-v1',image_id=IMAGE,cases={case:case},source_root=source_root,input_sha256=pins,prefix_sha256=prefix_pins,wrapper_gate_contract=gate_contract,task_wait_probe_ms=10 if task_wait_probe else None,append_components=[{'candidate':'tools/renode-sleep-transition-observer.cs','sha256':sha(observer)}],runtime_edits=[{'before_sha256':pins['run.py'],'after_sha256':sha(o/'run.py'),'change':'post-first-screen 100 ms observation only'}],semantics={case:{'candidate':contract,'control':contract}},source_invariants=source,observation={'virtual_ms':100,'host_seconds':180,'frame_limit':32},scope='bounded '+case+' post-screen lifecycle; not full E05 or physical boot')
 semantic_spec(plan,case,False);(o/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');(o/'runner-source.py').write_bytes(Path(__file__).read_bytes())
 return plan

def audit(folder,out):
 if out.exists() or not out.is_relative_to(S):raise ValueError('New private audit output required')
 plan=json.loads((folder/'plan.json').read_text());case=next(iter(plan['cases']));ex=folder/'exports'
 if not (ex/'boot-lifecycle.json').exists():
  errors=[l for l in (folder/'renode.log').read_text().splitlines() if l.startswith('BLACKWALL_TOUCH_RUNTIME_ERROR ') or 'There was an error executing' in l]
  result=dict(passed=False,execution_passed=False,semantic_validation={'passed':False,'status':'missing-post-screen-capture'},runtime_errors=errors,native_rerun=False)
  out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return result
 life=json.loads((ex/'boot-lifecycle.json').read_text());touch=json.loads((ex/'touch.json').read_text());gpu=json.loads((ex/'gpu.json').read_text());rows=life['frames']
 for x in rows:x['sha256']=sha(ex/x['file'])
 pairs=[]
 for kind in [0,1]:
  enters=[x for x in life['sleep_events'] if x[0]==kind and x[1]==1]
  if any(any(y[0]==kind and y[1]==0 and y[2]>=x[2] for y in life['sleep_events']) for x in enters):pairs.append(kind)
 checks=dict(target_reached=life['elapsed_ticks']==life['after']['ticks']-life['before']['ticks'] and life['elapsed_ticks']>=100*1000000 and life['after']['instructions']>life['before']['instructions'] and life['ticks_per_ms']==1000000 and life['stop_reason']=='virtual-limit',fault_free=all(g['accesses']==0 for g in touch['guards']) and touch['cfsr']==touch['hfsr']==touch['memory_violations']==gpu['rejections']==0 and gpu['fault']=='',multiple_frames=len(rows)>=3,ordered_without_gaps=life['skipped_frames']==0 and rows[0]['serial']==life['before']['frames'] and rows[-1]['serial']==life['after']['frames'] and all(life['before']['ticks']<=x['observed_ticks']<=life['after']['ticks'] for x in rows) and all(y['serial']==x['serial']+1 and y['observed_ticks']>=x['observed_ticks'] for x,y in zip(rows,rows[1:])),content_changed=len({x['sha256'] for x in rows})>=2,sleep_wake_pair=bool(pairs),fifo_ready=life['after']['fifo_ready'],first_frame_matches=sha(ex/'first-screen.bin')=='5bed2a24ac17aa73a627552376d35af5c27988fd57e60e12faa7c29b55403501',main_unmodified=sha(folder/'main.bin')==plan['source_invariants']['main_sha256'],source_model_unchanged=sha(folder/'strict.cs')==plan['source_invariants']['model_sha256'],init_wrapper_returned=life['before']['imu_wrapper_gate']==life['after']['imu_wrapper_gate']==1)
 witness=task_wait_witness(folder,life,touch,case) if plan.get('task_wait_probe_ms') else None
 if witness is not None:checks['task_wait_resume']=witness['passed']
 result=dict(case=case,control=False,boundary_kind='bounded-capture',observed=life['after'],selected_observation=dict(events=rows,sequence=len(rows),dropped_events=life['skipped_frames']),model_sha256=sha(folder/'strict.cs'),main_sha256=sha(folder/'main.bin'),diagnostics=checks)
 source=S/plan['source_root'];pin_checks={}
 for name,digest in plan['input_sha256'].items():
  pin_checks['source:'+name]=sha(source/name)==digest
  if name not in ['activation.cs','run.py','runner-source.py','plan.json']:pin_checks['input:'+name]=sha(folder/name)==digest
 for name,digest in plan.get('prefix_sha256',{}).items():
  pin_checks['prefix-source:'+name]=sha(source/'exports'/name)==digest
  pin_checks['prefix-capture:'+name]=sha(ex/name)==digest
 original=(source/'activation.cs').read_bytes();actual=(folder/'activation.cs').read_bytes()
 pin_checks['observer-prefix']=actual.startswith(original+b'\n')
 pin_checks['observer-component']=hashlib.sha256(actual[len(original)+1:]).hexdigest()==plan['append_components'][0]['sha256']
 pin_checks['runtime-edit']=sha(folder/'run.py')==plan['runtime_edits'][0]['after_sha256']
 runtime=(folder/'run.py').read_text();pin_checks['no-cpu-control-writes']=not any(re.search(x,runtime) for x in [r'\.SetRegister\s*\(',r'\.SeedRegister\s*\(',r'\.PC\s*=',r'\.WriteDoubleWord\s*\(',r'\.WriteByte\s*\('])
 log=(folder/'renode.log').read_text();pin_checks['no-runtime-error']='BLACKWALL_TOUCH_RUNTIME_ERROR' not in log and 'There was an error executing' not in log
 pin_checks['process-removed']=json.loads((folder/'renode.process.json').read_text())['status']=='removed'
 pin_checks['frame-bytes']=all((ex/x['file']).stat().st_size==576*288 and sum(v!=0 for v in (ex/x['file']).read_bytes())==x['nonzero'] for x in rows)
 result=finish_capture(result,plan['source_invariants'],semantic_spec(plan,case,False))
 result['execution_passed']=all(pin_checks.values());result['passed']=result['execution_passed'] and result['semantic_validation']['passed'];result['execution_checks']=pin_checks
 result['capture_hashes']={str(x.relative_to(folder)):sha(x) for x in folder.rglob('*') if x.is_file() and 'audit' not in x.relative_to(folder).parts}
 result.update(task_wait_witness=witness,lifecycle=life,sleep_pairs_observed=pairs,hardware_accessed=False,full_e05_verified=False,source_model_unchanged=checks['source_model_unchanged'])
 out.mkdir(mode=0o700,parents=True);(out/'runner-source.py').write_bytes(Path(__file__).read_bytes());(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],execution_passed=result['execution_passed'],checks=checks,elapsed_ms=life['elapsed_ticks']/1e6,frames=len(rows),stop_reason=life['stop_reason'])))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--case',choices=['stock24','stock23','cfw'],default='stock24');p.add_argument('--task-wait-probe',action='store_true');p.add_argument('--audit-existing',action='store_true');p.add_argument('--audit-output',type=Path);a=p.parse_args();o=a.output.resolve()
 if a.audit_existing:
  if a.audit_output is None:p.error('Audit output required')
  d=audit(o,a.audit_output.resolve());raise SystemExit(0 if d['passed'] else 1)
 plan=derive(o,a.case,a.task_wait_probe)
 execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','--mount',f'type=bind,source={o/"exports"},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=420)
 d=audit(o,o/'audit');raise SystemExit(0 if d['passed'] else 1)
