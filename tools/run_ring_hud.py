"""Extend the fixed ring-wake peripheral scenario to original UI return and frames."""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from run_native_candidate import semantic_spec,finish_capture
from ring_input_scenario import source_profile,validate_anchors,inspect as inspect_ring
from ring_wake_runtime import RUNTIME
from sync_peer_roundtrip import frame
R=Path(__file__).resolve().parents[1];S=Path.home()/'Library/Application Support/Blackwall/simulator'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
EXTEND=r'''
    if not display_reply or not display_reply.get('callback',{}).get('stopped'):raise ValueError('Original ring wake UI entry missing')
    if not m.IsPaused or int(cpu.PerformanceInMips)!=10:raise ValueError('Expected whole-machine 10MIPS UI-entry boundary')
    gp=g.GpuCommandDevice
    def screen_state():
        return dict(registers=regs(),instructions=int(cpu.ExecutedInstructions),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pc=int(cpu.PC.RawValue),tcb=int(b.ReadDoubleWord(p['tcb_slot'])),frames=int(gp.CompleteScreenCaptures),bytes=len(gp.CompleteScreenFrameBytes),draws=int(gp.Draws),lists=int(gp.ListsConsumed),gpu_rejections=int(gp.Rejections),gpu_fault=str(gp.Fault),clock_mode=int(g.McuClock.ModeWord),mips=int(cpu.PerformanceInMips),fifo_ready=bool(m['sysbus.iom4.imu_fifo'].Configuration.Ready),halted=bool(cpu.IsHalted))
    entry_state=screen_state()
    if ((entry_state['clock_mode']>>3)&3)!=2:raise ValueError('Expected original HP clock path')
    File.WriteAllBytes('/work-output/ring-rate-before-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    cpu.PerformanceInMips=167
    rate_after=screen_state()
    File.WriteAllBytes('/work-output/ring-rate-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    if {k:v for k,v in entry_state.items() if k!='mips'}!={k:v for k,v in rate_after.items() if k!='mips'}:raise ValueError('Execution rate input changed paused guest state')
    end_pc=wake['ui']['return_site']
    returned=BlackwallRuntimeConnectionObserver(m,cpu,int(uart.IrqHandlerAddress),end_pc,end_pc,p['tcb_slot'])
    start_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+90
    while not returned.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start_ticks<1000*int(TimeInterval.TicksPerMillisecond):time.sleep(0.01)
    m.Pause()
    return_state=screen_state()
    callback_return=dict(stopped=bool(returned.Stopped),entry=[int(v) for v in returned.Entry],exit=[int(v) for v in returned.Exit],state=return_state)
    File.WriteAllBytes('/work-output/ring-ui-return-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    if not returned.Stopped:raise ValueError('Original ring UI callback did not return')
    start_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+90
    while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start_ticks<500*int(TimeInterval.TicksPerMillisecond):
        if cpu.IsHalted or gp.Rejections or gp.CompleteScreenHasDetail:break
        time.sleep(0.02)
    m.Pause();first=screen_state()
    File.WriteAllBytes('/work-output/ring-first-frame.bin',gp.CompleteScreenFrameBytes)
    File.WriteAllBytes('/work-output/ring-first-frame-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    if not gp.CompleteScreenHasDetail:raise ValueError('No original ring HUD detail frame')
    samples=[]
    for n in range(20):
        def pause_sample():m.Pause();return True
        timer=BlackwallRuntimeInputDelay(m,5,Func[bool](pause_sample))
        EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+60
        while not timer.Accepted and time.time()<deadline:
            if cpu.IsHalted:break
            time.sleep(0.002)
        if not timer.Accepted:raise ValueError('Frame sample pause did not complete')
        samples.append(screen_state())
        File.WriteAllBytes('/work-output/ring-frame-%02d.bin'%n,gp.CompleteScreenFrameBytes)
    final=screen_state();guard_values=[]
    for item in result['guards']:
        owner=m['sysbus.'+item['name']];guard_values.append(dict(name=item['name'],accesses=int(owner.AccessCount),address=int(owner.LastAddress)))
    value=dict(entry=entry_state,rate_after=rate_after,callback_entry=display_reply['callback'],callback_return=callback_return,first=first,final=final,samples=samples,guards=guard_values,rows=[[int(v) for v in row] for row in trace.Rows],overflow=bool(trace.Overflow),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),system_control_violations=int(system_control.Violations),hardware_accessed=False)
    File.WriteAllText('/work-output/ring-screen.json',json.dumps(value))
    File.WriteAllBytes('/work-output/ring-final-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
'''


CONTROL_END=r'''
    regs=lambda:[int(cpu.GetRegister(n).RawValue) for n in range(16)]
    gp=g.GpuCommandDevice
    def control_state():
        return dict(registers=regs(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),instructions=int(cpu.ExecutedInstructions),frames=int(gp.CompleteScreenCaptures),bytes=len(gp.CompleteScreenFrameBytes),gpu_rejections=int(gp.Rejections),gpu_fault=str(gp.Fault),uart_read=int(uart.RxBytesRead),uart_pending=int(uart.RxPending),ring_tick=int(b.ReadDoubleWord(p['last_tick'])),role=int(b.ReadByte(p['flow']['role_slot'])),halted=bool(cpu.IsHalted),mips=int(cpu.PerformanceInMips))
    before=control_state()
    File.WriteAllBytes('/work-output/ring-control-before-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    def pause_control():m.Pause();return True
    timer=BlackwallRuntimeInputDelay(m,1000,Func[bool](pause_control))
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+180
    while not timer.Accepted and time.time()<deadline:
        if cpu.IsHalted or (m.IsPaused and not timer.Fired):break
        time.sleep(0.002)
    m.Pause();after=control_state();guards=[]
    for name in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail'):
        item=m['sysbus.'+name];guards.append(dict(name=name,accesses=int(item.AccessCount),address=int(item.LastAddress)))
    value=dict(before=before,after=after,timer_accepted=bool(timer.Accepted),timer_started=int(timer.StartedAt),timer_fired_at=int(timer.FiredAt),rows=[[int(v) for v in row] for row in trace.Rows],overflow=bool(trace.Overflow),guards=guards,cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),system_control_violations=int(system_control.Violations),hardware_accessed=False)
    File.WriteAllText('/work-output/ring-control.json',json.dumps(value))
    File.WriteAllBytes('/work-output/ring-control-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
except Exception as error:
    File.WriteAllText('/work-output/ring-screen-error.json',json.dumps(dict(error=str(error))))
    Console.WriteLine('BLACKWALL_RING_CONTROL_ERROR '+str(error))
'''

def derive(o,case,control=False):
 manifest=S/'active-reset-manifest.json'
 if sha(manifest)!='e7c16643e89b9000f9f2d9929b2961cdfb7cee20cdae2c307d2e85a16e83fb68':raise ValueError('Changed accepted functional board')
 if sha(R/'tools/ring_wake_runtime.py')!='f2a6dac1cfcb22ce88aa9565aa083a3a7f7a988aa85e9acfed63a2cb08489857':raise ValueError('Changed original ring runtime')
 m=load(manifest);source=S/'active-board-reset-shared-native-01'/case;profile=source_profile(case)
 if o.exists() or not o.is_relative_to(S) or o.is_relative_to(R):raise ValueError('New private output required')
 o.mkdir(mode=0o700,parents=True);(o/'exports').mkdir(mode=0o700);pins={}
 for p in source.iterdir():
  if p.is_file() and p.suffix in ['.py','.json','.cs','.resc','.repl','.bin'] and p.name!='renode.process.json':
   if sha(p)!=m['files'][str(p.relative_to(S))]['sha256']:raise ValueError('Changed fixed input '+p.name)
   shutil.copyfile(p,o/p.name);pins[p.name]=sha(p)
 raw=(o/'main.bin').read_bytes();validate_anchors(raw,profile)
 if sha(o/'main.bin')!=profile['ring']['raw_sha256']:raise ValueError('Original ring main required')
 base=load(o/'touch-profile.json');ring=profile['ring'];report=bytes.fromhex('00096100020aa7e8030000');wire=frame(0x9010,1,struct.pack('<4H',0x901,0x90,0,11)+report)
 selected=dict(base,schema=1,scenario='ring-wake',recipe_version=1,ring_receiver=ring['receiver'],ring_caller=ring['receiver_caller'],slider=ring['slider'],ring_relay=ring['relay_callback'],ring_enqueue=ring['queue_wrapper'],last_tick=ring['last_ring_tick'],hook=ring.get('hook'),fallback=ring.get('fallback'),wake=profile['wake'],flow=profile['flow'],report_hex=report.hex(),wire_hex=wire.hex(),baseline_sha256=ring['raw_sha256'],raw_sha256=sha(o/'main.bin'),model_sha256=sha(o/'strict.cs'),shared_iom_gate=True,gaf_calculation_supported=False)
 (o/'ring-profile.json').write_text(json.dumps(selected,indent=2)+'\n');(o/'ring-source-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
 connection=load(o/'connection-profile.json');connection['model_sha256']=sha(o/'strict.cs');(o/'connection-profile.json').write_text(json.dumps(connection,indent=2)+'\n')
 runtime=(o/'run.py').read_text();anchor='\ntry:\n    import clr,time,json\n'
 if runtime.count(anchor)!=1:raise ValueError('Changed main-hold phase boundary')
 end="except Exception as error:\n    Console.WriteLine('BLACKWALL_RING_RUNTIME_ERROR '+str(error))"
 if RUNTIME.count(end)!=1:raise ValueError('Changed ring export boundary')
 ring_runtime=RUNTIME.replace('while not timer.Fired and not m.IsPaused','while not timer.Accepted').replace('if not timer.Fired or len(requests)!=1','if not timer.Accepted or len(requests)!=1')
 ring_runtime=ring_runtime.replace(end,EXTEND+end.replace('    Console.WriteLine',"    File.WriteAllText('/work-output/ring-screen-error.json',json.dumps(dict(error=str(error))))\n    Console.WriteLine"))
 prefix=runtime.split(anchor,1)[0]
 if control:
  ring_boundary="    stop=BlackwallRuntimeConnectionObserver(m,cpu,int(uart.IrqHandlerAddress),p['ring_receiver'],p['ring_caller'],p['tcb_slot'])"
  if RUNTIME.count(ring_boundary)!=1:raise ValueError('Changed ring observer setup')
  ring_runtime=RUNTIME.split(ring_boundary,1)[0]+CONTROL_END
 (o/'run.py').write_text(prefix+'\n'+ring_runtime);(o/'runner-source.py').write_bytes(Path(__file__).read_bytes())
 checks=['legacy_ring_verified','ui_callback_returned','same_ui_thread','rate_preserved_state','frame_generated','frame_lifecycle','fault_free','original_model']
 contract=dict(boundary={'kind':'bounded-capture'},comparison={'policy':'bounded-invariants','paths':[['model_sha256'],['main_sha256']]},checks=[{'path':['diagnostics',k],'eq':True} for k in checks],allowed_differences=['Existing v1 ring UART relay replaces initial touch; fixed functional sensor/GPU/power model unchanged.','Declared 10 to167 MIPS HP UI execution-rate input; no guest register/SRAM/time writes.'],unresolved_differences=['Virtual opposite temple, not direct R1 BLE or physical timing.','Cold sensor service and reference GPU retain their declared numerical/physical limitations.'])
 control_checks=['no_ring_consumed','no_ui_frame','one_second_progress','fault_free','original_model']
 control_contract=dict(contract,checks=[{'path':['diagnostics',k],'eq':True} for k in control_checks])
 plan=dict(schema=2,id='ring-wake-hud-functional-v1',image_id=IMAGE,cases={case:case},source_root=str(source.relative_to(S)),source_input_sha256=pins,startup_prefix_sha256=hashlib.sha256(prefix.encode()).hexdigest(),input_sha256={p.name:sha(p) for p in o.iterdir() if p.is_file() and p.name not in ['plan.json','runner-source.py']},semantics={case:{'candidate':contract,'control':control_contract}},main_sha256=sha(o/'main.bin'),model_sha256=sha(o/'strict.cs'),control=control,hardware_accessed=False)
 semantic_spec(plan,case,False);(o/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')

def audit(o,out):
 if out.exists() or not out.is_relative_to(S) or out.is_relative_to(o):raise ValueError('New separate private audit output required')
 p=load(o/'plan.json');case=next(iter(p['cases']));e=o/'exports'
 if p.get('control'):return audit_control(o,out,p,case)
 if not (e/'ring-screen.json').exists():
  r=dict(passed=False,execution_passed=False,error=load(e/'ring-screen-error.json') if (e/'ring-screen-error.json').exists() else None,full_e11_verified=False);out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));return r
 dispatch=load(o/'ring-profile.json')['wake']['ui']['dispatch'];raw_main=(o/'main.bin').read_bytes()
 if raw_main[dispatch-0x438000:dispatch-0x438000+2]!=bytes.fromhex('feb5'):raise ValueError('Changed original dispatcher stack frame')
 legacy=inspect_ring(o,out/'legacy-ring');x=load(e/'ring-screen.json');entry=x['callback_entry']['entry'];exit=x['callback_return']['exit'];controls={n:sha(o/n)==h for n,h in p['input_sha256'].items()};controls['process_removed']=load(o/'renode.process.json')['status']=='removed'
 before={k:v for k,v in x['entry'].items() if k!='mips'};after={k:v for k,v in x['rate_after'].items() if k!='mips'};raw=(e/'ring-final-sram.bin').read_bytes();tcb=entry[4];offset=tcb-0x20000000;name=raw[offset+52:offset+84].split(b'\0')[0].decode('ascii',errors='replace')
 checks=dict(legacy_ring_verified=legacy['passed'],ui_callback_returned=x['callback_return']['stopped'] and x['callback_return']['state']['pc']==load(o/'ring-profile.json')['wake']['ui']['return_site'],same_ui_thread=entry[0]==2 and entry[2]+32==exit[0] and entry[4]==exit[1] and (entry[5]&511)==(exit[2]&511)==0 and name=='ui_task',rate_preserved_state=before==after and sha(e/'ring-rate-before-sram.bin')==sha(e/'ring-rate-after-sram.bin'),frame_generated=x['first']['bytes']==576*288 and len((e/'ring-first-frame.bin').read_bytes())==576*288 and any((e/'ring-first-frame.bin').read_bytes()),frame_lifecycle=x['final']['frames']>=x['first']['frames']+3 and len(x['samples'])==20 and x['final']['ticks']-x['first']['ticks']==100000000 and x['final']['bytes']==576*288,fault_free=x['cfsr']==x['hfsr']==x['memory_violations']==x['system_control_violations']==x['final']['gpu_rejections']==0 and not x['final']['gpu_fault'] and all(v['accesses']==0 for v in x['guards']) and not x['overflow'],original_model=sha(o/'strict.cs')==p['source_input_sha256']['strict.cs'])
 r=finish_capture(dict(case=case,control=False,boundary_kind='bounded-capture',observed=x['final'],selected_observation={'events':x['rows'],'sequence':len(x['rows']),'dropped_events':int(x['overflow'])},diagnostics=checks,main_sha256=sha(o/'main.bin'),model_sha256=sha(o/'strict.cs')),{'main_sha256':p['main_sha256'],'model_sha256':p['model_sha256']},semantic_spec(p,case,False));r.update(execution_passed=all(controls.values()),execution_checks=controls,screen=x,legacy_ring_report_sha256=sha(out/'legacy-ring/report.json'),full_e11_verified=False);r['passed']=r['execution_passed'] and r['semantic_validation']['passed'];(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');(out/'auditor-source.py').write_bytes(Path(__file__).read_bytes());print(json.dumps({'passed':r['passed'],'checks':checks}));return r


def audit_control(o,out,p,case):
 e=o/'exports'
 if not (e/'ring-control.json').exists():
  r=dict(passed=False,execution_passed=False,error=load(e/'ring-screen-error.json') if (e/'ring-screen-error.json').exists() else None,full_e11_verified=False);out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));return r
 x=load(e/'ring-control.json');before=x['before'];after=x['after'];controls={n:sha(o/n)==h for n,h in p['input_sha256'].items()};controls['process_removed']=load(o/'renode.process.json')['status']=='removed'
 checks=dict(no_ring_consumed=before['uart_read']==after['uart_read'] and before['ring_tick']==after['ring_tick'] and before['role']==after['role'] and not any(r[0] in [0,3,20,21,30,56] for r in x['rows']),no_ui_frame=before['frames']==after['frames']==0,one_second_progress=x['timer_accepted'] and x['timer_fired_at']-x['timer_started']==1000000000 and after['ticks']-before['ticks']==1000000000 and after['instructions']>before['instructions'],fault_free=x['cfsr']==x['hfsr']==x['memory_violations']==x['system_control_violations']==after['gpu_rejections']==0 and not after['gpu_fault'] and all(v['accesses']==0 for v in x['guards']) and not x['overflow'] and not after['halted'],original_model=sha(o/'strict.cs')==p['source_input_sha256']['strict.cs'])
 r=finish_capture(dict(case=case,control=True,boundary_kind='bounded-capture',observed=after,selected_observation={'events':x['rows'],'sequence':len(x['rows']),'dropped_events':int(x['overflow'])},diagnostics=checks,main_sha256=sha(o/'main.bin'),model_sha256=sha(o/'strict.cs')),{'main_sha256':p['main_sha256'],'model_sha256':p['model_sha256']},semantic_spec(p,case,True));r.update(execution_passed=all(controls.values()),execution_checks=controls,control_observation=x,full_e11_verified=False);r['passed']=r['execution_passed'] and r['semantic_validation']['passed'];out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');(out/'auditor-source.py').write_bytes(Path(__file__).read_bytes());print(json.dumps({'passed':r['passed'],'checks':checks}));return r

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);parser.add_argument('--case',choices=['stock24','stock23','cfw'],default='stock24');parser.add_argument('--control',action='store_true');parser.add_argument('--audit-existing',action='store_true');parser.add_argument('--audit-output',type=Path);a=parser.parse_args();o=a.output.resolve()
 if a.audit_existing:r=audit(o,a.audit_output.resolve())
 else:
  derive(o,a.case,a.control);execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','--mount',f'type=bind,source={o/"exports"},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=780)
  (o/'capture-files.json').write_text(json.dumps({'files':{str(p.relative_to(o)):sha(p) for p in o.rglob('*') if p.is_file() and '__pycache__' not in p.parts}},indent=2)+'\n');r=audit(o,o.parent/(o.name+'-audit'))
 raise SystemExit(0 if r['passed'] else 1)
