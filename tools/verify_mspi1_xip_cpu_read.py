"""Run a synthetic M55 guest that reads an unknown XIP word; original firmware is not used."""
import argparse,json,struct
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_mspi1_xip_guard import models,board
SETUP='''from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];c=m['sysbus.cpu'];x=g.Mspi1Config.XipGuard
if not g.Mspi1Power.TryWrite(0x8000,True):raise Exception('local ready mock')
g.Mspi1Power.ReadStatus();g.WriteDoubleWord(0x3110,0xa4234)
b.WriteDoubleWord(0x40061080,0x19);b.WriteDoubleWord(0x40061090,0x5ec);b.WriteDoubleWord(0x40061090,0x5ed)
'''
REPORT='''import json
from System import Console
checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
check('enabled-control',x.Enabled and x.EnableRequests==x.Transitions==1)
check('one-unknown-read',x.AccessCount==1 and x.LastAddress==0x80000000 and x.LastWidth==4 and x.LastOperation=='read')
check('faulting-instruction',int(c.PC.RawValue)==0x1000c)
check('after-read-marker-not-executed',int(c.GetRegister(2).RawValue)==0)
check('root-guard-unchanged',g.AccessCount==0 and m['sysbus.guard_iom7_tail'].AccessCount==0)
Console.WriteLine('BLACKWALL_MSPI1_XIP_CPU_READ '+json.dumps(dict(passed=True,count=len(checks),checks=checks,pc=int(c.PC.RawValue),address=int(x.LastAddress),width=int(x.LastWidth),scope='synthetic M55 data-load abort; ready inputs mocked; not original firmware, instruction fetch, backing or boot proof')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700)
 # movs r2,0; ldr r0,literal; ldr r1,[r0]; movs r2,0x5a; b .; padding; literal.
 guest=struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('0022024801685a22fee70000')+struct.pack('<I',0x80000000)
 (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-cq-init-main-01/stock24/board.repl').read_text()));(o/'guest.bin').write_bytes(guest);(o/'setup.py').write_text(SETUP);(o/'advance.py').write_text('EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(100))\n');(o/'report.py').write_text(REPORT)
 (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "xip-cpu-read"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/guest.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\ninclude @/work/advance.py\ninclude @/work/report.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(z.split('BLACKWALL_MSPI1_XIP_CPU_READ ',1)[1]) for z in log.splitlines() if z.startswith('BLACKWALL_MSPI1_XIP_CPU_READ ')]
 if len(rows)!=1:raise ValueError('Missing synthetic CPU result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))
if __name__=='__main__':main()
