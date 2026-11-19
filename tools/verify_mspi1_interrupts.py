"""Test MSPI interrupt masks and NVIC21 pending using software INTSET, no transfer engine."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def models(s):
 old=(s/'mspi1-irq-research-01/base-config.cs').read_bytes();frozen=(s/'mspi1-xip-guard-main-01/stock24/strict.cs').read_bytes()
 if frozen.count(old)!=1 or not frozen.startswith((ROOT/'tools/renode-strict-mmio.cs').read_bytes()):raise ValueError('Frozen model differs')
 return frozen.replace(old,(ROOT/'tools/renode-mspi1-config.cs').read_bytes())
def board(text,enabled=True):
 needle='    profile: "source-reset-config"\n'
 if text.count(needle)!=1 or 'mspi1_interrupts:' in text:raise ValueError('Unexpected interrupt owner')
 if not enabled:return text
 return text.replace(needle,needle+'    interrupts: mspi1_interrupts\n')+'\nmspi1_interrupts: Miscellaneous.BlackwallMspi1Interrupts @ none\n    profile: "source-reset"\n    IRQ -> nvic@21\n'
DRIVER='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];tail=m['sysbus.guard_iom7_tail'];i=g.Mspi1Config.Interrupts;p=g.Mspi1Power;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():return (i.Enable,i.Status,i.Reads,i.Writes,i.IRQ.IsSet,p.Phase)
def blocked(n,fn):
    old=state();count=g.AccessCount+tail.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount+tail.AccessCount==count+1)
check('reset',i.Enable==i.Status==i.Reads==i.Writes==0 and not i.IRQ.IsSet)
blocked('unpowered-read',lambda:b.ReadDoubleWord(0x40061200))
blocked('unpowered-clear',lambda:b.WriteDoubleWord(0x40061208,0x1a80))
check('local-ready-mock',p.TryWrite(0x8000,True));p.ReadStatus()
check('source-reset-read',b.ReadDoubleWord(0x40061200)==b.ReadDoubleWord(0x40061204)==0)
for bit in range(14):
    mask=1<<bit
    b.WriteDoubleWord(0x40061200,0);b.WriteDoubleWord(0x4006120c,mask)
    check('masked-status-'+str(bit),b.ReadDoubleWord(0x40061204)==mask and not i.IRQ.IsSet)
    b.WriteDoubleWord(0x40061200,mask)
    check('enabled-pending21-'+str(bit),i.IRQ.IsSet and (b.ReadDoubleWord(0xe000e200)&(1<<21))!=0)
    b.WriteDoubleWord(0x40061208,mask)
    check('clear-level-'+str(bit),i.Status==0 and not i.IRQ.IsSet)
    b.WriteDoubleWord(0xe000e280,1<<21)
    check('nvic-software-ack-'+str(bit),(b.ReadDoubleWord(0xe000e200)&(1<<21))==0)
b.WriteDoubleWord(0x4006120c,3);b.WriteDoubleWord(0x40061200,3);b.WriteDoubleWord(0x40061208,1)
check('selective-clear',i.Status==2 and i.IRQ.IsSet)
b.WriteDoubleWord(0x40061200,0);check('disable-preserves-status',i.Status==2 and not i.IRQ.IsSet)
for off in [0x200,0x208,0x20c]:blocked('reserved-mask-'+str(off),lambda off=off:b.WriteDoubleWord(0x40061000+off,0x4000))
blocked('status-write',lambda:b.WriteDoubleWord(0x40061204,0))
blocked('clear-alias-read',lambda:b.ReadDoubleWord(0x40061208));blocked('set-alias-read',lambda:b.ReadDoubleWord(0x4006120c))
blocked('byte-width',lambda:b.ReadByte(0x40061200));blocked('word-width',lambda:b.WriteWord(0x40061208,0))
blocked('pio-still-strict',lambda:b.WriteDoubleWord(0x40061000,1))
g.Reset();check('owner-reset',i.Enable==i.Status==i.Reads==i.Writes==0 and not i.IRQ.IsSet)
Console.WriteLine('BLACKWALL_MSPI1_INTERRUPTS_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='local ready mock/software INTSET and NVIC pending; no hardware transfer, CPU ISR or original main')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700)
 (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-xip-guard-main-01/stock24/board.repl').read_text()));(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "mspi-interrupts"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(z.split('BLACKWALL_MSPI1_INTERRUPTS_UNIT ',1)[1]) for z in log.splitlines() if z.startswith('BLACKWALL_MSPI1_INTERRUPTS_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing interrupt unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
