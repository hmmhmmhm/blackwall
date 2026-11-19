"""Expose host/CPU Pause ordering under an explicit 100ms scheduling window."""
import argparse,json,subprocess
from pathlib import Path
from run_renode_m55_probe import execute
from reset_restart_profiles import RENODE_IMAGE

def run(s,o,fixed=False):
 o.mkdir(mode=0o700,parents=True);root=Path(__file__).parent;source=(root/'renode-reset-entry-observer.cs').read_text()
 if fixed:
  from reset_entry_pause_contract import completed_pause
  source=completed_pause(source)
 anchor='machine.Pause();'
 if source.count(anchor)!=1:raise ValueError('Unknown observer fixture')
 source=source.replace(anchor,'System.Threading.Thread.Sleep(100);machine.Pause();')
 (o/'observer.cs').write_text(source);(o/'board.repl').write_bytes((root.parent/'tests/fixtures/m55-minimal.repl').read_bytes());(o/'guest.elf').write_bytes((s/'watchdog-reset-delivery-unit-02/gate-2/guest.elf').read_bytes())
 (o/'run.py').write_text('''import clr,time,json
from System import Console
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallResetEntryObserver').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallResetEntryObserver
m=monitor.Machine;c=m['sysbus.cpu']
o=BlackwallResetEntryObserver(m,c,int(m.SystemBus.ReadDoubleWord(4))&~1)
EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+5
while not o.Seen and time.time()<deadline:time.sleep(0.001)
Console.WriteLine('BLACKWALL_ENTRY_SEEN '+str(o.Seen))
m.Pause()
Console.WriteLine('BLACKWALL_ENTRY_PAUSE_COMPLETE '+json.dumps(dict(seen=bool(o.Seen),paused=bool(m.IsPaused))))
''')
 (o/'probe.resc').write_text('include @/work/observer.cs\nmach create\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/guest.elf\ninclude @/work/run.py\nquit\n')
 command=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',RENODE_IMAGE,'--disable-gui','--hide-monitor','-p','/work/probe.resc']
 try:log=execute(command,o,'renode',timeout=15)
 except (subprocess.TimeoutExpired,RuntimeError) as e:
  log=(o/'renode.log').read_text();result=dict(passed=False,completed=False,seen='BLACKWALL_ENTRY_SEEN True' in log,error=type(e).__name__,synthetic_schedule_window_ms=100)
 else:result=dict(passed='BLACKWALL_ENTRY_PAUSE_COMPLETE ' in log,completed='BLACKWALL_ENTRY_PAUSE_COMPLETE ' in log,seen='BLACKWALL_ENTRY_SEEN True' in log,synthetic_schedule_window_ms=100)
 (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--fixed',action='store_true');a=p.parse_args();run(a.simulator,a.output,a.fixed)
