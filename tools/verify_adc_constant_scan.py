"""Exercise ADC constant scan FIFO behavior in Renode without firmware or devices."""
import argparse
import json
from pathlib import Path
import shutil
from run_renode_m55_probe import execute

ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import clr, json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallAdcConstantScan').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallAdcDisabledConfig,BlackwallAdcConstantScan
cases=[]
def check(name, condition):
    if not condition: raise Exception(name)
    cases.append(name)
def setup(raw):
    b=BlackwallAdcDisabledConfig(True); b.SourceReset=True; b.Reset()
    b.Values[0x40038000]=0x2171015; b.Values[0x40038018]=0x7800301
    return b,BlackwallAdcConstantScan(b,raw)
for raw in (0,2048,4095):
    b,s=setup(raw)
    check('software-'+str(raw),s.TryWrite(0x40038008,0x37))
    ok,v=s.TryRead(0x40038038)
    check('peek-'+str(raw),ok and v==((3<<28)|(1<<20)|(raw<<6)) and s.Count==1)
    ok,v=s.TryRead(0x4003803c)
    check('pop-'+str(raw),ok and v==((3<<28)|(raw<<6)) and s.Count==0 and s.Pops==1)
    check('empty-pop-'+str(raw),not s.TryRead(0x4003803c)[0])
b,s=setup(100)
for i in range(16): check('fill-'+str(i),s.TryScan())
check('full-no-overwrite',not s.TryScan() and s.Count==16 and s.Samples==16)
check('pending-full',s.Pending==15)
check('clear-pending',s.TryWrite(0x40038208,15) and s.Pending==0)
check('irq-enable-blocked',not s.TryWrite(0x40038200,1))
check('write-pop',s.TryWrite(0x40038038,0xffffffff) and s.Count==15)
b,s=setup(200); b.Values[0x40038020]=0x800401
check('unsupported-atomic',not s.TryWrite(0x40038008,0x37) and s.Count==0 and s.Samples==0 and not s.Primed)
b,s=setup(300); b.Values[0x4003800c]=0x800301
check('multi-scan',s.TryScan() and s.Count==2)
check('slot-order0',(s.TryRead(0x4003803c)[1]>>28)==0)
check('slot-order3',(s.TryRead(0x4003803c)[1]>>28)==3)
b,s=setup(400); b.Values[0x40038000]=0x2170015
check('non-destructive',s.TryScan() and s.TryRead(0x4003803c)[0] and s.Count==1)
check('invalid-trigger',not s.TryWrite(0x40038008,0x36) and s.SoftwareTriggers==0)
Console.WriteLine('BLACKWALL_SCAN '+json.dumps(dict(passed=True,cases=cases,case_count=len(cases),scope='isolated C# functional model only; no firmware/hardware validation')))
'''

POWER_DRIVER="""
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallAdcPower
for profile in (0,1):
    p=BlackwallAdcPower(1,profile)
    check('power-on-request-'+str(profile),p.TryWrite(0x2000,True))
    check('power-on-response-'+str(profile),p.TryReadStatus(True)[1]==0x2000 and p.Phase=='on')
    check('off-quiescence-block-'+str(profile),not p.TryWrite(0,True,False) and p.RequestWord==0x2000 and not p.EpochRetired)
    check('off-request-'+str(profile),p.TryWrite(0,True,True) and p.RequestWord==0 and p.StatusWord==0x2000 and p.EpochRetired and p.Phase=='off-requested')
    check('off-response-'+str(profile),p.TryReadStatus(True)[1]==(0 if profile==1 else 0x2000) and p.Phase==('powered-off' if profile==1 else 'stuck-on'))
    check('off-count-'+str(profile),p.OffRequests==1 and p.Transitions==4 and p.Responses==2)
    if profile==0:
        check('stuck-on-reenable-block',not p.TryWrite(0x2000,True,True) and p.EpochRetired)
    else:
        check('restart-needs-quiescence',not p.TryWrite(0x2000,True,False) and p.EpochRetired and p.Requests==1)
        check('restart-needs-ready',not p.TryWrite(0x2000,False,True) and p.EpochRetired and p.Requests==1)
        check('restart-request',p.TryWrite(0x2000,True,True) and not p.EpochRetired and p.Phase=='requested' and p.Requests==2 and p.Responses==2 and p.StatusWord==0)
        check('restart-no-early-response',not p.TryReadStatus(False)[0] and p.Responses==2 and p.Phase=='requested')
        check('restart-response',p.TryReadStatus(True)[1]==0x2000 and p.Responses==3 and p.Phase=='on')
        for cycle in range(3):
            check('cycle-off-'+str(cycle),p.TryWrite(0,True,True) and p.EpochRetired)
            check('pending-off-restart-block-'+str(cycle),not p.TryWrite(0x2000,True,True) and p.Phase=='off-requested')
            check('cycle-off-response-'+str(cycle),p.TryReadStatus(True)[1]==0 and p.Phase=='powered-off')
            check('cycle-request-'+str(cycle),p.TryWrite(0x2000,True,True) and not p.EpochRetired)
            check('cycle-response-'+str(cycle),p.TryReadStatus(True)[1]==0x2000 and p.Phase=='on' and p.Requests==3+cycle and p.OffRequests==2+cycle)

    p.Reset()
    check('off-reset-'+str(profile),p.Phase=='off' and not p.EpochRetired and p.OffRequests==0)
p=BlackwallAdcPower(1);p.TryWrite(0x2000,True);p.TryReadStatus(True)
check('off-default-block',not p.TryWrite(0,True,True) and p.Phase=='on')
p=BlackwallAdcPower(1,1);p.TryWrite(0x2000,True);p.TryWrite(0,True)
check('cancelled-restart-block',not p.TryWrite(0x2000,True,True) and p.Phase=='cancelled')
p=BlackwallAdcPower(0,1);p.TryWrite(0x2000,True);p.TryReadStatus(True)
check('stuck-off-restart-block',not p.TryWrite(0x2000,True,True) and p.Phase=='stuck-off')

"""

TRIGGER_CYCLE_DRIVER="""
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallAdcInternalTrigger
b,scan=setup(200)
t=BlackwallAdcInternalTrigger(monitor.Machine,16);t.Scan=scan
word=0x8004001e;previous=0x4001e;cfg=0x2171015
check('trigger-initial-start',t.TryStart(word,previous,cfg) and t.StartRequests==1 and t.Phase=='armed')
check('trigger-active-repeat',t.TryStart(word,word,cfg) and t.StartRequests==1 and t.TriggerEvents==0)
check('trigger-active-change-block',not t.TryStart(word+1,word,cfg) and t.StartRequests==1 and t.Word==word)
for cycle in range(4):
    check('trigger-stop-'+str(cycle),t.TryStop() and t.Phase=='stopped')
    for name,w,prev,c in [('previous-enable',word,word,cfg),('changed-count',word+1,previous,cfg),('adc-disabled',word,previous,cfg&~1),('zero-count',0x80040000,0x40000,cfg),('divider',0x8003001e,0x3001e,cfg)]:
        check('trigger-restart-reject-'+name+'-'+str(cycle),not t.TryStart(w,prev,c) and t.Phase=='stopped' and t.StartRequests==cycle+1)
    check('trigger-restart-'+str(cycle),t.TryStart(word,previous,cfg) and t.Phase=='armed' and t.StartRequests==cycle+2 and t.Word==word and t.Divider==16 and t.TickLimit==30 and t.TriggerEvents==0)
check('trigger-fifo-preserved',scan.Count==0 and not scan.Primed)
"""

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--with-power-off',action='store_true');p.add_argument('--with-trigger-cycle',action='store_true');a=p.parse_args();o=a.output.resolve();o.mkdir(mode=0o700)
    shutil.copy2(ROOT/'tools/renode-strict-mmio.cs',o/'strict.cs')
    extra=(POWER_DRIVER if a.with_power_off else '')+(TRIGGER_CYCLE_DRIVER if a.with_trigger_cycle else '')
    (o/'test.py').write_text(DRIVER.replace("Console.WriteLine('BLACKWALL_SCAN ",extra+"\nConsole.WriteLine('BLACKWALL_SCAN "))
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "adc-scan-unit"\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','blackwall-renode:1.17.0-local','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(x.split('BLACKWALL_SCAN ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_SCAN ')]
    if len(rows)!=1:raise ValueError('Missing scan result; inspect log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))

if __name__=='__main__':main()
