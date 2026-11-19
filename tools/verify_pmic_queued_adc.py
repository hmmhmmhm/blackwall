"""Verify bounded ADC priority requests, raw sensor fixtures and result streaming; no device access."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from verify_pmic_interrupt_registers import EXTRA
from verify_pmic_gpio_storage import GPIO
from verify_pmic_charger_storage import CHARGER
from verify_pmic_vbus_storage import VBUS
from verify_pmic_adc_storage import ADC
from verify_pmic_scratch_storage import SCRATCH
from verify_pmic_adc_reset_profile import RESET
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
SETUP='''
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallPmicTimedProbe
m=monitor.Machine
def queued(reset='source-reset'):return BlackwallPmicTimedProbe(m,'fast-reset-stopped',-1,None,'source-reset-storage',None,-1,'queued-six-channel-fixture',778,5,-1,512,466,611,reset,0)
def send(q,v):q.Write(Array[Byte](v));q.FinishTransmission()
def pointer(q,a):q.Write(Array[Byte]([a>>8,a&255]));q.FinishTransmission()
def get(q,a):pointer(q,a);r=list(q.Read(1))[0];q.FinishTransmission();return r
def rejected(name,fn):
    try:fn()
    except Exception as e:
        if 'PMIC restore unsupported' not in str(e):raise
        check(name,True)
    else:raise Exception(name+' accepted')
q=queued();u=queued(None)
check('queue-initial-reset-not-measured',list(q.QueuedAdc.KnownMasks)==[255]*11 and list(q.QueuedAdc.Completed)==[0]*6 and q.Inner.EventState[0]==0)
check('queue-default-unknown',list(u.QueuedAdc.KnownMasks)==[0]*11 and u.QueuedAdc.Read(0x511,1) is None)
check('queue-read-address-bounds',q.QueuedAdc.Read(2147483647,1) is None and q.QueuedAdc.Read(0x511,2147483647) is None)
send(q,[5,0x24,1]);send(q,[0,4,0xcf]);send(q,[5,3,1]);send(q,[5,7,1]);send(q,[5,0,1]);send(q,[5,1,1]);send(q,[5,2,1]);send(q,[5,1,1])
send(u,[5,1,1])
check('queue-no-preemption',q.QueuedAdc.Active=='vsys' and q.QueuedAdc.PendingMask==43 and q.QueuedAdc.Requests==5 and q.QueuedAdc.RepeatedDrops==1)
before=(q.Inner.AdcConfigWrites,q.Inner.RegisterWrites,list(q.Inner.AdcConfigValues),q.QueuedAdc.PendingMask)
rejected('queue-active-config-blocked',lambda:send(q,[5,0x24,0]));check('queue-active-config-atomic',before==(q.Inner.AdcConfigWrites,q.Inner.RegisterWrites,list(q.Inner.AdcConfigValues),q.QueuedAdc.PendingMask))
'''
PHASES=[(249,"check('queue-before-first-completion',list(q.QueuedAdc.CompletionOrder)==[] and q.Inner.EventState[0]==0)"),(1,"""
check('queue-finish-active-before-high-priority',list(q.QueuedAdc.CompletionOrder)==[4] and q.QueuedAdc.Active=='vbat' and get(q,0x514)==152)
check('queue-unmeasured-read-unknown',u.QueuedAdc.Read(0x515,1) is None and u.QueuedAdc.KnownMasks[5]==12)
"""),(250,"check('queue-ntc-before-automatic-ibat',list(q.QueuedAdc.CompletionOrder)==[4,0] and q.QueuedAdc.Active=='ntc' and q.QueuedAdc.AutomaticIbatRequests==1)"),(250,"check('queue-ibat-before-die',list(q.QueuedAdc.CompletionOrder)==[4,0,1] and q.QueuedAdc.Active=='ibat')"),(250,"check('queue-die-last',list(q.QueuedAdc.CompletionOrder)==[4,0,1,2] and q.QueuedAdc.Active=='die')"),(250,"check('queue-vbus-last',q.QueuedAdc.Active=='vbus' and list(q.QueuedAdc.CompletionOrder)==[4,0,1,2,3])"),(250,"""
check('queue-all-completed',q.QueuedAdc.Active=='idle' and q.QueuedAdc.PendingMask==0 and list(q.QueuedAdc.CompletionOrder)==[4,0,1,2,3,5] and list(q.QueuedAdc.Completed)==[1]*6)
check('queue-six-event-latches',q.Inner.EventState[0]==0xcf and q.Inner.DigitalIrqPending)
check('queue-result-packing',list(q.QueuedAdc.Values)==[4,194,128,116,152,226,0,0,1,0,16])
pointer(q,0x511);parts=[list(q.Read(n)) for n in [4,4,2]]
check('queue-result-stream-4-4-2',parts==[[194,128,116,152],[226,0,0,1],[0,16]])
reads=q.Inner.DataReads;rejected('queue-stream-overrun',lambda:q.Read(1));check('queue-stream-overrun-atomic',q.Inner.DataReads==reads)
q.FinishTransmission();check('queue-pointer-advanced',q.Inner.Pointer==0x51b)
pointer(u,0x512);check('queue-unknown-scalar-readable',list(u.Read(1))==[128]);rejected('queue-unknown-stream-gap',lambda:u.Read(1));u.FinishTransmission()
check('queue-unrequested-burst-unknown',u.QueuedAdc.Read(0x516,1) is None)
for _ in range(200):get(q,0x2)
for _ in range(100):send(q,[5,0,0])
check('queue-trace-ring-does-not-stop-traffic',len(q.Inner.ReadAddresses)==64 and len(q.Inner.WriteAddresses)==64 and q.Inner.DataReads>200 and q.QueuedAdc.Requests==5)
send(q,[0,3,0xcf]);check('queue-guest-event-clear',q.Inner.EventState[0]==0 and not q.Inner.DigitalIrqPending)
q.Reset();send(q,[5,3,1]);send(q,[5,0,1])
"""),(100,"q.Reset();check('queue-reset-cancels-active-and-pending',q.QueuedAdc.Active=='idle' and q.QueuedAdc.PendingMask==0)"),(1500,"""
check('queue-no-late-completion',list(q.QueuedAdc.Completed)==[0]*6 and q.Inner.EventState[0]==0)
s=queued();send(s,[5,0,1]);pointer(s,0x511);check('queue-snapshot-first-chunk',list(s.Read(4))==[0]*4)
"""),(250,"""
check('queue-snapshot-bank-updated',s.QueuedAdc.Completed[0]==1 and s.QueuedAdc.Values[1]==194)
check('queue-snapshot-tail-stable',list(s.Read(4))+list(s.Read(2))==[0]*6);s.FinishTransmission()
check('queue-next-transaction-sees-new-result',get(s,0x511)==194 and get(s,0x515)==2)
check('queue-result-read-counters',s.Inner.AdcResultReads==5 and s.Inner.AdcResultBytes==12 and list(s.Inner.AdcResultAddresses)==[0x511,0x515,0x519,0x511,0x515])
""")]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence directory required')
 o.mkdir(mode=0o700);(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes()+b'\n'+(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes());driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+EXTRA+GPIO+CHARGER+VBUS+ADC+SCRATCH+RESET+SETUP;compile(driver,'setup.py','exec');(o/'setup.py').write_text(driver);resc='include @/work/peer.cs\nmach create "queued-adc"\ninclude @/work/setup.py\n'
 for n,(us,script) in enumerate(PHASES):
  compile(script,'phase.py','exec');(o/f'phase-{n}.py').write_text(script);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'report.py').write_text("Console.WriteLine('BLACKWALL_QUEUED_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='explicit raw fixtures and source-reset result option; nominal virtual250us; no physical ADC proof')))\n");(o/'probe.resc').write_text(resc+'include @/work/report.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_QUEUED_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_QUEUED_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing queued ADC marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
