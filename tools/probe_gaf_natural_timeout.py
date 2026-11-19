"""Run original request2's full timeout loop and stop at its real setter continuation."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
import capstone
from reset_restart_profiles import RENODE_IMAGE
from run_renode_m55_probe import execute
from verify_observer_suspension import validate

OBSERVER='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 using Antmicro.Renode.Core;using Antmicro.Renode.Peripherals.CPU;
 public sealed class BlackwallNaturalGafTimeoutStop {
  public BlackwallNaturalGafTimeoutStop(IMachine m,CortexM cpu,BlackwallImuGafFrozenCore fault,uint pc,uint slot) {
   cpu.AddHook(pc,(c,a)=>{if(!fault.Active || fault.Requests!=1 || fault.BusyReads==0)return;
    Seen=true;PC=(uint)a;R0=(uint)cpu.GetRegister(0).RawValue;SP=(uint)cpu.GetRegister(13).RawValue;
    LR=(uint)cpu.GetRegister(14).RawValue;Xpsr=(uint)cpu.GetRegister(25).RawValue;
    Tcb=m.SystemBus.ReadDoubleWord(slot);BusyReads=fault.BusyReads;m.Pause();});
  }
  public bool Seen {get;private set;}public uint PC {get;private set;}public uint R0 {get;private set;}
  public uint SP {get;private set;}public uint LR {get;private set;}public uint Xpsr {get;private set;}
  public uint Tcb {get;private set;}public int BusyReads {get;private set;}
 }
}
'''
PAUSE_OBSERVER='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 using Antmicro.Renode.Core;using Antmicro.Renode.Peripherals.CPU;
 public sealed class BlackwallMachinePauseObserver {
  public BlackwallMachinePauseObserver(IMachine machine,CortexM cpu) {
   machine.StateChanged+=(m,e)=>{
    if(Seen || (e.CurrentState!=MachineStateChangedEventArgs.State.Paused && e.CurrentState!=MachineStateChangedEventArgs.State.Aborted))return;
    Seen=true;InternalPause=m.InternalPause;State=e.CurrentState.ToString();PC=(uint)cpu.PC.RawValue;Trace=System.Environment.StackTrace;
   };
  }
  public bool Seen {get;private set;}public bool InternalPause {get;private set;}
  public string State {get;private set;}public string Trace {get;private set;}public uint PC {get;private set;}
 }
}
'''

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def build(s,o,local_version_hex=None,local_version_limit=0,virtual_budget_ms=300000,shared_iom_gate=False,observe_pause=False,watchdog_diagnostics=False):
 if not 1000<=virtual_budget_ms<=300000:raise ValueError('Bounded virtual observation required')
 if local_version_hex is None:
  if local_version_limit!=0:raise ValueError('Local version limit needs an explicit identity')
 else:
  local_version_hex=bytes.fromhex(local_version_hex).hex()
  if len(local_version_hex)!=16 or not 1<=local_version_limit<=32:raise ValueError('Explicit eight-byte identity and limit1..32 required')
 if o.exists() or not o.resolve().is_relative_to(s.resolve()) or shutil.disk_usage(s).free<1024**3:raise ValueError('Fresh private output and 1 GiB free required')
 ref=s/'main-read-routing-pilot-01/01-baseline';validate(ref);raw=(ref/'main.bin').read_bytes()
 if hashlib.sha256(raw).hexdigest()!='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a':raise ValueError('Changed original main')
 source=json.loads((s/'imu-parameter-full-setter-01/report.json').read_text());entry=next(c['entry'] for c in source['cases'] if c['case']=='stock24')
 md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS);code=list(md.disasm(raw[entry-0x438000:entry-0x438000+0x710],entry));calls=[i for i,x in enumerate(code) if x.mnemonic=='bl' and x.op_str=='#0x55405c']
 if len(calls)!=2 or [code[i-2].op_str for i in calls]!=['r1, #2','r1, #4'] or code[calls[0]+1].mnemonic!='orrs':raise ValueError('Changed original request caller contract')
 target=code[calls[0]].address+code[calls[0]].size
 if target!=0x55496e:raise ValueError('Changed first request continuation')
 o.mkdir(mode=0o700,parents=True);(o/'exports').mkdir();inputs=json.loads((ref/'connection-inputs.json').read_text())
 for n in inputs:
  if subprocess.run(['cp','-c',str(ref/n),str(o/n)],capture_output=True).returncode:shutil.copyfile(ref/n,o/n)
 baseline=s/'reset-domain-acceptance-research-01/baseline-system-control.cs';candidate=s/'reset-domain-acceptance-research-01/candidate-system-control.cs';model=(o/'strict.cs').read_bytes()
 if sha(baseline)!='82067ed1bdc22110330293a607718714e92b074d6835bee55cd761ae9e58d53c' or sha(candidate)!='5564e88984c662868830211cc1c2362fc15460159f1f4f54a967ef44623938f5' or model.count(baseline.read_bytes())!=1:raise ValueError('Changed cache control baseline')
 model=model.replace(baseline.read_bytes(),candidate.read_bytes(),1)
 if local_version_hex is not None:
  from runtime_local_version_model import compose
  model=compose(model.decode()).encode()
  board=(o/'board.repl').read_text();anchor='    runtimeConnectionEventHex:'
  if board.count(anchor)!=1:raise ValueError('Unknown runtime peer profile')
  (o/'board.repl').write_text(board.replace(anchor,'    runtimeLocalVersionHex: "'+local_version_hex+'"\n    runtimeLocalVersionLimit: '+str(local_version_limit)+'\n'+anchor))
 if shared_iom_gate:
  from iom_shared_power_model import compose as power_compose,board_profile
  model=power_compose(model.decode()).encode();(o/'board.repl').write_text(board_profile((o/'board.repl').read_text()))
 (o/'strict.cs').write_bytes(model)
 (o/'timeout-stop.cs').write_text(OBSERVER)
 with (o/'activation.cs').open('a') as f:f.write('\n'+OBSERVER+ ('\n'+PAUSE_OBSERVER if observe_pause else ''))
 profile=json.loads((o/'connection-profile.json').read_text());profile['model_sha256']=sha(o/'strict.cs')
 if local_version_hex is not None:profile['local_version']=dict(identity_hex=local_version_hex,limit=local_version_limit,physical_identity_verified=False)
 if shared_iom_gate:profile['iom_shared_gate']=True
 (o/'connection-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
 old='''    cpu.IsHalted=False
    EmulationManager.Instance.CurrentEmulation.PauseAll()
    phase_wall=time.time()
    EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMilliseconds(500))
    phase_wall=time.time()-phase_wall
    stop_reason='fixed-virtual-boundary'
    File.WriteAllText('/work-output/fixed-boundary.json',json.dumps(dict(start_ticks=start_ticks,end_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),wall_seconds=phase_wall,requested_ms=500,registers=[int(cpu.GetRegister(k).RawValue) for k in range(16)],instructions=int(cpu.ExecutedInstructions))))'''
 new='''    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallNaturalGafTimeoutStop').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallNaturalGafTimeoutStop
    d=m['sysbus.iom4.imu_identity'].OnDemand
    timeout_stop=BlackwallNaturalGafTimeoutStop(m,cpu,d,TARGET,p['tcb_slot'])
    phase_wall=time.time();deadline=phase_wall+1500;next_progress=phase_wall
    cpu.IsHalted=False
    EmulationManager.Instance.CurrentEmulation.StartAll()
    while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start_ticks<300000*int(TimeInterval.TicksPerMillisecond):
        if time.time()>=next_progress:
            File.AppendAllText('/work-output/timeout-progress.jsonl',json.dumps(dict(wall_seconds=time.time()-phase_wall,busy_reads=int(d.BusyReads),requests=int(d.Requests),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)))+chr(10))
            next_progress=time.time()+30
        time.sleep(0.01)
    stop_reason='natural-timeout-caller' if timeout_stop.Seen else 'device-or-guard-pause' if m.IsPaused else 'host-deadline' if time.time()>=deadline else 'virtual-budget'
    m.Pause()
    File.WriteAllText('/work-output/natural-timeout.json',json.dumps(dict(seen=bool(timeout_stop.Seen),pc=int(timeout_stop.PC),r0=int(timeout_stop.R0),sp=int(timeout_stop.SP),lr=int(timeout_stop.LR),xpsr=int(timeout_stop.Xpsr),tcb=int(timeout_stop.Tcb),busy_reads=int(timeout_stop.BusyReads),wall_seconds=time.time()-phase_wall,stop_reason=stop_reason,host_pc_register_seed=False,original_main_executed=True,hardware_accessed=False)))'''.replace('TARGET',str(target))
 if virtual_budget_ms!=300000:new=new.replace('<300000*','<'+str(virtual_budget_ms)+'*')
 if observe_pause:
  anchor="    timeout_stop=BlackwallNaturalGafTimeoutStop(m,cpu,d,"+str(target)+",p['tcb_slot'])"
  new=new.replace(anchor,anchor+"\n    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMachinePauseObserver\n    pause_observer=BlackwallMachinePauseObserver(m,cpu)")
 runtime=(o/'run.py').read_text()
 if runtime.count(old)!=1:raise ValueError('Changed fixed-phase recipe')
 (o/'run.py').write_text(runtime.replace(old,new))
 runtime=(o/'run.py').read_text()
 anchor="    File.WriteAllBytes('/work-output/frozen-core-sram.bin',m.SystemBus.ReadBytes(0x20000000,0x380000,True))"
 diagnostic='''    frontier_registers=[int(cpu.GetRegister(k).RawValue) for k in range(16)]
    frontier_buffers={}
    for k in (0,1,2,3,4,5,6,7,8,9,10):
        address=frontier_registers[k]
        if 0x20000000<=address<=0x20380000-64:
            frontier_buffers[str(k)]=dict(address=address,bytes=[int(v) for v in b.ReadBytes(address,64,True)])
    File.WriteAllText('/work-output/timeout-frontier.json',json.dumps(dict(registers=frontier_registers,buffers=frontier_buffers,tcb=int(b.ReadDoubleWord(p['tcb_slot'])),xpsr=int(cpu.GetRegister(25).RawValue),peer=dict(state=str(peer.State),commands=int(peer.CommandsAccepted),events=int(peer.RuntimeEventsConsumed)),guards=[dict(name=x['name'],accesses=int(m['sysbus.'+x['name']].AccessCount),address=int(m['sysbus.'+x['name']].LastAddress),operation=str(m['sysbus.'+x['name']].LastOperation)) for x in result['guards']])))
'''
 if local_version_hex is not None:diagnostic+="    File.WriteAllText('/work-output/local-version.json',json.dumps(dict(identity=p['local_version'],commands=int(peer.LocalVersionCommands),replies=int(peer.LocalVersionReplies),pending=bool(peer.RuntimeEventPending),gpio_irq=bool(g.GpioInterrupts.IRQ.IsSet))))\n"
 if shared_iom_gate:diagnostic+="    File.WriteAllText('/work-output/iom-shared-power.json',json.dumps(dict(powers=[dict(module=int(pair.Key),selected=bool(pair.Value.SharedIomGate),phase=str(pair.Value.Phase),request=int(pair.Value.RequestWord),status=int(pair.Value.StatusWord),requests=int(pair.Value.Requests),responses=int(pair.Value.Responses),off_requests=int(pair.Value.OffRequests),power_cycles=int(pair.Value.PowerCycles),device_power_downs=int(m['sysbus.iom'+str(pair.Key)].PowerDowns)) for pair in g.IomPowers],physical_retention_verified=False,hardware_accessed=False)))\n"
 if observe_pause:diagnostic+="    File.WriteAllText('/work-output/pause-observer.json',json.dumps(dict(seen=bool(pause_observer.Seen),internal_pause=bool(pause_observer.InternalPause),state=str(pause_observer.State),pc=int(pause_observer.PC),trace=str(pause_observer.Trace),machine_aborted=bool(m.IsAborted))))\n"
 if watchdog_diagnostics:diagnostic+="    watchdog=m['sysbus.wdt'];reset_gate=m['sysbus.rstgen']\n    File.WriteAllText('/work-output/watchdog-state.json',json.dumps(dict(configuration=int(watchdog.Configuration),configuration_reads=int(watchdog.ConfigurationReads),configuration_writes=int(watchdog.ConfigurationWrites),restarts=int(watchdog.Restarts),interrupt_events=int(watchdog.InterruptEvents),interrupt_pending=bool(watchdog.InterruptPending),irq=bool(watchdog.IRQ.IsSet),reset_due=bool(watchdog.ResetDue),gating_evaluated=bool(watchdog.ResetGatingEvaluated),allowed_by_gate=bool(watchdog.ResetAllowedByGate),source_clock=str(watchdog.SourceClock),reset_propagation=str(watchdog.ResetPropagation),rstgen_configuration=int(reset_gate.Configuration),rstgen_reads=int(reset_gate.ConfigurationReads),rstgen_writes=int(reset_gate.ConfigurationWrites),wdren=bool(reset_gate.WatchdogResetEnabled),hardware_verified=False)))\n"
 if runtime.count(anchor)!=1:raise ValueError('Changed final snapshot boundary')
 runtime=runtime.replace(anchor,diagnostic+anchor)
 compile(runtime,'generated-run.py','exec')
 (o/'run.py').write_text(runtime)
 metadata=dict(reference=str(ref.relative_to(s)),reference_manifest_sha256=sha(ref/'capture-files.json'),original_main_sha256=sha(o/'main.bin'),setter_entry=entry,request_helper=0x55405c,continuation=target,request_calls=[dict(pc=code[i].address,instruction=bytes(code[i].bytes).hex(),request=2 if n==0 else 4) for n,i in enumerate(calls)],timeout_poll_limit=200000,delay_us=5,host_budget_seconds=1500,virtual_budget_ms=virtual_budget_ms,calculation_supported=False,host_pc_register_seed=False)
 if local_version_hex is not None:metadata['local_version']=profile['local_version']
 if shared_iom_gate:metadata['iom_shared_gate']=True
 if observe_pause:metadata['observe_pause']=True
 if watchdog_diagnostics:metadata['watchdog_diagnostics']=True
 (o/'natural-timeout-source.json').write_text(json.dumps(metadata,indent=2)+'\n')
 for n in set(inputs)|{'timeout-stop.cs','natural-timeout-source.json'}:inputs[n]=sha(o/n)
 (o/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');return metadata

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--local-version-hex');p.add_argument('--local-version-limit',type=int,default=0);p.add_argument('--virtual-budget-ms',type=int,default=300000);p.add_argument('--shared-iom-gate',action='store_true');p.add_argument('--observe-pause',action='store_true');p.add_argument('--watchdog-diagnostics',action='store_true');a=p.parse_args();build(a.simulator,a.output,a.local_version_hex,a.local_version_limit,a.virtual_budget_ms,a.shared_iom_gate,a.observe_pause,a.watchdog_diagnostics)
 execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=1600,stream=True)
 r=json.loads((a.output/'exports/natural-timeout.json').read_text());f=json.loads((a.output/'exports/frozen-core.json').read_text());passed=r['seen'] and r['r0']==0xfffffffc and r['busy_reads']==200000 and f['cfsr']==f['hfsr']==f['memory_violations']==0 and not any(g['accesses'] for g in f['guards']) and f['completed_calculations']==0
 (a.output/'verdict.json').write_text(json.dumps(dict(passed=passed,natural_request2_timeout_observed=passed,full_initialization_complete=False,normal_calculation_supported=False,physical_hardware_access=False),indent=2)+'\n');print(json.dumps(dict(passed=passed,result=r)),flush=True)
 if not passed:raise SystemExit(1)
if __name__=='__main__':main()
