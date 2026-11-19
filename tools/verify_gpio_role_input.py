"""Test a bounded, source-consumer-specific GPIO156 input adapter; no device access."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute

DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallGpioRoleInput').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallGpioRoleInput
checks=[];m=monitor.Machine;pc=0x49668c
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
for level in [0,1]:
    p=BlackwallGpioRoleInput(m,level,pc,5)
    def blocked(n,pin,site,cfg):
        old=p.Reads;ok,value=p.TrySample(pin,site,cfg);check(n,not ok and p.Reads==old)
    blocked('unknown-pin',155,pc,True)
    blocked('unknown-consumer',156,pc+2,True)
    blocked('unconfigured',156,pc,False)
    ok,value=p.TryRead(0x40010410,True);check('other-bank-blocked',not ok and p.Reads==0)
    ok,value=p.TryRead(0x40010414,True);check('host-without-CPU-context-blocked',not ok and p.Reads==0)
    for i in range(5):
        ok,value=p.TrySample(156,pc,True);check('sample-'+str(level)+'-'+str(i),ok and value==level<<28 and p.Reads==i+1)
    blocked('finite-budget',156,pc,True)
    p.Reset();check('reset-budget',p.Reads==0)
    ok,value=p.TrySample(156,pc,True);check('reset-resamples',ok and value==level<<28 and p.Reads==1)
for machine,level,site,budget in [(None,0,pc,5),(m,-1,pc,5),(m,2,pc,5),(m,0,pc+1,5),(m,0,pc,0),(m,0,pc,65)]:
    try:BlackwallGpioRoleInput(machine,level,site,budget)
    except Exception as e:check('invalid-profile','explicit level, original read PC and finite budget' in str(e))
    else:raise Exception('invalid input accepted')
g=m['sysbus.guard'];b=m.SystemBus
for name,operation in [('input-write',lambda:b.WriteDoubleWord(0x40010414,0)),('input-byte',lambda:b.ReadByte(0x40010414)),('host-read',lambda:b.ReadDoubleWord(0x40010414)),('other-bank',lambda:b.ReadDoubleWord(0x40010410))]:
    count=g.AccessCount;old=g.GpioRoleInput.Reads
    try:operation()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(name+' accepted')
    check(name+'-root-guard',g.AccessCount==count+1 and g.GpioRoleInput.Reads==old)
ok,value=g.GpioRoleInput.TrySample(156,pc,True)
check('root-unit-sample',ok and g.GpioRoleInput.Reads==1)
g.Reset();check('root-reset-samples',g.GpioRoleInput.Reads==0)
Console.WriteLine('BLACKWALL_GPIO_ROLE_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='direct adapter guards/sample logic; no original HAL call or full main proof')))
'''


RUNTIME_TOUCH_DRIVER='''
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallGpioInterruptIdle
q=BlackwallGpioInterruptIdle(False,True);off=BlackwallGpioInterruptIdle()
t=BlackwallGpioRoleInput(m,0,pc,5,1,4)
for pin,site,cfg,source in [(26,pc,True,q),(27,pc+2,True,q),(27,pc,False,q),(27,pc,True,None),(27,pc,True,off)]:
    ok,value=t.TryRuntimeTouchSample(pin,site,cfg,source)
    check('runtime-context-rejected',not ok and t.TouchReads==0 and q.FallingEdges==0)
ok,value=t.TryRuntimeTouchSample(27,pc,True,q)
check('runtime-initial-high',ok and value==1<<27 and t.TouchReads==1)
check('runtime-falling-input',q.TrySetPin27(False,True) and q.Pending27 and q.FallingEdges==1)
ok,value=t.TryRuntimeTouchSample(27,pc,True,q)
check('runtime-low-observed',ok and value==0 and t.TouchReads==2 and q.Pending27)
q.TrySetPin27(True,True)
ok,value=t.TryRuntimeTouchSample(27,pc,True,q)
check('runtime-release-observed',ok and value==1<<27 and t.TouchReads==3 and q.Pending27 and q.FallingEdges==1)
q.TrySetPin27(False,True)
ok,value=t.TryRuntimeTouchSample(27,pc,True,q)
check('runtime-second-edge',ok and value==0 and t.TouchReads==4 and q.FallingEdges==2)
ok,value=t.TryRuntimeTouchSample(27,pc,True,q)
check('runtime-budget-strict',not ok and t.TouchReads==4)
t.Reset()
check('reader-reset-keeps-source-low',not q.Pin27High and q.Pending27 and t.TouchReads==0)
q.Reset();ok,value=t.TryRuntimeTouchSample(27,pc,True,q)
check('source-reset-initial-level',ok and value==1<<27 and not q.Pending27)
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--touch',action='store_true');p.add_argument('--runtime-touch',action='store_true');a=p.parse_args();
    if a.runtime_touch and not a.touch:p.error('--runtime-touch requires --touch')
    s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    driver=DRIVER
    if a.touch:
        extra='''
for level in [0,1]:
    t=BlackwallGpioRoleInput(m,0,pc,5,level,2)
    check('touch-bank-selected',t.Owns(0x40010404) and t.Owns(0x40010414))
    for pin,site,cfg in [(26,pc,True),(156,pc,True),(27,pc+2,True),(27,pc,False)]:
        ok,value=t.TryTouchSample(pin,site,cfg);check('touch-invalid-context',not ok and t.TouchReads==0 and t.Reads==0)
    for sample in range(2):
        ok,value=t.TryTouchSample(27,pc,True);check('touch-value-'+str(level),ok and value==level<<27 and t.TouchReads==sample+1 and t.Reads==0)
    ok,value=t.TryTouchSample(27,pc,True);check('touch-finite-budget',not ok and t.TouchReads==2)
    ok,value=t.TrySample(156,pc,True);check('role-budget-independent',ok and t.Reads==1 and t.TouchReads==2)
    t.Reset();check('both-budgets-reset',t.Reads==t.TouchReads==t.LastTouchContextPc==t.LastTouchContextPin==0)
t=BlackwallGpioRoleInput(m,0,pc,5)
ok,value=t.TryTouchSample(27,pc,True)
check('touch-disabled-default',not ok and not t.Owns(0x40010404) and t.TouchReads==0)
for level,budget in [(-2,1),(2,1),(0,0),(0,65)]:
    try:BlackwallGpioRoleInput(m,0,pc,5,level,budget)
    except Exception as e:check('touch-invalid-profile','GPIO touch input' in str(e))
    else:raise Exception('invalid touch input accepted')
for name,operation in [('touch-write',lambda:b.WriteDoubleWord(0x40010404,0)),('touch-byte',lambda:b.ReadByte(0x40010404)),('touch-host-read',lambda:b.ReadDoubleWord(0x40010404))]:
    count=g.AccessCount;before=g.GpioRoleInput.TouchReads
    try:operation()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(name+' accepted')
    check(name+'-strict',g.AccessCount==count+1 and g.GpioRoleInput.TouchReads==before)
'''
        driver=driver.replace("Console.WriteLine('BLACKWALL_GPIO_ROLE_UNIT",extra+"Console.WriteLine('BLACKWALL_GPIO_ROLE_UNIT")
    if a.runtime_touch:
        driver=driver.replace("Console.WriteLine('BLACKWALL_GPIO_ROLE_UNIT",RUNTIME_TOUCH_DRIVER+"Console.WriteLine('BLACKWALL_GPIO_ROLE_UNIT")
    (o/'strict.cs').write_bytes(models(s));(o/'test.py').write_text(driver)
    board=s/'gpio-role-main-01/stock24-low/board.repl'
    text=board.read_text()
    if a.touch:
        anchor='gpio_role_input: Miscellaneous.BlackwallGpioRoleInput @ none\n'
        if text.count(anchor)!=1:raise ValueError('GPIO adapter anchor differs')
        text=text.replace(anchor,anchor+'    touchLevel: 1\n    touchReadBudget: 1\n')
    (o/'board.repl').write_text(text)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "GPIO-role"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_GPIO_ROLE_UNIT ')]
    if len(rows)!=1:raise ValueError('Missing GPIO unit result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
