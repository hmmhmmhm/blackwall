"""Continue the original first timeout into request4, cleanup or an unchanged watchdog boundary."""
import argparse,hashlib,json
from pathlib import Path
from probe_gaf_timeout_cadence import build as prepare
from reset_restart_profiles import RENODE_IMAGE
from run_renode_m55_probe import execute

OBSERVER='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 using System.Collections.Generic;using Antmicro.Renode.Core;using Antmicro.Renode.Peripherals.CPU;
 public sealed class BlackwallGafAfterTimeoutObserver {
  public BlackwallGafAfterTimeoutObserver(IMachine machine,CortexM cpu,BlackwallImuGafFrozenCore fault,uint slot) {
   foreach(var p in new ulong[][]{new ulong[]{1,0x554974},new ulong[]{2,0x554978},new ulong[]{3,0x55497a},new ulong[]{4,0x554c64}}) {
    var tag=p[0];var pc=p[1];cpu.AddHook(pc,(c,a)=>{
     if(!fault.Active || fault.Requests<1 || Rows.Count>=16)return;
     Rows.Add(new ulong[]{tag,a,cpu.GetRegister(0).RawValue,cpu.GetRegister(1).RawValue,cpu.GetRegister(4).RawValue,cpu.GetRegister(13).RawValue,cpu.GetRegister(14).RawValue,machine.SystemBus.ReadDoubleWord(slot),cpu.GetRegister(25).RawValue,(ulong)fault.Requests,(ulong)fault.BusyReads});
     if(tag==4 && !SetterSeen){SetterSeen=true;machine.Pause();}
    });
   }
  }
  public List<ulong[]> Rows {get;}=new List<ulong[]>();public bool SetterSeen {get;private set;}
 }
}
'''
POST='''
try:
    if not timeout_stop.Seen or not m.IsPaused or int(cpu.PC.RawValue)!=0x55496e or int(cpu.GetRegister(0).RawValue)!=0xfffffffc or int(d.BusyReads)!=200000:raise ValueError('Need actual first timeout caller, not seeded state')
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallGafAfterTimeoutObserver
    after_observer=BlackwallGafAfterTimeoutObserver(m,cpu,d,p['tcb_slot'])
    after_pause=BlackwallMachinePauseObserver(m,cpu)
    after_start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);after_wall=time.time();after_deadline=after_wall+900;after_next=after_wall
    EmulationManager.Instance.CurrentEmulation.StartAll()
    while not m.IsPaused and time.time()<after_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-after_start<15000000000:
        if time.time()>=after_next:
            File.AppendAllText('/work-output/after-timeout-progress.jsonl',json.dumps(dict(wall_seconds=time.time()-after_wall,requests=int(d.Requests),busy_reads=int(d.BusyReads),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)))+chr(10));after_next=time.time()+30
        time.sleep(0.01)
    m.Pause()
    wd=m['sysbus.wdt'];rg=m['sysbus.rstgen']
    after=dict(start_ticks=after_start,ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),wall_seconds=time.time()-after_wall,registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],xpsr=int(cpu.GetRegister(25).RawValue),tcb=int(b.ReadDoubleWord(p['tcb_slot'])),setter_return_seen=bool(after_observer.SetterSeen),rows=[[int(x) for x in row] for row in after_observer.Rows],prior_failure_rows=[[int(x) for x in row] for row in failure_observer.Rows],gaf=dict(requests=int(d.Requests),request_id=int(d.RequestId),triggers=int(d.Triggers),busy_reads=int(d.BusyReads),phase=str(d.Phase),pending=bool(d.Pending),history=str(d.History),ram_reads=int(d.RamReads),ram_writes=int(d.RamWrittenBytes),last_reject=str(d.LastReject),calculation_supported=bool(d.CalculationSupported),completed_calculations=int(d.CompletedCalculations)),watchdog=dict(configuration=int(wd.Configuration),restarts=int(wd.Restarts),reset_due=bool(wd.ResetDue),gating_evaluated=bool(wd.ResetGatingEvaluated),allowed_by_gate=bool(wd.ResetAllowedByGate),rstgen_cfg=int(rg.Configuration),wdren=bool(rg.WatchdogResetEnabled)),pause=dict(seen=bool(after_pause.Seen),internal=bool(after_pause.InternalPause),state=str(after_pause.State),trace=str(after_pause.Trace),aborted=bool(m.IsAborted)),mode_word=int(g.McuClock.ModeWord),mips=int(cpu.PerformanceInMips),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),guards=[dict(name=x['name'],accesses=int(m['sysbus.'+x['name']].AccessCount),address=int(m['sysbus.'+x['name']].LastAddress),width=int(m['sysbus.'+x['name']].LastWidth),operation=str(m['sysbus.'+x['name']].LastOperation),value=int(m['sysbus.'+x['name']].LastValue)) for x in result['guards']],host_pc_register_seed=False,original_main_executed=True,normal_calculation_supported=False,hardware_accessed=False)
    after['outcome']='setter-return' if after['setter_return_seen'] else 'watchdog-reset-request' if after['watchdog']['reset_due'] else 'strict-guard' if any(x['accesses'] for x in after['guards']) else 'fault' if after['cfsr'] or after['hfsr'] else 'host-or-virtual-budget'
    File.WriteAllBytes('/work-output/after-timeout-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    File.WriteAllText('/work-output/after-timeout.json',json.dumps(after));Console.WriteLine('BLACKWALL_GAF_AFTER_TIMEOUT '+json.dumps(after))
except Exception as error:Console.WriteLine('BLACKWALL_GAF_AFTER_TIMEOUT_ERROR '+str(error))
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(s,o):
 meta=prepare(s,o);root=Path(__file__).parent
 raw=(o/'main.bin').read_bytes()
 for pc,bytecode in [(0x554974,'fff772fb'),(0x554c62,'200007b0')]:
  if raw[pc-0x438000:pc-0x438000+len(bytes.fromhex(bytecode))]!=bytes.fromhex(bytecode):raise ValueError('Changed original continuation '+hex(pc))
 # A one-shot owned observer does not pause again when the same instruction resumes.
 for n in ['activation.cs','timeout-stop.cs']:
  code=(o/n).read_text();old='if(!fault.Active || fault.Requests!=1 || fault.BusyReads==0)return;'
  if code.count(old)!=1:raise ValueError('Unknown owned timeout stop')
  (o/n).write_text(code.replace(old,'if(Seen || !fault.Active || fault.Requests!=1 || fault.BusyReads==0)return;',1))
 with (o/'activation.cs').open('a') as f:f.write('\n'+OBSERVER)
 with (o/'run.py').open('a') as f:f.write(POST)
 compile((o/'run.py').read_text(),'generated-run.py','exec')
 meta.update(after_first_timeout=True,first_stop_one_shot=True,post_virtual_budget_ms=15000,post_host_budget_seconds=900)
 (o/'after-timeout-profile.json').write_text(json.dumps(meta,indent=2)+'\n');inputs=json.loads((o/'connection-inputs.json').read_text());inputs['after-timeout-profile.json']=''
 for n in inputs:inputs[n]=sha(o/n)
 (o/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');return meta
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build(a.simulator,a.output)
 execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=2500,stream=True)
 r=json.loads((a.output/'exports/after-timeout.json').read_text());print(json.dumps(dict(outcome=r['outcome'],requests=r['gaf']['requests'],busy_reads=r['gaf']['busy_reads'],setter_return_seen=r['setter_return_seen'],guards=[x for x in r['guards'] if x['accesses']])),flush=True)
