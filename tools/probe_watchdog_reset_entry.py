"""Original stock ARM natural watchdog request -> main reset vector, bounded observer."""
import argparse,json,hashlib
from pathlib import Path
from probe_gaf_natural_timeout import build as prepare
from watchdog_reset_delivery_model import compose
from reset_restart_profiles import RENODE_IMAGE
from run_renode_m55_probe import execute

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(s,o):
 meta=prepare(s,o,'0d34120d5a007856',32,300000,True,True,True);root=Path(__file__).parent
 model=compose((o/'strict.cs').read_text())+'\n'+(root/'renode-reset-aware-nvic.cs').read_text();(o/'strict.cs').write_text(model)
 board=(o/'board.repl').read_text()
 for old,new in [('    PerformanceInMips: 10\n','    PerformanceInMips: 10\n    InitVectorTableOffset: 0x438000\n'),('nvic: IRQControllers.NVIC @','nvic: Miscellaneous.BlackwallResetAwareNVIC @'),('    resetController: rstgen\n','    resetController: rstgen\n    propagateSystemReset: true\n'),('rstgen: Miscellaneous.BlackwallResetController @ sysbus 0x40000000\n','rstgen: Miscellaneous.BlackwallResetController @ sysbus 0x40000000\n    mainOnlyWatchdogBootContract: true\n')]:
  if board.count(old)!=1:raise ValueError('Unknown board reset boundary '+old)
  board=board.replace(old,new,1)
 (o/'board.repl').write_text(board)
 with (o/'activation.cs').open('a') as f:f.write('\n'+(root/'renode-reset-entry-observer.cs').read_text())
 runtime=(o/'run.py').read_text();anchor='    phase_wall=time.time();deadline=phase_wall+1500;next_progress=phase_wall'
 addition='''    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallResetEntryObserver
    expected_reset_entry=int(b.ReadDoubleWord(0x438004))&~1
    expected_reset_sp=int(b.ReadDoubleWord(0x438000))
    reset_entry_observer=BlackwallResetEntryObserver(m,cpu,expected_reset_entry)
'''
 if runtime.count(anchor)!=1:raise ValueError('Unknown observer boundary')
 runtime=runtime.replace(anchor,addition+anchor)
 anchor="    File.WriteAllBytes('/work-output/frozen-core-sram.bin',m.SystemBus.ReadBytes(0x20000000,0x380000,True))"
 addition="    File.WriteAllText('/work-output/watchdog-reset-entry.json',json.dumps(dict(seen=bool(reset_entry_observer.Seen),pc=int(cpu.PC.RawValue),sp=int(cpu.GetRegister(13).RawValue),expected_pc=expected_reset_entry,expected_sp=expected_reset_sp,vtor=int(cpu.VectorTableOffset),boot_status=int(reset_gate.VirtualBootStatus),deliveries=int(reset_gate.WatchdogResetDeliveries),pending=bool(reset_gate.WatchdogResetPending),nvic_resets=int(m['sysbus.nvic'].ResetCompletions),watchdog_configuration=int(watchdog.Configuration),memory_violations=int(memory_policy.Violations),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),host_pc_register_seed=False,main_only_virtual_boot_contract=True,guest_status_mapped=False,bootrom_executed=False,hardware_accessed=False)))\n"
 if runtime.count(anchor)!=1:raise ValueError('Unknown entry export boundary')
 runtime=runtime.replace(anchor,addition+anchor);compile(runtime,'generated-run.py','exec');(o/'run.py').write_text(runtime)
 meta.update(watchdog_reset_delivery=True,main_only_boot_contract=True,reset_entry_observer=True,full_initialization_complete=False)
 (o/'watchdog-reset-profile.json').write_text(json.dumps(meta,indent=2)+'\n')
 inputs=json.loads((o/'connection-inputs.json').read_text());inputs['watchdog-reset-profile.json']=''
 for n in inputs:inputs[n]=sha(o/n)
 (o/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
 return meta
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build(a.simulator,a.output)
 execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=1600,stream=True)
 r=json.loads((a.output/'exports/watchdog-reset-entry.json').read_text());print(json.dumps(r),flush=True)
 if not(r['seen'] and r['pc']==r['expected_pc'] and r['sp']==r['expected_sp'] and r['deliveries']==r['nvic_resets']==1 and r['boot_status']==64 and r['cfsr']==r['hfsr']==r['memory_violations']==0):raise SystemExit(1)
