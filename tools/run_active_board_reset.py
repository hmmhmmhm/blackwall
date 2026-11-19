"""Frozen E05 active board -> external virtual NVIC reset -> original main/UI replay.
Uses the accepted reset-aware NVIC and bw419/420 protection/cache fixes. No hardware.
"""
import argparse,hashlib,json,shutil,re
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from reset_entry_pause_contract import completed_pause
from reset_memory_policy_candidate import with_memory_policy,with_system_control
from run_native_candidate import semantic_spec,finish_capture
R=Path(__file__).resolve().parents[1];S=Path.home()/'Library/Application Support/Blackwall/simulator'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
POST='''
try:
    from System.Security.Cryptography import SHA256
    from System import BitConverter
    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallResetEntryObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallResetEntryObserver
    def reset_digest(data):return str(BitConverter.ToString(SHA256.Create().ComputeHash(data))).replace('-','').lower()
    def active_reset_state():
        gp=g.GpuCommandDevice;im=m['sysbus.iom4.imu_fifo'].StartupPeer;hc=m['sysbus.iom6'].SpiWordTransfer.Peer
        backing=g.Mspi1Config.Pio.ArrayBacking;vol=backing.AdditionalWindow
        ok,kv=backing.TryRead(backing.Start,backing.Length)
        if not ok:raise ValueError('Missing retained NOR')
        ok,fs=vol.TryRead(vol.Start,vol.Length)
        if not ok:raise ValueError('Missing retained filesystem')
        return dict(pc=int(cpu.PC.RawValue),sp=int(cpu.GetRegister(13).RawValue),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),mips=int(cpu.PerformanceInMips),paused=bool(m.IsPaused),halted=bool(cpu.IsHalted),vtor=int(cpu.VectorTableOffset),reset_count=int(m['sysbus.nvic'].ResetCompletions),basepri=int(m['sysbus.nvic'].BASEPRI_NS),sram_sha256=reset_digest(b.ReadBytes(0x20000000,0x380000,True)),itcm_sha256=reset_digest(b.ReadBytes(0,0x40000,True)),kv_sha256=reset_digest(kv),fs_sha256=reset_digest(fs),pio_busy=bool(g.Mspi1Config.Pio.Busy),program_busy=bool(g.Mspi1Config.Pio.ProgramBusy),erase_busy=bool(g.Mspi1Config.Pio.EraseBusy),icache=bool(system_control.ICacheEnabled),dcache=bool(system_control.DataCache.Enabled),cache_lines=int(system_control.DataCache.InitializedLines),system_control_violations=int(system_control.Violations),memory_violations=int(memory_policy.Violations),written_itcm=int(memory_policy.WrittenBytes),gpu=dict(frames=int(gp.CompleteScreenCaptures),bytes=len(gp.CompleteScreenFrameBytes),lists=int(gp.ListsConsumed),rejections=int(gp.Rejections),fault=str(gp.Fault),irq=bool(gp.IRQ.IsSet)),imu=dict(phase=str(im.OnDemand.Phase),services=int(im.OnDemand.CompletedServices),fifo_ready=bool(m['sysbus.iom4.imu_fifo'].Configuration.Ready)),peer=dict(state=str(hc.State),commands=int(hc.CommandsAccepted),events=int(hc.RuntimeEventsConsumed)),uart_rx=int(g.Uarts[0].RxBytesRead),touch_frames=int(m['sysbus.iom5.iom5_register_probe'].EventFramesCompleted),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)))
    active_before=active_reset_state()
    File.WriteAllText('/work-output/active-reset-before.json',json.dumps(active_before))
    File.WriteAllBytes('/work-output/active-reset-before-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    if not m.IsPaused or active_before['gpu']['frames']<5 or active_before['gpu']['rejections'] or active_before['cfsr'] or active_before['hfsr'] or active_before['memory_violations']:raise ValueError('Need clean active first-boot lifecycle')
    if active_before['pio_busy'] or active_before['program_busy'] or active_before['erase_busy']:raise ValueError('This scenario requires idle storage transaction at active-board reset')
    reset_entry=int(b.ReadDoubleWord(0x438004))&~1
    entry_watch=BlackwallResetEntryObserver(m,cpu,reset_entry)
    EmulationManager.Instance.CurrentEmulation.PauseAll()
    b.WriteDoubleWord(0xe000ed0c,0x05fa0004)
    EmulationManager.Instance.CurrentEmulation.StartAll();entry_deadline=time.time()+15
    while not entry_watch.Seen and time.time()<entry_deadline:time.sleep(0.001)
    if not entry_watch.Seen:raise ValueError('Reset entry pause did not complete; no concurrent host Pause issued')
    active_entry=active_reset_state()
    File.WriteAllText('/work-output/active-reset-entry.json',json.dumps(dict(seen=True,expected_pc=reset_entry,expected_sp=int(b.ReadDoubleWord(0x438000)),request=dict(address=0xe000ed0c,value=0x05fa0004,origin='external virtual NVIC input'),state=active_entry)))
    File.WriteAllBytes('/work-output/active-reset-entry-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    entry_watch.Detach()
    # Restore the declared startup execution-rate input; no guest register/state writes.
    cpu.PerformanceInMips=10
    rate_after=active_reset_state()
    File.WriteAllText('/work-output/active-reset-rate.json',json.dumps(dict(before=active_entry,after=rate_after)))
    if {k:v for k,v in active_entry.items() if k!='mips'}!={k:v for k,v in rate_after.items() if k!='mips'}:raise ValueError('Startup rate input changed paused state')
    warm_hold=BlackwallUiActivationHold(m,cpu,p['getter'])
    EmulationManager.Instance.CurrentEmulation.StartAll();warm_deadline=time.time()+180;warm_started=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    while not warm_hold.Held and not cpu.IsHalted and time.time()<warm_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-warm_started<20000*int(TimeInterval.TicksPerMillisecond):time.sleep(0.02)
    # Hold publishes Held before Pause; give the owning callback completion before host reads.
    if not warm_hold.Held:raise ValueError('Original main did not reach its post-reset getter')
    while not m.IsPaused and time.time()<warm_deadline:time.sleep(0.001)
    warm_getter=active_reset_state()
    File.WriteAllText('/work-output/active-reset-getter.json',json.dumps(warm_getter))
    File.WriteAllBytes('/work-output/active-reset-getter-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    if not m.IsPaused or int(cpu.PC.RawValue)!=p['getter']:raise ValueError('Post-reset getter did not pause the whole machine')
    exec(File.ReadAllText('/work/epoch-replay.py'))
    File.WriteAllText('/work-output/active-reset-final.json',json.dumps(active_reset_state()))
    Console.WriteLine('BLACKWALL_ACTIVE_RESET_COMPLETE')
except Exception as error:
    File.WriteAllText('/work-output/active-reset-error.json',json.dumps(dict(error=str(error))))
    Console.WriteLine('BLACKWALL_ACTIVE_RESET_ERROR '+str(error))
'''
def derive(case,o,power_diagnostic=False,shared_iom=False):
 manifest=S/'native-main-boot-manifest.json'
 if sha(manifest)!='55adce9d944491eea64d0cb12487e41ffa9fc70f1db067f774ce7b50bb0295e3':raise ValueError('Changed E05 acceptance')
 m=load(manifest);source=S/'ui-task-wait-native-01'/case
 if o.exists() or not o.is_relative_to(S) or o.is_relative_to(R):raise ValueError('New private output required')
 o.mkdir(mode=0o700,parents=True);(o/'exports/restart').mkdir(mode=0o700,parents=True);pins={};values={}
 for p in source.iterdir():
  if p.is_file() and p.suffix in ['.py','.json','.cs','.bin','.resc','.repl'] and p.name!='renode.process.json':
   expected=m['files'][str(p.relative_to(S))]['sha256']
   if sha(p)!=expected:raise ValueError('Changed source '+p.name)
   values[p.name]=p.read_bytes();pins[p.name]=expected
 meta={};components={}
 for field,name,digest in [('memory','reset-memory-protection-research-01/candidate-memory-policy.cs','29daafce028464c94a217260df7cc0016617b8be3c158498b4dced63b6837c5e'),('cache','reset-domain-acceptance-research-01/candidate-system-control.cs','5564e88984c662868830211cc1c2362fc15460159f1f4f54a967ef44623938f5')]:
  p=S/name
  if sha(p)!=digest:raise ValueError('Changed accepted reset component')
  values,meta=(with_memory_policy if field=='memory' else with_system_control)(S,values,meta,p);components[field]={'path':name,'sha256':digest}
 for name in ['renode-reset-aware-nvic.cs','renode-reset-entry-observer.cs']:
  p=R/'tools'/name;data=p.read_text();components[name]={'sha256':sha(p)}
  if name=='renode-reset-entry-observer.cs':data=completed_pause(data)
  values['activation.cs']+=b'\n'+data.encode()
 board=values['board.repl'].decode()
 if board.count('    PerformanceInMips: 10\n')!=1 or board.count('nvic: IRQControllers.NVIC @')!=1:raise ValueError('Changed CPU/NVIC profile')
 board=board.replace('    PerformanceInMips: 10\n','    PerformanceInMips: 10\n    InitVectorTableOffset: 0x438000\n').replace('nvic: IRQControllers.NVIC @','nvic: Miscellaneous.BlackwallResetAwareNVIC @')
 if shared_iom:
  from iom_shared_power_model import compose,board_profile
  frontier=S/'active-board-reset-power-native-01/stock24/exports/power-frontier.json';diagnostic=load(frontier)
  i7=next(v for v in diagnostic['ioms'] if v['module']==7);i4=next(v for v in diagnostic['ioms'] if v['module']==4)
  if not (diagnostic['request_before']==0x8e20 and diagnostic['proposed']==0x8f20 and diagnostic['changed_mask']==0x100 and diagnostic['buck_phase']=='active' and i7['phase']=='off-requested' and i7['request']==0 and i7['status']==0x100 and i4['phase']=='on' and i4['request']==i4['status']==0x20):raise ValueError('Not the observed shared HCPC/IOM7 reopen boundary')
  if not load(frontier.with_name('power-read-only.json'))['exact']:raise ValueError('Power observation changed paused state')
  values['strict.cs']=compose(values['strict.cs'].decode()).encode();board=board_profile(board)
  components['shared-iom']={'builder':'tools/iom_shared_power_model.py','builder_sha256':sha(R/'tools/iom_shared_power_model.py'),'power_frontier_sha256':sha(frontier),'source_class_sha256':'5221ccf22756c86c7049c73bc305a2a30c9df380f587373688faeed0a78826da','board_owners':5}
 values['board.repl']=board.encode()
 runtime=values['run.py'].decode();anchor='\ntry:\n    import clr,time,json\n'
 if runtime.count(anchor)!=1:raise ValueError('Changed original touch/UI phase')
 replay='try:\n    import clr,time,json\n'+runtime.split(anchor,1)[1]
 if replay.count('/work-output/')<10:raise ValueError('Missing original capture phase')
 values['epoch-replay.py']=replay.replace('/work-output/','/work-output/restart/').encode()
 extra=''
 if power_diagnostic:
  import ast
  power_source=S/'ring-app-wake-research-01/final-probe_reconnect_power.py'
  if sha(power_source)!='91ca1202c76971b94a5dce8350170f7a39b60f0fa1e462f25741ec48afe807a0':raise ValueError('Changed frozen post-stop exporter')
  tree=ast.parse(power_source.read_text());assign=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='POST' for t in n.targets))
  extra=ast.literal_eval(assign.value).replace('reconnect-power.json','power-frontier.json').replace('BLACKWALL_RECONNECT_POWER','BLACKWALL_ACTIVE_RESET_POWER')
  extra="\npower_read_before=dict(pc=int(cpu.PC.RawValue),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],sram_sha256=reset_digest(b.ReadBytes(0x20000000,0x380000,True)))\n"+extra
  extra+="\npower_read_after=dict(pc=int(cpu.PC.RawValue),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],sram_sha256=reset_digest(b.ReadBytes(0x20000000,0x380000,True)))\nFile.WriteAllText('/work-output/power-read-only.json',json.dumps(dict(before=power_read_before,after=power_read_after,exact=power_read_before==power_read_after)))\n"
  components['post-stop-power-exporter']={'path':str(power_source.relative_to(S)),'sha256':sha(power_source),'transform':'output filename/console prefix only; wrapped with paused state equality'}
 values['run.py']=(runtime+POST+extra).encode()
 for name,data in values.items():(o/name).write_bytes(data)
 (o/'runner-source.py').write_bytes(Path(__file__).read_bytes())
 checks=['reset_entry','volatile_reset','retained_backing','warm_getter','warm_screen','warm_lifecycle','fault_free','source_main_unmodified','cold_prefix_exact','rate_preserved_state']
 contract=dict(boundary={'kind':'bounded-capture'},comparison={'policy':'bounded-invariants','paths':[['main_sha256']]},checks=[{'path':['diagnostics',k],'eq':True} for k in checks],allowed_differences=['Accepted memory-read protection/cache-reset components replace legacy copies; original main is unchanged.','External NVIC SYSRESETREQ is a device input, never a host PC/SP/TCB seed.','Startup execution-rate input returns to10 MIPS at paused original reset entry, then original UI phase selects167 again.'],unresolved_differences=['Retained SRAM backing may be modified by original instructions between asynchronous request and reset entry.','Declared all-board virtual reset domains are not certification of Apollo physical reset/power retention.'])
 plan=dict(schema=2,id='active-board-reset-v1',image_id=IMAGE,cases={case:case},source_root=str(source.relative_to(S)),source_input_sha256=pins,components=components,component_transforms=meta,input_sha256={n:sha(o/n) for n in values if n not in ['plan.json','runner-source.py']},semantics={case:{'candidate':contract,'control':contract}},original_main_sha256=sha(o/'main.bin'),host_budget_seconds=780,hardware_accessed=False)
 semantic_spec(plan,case,False);(o/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');return plan

def audit(o,out):
 if out.exists() or not out.is_relative_to(S):raise ValueError('New private audit required')
 p=load(o/'plan.json');case=next(iter(p['cases']));e=o/'exports';files=['active-reset-before.json','active-reset-entry.json','active-reset-getter.json','active-reset-final.json','restart/boot-lifecycle.json','restart/touch.json','restart/'+('screen-complete.bin' if case=='stock24' else 'family-screen.bin')]
 missing=[name for name in files if not (e/name).exists()]
 if missing:
  out.mkdir(mode=0o700,parents=True)
  err=load(e/'active-reset-error.json') if (e/'active-reset-error.json').exists() else None
  integrity={name:sha(o/name)==digest for name,digest in p['input_sha256'].items()};integrity['process-removed']=load(o/'renode.process.json')['status']=='removed';integrity['no-host-error']=err is None
  observations={name:load(e/name) for name in ['active-reset-before.json','active-reset-entry.json','active-reset-getter.json','active-reset-final.json','power-frontier.json','power-read-only.json'] if (e/name).exists()}
  r=dict(passed=False,execution_passed=all(integrity.values()),execution_checks=integrity,semantic_validation={'passed':False,'status':'missing-post-reset-lifecycle'},missing=missing,error=err,observations=observations,full_e06_verified=False)
  (out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'passed':False,'execution_passed':r['execution_passed'],'missing':missing,'error':err}));return r
 before=load(e/'active-reset-before.json');entry=load(e/'active-reset-entry.json');v=entry['state'];after=load(e/'active-reset-final.json');getter=load(e/'active-reset-getter.json');life=load(e/'restart/boot-lifecycle.json');touch=load(e/'restart/touch.json');rate=load(e/'active-reset-rate.json')
 screen=e/'restart'/('screen-complete.bin' if case=='stock24' else 'family-screen.bin')
 cold=load(e/'touch.json');cold_life=load(e/'boot-lifecycle.json')
 source=S/p['source_root'];prefix=['before-input-sram.bin','after-input-sram.bin','before-reply-sram.bin','after-reply-sram.bin','app-request-sram.bin','ui-dispatch-sram.bin']
 checks=dict(reset_entry=entry['seen'] and v['pc']==entry['expected_pc'] and v['sp']==entry['expected_sp'] and v['vtor']==0x438000 and v['reset_count']==before['reset_count']+1==after['reset_count'],volatile_reset=v['basepri']==0 and not v['icache'] and not v['dcache'] and v['cache_lines']==0 and v['gpu']['frames']==v['gpu']['lists']==0 and v['gpu']['bytes']==0 and not v['imu']['fifo_ready'] and v['imu']['phase']=='unselected' and v['peer']['state']=='Unreleased' and v['peer']['commands']==v['peer']['events']==0 and v['uart_rx']==v['touch_frames']==0,retained_backing=all(before[k]==v[k] for k in ['itcm_sha256','kv_sha256','fs_sha256']) and before['written_itcm']==v['written_itcm'],warm_getter=getter['paused'] and getter['pc']==load(o/'touch-profile.json')['getter'] and getter['peer']['commands']==59 and getter['peer']['state']=='Complete',warm_screen=screen.stat().st_size==576*288 and len(set(screen.read_bytes()))>1,warm_lifecycle=life['stop_reason']=='virtual-limit' and life['elapsed_ticks']>=100000000 and len(life['frames'])>=3 and life['skipped_frames']==0 and after['gpu']['frames']>=5,fault_free=all(s['cfsr']==s['hfsr']==s['memory_violations']==s['system_control_violations']==s['gpu']['rejections']==0 and s['gpu']['fault']=='' for s in [before,v,getter,after]) and touch['memory_violations']==touch['cfsr']==touch['hfsr']==cold['memory_violations']==cold['cfsr']==cold['hfsr']==0 and all(g['accesses']==0 for g in touch['guards']+cold['guards']) and all(not state['halted'] for state in [before,v,getter,after]) and cold_life['stop_reason']=='virtual-limit',source_main_unmodified=sha(o/'main.bin')==p['original_main_sha256']==sha(source/'main.bin'),cold_prefix_exact=all(sha(e/name)==sha(source/'exports'/name) for name in prefix),rate_preserved_state={k:x for k,x in rate['before'].items() if k!='mips'}=={k:x for k,x in rate['after'].items() if k!='mips'} and rate['after']['mips']==10)
 from run_post_screen_lifecycle import task_wait_witness
 witness=task_wait_witness(o,life,touch,case,export_subdir='exports/restart')
 callback=touch.get('display_reply',{}).get('callback',{}) if case=='stock24' else load(e/'restart/family-boot.json')['callback']
 replay=(o/'epoch-replay.py').read_text()
 if case=='stock24':
  return_watch="callback_end=BlackwallRuntimeConnectionObserver(m,cpu,p['isr'],0x4b7a58,0x4456ec,p['tcb_slot'])" in replay
  return_row=load(e/'restart/ui-layout.json')['first'].get('8',[])
  return_watch=return_watch and len(return_row)==11 and return_row[1]==0x4456ec and return_row[8]==callback['entry'][4] and (return_row[9]&0x1ff)==0
 else:
  ui=load(o/'touch-profile.json')['wake']['ui']
  return_watch=ui['return_site']==0x445694 and ui['callback']==0x4ad7e4 and "callback_end=BlackwallRuntimeConnectionObserver(m,cpu,p['isr'],wake['ui']['callback'],wake['ui']['return_site'],p['tcb_slot'])" in replay
 checks['warm_lifecycle']=checks['warm_lifecycle'] and return_watch and witness['passed'] and callback.get('stopped',False) and callback['pc']==(life['after']['pc'] if case=='stock24' else 0x445694) and callback['entry'][0]==2 and callback['entry'][4]==callback['exit'][1] and (callback['entry'][5]&0x1ff)==0 and after['imu']['fifo_ready'] and after['imu']['phase']=='disabled'
 result=finish_capture(dict(case=case,control=False,boundary_kind='bounded-capture',observed=after,selected_observation={'events':[],'sequence':0,'dropped_events':0},diagnostics=checks,main_sha256=sha(o/'main.bin')),{'main_sha256':p['original_main_sha256']},semantic_spec(p,case,False))
 integrity={n:sha(o/n)==digest for n,digest in p['input_sha256'].items()};integrity['process-removed']=load(o/'renode.process.json')['status']=='removed';integrity['no-runtime-error']='BLACKWALL_ACTIVE_RESET_ERROR' not in (o/'renode.log').read_text() and 'BLACKWALL_TOUCH_RUNTIME_ERROR' not in (o/'renode.log').read_text()
 result.update(execution_passed=all(integrity.values()),execution_checks=integrity,before=before,entry=entry,warm_getter=getter,warm_task_wait_witness=witness,warm_lifecycle=life,full_e06_verified=False,hardware_accessed=False)
 result['capture_hashes']={str(child.relative_to(o)):sha(child) for child in o.rglob('*') if child.is_file() and 'audit' not in child.relative_to(o).parts}
 result['passed']=result['execution_passed'] and result['semantic_validation']['passed'];out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':result['passed'],'checks':checks}));return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--case',choices=['stock24','stock23','cfw'],default='stock24');p.add_argument('--power-diagnostic',action='store_true');p.add_argument('--shared-iom',action='store_true');p.add_argument('--audit-existing',action='store_true');p.add_argument('--audit-output',type=Path);a=p.parse_args();o=a.output.resolve()
 if a.audit_existing:
  if a.audit_output is None:p.error('Separate audit output required')
  r=audit(o,a.audit_output.resolve())
 else:
  derive(a.case,o,a.power_diagnostic,a.shared_iom)
  execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','--mount',f'type=bind,source={o/"exports"},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=780)
  r=audit(o,o/'audit')
 raise SystemExit(0 if r['passed'] else 1)
