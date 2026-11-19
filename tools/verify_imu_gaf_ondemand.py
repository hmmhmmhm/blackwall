"""Timed GAF control capability tests; no firmware or calculated-output oracle."""
import argparse,json
from pathlib import Path
from runtime_event_models import compose,integrate_gaf
from native_replay import IMAGE
from run_renode_m55_probe import execute

DRIVER='''import clr,json
from System import Array,Byte,Console
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallImuGafOnDemand').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuEdmpQuiesce,BlackwallImuEdmpService,BlackwallImuPowerSave,BlackwallImuGafParameters,BlackwallImuGafOnDemand
m=monitor.Machine;checks=[]
def check(name,value):
 if not value:raise Exception(name)
 checks.append(name)
def advance(us):EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(us))
def put(owner,address,value):
 if not owner.TryWrite(address,Array[Byte]([value])):raise Exception('bootstrap-write-'+hex(address))
def ready():
 bank=BlackwallImuEdmpQuiesce(m,'f28f',100,True)
 owner=BlackwallImuEdmpService(m,bank,'a5b6c7d8e9',0xa5,100,True)
 for k,v in enumerate([0,0x40,4,0x40,8,0x40,2]):put(owner,0xa24f+k,v)
 owner.Read(0xa2a7);put(owner,0xa2a7,0xa7);owner.Read(0x29);owner.Read(0x2a)
 for address,data in [(0x118,[1,0,0,0]),(0x11c,[0,0]),(0x120,[0,0x18]),(0x11e,[0])]:
  for k,v in enumerate(data):put(owner,address+k,v)
 owner.Read(0xa273);put(owner,0xa273,0xd8);owner.Read(0x2a);put(owner,0x2a,0xcf);owner.Read(0x73);put(owner,0x73,0xe9);advance(101)
 put(owner,0x29,0xf2);put(owner,0x2a,0x8f)
 for address in [0xa271,0xa272,0xa273]:put(owner,address,0x3f)
 owner.Read(0xa272);put(owner,0xa272,0x1f);put(owner,0x29,0);put(owner,0x2a,0x42);owner.Read(0x73);put(owner,0x73,0xe9);advance(101)
 put(owner,0x29,0xf2);put(owner,0x2a,0x8f)
 ps=BlackwallImuPowerSave(owner,'78563412');ps.BeginRead(0x40)
 for _ in range(4):ps.ReadNext()
 ps.ReadControl();v=ps.ReadControl();check('power-save-prerequisite',ps.TryWriteControl(v&~4))
 for k,v in enumerate([0x78,0x56,0x34,0x12]):check('power-save-time',ps.TryWriteTime(0x40+k,v))
 config=BlackwallImuGafParameters(owner,ps,fixture,True,133)
 return owner,config
def configure(config):
 for address,length in fields:
  if not config.BeginRead(address):raise Exception('getter')
  for _ in range(length):config.ReadNext()
 check('clock-prerequisite',config.BeginClockRead() and config.ReadNext()==133)
 for address,value in writes:
  if not config.TryWrite(address,Array[Byte]([value])):raise Exception('configuration')
for request in (2,4):
 for masked in (0x1f,0x3f):
  owner,config=ready();c=BlackwallImuGafOnDemand(m,owner,config,100)
  before=[owner.RamByte(k) for k in range(8192)]
  check('early-request-rejected',not c.TryRequest(4,Array[Byte]([request])) and not c.Active and before==[owner.RamByte(k) for k in range(8192)])
  configure(config);owner.Read(0xa272);put(owner,0xa272,masked)
  for invalid in (0,1,3,255):check('unknown-request-rejected',not c.TryRequest(4,Array[Byte]([invalid])) and not c.Active)
  before=[owner.RamByte(k) for k in range(8192)]
  check('request-recorded',c.TryRequest(4,Array[Byte]([request])) and c.RequestId==request and c.Requests==1 and c.Phase=='requested' and owner.RamByte(4)==request)
  expected=list(before);expected[4]=request
  check('request-neighbors-preserved',expected==[owner.RamByte(k) for k in range(8192)])
  check('no-overlapping-request',not c.TryRequest(4,Array[Byte]([request])))
  check('no-early-idle',not c.CanSelectRead(0xa297))
  for address,mask in [(0xa272,0x20),(0x2a,0x40),(0x73,0x20)]:
   check('write-needs-read',not c.TryWriteRegister(address,0))
   ok,value=c.TryReadRegister(address);check('ordered-control-read',ok)
   wanted=value&~mask if address==0xa272 else value|mask
   check('unrelated-bits-rejected',not c.TryWriteRegister(address,wanted^0x80))
   check('rmw-exact-preservation',c.TryWriteRegister(address,wanted))
  check('trigger-pending-not-completed',c.Pending and c.Triggers==1 and c.Writes==3 and c.CompletedCalculations==0 and not c.CalculationSupported)
  check('unavailable-derived-memory',not c.CanSelectRead(0x280))
  ok,value=c.TryReadRegister(0xa297);check('busy-byte',ok and value==0 and c.BusyReads==1)
  advance(99);check('window-not-early',not c.ObservationEnded and c.Pending)
  advance(1)
  Console.WriteLine('BLACKWALL_GAF_CONTROL_TIMING '+json.dumps(dict(triggered=int(c.TriggeredAt),deadline=int(c.DeadlineAt),observed=int(c.EndedObservedAt),elapsed=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),phase=str(c.Phase),pending=bool(c.Pending))))
  check('window-1us-step-and-unsupported',c.ObservationEnded and c.Pending and c.DeadlineAt-c.TriggeredAt==100000 and c.EndedObservedAt==c.DeadlineAt and c.Phase=='result-unsupported')
  ok,value=c.TryReadRegister(0xa297);check('no-fabricated-idle',not ok and c.LastReject=='derived-result-unavailable' and c.CompletedCalculations==0)
  check('no-calculated-ram-writes',expected==[owner.RamByte(k) for k in range(8192)] and owner.Completions==2)
  c.Reset();advance(200);check('reset-cancels-state',not c.Active and not c.ObservationEnded and c.Requests==c.Triggers==0)
owner,config=ready();configure(config);c=BlackwallImuGafOnDemand(m,owner,config,100)
c.TryRequest(4,Array[Byte]([2]))
for address,mask in [(0xa272,0x20),(0x2a,0x40),(0x73,0x20)]:
 ok,value=c.TryReadRegister(address);c.TryWriteRegister(address,value&~mask if address==0xa272 else value|mask)
advance(50);c.Reset();advance(100);check('reset-cancels-live-timer',not c.ObservationEnded and c.EndedObservedAt==0)
owner,config=ready();configure(config);c=BlackwallImuGafOnDemand(m,owner,config,100)
c.TryRequest(4,Array[Byte]([2]))
for address,mask in [(0xa272,0x20),(0x2a,0x40),(0x73,0x20)]:
 ok,value=c.TryReadRegister(address);c.TryWriteRegister(address,value&~mask if address==0xa272 else value|mask)
advance(101)
Console.WriteLine('BLACKWALL_GAF_CONTROL_COARSE '+json.dumps(dict(triggered=int(c.TriggeredAt),deadline=int(c.DeadlineAt),observed=int(c.EndedObservedAt),elapsed=int(m.ElapsedVirtualTime.TimeElapsed.Ticks))))
check('coarse-observation-bounded',c.ObservationEnded and c.DeadlineAt-c.TriggeredAt==100000 and 0<=c.EndedObservedAt-c.DeadlineAt<=1000)
for bad in (0,1000001):
 try:BlackwallImuGafOnDemand(m,owner,config,bad)
 except Exception:checks.append('invalid-window-'+str(bad))
 else:raise Exception('invalid window accepted')
Console.WriteLine('BLACKWALL_GAF_CONTROL_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_firmware_executed=False,calculation_supported=False)))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    assert a.output.resolve().is_relative_to(a.simulator.resolve()) and not a.output.exists()
    a.output.mkdir();base=(a.simulator/'tpl-time-native-01/stock24/strict.cs').read_text();model,profile=integrate_gaf(a.simulator,compose(a.simulator,base),True)
    (a.output/'strict.cs').write_text(model);(a.output/'board.repl').write_text('power: Miscellaneous.BlackwallPeripheralPower\n    mask: 32\n    profile: 1\n    offProfile: 0\niom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40054000\n    power: power\n    module: 4\n')
    fields=json.loads((Path(__file__).resolve().parents[1]/'docs/data/imu-gaf-default-profile.json').read_text())['fields']
    old=json.loads((a.simulator/'runtime-gaf-delay-1000-native-01/stock24/exports/disconnect.json').read_text())['imu_gaf']['history']
    writes=[(int(x.split(':')[0],16),int(x.split(':')[1],16)) for x in old.split('|')];assert len(writes)==225
    code='fixture='+repr(profile['parameters_hex'])+'\nfields='+repr([(f['address'],f['length']) for f in fields])+'\nwrites='+repr(writes)+'\n'+DRIVER
    (a.output/'test.py').write_text(code);(a.output/'probe.resc').write_text('include @/work/strict.cs\nmach create "gaf-control-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=90)
    rows=[json.loads(x.split('BLACKWALL_GAF_CONTROL_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_GAF_CONTROL_UNIT ')];assert len(rows)==1,log[-2000:]
    (a.output/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))


if __name__=='__main__':main()
