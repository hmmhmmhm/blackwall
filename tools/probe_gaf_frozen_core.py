"""Run original main with an explicit stuck EDMP fault, never a ready result."""
import argparse
import hashlib
import json
from pathlib import Path

from inspect_ambiq_target import decode
from native_replay import IMAGE
from run_renode_m55_probe import execute
from run_runtime_connection_m55 import build as runtime_build, pin_capture
from runtime_event_models import imu_span


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def scoped_observer_component(model):
    point=model.index('    public sealed class BlackwallExecutionObserver')
    begin=model.rfind('namespace Antmicro.Renode.Peripherals.Miscellaneous',0,point)
    end=model.find('\nnamespace ',point)
    if end<0:end=len(model)
    old=model[begin:end].rstrip()
    if hashlib.sha256((old+'\n').encode()).hexdigest()!='cbb91e4a0a779a39ce0c185e3bc9a842a770aea3b838001dedc2cfd12df8aaef':
        raise ValueError('Unknown diagnostic observer component')
    new=Path(__file__).with_name('renode-execution-observer.cs').read_text().rstrip()
    return model[:begin]+new+model[begin+len(old):]


def compose_frozen(model):
    old=Path(__file__).with_name('renode-gaf-ondemand.cs').read_text()
    new=Path(__file__).with_name('renode-gaf-frozen-core.cs').read_text()
    if model.count(old)!=1:raise ValueError('Unknown on-demand composition')
    model=model.replace(old,new)
    if model.count('BlackwallImuGafOnDemand')!=2:raise ValueError('Unknown control owner references')
    model=model.replace('BlackwallImuGafOnDemand','BlackwallImuGafFrozenCore')
    anchor='            if(OnDemand!=null && !IregPending && !IregReady && data.Length>=3 && data[0]==0x7c)'
    continuation='''            if(OnDemand!=null && OnDemand.Active && !IregPending && !IregReady && data.Length>=2 && data[0]==0x7e && gafWriteCursor>=0 && gafWriteBase==IregAddress && gafWriteReadEpoch==IregStarts)
            {
                var bytes=new byte[data.Length-1];Array.Copy(data,1,bytes,0,bytes.Length);
                if(!OnDemand.TryWriteRam(gafWriteCursor,bytes))return false;
                gafWriteCursor+=bytes.Length;Pointer=0x7e;pending=false;return true;
            }
'''
    if model.count(anchor)!=1:raise ValueError('Unknown indirect routing')
    model=model.replace(anchor,continuation+anchor)
    anchor='''                if(OnDemand.Active)
                {
'''
    extra='''                    if(data.Length>=4 && address<0x2000)
                    {
                        var bytes=new byte[data.Length-3];Array.Copy(data,3,bytes,0,bytes.Length);
                        if(!OnDemand.TryWriteRam(address,bytes))return false;
                        gafWriteBase=IregAddress=address;gafWriteCursor=address+bytes.Length;gafWriteReadEpoch=IregStarts;
                        powerSaveWriteCursor=womWriteCursor=patchWriteCursor=masterWriteCursor=serviceWriteCursor=-1;
                        Pointer=0x7c;pending=false;return true;
                    }
                    if(data.Length==3 && address==0x5bc && OnDemand.BeginRamRead(address))
                    {IregAddress=address;IregPending=true;IregStarts++;pending=false;Pointer=0x7c;iregTimer.ResetValue();iregTimer.Enabled=true;return true;}
'''
    if model.count(anchor)!=1:raise ValueError('Unknown active control routing')
    model=model.replace(anchor,anchor+extra)
    anchor='IregReady=(Patch!=null && Patch.ReadRemaining>0)'
    if model.count(anchor)!=1:raise ValueError('Unknown indirect read lifetime')
    return model.replace(anchor,'IregReady=(OnDemand!=null && OnDemand.RamReadRemaining>0) || (Patch!=null && Patch.ReadRemaining>0)')


def return_sites(raw,case,s):
    helper=0x55405c if case=='stock24' else 0x520204
    code=decode(raw,helper,0x32)
    if code[-1].mnemonic!='pop' or code[-1].op_str!='{r1, r4, r5, pc}':raise ValueError('Unknown request return')
    calls=[i.operands[0].imm for i in code if i.mnemonic=='bl']
    if len(calls)!=4:raise ValueError('Unknown request helper')
    idle=decode(raw,calls[-1],0x44)
    wait_return=next(i.address for i in idle if i.mnemonic=='pop' and 'pc' in i.op_str)
    source=json.loads((s/'imu-parameter-full-setter-01/report.json').read_text())
    entry=next(c['entry'] for c in source['cases'] if c['case']==case)
    setter_return=next(i.address for i in decode(raw,entry,0x710) if i.mnemonic.startswith('pop') and 'pc' in i.op_str)
    return [wait_return,code[-1].address,setter_return]


OBSERVER='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 using System;using System.Collections.Generic;using Antmicro.Renode.Core;using Antmicro.Renode.Peripherals.CPU;
 public sealed class BlackwallGafFailureObserver {
  public BlackwallGafFailureObserver(IMachine m,CortexM cpu,BlackwallImuGafFrozenCore fault,uint slot,uint[] sites) {
   for(uint k=0;k<sites.Length;k++){var kind=k;cpu.AddHook(sites[k],(c,pc)=>{
    if(!fault.Active || fault.BusyReads==0)return;
    if(Rows.Count>=16){Overflow=true;return;}
    Rows.Add(new uint[]{kind,(uint)pc,(uint)cpu.GetRegister(0).RawValue,(uint)cpu.GetRegister(13).RawValue,(uint)cpu.GetRegister(14).RawValue,m.SystemBus.ReadDoubleWord(slot),(uint)cpu.GetRegister(25).RawValue,(uint)fault.BusyReads,(uint)fault.Requests});
   });}
  }
  public List<uint[]> Rows {get;}=new List<uint[]>();public bool Overflow {get;private set;}
 }
}
'''


def build(s,out,case,observe,budget_ms,suspend_startup_observer=False):
    profile=runtime_build(s,out,case,att_time=True,gaf_profile=True,gaf_on_demand_control=True)
    before=(out/'strict.cs').read_text();model=compose_frozen(before)
    if suspend_startup_observer:model=scoped_observer_component(model)
    (out/'strict.cs').write_text(model)
    begin,end=imu_span(model)
    gaf=json.loads((out/'gaf-profile.json').read_text())
    gaf.update(candidate_sha256=hashlib.sha256(model[begin:end].encode()).hexdigest(),
               control_fragment_sha256=sha(Path(__file__).with_name('renode-gaf-frozen-core.cs')),
               on_demand_fault='frozen-core',calculation_supported=False,
               retained_ram_source='prior modeled clear and explicit host writes; no EDMP execution')
    (out/'gaf-profile.json').write_text(json.dumps(gaf,indent=2)+'\n')
    profile.update(gaf_profile=gaf,gaf_profile_sha256=sha(out/'gaf-profile.json'),model_sha256=sha(out/'strict.cs'),virtual_budget_ms=budget_ms)
    if suspend_startup_observer:profile['suspended_startup_observer_labels']=['iom7-address','iom7-fifo','iom7-command']
    (out/'connection-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    sites=return_sites((out/'main.bin').read_bytes(),case,s)
    (out/'failure-observer.cs').write_text(OBSERVER)
    with (out/'activation.cs').open('a') as f:f.write('\n'+OBSERVER)
    runtime=(out/'run.py').read_text();anchor='        started_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);ticks_per_ms=int(TimeInterval.TicksPerMillisecond)'
    # run.py is dedented by the existing builder.
    anchor=anchor.lstrip()
    setup='''failure_observer=None
if OBSERVE:
    from System import Array,UInt32
    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallGafFailureObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallGafFailureObserver
    failure_observer=BlackwallGafFailureObserver(m,cpu,m['sysbus.iom4.imu_identity'].OnDemand,SLOT,Array[UInt32](SITES))
'''.replace('OBSERVE',repr(observe)).replace('SLOT',str(profile['tcb_slot'])).replace('SITES',repr(sites))
    # This point remains inside the builder's outer try block.
    indented='\n'.join('    '+line if line else '' for line in setup.splitlines())+'\n'
    anchor='    '+anchor
    if runtime.count(anchor)!=1:raise ValueError('Unknown runtime entry')
    runtime=runtime.replace(anchor,indented+anchor).replace('deadline=time.time()+45','deadline=time.time()+120')
    post='''
try:
    from System import Console
    from System.IO import File
    if not result.get('att',{}).get('stopped') or any(v['accesses'] for v in result['guards']) or result['cfsr'] or result['hfsr'] or result['memory_violations']:
        raise ValueError('Fault run requires a completed ATT phase with no prior guard or architectural fault')
    suspended_points=[]
    if p.get('suspended_startup_observer_labels'):
        if not m.IsPaused:raise ValueError('Observer suspension requires the whole machine paused')
        for label in p['suspended_startup_observer_labels']:
            if not observer.SuspendPoint(label):raise ValueError('Observer point was already suspended')
        suspended_points=[dict(label=str(v.Label),address=int(v.Address),hits=int(v.Hits)) for v in observer.Points if v.Suspended]
    start_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    cpu.IsHalted=False
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+120
    while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start_ticks<p['virtual_budget_ms']*int(TimeInterval.TicksPerMillisecond):time.sleep(0.01)
    stop_reason='guard-or-device-pause' if m.IsPaused else 'host-deadline' if time.time()>=deadline else 'virtual-budget'
    m.Pause()
    imu=m['sysbus.iom4.imu_identity'];d=imu.OnDemand
    guards=[dict(name=name,accesses=int(m['sysbus.'+name].AccessCount),address=int(m['sysbus.'+name].LastAddress)) for name in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail')]
    result=dict(fault='frozen-core',fault_injected=bool(d.FaultInjected),phase=str(d.Phase),requests=int(d.Requests),triggers=int(d.Triggers),busy_reads=int(d.BusyReads),ram_reads=int(d.RamReads),ram_written_bytes=int(d.RamWrittenBytes),calculation_supported=bool(d.CalculationSupported),completed_calculations=int(d.CompletedCalculations),pending=bool(d.Pending),history=str(d.History),last_reject=str(d.LastReject),pc=int(m['sysbus.cpu'].PC.RawValue),start_ticks=start_ticks,virtual_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),stop_reason=stop_reason,rows=[] if failure_observer is None else [[int(v) for v in row] for row in failure_observer.Rows],observer_overflow=False if failure_observer is None else bool(failure_observer.Overflow),initial_service_completions=int(imu.Service.Completions),gaf=gaf_snapshot(),guards=guards,cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations))
    File.WriteAllBytes('/work-output/frozen-core-sram.bin',m.SystemBus.ReadBytes(0x20000000,0x380000,True))
    if suspended_points:result['suspended_startup_observer_points']=suspended_points
    File.WriteAllText('/work-output/frozen-core.json',json.dumps(result));Console.WriteLine('BLACKWALL_GAF_FROZEN_CORE '+json.dumps(result))
except Exception as error:Console.WriteLine('BLACKWALL_GAF_FROZEN_CORE_ERROR '+str(error))
'''
    (out/'run.py').write_text(runtime+post)
    metadata=dict(case=case,fault='EDMP does not execute after request2/4; busy remains asserted',
                  observe=observe,return_sites=sites,virtual_budget_ms=budget_ms,
                  base_model_sha256=hashlib.sha256(before.encode()).hexdigest(),
                  fault_fragment_sha256=sha(Path(__file__).with_name('renode-gaf-frozen-core.cs')),
                  suspended_startup_observer=suspend_startup_observer,
                  physical_fault_verified=False,nominal_calculation_supported=False)
    (out/'frozen-core-source.json').write_text(json.dumps(metadata,indent=2)+'\n')
    inputs=json.loads((out/'connection-inputs.json').read_text())
    for name in set(inputs)|{'failure-observer.cs','frozen-core-source.json'}:inputs[name]=sha(out/name)
    (out/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--case',choices=('stock24','stock23','cfw'),default='stock24');p.add_argument('--observe',action='store_true')
    p.add_argument('--virtual-budget-ms',type=int,default=30000)
    p.add_argument('--suspend-startup-observer',action='store_true');a=p.parse_args()
    if not 1000<=a.virtual_budget_ms<=30000:raise ValueError('Explicit bounded fault scenario required')
    build(a.simulator,a.output,a.case,a.observe,a.virtual_budget_ms,a.suspend_startup_observer)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,
        '--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=240)
    pin_capture(a.output);r=json.loads((a.output/'exports/frozen-core.json').read_text())
    timeout_rows=[row for row in r['rows'] if row[0] in (0,1) and row[2]==0xfffffffc]
    completed=bool(timeout_rows) and not r['calculation_supported'] and r['completed_calculations']==0
    verdict=dict(execution_captured=True,natural_timeout_observed=completed,
                 observation_without_hooks_verified=False,full_boot_complete=False,
                 host_deadline_exhausted=r['stop_reason']=='host-deadline',hardware_accessed=False)
    (a.output/'fault-verification.json').write_text(json.dumps(verdict,indent=2)+'\n')
    print(json.dumps(dict(phase=r['phase'],requests=r['requests'],busy_reads=r['busy_reads'],
                         stop_reason=r['stop_reason'],natural_timeout_observed=completed)))
    if not completed:raise SystemExit(1)


if __name__=='__main__':main()
