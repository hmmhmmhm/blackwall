"""Verify the pinned native DWT's virtual-time counter, not physical CPU cycles."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
DRIVER='''import json
from System import Console
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
m=monitor.Machine;d=m['sysbus.dwt'];checks=[]
def check(n,ok):
 if not ok:raise Exception(n)
 checks.append(n)
def advance(us):EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(us))
check('native-type',d.GetType().FullName=='Antmicro.Renode.Peripherals.Miscellaneous.DWT')
check('reset-disabled',d.ReadDoubleWord(0)==0 and d.ReadDoubleWord(4)==0)
advance(10);check('disabled-stable',d.ReadDoubleWord(4)==0)
d.WriteDoubleWord(0,1);check('enable-readback',d.ReadDoubleWord(0)&1==1)
advance(1);check('nominal10mhz',d.ReadDoubleWord(4)==10)
advance(24);check('elapsed25us',d.ReadDoubleWord(4)==250)
d.WriteDoubleWord(0,0);saved=d.ReadDoubleWord(4);advance(25);check('disable-retains-counter',d.ReadDoubleWord(4)==saved)
d.WriteDoubleWord(0,1);advance(2);check('reenable-no-reset',d.ReadDoubleWord(4)==saved+20)
d.WriteDoubleWord(4,0xfffffff8);advance(2);check('32bit-wrap',d.ReadDoubleWord(4)==12)
d.Reset();check('reset-clears',d.ReadDoubleWord(0)==0 and d.ReadDoubleWord(4)==0)
Console.WriteLine('BLACKWALL_DWT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,frequency=10000000,physical_cycle_accuracy=False)))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 out.mkdir(mode=0o700);(out/'board.repl').write_text('dwt: Miscellaneous.DWT @ sysbus 0xe0001000\n    frequency: 10000000\n');(out/'test.py').write_text(DRIVER);(out/'probe.resc').write_text('mach create "boot-dwt"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'native',timeout=120)
 rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_DWT ')];r=rows[0] if len(rows)==1 else dict(passed=False)
 (out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
if __name__=='__main__':main()
