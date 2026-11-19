"""Original timeout with an explicitly gated post-ATT HAL-equivalent instruction rate."""
import argparse,hashlib,json
from pathlib import Path
from probe_gaf_natural_timeout import build as prepare
from hal_loop_time_profile import profile
from reset_restart_profiles import RENODE_IMAGE
from run_renode_m55_probe import execute

BOUNDARY='''    if not m.IsPaused:raise ValueError('Rate input requires the whole machine paused')
    if g.McuClock is None or ((int(g.McuClock.ModeWord)>>3)&3)!=2:raise ValueError('Only the observed high-mode HAL path is supported')
    if int(cpu.PerformanceInMips)!=10:raise ValueError('Need the preserved 10MIPS startup prefix')
    def cadence_state():
        return dict(ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),registers=[int(cpu.GetRegister(k).RawValue) for k in range(16)],instructions=int(cpu.ExecutedInstructions),mode_word=int(g.McuClock.ModeWord),mips=int(cpu.PerformanceInMips),wdt_configuration=int(m['sysbus.wdt'].Configuration),stimer_counter=int(g.Stimer.Counter),paused=bool(m.IsPaused))
    cadence_before=cadence_state()
    File.WriteAllBytes('/work-output/cadence-before-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    cpu.PerformanceInMips=RATE
    cadence_after=cadence_state()
    File.WriteAllBytes('/work-output/cadence-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    if {k:v for k,v in cadence_before.items() if k!='mips'}!={k:v for k,v in cadence_after.items() if k!='mips'}:raise ValueError('Rate input changed paused architectural state or peripheral time')
    File.WriteAllText('/work-output/cadence-boundary.json',json.dumps(dict(before=cadence_before,after=cadence_after,profile=PROFILE,host_pc_register_seed=False,original_code_changed=False,timeout_or_watchdog_changed=False,physical_timing_verified=False,hardware_accessed=False)))
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(s,o):
 meta=prepare(s,o,'0d34120d5a007856',32,300000,True,True,True);rate=profile('hp');code=(o/'run.py').read_text();anchor='    start_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n    clr.AddReference(TypeManager.Instance.GetTypeByName(\'Antmicro.Renode.Peripherals.Miscellaneous.BlackwallNaturalGafTimeoutStop\').Assembly)'
 if code.count(anchor)!=1:raise ValueError('Unknown post-ATT rate boundary')
 code=code.replace(anchor,BOUNDARY.replace('RATE',str(rate['mips'])).replace('PROFILE',repr(rate))+anchor,1);compile(code,'generated-run.py','exec');(o/'run.py').write_text(code)
 meta.update(cadence_profile=rate,rate_scope='after original ATT return only; startup and board default preserved at10MIPS',original_timeout_poll_limit=200000,original_delay_us=5)
 (o/'cadence-profile.json').write_text(json.dumps(meta,indent=2)+'\n');inputs=json.loads((o/'connection-inputs.json').read_text());inputs['cadence-profile.json']=''
 for n in inputs:inputs[n]=sha(o/n)
 (o/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');return meta
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build(a.simulator,a.output)
 execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=1600,stream=True)
 r=json.loads((a.output/'exports/natural-timeout.json').read_text());f=json.loads((a.output/'exports/frozen-core.json').read_text());passed=r['seen'] and r['r0']==0xfffffffc and r['busy_reads']==200000 and f['cfsr']==f['hfsr']==f['memory_violations']==0 and not any(g['accesses'] for g in f['guards'])
 (a.output/'verdict.json').write_text(json.dumps(dict(passed=passed,natural_request2_timeout_observed=passed,normal_calculation_supported=False,full_initialization_complete=False,physical_timing_verified=False,hardware_accessed=False),indent=2)+'\n');print(json.dumps(dict(passed=passed,result=r)),flush=True)
 if not passed:raise SystemExit(1)
