"""Exercise a synthetic M55 IRQ21 ISR that clears MSPI INTSTAT and returns to a spin thread."""
import argparse,json,struct
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_mspi1_interrupts import models,board
SETUP='''from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];i=g.Mspi1Config.Interrupts;c=m['sysbus.cpu']
if not g.Mspi1Power.TryWrite(0x8000,True):raise Exception('local ready mock')
g.Mspi1Power.ReadStatus();b.WriteDoubleWord(0x20000000,0)
'''
INJECT='''b.WriteDoubleWord(0xe000e100,1<<21)
b.WriteDoubleWord(0x40061200,0x80);b.WriteDoubleWord(0x4006120c,0x80)
if not i.IRQ.IsSet or (b.ReadDoubleWord(0xe000e200)&(1<<21))==0:raise Exception('IRQ21 not pending')
'''
REPORT='''import json
from System import Console
checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
check('ISR-marker',b.ReadDoubleWord(0x20000000)==0x5a)
check('guest-cleared-source',i.Enable==0x80 and i.Status==0 and not i.IRQ.IsSet)
check('software-set-and-guest-clear',i.Writes==3)
check('return-to-thread',int(c.PC.RawValue)==0x10200)
check('not-active21',(b.ReadDoubleWord(0xe000e300)&(1<<21))==0)
check('not-pending21',(b.ReadDoubleWord(0xe000e200)&(1<<21))==0)
check('no-guard-access',g.AccessCount==0 and m['sysbus.guard_iom7_tail'].AccessCount==0)
Console.WriteLine('BLACKWALL_MSPI1_INTERRUPT_CPU '+json.dumps(dict(passed=True,count=len(checks),checks=checks,pc=int(c.PC.RawValue),scope='synthetic M55 IRQ21/ISR/exception return; local ready mock and software INTSET; not original firmware ISR or hardware transfer')))
'''
def guest_bytes():
 data=bytearray(0x204);struct.pack_into('<II',data,0,0x20001000,0x10201);struct.pack_into('<I',data,37*4,0x10101)
 handler=bytes.fromhex('03488021016003485a21016070470000')+struct.pack('<II',0x40061208,0x20000000)
 data[0x100:0x100+len(handler)]=handler;data[0x200:0x202]=bytes.fromhex('fee7');return bytes(data)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700)
 (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-xip-guard-main-01/stock24/board.repl').read_text()));(o/'guest.bin').write_bytes(guest_bytes());(o/'setup.py').write_text(SETUP);(o/'inject.py').write_text(INJECT);(o/'report.py').write_text(REPORT)
 for name,us in [('start',20),('service',100)]:(o/(name+'.py')).write_text('EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n')
 (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "mspi-irq-cpu"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/guest.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\ninclude @/work/start.py\ninclude @/work/inject.py\ninclude @/work/service.py\ninclude @/work/report.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(z.split('BLACKWALL_MSPI1_INTERRUPT_CPU ',1)[1]) for z in log.splitlines() if z.startswith('BLACKWALL_MSPI1_INTERRUPT_CPU ')]
 if len(rows)!=1:raise ValueError('Missing synthetic IRQ CPU result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))
if __name__=='__main__':main()
