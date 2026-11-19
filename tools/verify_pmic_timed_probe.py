"""Verify virtual PMIC watchdog time and bounded I2C timer frames, without hardware."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from verify_pmic_interrupt_registers import EXTRA
from verify_pmic_gpio_storage import GPIO
from verify_pmic_charger_storage import CHARGER
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
SETUP='''
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallPmicTimedProbe
m=monitor.Machine
q=BlackwallPmicTimedProbe(m,'fast-reset-stopped',0)
def send(v):q.Write(Array[Byte](v));q.FinishTransmission()
def selected(address,count):q.Write(Array[Byte]([address>>8,address&255]));q.FinishTransmission();r=list(q.Read(count));q.FinishTransmission();return r
check('inner-read-preserved',selected(0x509,1)==[0])
send([7,5,10]);q.Write(Array[Byte]([7,8,0,0]));check('fragment-not-applied',not q.Timer.TargetKnown and q.Timer.Read(0x708,3,0) is None)
q.Write(Array[Byte]([5]));q.FinishTransmission();check('target-staged-not-committed',not q.Timer.TargetKnown and selected(0x708,3)==[0,0,5])
send([7,3,1]);check('target-committed',q.Timer.Target==5 and q.Timer.Strobes==1)
q.Write(Array[Byte]([7,5]));check('repeated-start-profile',list(q.Read(6))==[10,0,0,0,0,5]);q.FinishTransmission();check('repeated-start-count',q.RepeatedStarts==1)
q.Write(Array[Byte]([7,5]));check('split-read-head',list(q.Read(4))==[10,0,0,0]);check('split-read-tail',list(q.Read(2))==[0,5])
try:q.Read(1)
except Exception:check('split-read-overrun-blocked',q.LastOperation=='timer-read-overlap')
else:raise Exception('split read overrun accepted')
q.FinishTransmission()
r=BlackwallPmicTimedProbe(m,'fast-reset-stopped')
r.Write(Array[Byte]([7,5,10]));r.FinishTransmission();r.Write(Array[Byte]([7,8,0,0,5]));r.FinishTransmission()
r.Write(Array[Byte]([7,5]));r.FinishTransmission()
try:r.Read(6)
except Exception as e:check('read-holes-default-unknown','timer-read-unknown' in str(e))
else:raise Exception('unknown holes read accepted')
bad=BlackwallPmicTimedProbe(m,'fast-reset-stopped')
bad.Write(Array[Byte]([7,5,255]))
try:bad.FinishTransmission()
except Exception:check('invalid-mode-atomic',not bad.Timer.ConfigKnown)
else:raise Exception('invalid config accepted')
bad.Reset();bad.Write(Array[Byte]([7,8,0,0]))
try:bad.FinishTransmission()
except Exception:check('incomplete-target-atomic',bad.Timer.Read(0x708,3,0) is None)
else:raise Exception('incomplete frame accepted')
bad.Reset();check('start-needs-commit',not bad.Timer.Write(0x700,1));check('inactive-kick-rejected',not bad.Timer.Write(0x704,1))
fault=BlackwallPmicTimedProbe(m,'fast-reset-stopped')
try:fault.Write(Array[Byte]([7,2]))
except Exception:check('timer-guard-owner',fault.LastOperation=='timer-register-unknown')
else:raise Exception('reserved timer register accepted')
try:fault.Write(Array[Byte]([1,0]))
except Exception:check('latest-inner-guard-owner',fault.AccessCount==2 and fault.LastOperation=='peer-write-unsupported' and fault.LastValue==0x100)
else:raise Exception('unknown inner address accepted')
check('zero-task-noop',bad.Timer.Write(0x700,0) and not bad.Timer.Running)
check('zero-target-stage',bad.Timer.StageTarget(Array[Byte]([0,0,0])))
check('configure-before-strobe',bad.Timer.Write(0x705,10) and not bad.Timer.Write(0x703,1))
send([0,0x14,8]);send([7,0,1]);check('started-5ticks',q.Timer.Running and q.Timer.Starts==1)
'''
PHASES=[('007',"check('before-warning',q.Timer.Warnings==0 and q.Timer.Running)"),('001',"check('warning-at-8ms',q.Timer.Warnings==1 and q.Inner.EventState[4]==8 and q.Inner.DigitalIrqPending)\nsend([7,4,1]);check('kick-reloads-not-event-clear',q.Timer.Kicks==1 and q.Inner.EventState[4]==8)\nsend([0,0x13,8]);check('guest-warning-clear',not q.Inner.DigitalIrqPending)"),('007',"check('kick-prevents-old-expiry',q.Timer.Running and not q.Timer.ResetRequested and q.Timer.Warnings==1)"),('001',"check('second-warning',q.Timer.Warnings==2 and q.Inner.DigitalIrqPending)"),('002',"check('expiry-request',q.Timer.ResetRequested and q.Timer.ResetRequests==1 and not q.Timer.Running and q.LastOperation=='pmic-watchdog-reset-request')\ncheck('stop-does-not-hide-reset',not q.Timer.Write(0x701,1))\ncheck('reset-request-freezes-target',not q.Timer.StageTarget(Array[Byte]([0,0,10])))")]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Use fresh evidence directory')
 o.mkdir(mode=0o700);root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes();(o/'peer.cs').write_bytes(root+b'\n'+timed)
 driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+EXTRA+GPIO+CHARGER+SETUP
 compile(driver,'setup.py','exec');(o/'setup.py').write_text(driver);resc='include @/work/peer.cs\nmach create "pmic-clock"\ninclude @/work/setup.py\n'
 for n,(duration,text) in enumerate(PHASES):
  compile(text,'phase.py','exec');(o/f'phase-{n}.py').write_text(text+'\n');resc+='emulation RunFor "00:00:00.'+duration+'"\ninclude @/work/phase-'+str(n)+'.py\n'
 nominal="q.Reset();send([7,5,10]);send([7,8,0,0x3c,0]);send([7,3,1]);send([0,0x14,8]);send([7,0,1]);check('nominal-target-committed',q.Timer.Target==0x3c00 and q.Timer.Running)\n"
 (o/'nominal.py').write_text(nominal);resc+='include @/work/nominal.py\n'
 for n,(duration,text) in enumerate([('30.717',"check('nominal-before-warning',q.Timer.Warnings==0 and q.Timer.Running)"),('00.001',"check('nominal-warning-30718ms',q.Timer.Warnings==1 and q.Inner.DigitalIrqPending)"),('00.002',"check('nominal-expiry-30720ms',q.Timer.ResetRequests==1 and q.Timer.ResetRequested)")]):
  (o/f'nominal-{n}.py').write_text(text+'\n');resc+='emulation RunFor "00:00:'+duration+'"\ninclude @/work/nominal-'+str(n)+'.py\n'
 stop_setup="q.Reset();send([7,5,10]);send([7,8,0,0,5]);send([7,3,1]);send([0,0x14,8]);send([7,0,1])\n"
 (o/'stop-setup.py').write_text(stop_setup);resc+='include @/work/stop-setup.py\n'
 stop_phases=[('004',"send([7,1,1]);check('stop-before-expiry',not q.Timer.Running and q.Timer.Stops==1)"),('020',"check('stop-cancels-warning-and-expiry',q.Timer.Warnings==0 and q.Timer.ResetRequests==0)\nsend([7,0,1]);check('restart',q.Timer.Starts==2 and q.Timer.Running)"),('007',"check('restart-full-period',q.Timer.Warnings==0 and q.Timer.Running)"),('001',"check('restart-warning',q.Timer.Warnings==1)"),('002',"check('restart-expiry',q.Timer.ResetRequests==1)")]
 for n,(duration,text) in enumerate(stop_phases):
  (o/f'stop-{n}.py').write_text(text+'\n');resc+='emulation RunFor "00:00:00.'+duration+'"\ninclude @/work/stop-'+str(n)+'.py\n'
 report="Console.WriteLine('BLACKWALL_TIMED_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,warnings=int(q.Timer.Warnings),reset_requests=int(q.Timer.ResetRequests),scope='virtual 500Hz timing and bounded timer I2C; no hardware reset or GPIO wiring')))\n";(o/'report.py').write_text(report);(o/'probe.resc').write_text(resc+'include @/work/report.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_TIMED_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_TIMED_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing timed unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
