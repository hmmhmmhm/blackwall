"""Check boot-time peripheral and clock contracts without forcing hardware state."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from run_renode_m55_probe import execute


DRIVER = '''import json
from System import Console
g=monitor.Machine['sysbus.guard']
checks=[]
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
def blocked(name,action):
 before=int(g.AccessCount)
 try:action()
 except Exception:pass
 else:raise Exception(name+' accepted')
 check(name,int(g.AccessCount)==before+1 and g.AdcPower.RequestWord==0)
def clear_cal():g.WriteDoubleWord(0x1f10c,0)
try:
 g.Reset();clear_cal()
 check('cold-buck-off',g.BuckResponsePhase=='off' and not g.BuckStart.EnableRequested)
 g.WriteDoubleWord(0x20004,0x2000)
 check('cold-request-latched',g.AdcPower.RequestWord==0x2000 and g.AdcPower.StatusWord==0 and g.AdcPower.Requests==1 and g.AdcPower.Responses==0)
 check('cold-request-readback',g.ReadDoubleWord(0x20004)==0x2000)
 check('cold-status-profile',g.ReadDoubleWord(0x20008)==(0x2000 if PROFILE else 0))
 check('cold-status-phase',g.AdcPower.Phase==('on' if PROFILE else 'stuck-off') and g.AdcPower.Responses==1)
 check('buck-state-not-forced',g.BuckResponsePhase=='off' and g.BuckResponseTransitions==0 and g.BuckOverrideStep==0 and not g.BuckStart.EnableRequested)
 check('calibration-not-fabricated',g.AdcCalibrationControl.Value==0)
 check('other-owners-preserved',g.GpuPower.RequestWord==0 and all(p.Value.RequestWord==0 for p in g.UartPowers) and all(p.Value.RequestWord==0 for p in g.IomPowers))
 g.Reset()
 blocked('automatic-calibration-unsupported',lambda:g.WriteDoubleWord(0x20004,0x2000))
 g.Reset();clear_cal()
 blocked('two-owner-write-atomic',lambda:g.WriteDoubleWord(0x20004,0x2200))
 check('uart-preserved-after-reject',g.UartPowers[0].RequestWord==0)
 g.Reset();clear_cal()
 blocked('unknown-bit-atomic',lambda:g.WriteDoubleWord(0x20004,0x80002000))
 g.Reset();clear_cal()
 blocked('partial-write-rejected',lambda:g.WriteWord(0x20004,0x2000))
 for mask in (0x4000,0x8000,0x08000000,0x200000):
  g.Reset();clear_cal()
  blocked('other-cold-domain-'+str(mask),lambda:g.WriteDoubleWord(0x20004,mask))
 g.Reset();clear_cal();g.WriteDoubleWord(0x20004,0x2000);g.WriteDoubleWord(0x1f10c,1)
 before=int(g.AccessCount)
 try:g.ReadDoubleWord(0x20008)
 except Exception:pass
 else:raise Exception('pending calibration change accepted')
 check('pending-calibration-change-rejected',g.AccessCount==before+1 and g.AdcPower.RequestWord==0x2000 and g.AdcPower.StatusWord==0 and g.AdcPower.Responses==0)
 g.Reset();clear_cal();g.WriteDoubleWord(0x20004,0x2000);g.WriteDoubleWord(0x20004,0)
 check('pending-cancel-preserved',g.AdcPower.Phase=='cancelled' and g.AdcPower.RequestWord==0 and g.AdcPower.StatusWord==0 and g.AdcPower.Cancellations==1)
 result=dict(passed=True,profile=PROFILE,checks=checks)
except Exception as error:
 result=dict(passed=False,profile=PROFILE,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_ADC_COLD '+json.dumps(result))
'''


CLOCK_DRIVER = '''import json
from System import Console
g=monitor.Machine['sysbus.guard']
checks=[]
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
def blocked(name,action):
 before=int(g.AccessCount);word=int(g.McuClock.MiscWord);mode=int(g.McuClock.ModeWord)
 try:action()
 except Exception:pass
 else:raise Exception(name+' accepted')
 check(name,g.AccessCount==before+1 and g.McuClock.MiscWord==word and g.McuClock.ModeWord==mode)
try:
 g.Reset()
 check('cold-buck-off',g.BuckResponsePhase=='off' and not g.BuckStart.EnableRequested)
 initial=int(g.McuClock.MiscWord)
 g.WriteDoubleWord(0x3044,initial|1)
 check('hfrc-force-on',g.McuClock.HfrcForced and g.McuClock.MiscWord==initial|1)
 check('hfrc-status',g.ReadDoubleWord(0x3030)&0x40000000==0x40000000)
 g.WriteDoubleWord(0x3044,initial|33)
 check('hfrc2-force-on',g.McuClock.Enabled and g.McuClock.MiscWord==initial|33)
 check('hfrc2-status-profile',bool(g.ReadDoubleWord(0x3030)&0x1000000)==(PROFILE==0))
 blocked('mcu-mode-still-needs-buck',lambda:g.WriteDoubleWord(0x20000,(g.McuClock.ModeWord&~3)|2))
 g.WriteDoubleWord(0x3044,initial)
 check('release-force',not g.McuClock.HfrcForced and g.McuClock.MiscWord==initial)
 check('buck-unchanged',g.BuckResponsePhase=='off' and g.BuckResponseTransitions==0 and not g.BuckStart.EnableRequested)
 blocked('reserved-bit',lambda:g.WriteDoubleWord(0x3044,initial^2))
 blocked('partial-write',lambda:g.WriteWord(0x3044,1))
 blocked('status-write',lambda:g.WriteDoubleWord(0x3030,0))
 check('adc-unchanged',g.AdcPower.RequestWord==0 and g.AdcPower.StatusWord==0)
 result=dict(passed=True,profile=PROFILE,checks=checks)
except Exception as error:
 result=dict(passed=False,profile=PROFILE,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_ADC_COLD '+json.dumps(result))
'''


UART_DRIVER = '''import json
from System import Console
g=monitor.Machine['sysbus.guard']
checks=[]
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
def blocked(name,action,request):
 before=int(g.AccessCount)
 try:action()
 except Exception:pass
 else:raise Exception(name+' accepted')
 check(name,g.AccessCount==before+1 and g.ReadDoubleWord(0x20004)==request)
try:
 for module in range(4):
  g.Reset();mask=0x200<<module;p=g.UartPowers[module]
  g.WriteDoubleWord(0x20004,mask)
  check('uart-'+str(module)+'-request',p.RequestWord==mask and p.StatusWord==0 and p.Requests==1)
  check('uart-'+str(module)+'-status',g.ReadDoubleWord(0x20008)&mask==mask and p.StatusWord==mask and p.Phase=='on')
  blocked('uart-'+str(module)+'-busy-off',lambda:g.WriteDoubleWord(0x20004,0),mask)
  g.WriteDoubleWord(int(g.Uarts[module].BaseAddress)-0x40001000+0x30,0)
  check('uart-'+str(module)+'-quiescent',g.Uarts[module].Quiescent)
  g.WriteDoubleWord(0x20004,0)
  check('uart-'+str(module)+'-off',g.ReadDoubleWord(0x20008)==0 and p.Phase=='powered-off' and p.PowerCycles==1)
  g.WriteDoubleWord(0x20004,mask)
  check('uart-'+str(module)+'-reenable',g.ReadDoubleWord(0x20008)&mask==mask and p.StatusWord==mask and p.Requests==2)
  check('uart-'+str(module)+'-buck-not-forced',g.BuckResponsePhase=='off' and not g.BuckStart.EnableRequested)
 g.Reset()
 blocked('two-uart-atomic',lambda:g.WriteDoubleWord(0x20004,0x600),0)
 blocked('unknown-bit-atomic',lambda:g.WriteDoubleWord(0x20004,0x80000400),0)
 blocked('partial-write',lambda:g.WriteWord(0x20004,0x400),0)
 blocked('crypto-still-needs-otp',lambda:g.WriteDoubleWord(0x20004,0x200000),0)
 g.WriteDoubleWord(0x20004,0x400);g.ReadDoubleWord(0x20008)
 g.WriteDoubleWord(0x20004,0xc00);g.ReadDoubleWord(0x20008)
 g.WriteDoubleWord(int(g.Uarts[1].BaseAddress)-0x40001000+0x30,0)
 g.WriteDoubleWord(0x20004,0x800)
 check('shared-held-gate',g.UartPowers[1].Phase=='gated' and g.UartPowers[2].Phase=='on')
 g.WriteDoubleWord(0x20004,0xc00)
 check('shared-held-reenable',g.UartPowers[1].Phase=='on' and g.ReadDoubleWord(0x20008)&0xc00==0xc00)
 check('other-domains-preserved',g.AdcPower.RequestWord==0 and g.GpuPower.RequestWord==0 and all(p.Value.RequestWord==0 for p in g.IomPowers))
 result=dict(passed=True,profile=PROFILE,checks=checks)
except Exception as error:
 result=dict(passed=False,profile=PROFILE,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_ADC_COLD '+json.dumps(result))
'''


UART_CLOCK_DRIVER = '''import json
from System import Console
g=monitor.Machine['sysbus.guard']
checks=[]
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
def blocked(name,action):
 before=int(g.AccessCount);word=int(g.HalStorage.Registers[0x400201b0].Value)
 try:action()
 except Exception:pass
 else:raise Exception(name+' accepted')
 check(name,g.AccessCount==before+1 and g.HalStorage.Registers[0x400201b0].Value==word)
try:
 for module in range(4):
  g.Reset();mask=0x200<<module;u=g.Uarts[module]
  check('ldo-initial-'+str(module),g.MemLdo.StepsCompleted==0)
  blocked('unpowered-'+str(module),lambda:g.WriteDoubleWord(0x1f1b0,0))
  g.WriteDoubleWord(0x20004,mask);g.ReadDoubleWord(0x20008)
  blocked('wrong-control-'+str(module),lambda:g.WriteDoubleWord(0x1f1b0,0))
  g.WriteDoubleWord(int(u.BaseAddress)-0x40001000+0x30,8)
  word=int(g.HalStorage.Registers[0x400201b0].Value)
  blocked('unrelated-field-'+str(module),lambda:g.WriteDoubleWord(0x1f1b0,word^0x10000))
  g.WriteDoubleWord(0x1f1b0,word&~(0x400000<<module))
  check('cold-clock-clear-'+str(module),u.ClockSpareClears==1 and g.MemLdo.StepsCompleted==0 and g.BuckResponsePhase=='off')
  blocked('epoch-repeat-'+str(module),lambda:g.WriteDoubleWord(0x1f1b0,word&~(0x400000<<module)))
 g.Reset()
 for module in (1,2):
  g.WriteDoubleWord(0x20004,0x400 if module==1 else 0xc00);g.ReadDoubleWord(0x20008)
  g.WriteDoubleWord(int(g.Uarts[module].BaseAddress)-0x40001000+0x30,8)
 blocked('ambiguous-owner',lambda:g.WriteDoubleWord(0x1f1b0,0))
 check('ambiguous-atomic',g.Uarts[1].ClockSpareClears==0 and g.Uarts[2].ClockSpareClears==0)
 result=dict(passed=True,profile=PROFILE,checks=checks)
except Exception as error:
 result=dict(passed=False,profile=PROFILE,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_ADC_COLD '+json.dumps(result))
'''


IOM_DRIVER = '''import json
from System import Console
g=monitor.Machine['sysbus.guard']
checks=[]
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
def blocked(name,value):
 before=int(g.AccessCount)
 try:g.WriteDoubleWord(0x20004,value)
 except Exception:pass
 else:raise Exception(name+' accepted')
 check(name,g.AccessCount==before+1 and all(p.Value.RequestWord==0 for p in g.IomPowers))
try:
 for module in (2,4,5,6,7):
  g.Reset();p=g.IomPowers[module];mask=int(p.Mask)
  g.WriteDoubleWord(0x20004,mask)
  check('iom-'+str(module)+'-requested',p.RequestWord==mask and p.StatusWord==0 and p.Requests==1)
  check('iom-'+str(module)+'-readback',g.ReadDoubleWord(0x20004)==mask)
  check('iom-'+str(module)+'-status',g.ReadDoubleWord(0x20008)==mask and p.Phase=='on' and p.Responses==1)
  check('iom-'+str(module)+'-buck-unmodified',g.BuckResponsePhase=='off' and not g.BuckStart.EnableRequested)
  bus=monitor.Machine.SystemBus
  bus.WriteDoubleWord(0x40050000+module*0x1000+0x11c,0x10)
  before=int(g.AccessCount)
  try:g.WriteDoubleWord(0x20004,0)
  except Exception:pass
  else:raise Exception('busy IOM off accepted')
  check('iom-'+str(module)+'-busy-off',g.AccessCount==before+1 and p.Phase=='on' and p.RequestWord==mask)
  bus.WriteDoubleWord(0x40050000+module*0x1000+0x11c,0)
  g.WriteDoubleWord(0x20004,0)
  check('iom-'+str(module)+'-off',g.ReadDoubleWord(0x20008)==0 and p.Phase=='powered-off' and p.PowerCycles==1)
  g.WriteDoubleWord(0x20004,mask)
  check('iom-'+str(module)+'-reenable',g.ReadDoubleWord(0x20008)==mask and p.Requests==2)
  g.Reset();p=g.IomPowers[module];g.WriteDoubleWord(0x20004,mask);g.WriteDoubleWord(0x20004,0)
  check('iom-'+str(module)+'-cancel',p.Phase=='cancelled' and p.StatusWord==0 and p.RequestWord==0)
 g.Reset();blocked('two-iom-atomic',0x28)
 blocked('iom-and-uart-atomic',0x408)
 blocked('unknown-bit-atomic',0x80000008)
 blocked('crypto-otp-gate',0x200000)
 check('other-domains-preserved',g.AdcPower.RequestWord==0 and g.GpuPower.RequestWord==0 and all(p.Value.RequestWord==0 for p in g.UartPowers))
 result=dict(passed=True,profile=PROFILE,checks=checks)
except Exception as error:
 result=dict(passed=False,profile=PROFILE,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_ADC_COLD '+json.dumps(result))
'''


CLOCK_GATES_DRIVER = '''import json
from System import Console
g=monitor.Machine['sysbus.guard']
checks=[]
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
def blocked(name,value):
 before=int(g.AccessCount);word=int(g.McuClock.MiscWord)
 try:g.WriteDoubleWord(0x3044,value)
 except Exception:pass
 else:raise Exception(name+' accepted')
 check(name,g.AccessCount==before+1 and g.McuClock.MiscWord==word)
try:
 for force in (1,0,32,33):
  g.Reset();g.WriteDoubleWord(0x3044,force)
  status=int(g.ReadDoubleWord(0x3030));writes=int(g.McuClock.ForceWrites)
  g.WriteDoubleWord(0x3044,0xfbbfc0|force)
  check('gate-word-'+str(force),g.McuClock.MiscWord==0xfbbfc0|force)
  check('force-preserved-'+str(force),g.ReadDoubleWord(0x3030)==status and g.McuClock.ForceWrites==writes)
  check('gate-counter-'+str(force),g.McuClock.GateWrites==1)
  check('buck-preserved-'+str(force),g.BuckResponsePhase=='off' and not g.BuckStart.EnableRequested)
  g.WriteDoubleWord(0x3044,0xfbbfc0|(force^1))
  check('later-force-'+str(force),g.McuClock.MiscWord==0xfbbfc0|(force^1) and g.McuClock.ForceWrites==writes+1 and g.McuClock.GateWrites==1)
 g.Reset()
 blocked('combined-force-and-gate',0xfbbfc1)
 blocked('partial-gate-pattern',0xfbbf80)
 blocked('unsupported-trunk-gate',0x1000000)
 blocked('unsupported-burst-off',2)
 blocked('reserved-bit',4)
 check('rejected-no-gate-effects',g.McuClock.GateWrites==0 and g.McuClock.ForceWrites==0)
 result=dict(passed=True,profile=PROFILE,checks=checks)
except Exception as error:
 result=dict(passed=False,profile=PROFILE,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_ADC_COLD '+json.dumps(result))
'''


HFADJ_DRIVER = '''import json
from System import Console
g=monitor.Machine['sysbus.guard']
checks=[]
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
def blocked(name,action):
 before=int(g.AccessCount);writes=int(g.HalStorage.Registers[0x40004020].Writes)
 try:action()
 except Exception:pass
 else:raise Exception(name+' accepted')
 check(name,g.AccessCount==before+1 and g.ReadDoubleWord(0x3020)==0x25b800 and g.HalStorage.Registers[0x40004020].Writes==writes)
try:
 g.Reset()
 check('dfp-reset-word',g.ReadDoubleWord(0x3020)==0x25b800)
 for n in range(3):
  value=int(g.ReadDoubleWord(0x3020));g.WriteDoubleWord(0x3020,value&~1)
  check('disable-preserves-fields-'+str(n),g.ReadDoubleWord(0x3020)==0x25b800 and g.HalStorage.Registers[0x40004020].Writes==n+1)
 check('no-calibration-status',g.ReadDoubleWord(0x3030)&0x8000000==0)
 for label,value in [('enable',0x25b801),('target-change',0x25b900),('gain-change',0x45b800),('reserved',0x25b810),('clear-all',0)]:
  blocked(label,lambda:g.WriteDoubleWord(0x3020,value))
 blocked('byte-write',lambda:g.WriteByte(0x3020,0))
 blocked('halfword-write',lambda:g.WriteWord(0x3020,0xb800))
 check('buck-unchanged',g.BuckResponsePhase=='off' and not g.BuckStart.EnableRequested)
 g.Reset()
 check('reset-restores-metadata',g.ReadDoubleWord(0x3020)==0x25b800 and g.HalStorage.Registers[0x40004020].Writes==0)
 result=dict(passed=True,profile=PROFILE,checks=checks)
except Exception as error:
 result=dict(passed=False,profile=PROFILE,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_ADC_COLD '+json.dumps(result))
'''


BOOT_MARKER_DRIVER = '''import json,clr
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallOtaMarkerRead').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallOtaMarkerRead
tail=monitor.Machine['sysbus.guard_mram_tail'];p=tail.OtaMarker
checks=[]
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
def rejected(name,action):
 try:action()
 except Exception:checks.append(name);return
 raise Exception(name+' accepted')
try:
 check('boot-cleared-read',p.TrySample(0x42e582,0x7fe000,0,0x7fe000)==(True,0xffffffff))
 check('boot-counter-isolated',p.Reads==1 and p.BootReads==1 and p.StartupReads==0 and p.SetterReads==0)
 for label,pc,r0,address in [('wrong-pc',0x42e580,0x7fe000,0x7fe000),('wrong-r0',0x42e582,0,0x7fe000),('wrong-address',0x42e582,0x7fe004,0x7fe004)]:
  check(label,not p.TrySample(pc,r0,0,address)[0] and p.Reads==1)
 check('main-startup-preserved',p.TrySample(p.StartupPc,0x7fe000,0,0x7fe000)==(True,0xffffffff) and p.StartupReads==1)
 for offset in (0x12,0x3e,0x56):
  check('setter-preserved-'+str(offset),p.TrySample(p.SetterEntry+offset,0,0x7fe000,0x7fe000)==(True,0xffffffff))
 unknown=BlackwallOtaMarkerRead('unknown',p.StartupPc,p.SetterEntry,0x42e582)
 check('unknown-denied',not unknown.TrySample(0x42e582,0x7fe000,0,0x7fe000)[0])
 pending=BlackwallOtaMarkerRead('pending',p.StartupPc,p.SetterEntry,0x42e582)
 check('pending-not-cleared',pending.TrySample(0x42e582,0x7fe000,0,0x7fe000)==(True,0x55555555))
 legacy=BlackwallOtaMarkerRead('cleared',p.StartupPc,p.SetterEntry)
 check('default-boot-unsupported',not legacy.TrySample(0x42e582,0x7fe000,0,0x7fe000)[0])
 for pc in (0x400000,0x438000,0x42e583):
  rejected('invalid-boot-pc-'+str(pc),lambda:BlackwallOtaMarkerRead('cleared',p.StartupPc,p.SetterEntry,pc))
 rejected('marker-write',lambda:tail.WriteDoubleWord(0x6000,0))
 rejected('marker-byte',lambda:tail.ReadByte(0x6000))
 rejected('marker-halfword',lambda:tail.ReadWord(0x6000))
 rejected('marker-wide',lambda:tail.ReadQuadWord(0x6000))
 p.Reset();check('reset-counters',p.Reads==p.BootReads==p.StartupReads==p.SetterReads==0)
 result=dict(passed=True,profile=PROFILE,checks=checks)
except Exception as error:
 result=dict(passed=False,profile=PROFILE,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_ADC_COLD '+json.dumps(result))
'''


MCU_LP_DRIVER = '''import json,clr
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallMcuClock').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMcuClock,BlackwallHalStorage
checks=[]
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
try:
 c=BlackwallMcuClock(BlackwallHalStorage(),'hp',0,True)
 check('original-hp-to-lp-request',c.TryWrite(0x40021000,0x15,True))
 check('lp-ack-status',c.ModeWord==13 and c.Phase=='acked' and c.Transitions==1 and c.ModeWrites==1)
 for profile,expected,phase in [(1,13,'acked'),(2,17,'pending'),(3,21,'denied')]:
  c=BlackwallMcuClock(BlackwallHalStorage(),'hp',profile,True)
  check('lp-profile-request-'+str(profile),c.TryWrite(0x40021000,21,True))
  check('lp-profile-response-'+str(profile),c.ModeWord==expected and c.Phase==phase)
 c=BlackwallMcuClock(BlackwallHalStorage(),'lp',0,True)
 check('lp-no-buck-required',c.TryWrite(0x40021000,13,False) and c.ModeWord==13)
 for value in (12,15,2,0x8000000e):
  c=BlackwallMcuClock(BlackwallHalStorage(),'lp',0,True)
  check('invalid-or-readonly-'+str(value),not c.TryWrite(0x40021000,value,True) and c.ModeWord==13 and c.ModeWrites==0)
 c=BlackwallMcuClock(BlackwallHalStorage(),'lp',0,True)
 c.TryWrite(0x40004044,32,False)
 check('hp-still-requires-buck',not c.TryWrite(0x40021000,14,False) and c.ModeWord==13)
 check('hp-preserved',c.TryWrite(0x40021000,14,True) and c.ModeWord==22)
 check('round-trip-lp',c.TryWrite(0x40021000,21,True) and c.ModeWord==13 and c.Transitions==2)
 c=BlackwallMcuClock(BlackwallHalStorage(),'lp',1,True);c.TryWrite(0x40004044,32,False)
 check('hp-unready-denied',not c.TryWrite(0x40021000,14,True) and c.ModeWord==13)
 result=dict(passed=True,profile=PROFILE,checks=checks)
except Exception as error:
 result=dict(passed=False,profile=PROFILE,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_ADC_COLD '+json.dumps(result))
'''


WARM_VRCTRL_DRIVER = '''import json
from System import Console
g=monitor.Machine['sysbus.guard'];checks=[]
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
def state():return (int(g.VrctrlValue),int(g.VrctrlWrites),int(g.BuckOverrideStep),str(g.BuckResponsePhase),int(g.BuckResponseTransitions),bool(g.BuckStart.EnableRequested))
def blocked(name,action):
 before=state();accesses=int(g.AccessCount)
 try:action()
 except Exception:pass
 else:raise Exception(name+' accepted')
 check(name,state()==before and g.AccessCount==accesses+1)
try:
 g.Reset();g.WriteDoubleWord(0x1f060,0xe000)
 for n,value in enumerate((0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef)):
  g.WriteDoubleWord(0x1f060,value)
  check('cold-step-'+str(n+1),g.VrctrlValue==value and g.BuckOverrideStep==n+1)
 before=state()
 for mask in (0x8000,0x4000,0x2000):
  word=int(g.ReadDoubleWord(0x1f060));g.WriteDoubleWord(0x1f060,word|mask)
  check('completed-same-value-'+str(mask),g.VrctrlValue==0xfe1ef and g.BuckOverrideStep==10 and g.BuckOverrideComplete)
 check('no-new-power-transition',state()[3:]==before[3:] and g.VrctrlWrites==before[1]+3)
 for value in (0xfe1ee,0xe000,0x10fe1ef):blocked('changed-value-'+str(value),lambda:g.WriteDoubleWord(0x1f060,value))
 blocked('partial-width',lambda:g.WriteWord(0x1f060,0xe1ef))
 g.Reset();g.WriteDoubleWord(0x1f060,0xe000);g.WriteDoubleWord(0x1f060,0x2e000)
 blocked('incomplete-reentry-still-rejected',lambda:g.WriteDoubleWord(0x1f060,0x2e000))
 result=dict(passed=True,profile=PROFILE,checks=checks)
except Exception as error:result=dict(passed=False,profile=PROFILE,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_ADC_COLD '+json.dumps(result))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--board', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--contract', choices=('adc', 'clock', 'clock-gates', 'hfadj', 'uart', 'uart-clock', 'iom', 'boot-marker', 'mcu-lp', 'warm-vrctrl'), default='adc')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(mode=0o700)
    shutil.copy2(args.model, out / 'strict.cs')
    board = args.board.read_text()
    field, initial, profiles, driver = ('adcPowerResponse', 1, (1, 0), DRIVER) if args.contract == 'adc' else ('mcuClockResponse', 0, (0,), CLOCK_DRIVER)
    if args.contract == 'uart':
        driver = UART_DRIVER
    elif args.contract == 'uart-clock':
        driver = UART_CLOCK_DRIVER
    elif args.contract == 'iom':
        driver = IOM_DRIVER
    elif args.contract == 'clock-gates':
        driver = CLOCK_GATES_DRIVER
    elif args.contract == 'hfadj':
        driver = HFADJ_DRIVER
    elif args.contract == 'boot-marker':
        driver = BOOT_MARKER_DRIVER
    elif args.contract == 'mcu-lp':
        driver = MCU_LP_DRIVER
    elif args.contract == 'warm-vrctrl':
        driver = WARM_VRCTRL_DRIVER
    marker = f'    {field}: {initial}\n'
    if board.count(marker) != 1:
        raise ValueError('Expected one explicit power response profile')
    script = 'include @/work/strict.cs\n'
    for profile in profiles:
        (out / f'board-{profile}.repl').write_text(board.replace(marker, f'    {field}: {profile}\n', 1))
        (out / f'test-{profile}.py').write_text(f'PROFILE={profile}\n' + driver)
        script += f'mach create "adc-cold-{profile}"\nmachine LoadPlatformDescription @/work/board-{profile}.repl\ninclude @/work/test-{profile}.py\n'
    (out / 'probe.resc').write_text(script + 'quit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1',
                   '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                   '--mount', f'type=bind,source={out},target=/work,readonly', args.image,
                   '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'],
                  out, 'renode', timeout=180, stream=True)
    rows = [json.loads(line.split('BLACKWALL_ADC_COLD ', 1)[1]) for line in log.splitlines()
            if line.startswith('BLACKWALL_ADC_COLD ')]
    passed = len(rows) == len(profiles) and all(row['passed'] for row in rows)
    report = dict(passed=passed, contract=args.contract, rows=rows, image_id=args.image, hardware_accessed=False,
                  scope='Isolated C# shared-register transaction tests; not original ARM or analog validation',
                  model_sha256=hashlib.sha256((out / 'strict.cs').read_bytes()).hexdigest(),
                  board_source_sha256=hashlib.sha256(args.board.read_bytes()).hexdigest())
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=passed, profiles=len(rows), checks=sum(len(r['checks']) for r in rows))))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
