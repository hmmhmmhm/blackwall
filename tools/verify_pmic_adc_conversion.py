"""Verify virtual PMIC VBAT/IBAT time, result bits and events with declared raw samples."""
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
def fixture(vbat=778,ibat=5,mock=0):return BlackwallPmicTimedProbe(m,'fast-reset-stopped',-1,None,'source-reset-storage',None,-1,'discharging-vbat-ibat-fixture',vbat,ibat,mock)
def send(q,v):q.Write(Array[Byte](v));q.FinishTransmission()
def get(q,address):q.Write(Array[Byte]([address>>8,address&255]));q.FinishTransmission();value=list(q.Read(1))[0];q.FinishTransmission();return value
def reject_q(name,fn):
    try:fn()
    except Exception as e:
        if 'PMIC restore unsupported' not in str(e):raise
        check(name,True)
    else:raise Exception(name+' accepted')
q=fixture();u=fixture(mock=-1);low=fixture(0,1023);high=fixture(1023,0)
check('conversion-initial-unknown',q.AdcConversion.Read(0x511,1) is None and list(q.AdcConversion.KnownMasks)==[0,0,0,0,0,252,0,0,0,0,207])
for obj in [q,low,high]:send(obj,[5,0x24,1]);send(obj,[0,4,0x41]);send(obj,[5,0,1])
send(u,[5,0,1]);check('conversion-no-immediate-event',q.AdcConversion.Phase=='vbat' and q.Inner.EventState[0]==0 and not q.Inner.DigitalIrqPending)
reject_q('conversion-result-before-ready',lambda:q.Write(Array[Byte]([5,0x11])))
for v,i in [(-1,0),(1024,0),(0,1024)]:
    try:fixture(v,i)
    except Exception:check('conversion-invalid-sample-'+str(v)+'-'+str(i),True)
    else:raise Exception('invalid sample accepted')
try:BlackwallPmicTimedProbe(m,'fast-reset-stopped',-1,None,'guest-storage',None,-1,'discharging-vbat-ibat-fixture',778,5,0)
except Exception:check('conversion-requires-explicit-source-state',True)
else:raise Exception('implicit ADC state accepted')
'''
PHASES=[('000249',"""
check('conversion-before-250us',q.AdcConversion.VbatCompletions==0 and q.Inner.EventState[0]==0)
send(q,[5,0,1]);check('conversion-repeat-lost-not-rearmed',q.AdcConversion.Requests==1 and q.AdcConversion.RepeatedDrops==1)
before_cfg=(list(q.Inner.AdcConfigValues),q.Inner.AdcConfigWrites,q.Inner.RegisterWrites,q.Inner.AdcAutoUpdateRequests)
for address,value in [(0x524,0),(0x509,1),(0x50c,1)]:reject_q('conversion-active-config-rejected-'+str(address),lambda:send(q,[address>>8,address&255,value]))
check('conversion-active-config-atomic',before_cfg==(list(q.Inner.AdcConfigValues),q.Inner.AdcConfigWrites,q.Inner.RegisterWrites,q.Inner.AdcAutoUpdateRequests) and q.AdcConversion.Phase=='vbat')
"""),('000001',"""
Console.WriteLine('BLACKWALL_ADC_TIME '+json.dumps(dict(phase=q.AdcConversion.Phase,vbat_ticks=int(q.AdcConversion.VbatTicks),ibat_ticks=int(q.AdcConversion.IbatTicks),vbat_done=int(q.AdcConversion.VbatCompletions),virtual_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks))))
check('conversion-clock-exact-250us',m.ElapsedVirtualTime.TimeElapsed.Ticks==TimeInterval.FromMicroseconds(250).Ticks)
check('conversion-vbat-250us',q.AdcConversion.VbatCompletions==1 and q.AdcConversion.Phase=='ibat' and q.AdcConversion.IbatCompletions==0)
check('conversion-vbat-event',q.Inner.EventState[0]==1 and q.Inner.DigitalIrqPending)
check('conversion-vbat-packing',get(q,0x511)==194 and get(q,0x515)==2)
check('conversion-unknown-shared-bits',u.AdcConversion.KnownMasks[5]==3 and u.AdcConversion.Read(0x515,1) is None)
check('conversion-unpaired-idle',u.AdcConversion.Phase=='idle' and u.AdcConversion.IbatCompletions==0)
reject_q('conversion-unknown-lsb-read-blocked',lambda:u.Write(Array[Byte]([5,0x15])))
reject_q('conversion-ibat-before-ready',lambda:q.Write(Array[Byte]([5,0x18])))
reject_q('conversion-alternate-request-unmodeled',lambda:send(q,[5,0,1]))
reject_q('conversion-ibat-config-write-blocked',lambda:send(q,[5,0x24,0]))
check('conversion-alternate-preserves-state',q.AdcConversion.Requests==1 and q.AdcConversion.Phase=='ibat')
check('conversion-zero-max-vbat',get(low,0x511)==0 and get(low,0x515)==0 and get(high,0x511)==255 and get(high,0x515)==3)
"""),('000249',"""
check('conversion-before-500us',q.AdcConversion.IbatCompletions==0 and q.Inner.EventState[0]==1)
"""),('000001',"""
check('conversion-clock-exact-500us',m.ElapsedVirtualTime.TimeElapsed.Ticks==TimeInterval.FromMicroseconds(500).Ticks)
check('conversion-ibat-500us',q.AdcConversion.IbatCompletions==1 and q.AdcConversion.Phase=='idle')
check('conversion-ibat-event',q.Inner.EventState[0]==0x41 and q.Inner.DigitalIrqPending)
check('conversion-ibat-packing',get(q,0x518)==1 and get(q,0x51a)==16 and get(q,0x510)==4)
check('conversion-zero-max-ibat',get(low,0x518)==255 and get(low,0x51a)==48 and get(high,0x518)==0 and get(high,0x51a)==0)
check('conversion-other-channels-unknown',q.AdcConversion.Read(0x512,1) is None and q.AdcConversion.Read(0x511,10) is None)
send(q,[0,3,0x41]);check('conversion-guest-event-clear',q.Inner.EventState[0]==0 and not q.Inner.DigitalIrqPending)
send(q,[5,0,0]);check('conversion-zero-task-noop',q.AdcConversion.Requests==1 and q.AdcConversion.Phase=='idle')
reject_q('conversion-auto-scheduling-unmodeled',lambda:send(q,[5,9,1]));check('conversion-core-auto-task-rejected',not q.AdcConversion.Task(1,1,1))
check('conversion-rejected-config-no-result-change',get(q,0x511)==194 and q.AdcConversion.Requests==1)
q.Reset();send(q,[5,0,1])
"""),('000100',"""
q.Reset();check('conversion-reset-cancels',q.AdcConversion.Phase=='idle' and q.AdcConversion.Requests==0)
"""),('000500',"""
check('conversion-reset-no-late-result',q.AdcConversion.VbatCompletions==0 and q.AdcConversion.Read(0x511,1) is None and q.Inner.EventState[0]==0)
""")]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence required')
 o.mkdir(mode=0o700);(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes()+b'\n'+(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes());driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+EXTRA+GPIO+CHARGER+VBUS+ADC+SCRATCH+RESET+SETUP;compile(driver,'setup.py','exec');(o/'setup.py').write_text(driver);resc='include @/work/peer.cs\nmach create "adc-conversion"\ninclude @/work/setup.py\n'
 for n,(duration,text) in enumerate(PHASES):
  compile(text,'phase.py','exec');(o/f'phase-{n}.py').write_text(text)
  advance='from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(int(duration))+'))\n'
  (o/f'advance-{n}.py').write_text(advance);resc+='include @/work/advance-'+str(n)+'.py\ninclude @/work/phase-'+str(n)+'.py\n'
 (o/'precision-before.py').write_text('precision_before=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n');(o/'precision-after.py').write_text("Console.WriteLine('BLACKWALL_TIME_PRECISION '+json.dumps(dict(string_249us_delta_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-precision_before,integer_249us_ticks=int(TimeInterval.FromMicroseconds(249).Ticks))))\n");resc+='include @/work/precision-before.py\nemulation RunFor \"00:00:00.000249\"\ninclude @/work/precision-after.py\n'
 report="Console.WriteLine('BLACKWALL_CONVERSION_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='explicit raw sample and nominal virtual250us per stage; no physical/analog/full ADC proof')))\n";(o/'report.py').write_text(report);(o/'probe.resc').write_text(resc+'include @/work/report.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_CONVERSION_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_CONVERSION_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing conversion unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
