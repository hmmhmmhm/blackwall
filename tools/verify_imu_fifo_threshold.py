"""Verify the opt-in FIFO threshold event and real IOM status transfer contract."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from run_renode_m55_probe import execute
from native_replay import IMAGE
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('simulator',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
S=args.simulator.resolve();out=args.output.resolve()
if out.exists() or not out.is_relative_to(S) or out.is_relative_to(ROOT):parser.error('New private simulator output required')
out.mkdir(mode=0o700)
(out/'runner-source.py').write_bytes(Path(__file__).read_bytes())
model=(S/'mspi0-rx-main-01/stock24/strict.cs').read_text()
for name in ['renode-imu-raw-fifo.cs','renode-imu-fifo-threshold.cs','renode-imu-fifo-transport.cs']:
 p=ROOT/'tools'/name
 if p.exists():model+='\n'+p.read_text()
model+='''
namespace Antmicro.Renode.Peripherals.Miscellaneous {
using System;using Antmicro.Renode.Peripherals.I2C;
public sealed class BlackwallThresholdTestPeer:II2CPeripheral {
public int Pointer=-1;public int Reads;public int Finishes;
public void Write(byte[] data){if(data==null || data.Length!=1 || data[0]!=0x19)throw new ArgumentException("Fixture register");Pointer=data[0];}
public byte[] Read(int count=1){if(Pointer!=0x19 || (count!=1 && count!=2))throw new ArgumentException("Fixture read");Reads++;return count==1 ? new byte[]{0x80}:new byte[]{0x40,0x20};}
public void FinishTransmission(){Finishes++;}
public void Reset(){Pointer=-1;Reads=Finishes=0;}
}}
'''
(out/'model.cs').write_text(model)
(out/'board.repl').write_text('''power: Miscellaneous.BlackwallPeripheralPower
    mask: 32
    profile: 1
iom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40054000
    power: power
    module: 4
raw: Miscellaneous.BlackwallImuRawFifo @ none
    enabled: true
    capacityPackets: 4
threshold: Miscellaneous.BlackwallImuFifoThreshold @ none
    rawFifo: raw
    watermarkPackets: 2
    interruptEnabled: true
peer: Miscellaneous.BlackwallThresholdTestPeer @ none
transport: Miscellaneous.BlackwallImuFifoTransport @ iom 0x69
    owner: iom
    startupPeer: peer
    rawFifo: raw
    threshold: threshold
''')
SCRIPT='''import clr,json
from System import Array,Byte,Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallImuFifoThreshold').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuFifoThreshold,BlackwallImuRawFifo
m=monitor.Machine;b=m.SystemBus;i=m['sysbus.iom'];t=m['sysbus.iom.transport'];q=t.RawFifo;h=t.Threshold;p=t.StartupPeer;checks=[]
def check(n,v):
 if not v:raise Exception(n)
 checks.append(n)
def frame(seed):return Array[Byte]([0x68]+[(seed+k)&255 for k in range(15)])
def w(o,v):b.WriteDoubleWord(0x40054000+o,v)
def r(o):return int(b.ReadDoubleWord(0x40054000+o))
def status():
 w(0x208,0x7fff);w(0x10c,0x19);w(0x120,0x101);w(0x208,0x7fff);w(0x120,0x202)
 return r(0x108)&0xffff
check('power',i.Power.TryWrite(32,True) and i.Power.ReadStatus()==32)
for o,v in [(0x118,1),(0x11c,0x10),(0x2c0,0x23040),(0x2c4,0x69),(0x200,1)]:w(o,v)
w(0x208,0x7fff);w(0x10c,0x19);w(0x120,0x101);w(0x208,0x7fff);w(0x120,0x102)
check('initial-reset-done-byte-delegated',r(0x108)&255==0x80 and not h.Pending and not h.IRQ.IsSet)
check('initial-clear',not h.Pending and not h.IRQ.IsSet and h.Snapshot()==0)
check('preserve-other-status',status()==0x2040 and p.Reads==2 and q.PacketCount==0)
check('one-below',q.TryEnqueueFrame(frame(1)) and not h.Pending)
check('below-status',status()==0x2040)
check('threshold-event',q.TryEnqueueFrame(frame(20)) and h.Pending and h.IRQ.IsSet and h.EventsRaised==1)
check('latched-status',status()==0x2042 and not h.Pending and not h.IRQ.IsSet and q.PacketCount==2)
check('read-does-not-reassert',status()==0x2040 and q.PacketCount==2)
check('greater-reasserts',q.TryEnqueueFrame(frame(40)) and h.Pending and h.EventsRaised==2)
epoch=h.Snapshot();check('capture-nonzero',epoch!=0)
check('next-event',q.TryEnqueueFrame(frame(60)) and h.EventsRaised==3)
h.Acknowledge(epoch);check('stale-clear-preserves-new-event',h.Pending and h.IRQ.IsSet)
epoch=h.Snapshot();h.Acknowledge(epoch);check('matching-clear',not h.Pending and not h.IRQ.IsSet)
check('full-reject-not-event',not q.TryEnqueueFrame(frame(70)) and h.EventsRaised==3)
q.Reset();check('device-reset-clears',not h.Pending and not h.IRQ.IsSet and h.EventsRaised==h.StatusClears==0)
check('fresh-event-after-reset',q.TryEnqueueFrame(frame(1)) and q.TryEnqueueFrame(frame(2)) and h.Pending)
h.Acknowledge(epoch);check('pre-reset-clear-cannot-clear-new-event',h.Pending)
check('flush-queue',q.TryFlush() and q.PacketCount==0 and h.Pending)
check('event-survives-queue-drain',status()==0x2042 and not h.Pending)
for enabled,wm in [(False,2),(True,0)]:
 a=BlackwallImuRawFifo(True,False,4);z=BlackwallImuFifoThreshold(a,wm,enabled,True)
 for n in range(3):a.TryEnqueueFrame(frame(n))
 check('disabled-no-events',not z.Pending and not z.IRQ.IsSet and z.EventsRaised==0)
a=BlackwallImuRawFifo(True,False,4);z=BlackwallImuFifoThreshold(a,2,True,False)
for n in range(2):a.TryEnqueueFrame(frame(n))
check('equal-threshold-event',z.Pending);z.Acknowledge(z.Snapshot());a.TryEnqueueFrame(frame(3));check('equal-above-not-event',not z.Pending and z.EventsRaised==1)

q.Reset()
for n in range(2):q.TryEnqueueFrame(frame(n))
for size,continued in [(1,False),(2,True)]:
 w(0x208,0x7fff);w(0x10c,0x19);w(0x120,0x101);reads=p.Reads
 try:w(0x120,(size<<8)|2|(0x80 if continued else 0))
 except Exception as error:
  if 'Blackwall unsupported IOM' not in str(error):raise
 else:raise Exception('invalid status transfer accepted')
 check('invalid-status-preserves-event-and-peer',h.Pending and h.IRQ.IsSet and p.Reads==reads)
 i.ResetThroughInterface()
 for offset,value in [(0x118,1),(0x11c,0x10),(0x2c0,0x23040),(0x2c4,0x69),(0x200,1)]:w(offset,value)
check('valid-status-after-rejections',status()==0x2042 and not h.Pending)
Console.WriteLine('BLACKWALL_THRESHOLD '+json.dumps(dict(passed=True,count=len(checks),checks=checks,physical_gpio_connected=False,original_arm_executed=False)))
'''
(out/'test.py').write_text(SCRIPT);(out/'probe.resc').write_text('include @/work/model.cs\nmach create "threshold"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode',timeout=90)
rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_THRESHOLD ')]
if len(rows)!=1:raise ValueError('Threshold suite incomplete; inspect preserved log')
(out/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
