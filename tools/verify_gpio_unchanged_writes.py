"""Verify bounded unchanged latch writes without assuming unknown pad configuration."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models

DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallGpioOutputLatch').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallGpioConfig,BlackwallGpioOutputLatch
checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state(t):return (tuple(t.Words),t.Reads,t.DirectWrites,t.SetWrites,t.ClearWrites,t.UnconfiguredNoOpWrites,t.LastNoOpMask,t.LastNoOpGroup)
def reject(t,n,a,v):
    before=state(t);check(n,not t.TryWrite(a,v) and state(t)==before)
c=BlackwallGpioConfig();t=BlackwallGpioOutputLatch(c,True)
check('explicit-mode',t.IdempotentUnconfiguredWrites)
check('unknown-clear-zero',t.TryWrite(0x40010468,0x100) and t.Words[4]==0 and t.UnconfiguredNoOpWrites==1 and t.LastNoOpMask==0x100 and t.LastNoOpGroup==4)
check('pad-not-invented',not c.Values.ContainsKey(0x40010220))
reject(t,'unknown-set-changes',0x4001044c,0x100)
reject(t,'reserved-noop-still-rejected',0x40010468,0x80)
reject(t,'mixed-reserved-noop-atomic',0x40010468,0x180)
check('zero-mask',t.TryWrite(0x40010468,0) and t.UnconfiguredNoOpWrites==1)
c.Values[0x40010220]=0x103
check('configured-set',t.TryWrite(0x4001044c,0x100) and t.Words[4]==0x100)
c.Values.Remove(0x40010220)
check('unknown-set-one-unchanged',t.TryWrite(0x4001044c,0x100) and t.Words[4]==0x100 and t.UnconfiguredNoOpWrites==2)
reject(t,'unknown-clear-one-changes',0x40010468,0x100)
c.Values[0x4001001c]=0x103
check('known-set',t.TryWrite(0x4001043c,0x80) and t.Words[0]==0x80)
check('mixed-known-change-unknown-unchanged',t.TryWrite(0x40010458,0x180) and t.Words[0]==0 and t.LastNoOpMask==0x100)
c.Values[0x40010020]=0x103
check('seed-both',t.TryWrite(0x4001043c,0x180) and t.Words[0]==0x180)
c.Values.Remove(0x40010020)
reject(t,'mixed-unknown-change-atomic',0x40010458,0x180)
check('direct-preserves-unknown',t.TryWrite(0x40010420,0x100) and t.Words[0]==0x100)
reject(t,'direct-changes-unknown',0x40010420,0)
reject(t,'direct-reserved-word',0x40010430,0x100)
reject(t,'unaligned',0x40010459,0)
ok,value=t.TryRead(0x40010458);check('clear-read-rejected',not ok)
t.Reset();check('reset',tuple(t.Words)==(0,)*7 and t.UnconfiguredNoOpWrites==t.LastNoOpMask==t.LastNoOpGroup==0)
legacy=BlackwallGpioOutputLatch(BlackwallGpioConfig())
reject(legacy,'legacy-unknown-noop-rejected',0x40010468,0x100)
check('legacy-default-off',not legacy.IdempotentUnconfiguredWrites)
m=monitor.Machine;g=m['sysbus.guard'];b=m.SystemBus
check('root-profile',g.GpioOutput.IdempotentUnconfiguredWrites)
check('root-missing-pad',not g.GpioConfig.Values.ContainsKey(0x40010220))
b.WriteDoubleWord(0x40010468,0x100)
check('root-noop-recorded',g.GpioOutput.UnconfiguredNoOpWrites==1 and g.GpioOutput.LastNoOpMask==0x100 and g.GpioOutput.Words[4]==0)
for name,fn in [('root-unknown-change',lambda:b.WriteDoubleWord(0x4001044c,0x100)),('root-byte',lambda:b.WriteByte(0x40010468,0)),('root-alias-read',lambda:b.ReadDoubleWord(0x40010468))]:
    count=g.AccessCount;before=state(g.GpioOutput)
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(name+' accepted')
    check(name,g.AccessCount==count+1 and state(g.GpioOutput)==before)
g.Reset();check('root-reset',g.GpioOutput.UnconfiguredNoOpWrites==0 and tuple(g.GpioOutput.Words)==(0,)*7)
Console.WriteLine('BLACKWALL_GPIO_UNCHANGED '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='explicit known-latch unchanged results only; no unknown pad state or physical signal behavior')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
 text=(s/'gpio-role-main-01/stock24-low/board.repl').read_text();anchor='    gpioOutputLatch: true\n'
 if text.count(anchor)!=1:raise ValueError('Output profile anchor differs')
 text=text.replace(anchor,anchor+'    gpioOutputIdempotentWrites: true\n')
 (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(text);(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "gpio-unchanged"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
 rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_GPIO_UNCHANGED ')]
 if len(rows)!=1:raise ValueError('Missing unchanged latch unit result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))
if __name__=='__main__':main()
