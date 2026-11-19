"""Verify raw32 FIFO configuration, shared fields and timed indirect access."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from native_replay import IMAGE
from run_renode_m55_probe import execute
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('simulator',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
S=args.simulator.resolve();out=args.output.resolve()
if out.exists() or not out.is_relative_to(S) or out.is_relative_to(ROOT):parser.error('New private simulator output required')
out.mkdir(mode=0o700)
(out/'runner-source.py').write_bytes(Path(__file__).read_bytes())
model=(S/'mspi0-rx-main-01/stock24/strict.cs').read_text()
for n in ['renode-imu-identity.cs','renode-imu-raw-fifo.cs','renode-imu-fifo-threshold.cs','renode-imu-fifo-transport.cs','renode-imu-fifo-configuration.cs']:
 p=ROOT/'tools'/n
 if p.exists():model+='\n'+p.read_text()
(out/'model.cs').write_text(model)
(out/'board.repl').write_text('''power: Miscellaneous.BlackwallPeripheralPower
    mask: 32
    profile: 1
iom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40054000
    power: power
    module: 4
peer: Miscellaneous.BlackwallImuIdentity @ none
    owner: iom
    profile: "icm45608-reset-lifecycle"
    identityByte: 129
    initialInterface: 165
    initialDrive: 90
    sregControl: 2
    fsyncConfig: 0
    int1Config2: 166
    edmpConfigurationHex: "ffff"
    powerConfigurationHex: "af2500000000"
    auxiliaryConfigurationHex: "a5b6d7"
    initialIregReady: true
raw: Miscellaneous.BlackwallImuRawFifo @ none
    enabled: true
    frameBytes: 32
    capacityPackets: 64
threshold: Miscellaneous.BlackwallImuFifoThreshold @ none
    rawFifo: raw
configuration: Miscellaneous.BlackwallImuFifoConfiguration @ none
    startupPeer: peer
    rawFifo: raw
    threshold: threshold
transport: Miscellaneous.BlackwallImuFifoTransport @ iom 0x69
    owner: iom
    startupPeer: peer
    rawFifo: raw
    threshold: threshold
    configuration: configuration
''')
SCRIPT='''import json
from System import Array,Byte,Console
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
m=monitor.Machine;b=m.SystemBus;i=m['sysbus.iom'];t=m['sysbus.iom.transport'];q=t.RawFifo;h=t.Threshold;c=t.Configuration;p=t.StartupPeer;checks=[]
def check(n,v):
 if not v:raise Exception(n)
 checks.append(n)
def w(o,v):b.WriteDoubleWord(0x40054000+o,v)
def r(o):return int(b.ReadDoubleWord(0x40054000+o))
def advance(us):EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(us))
def select(reg):w(0x208,0x7fff);w(0x10c,reg);w(0x120,0x101)
def receive(n):
 w(0x208,0x7fff);w(0x120,(n<<8)|2);out=[]
 for at in range(0,n,4):
  v=r(0x108);out += [(v>>(8*k))&255 for k in range(min(4,n-at))]
 return out
def read(reg,n):select(reg);return receive(n)
def write(reg,data):
 payload=[reg]+data;w(0x208,0x7fff)
 for at in range(0,len(payload),4):w(0x10c,sum(x<<(8*k) for k,x in enumerate(payload[at:at+4])))
 w(0x120,(len(payload)<<8)|1)
def fail(n,fn):
 old=(c.Watermark,c.Writes,p.Configuration.FifoValue,h.Pending)
 try:fn()
 except Exception as error:
  if 'Blackwall unsupported IOM' not in str(error):raise
 else:raise Exception(n+' unexpectedly accepted')
 check(n+' old='+str(old)+' new='+str((c.Watermark,c.Writes,p.Configuration.FifoValue,h.Pending)),(c.Watermark,c.Writes,p.Configuration.FifoValue,h.Pending)==old)
 i.ResetThroughInterface()
 for offset,value in [(0x118,1),(0x11c,0x10),(0x2c0,0x23040),(0x2c4,0x69),(0x200,1)]:w(offset,value)
def frame(seed):return Array[Byte]([0xe0,0x1f]+[(seed+k)&255 for k in range(30)])
check('initial-gated',not c.Ready and h.WatermarkPackets==0 and not q.TryEnqueueFrame(frame(0)))
check('power',i.Power.TryWrite(32,True) and i.Power.ReadStatus()==32)
for o,v in [(0x118,1),(0x11c,0x10),(0x2c0,0x23040),(0x2c4,0x69),(0x200,1)]:w(o,v)
p.Configuration.ReadRegister(0x20);check('real-flush-request',p.Configuration.TryWriteRegister(0x20,0xa5));advance(1001)
check('real-flush-done',p.Configuration.FlushDone)
check('bank-read',read(0x1d,6)==[0,0,0,0x25,0,0] and c.Active)
check('decimation-read',read(0x28,1)==[0])
write(0x21,[0]);write(0x1d,[0])
fail('atomic-invalid-burst',lambda:write(0x1d,[7,10,0,0x2d,0x3e,1]))
check('no-partial-watermark',h.WatermarkPackets==0)
w(0x208,0x7fff);w(0x10c,0x000a071d);w(0x120,0x701)
check('partial-write-not-applied',c.Watermark==0 and p.Configuration.FifoValue==0x25)
try:t.FinishTransmission()
except Exception as error:
 if 'Blackwall unsupported IOM' not in str(error):raise
else:raise Exception('partial write finish unexpectedly accepted')
check('partial-finish-preserves-state',c.Watermark==0 and p.Configuration.FifoValue==0x25)
w(0x10c,0x0001362d);check('shared-comparator-and-watermark',p.Configuration.FifoValue==0x2d and c.Watermark==h.WatermarkPackets==10 and not c.Ready)
write(0x28,[0])
write(0x7c,[0xa2,0x58]);check('timed-ireg-pending',p.IregPending and not p.IregReady)
advance(3);check('timed-ireg-not-early',p.IregPending and not p.IregReady)
advance(2);check('timed-ireg-ready',p.IregReady and not p.IregPending)
check('timestamp-read',read(0x7e,1)==[0x60] and c.IndirectReads==1)
write(0x7c,[0xa2,0x58,0x60]);check('timestamp-rmw',c.TimestampControl==0x60 and c.IndirectWrites==1)
write(0x1d,[0x87]);check('mode-alone-not-ready',not c.Ready)
write(0x21,[0x37]);write(0x22,[1]);check('configured-ready',c.Ready and h.InterruptEnabled and h.GreaterOrEqual)
check('enqueue-ten',all(q.TryEnqueueFrame(frame(n)) for n in range(10)) and h.Pending)
fail('live-reconfiguration-rejected',lambda:write(0x1e,[4]))
check('count-ten',read(0x12,2)==[10,0]);data=read(0x14,320)
check('configured-fifo-bytes',data==sum([list(frame(n)) for n in range(10)],[]) and q.PacketCount==0 and q.PacketsConsumed==10)
h.Acknowledge(h.Snapshot())
write(0x21,[0x36]);write(0x1d,[7]);write(0x1e,[1]);check('low-not-applied',c.Watermark==10 and read(0x1e,1)==[1])
write(0x1f,[1]);check('high-commits-full16bit',c.Watermark==h.WatermarkPackets==257)
fail('high-without-low-rejected',lambda:write(0x1f,[0]))
t.Reset();check('reset-clears-config-and-gates',not c.Active and not c.Ready and c.Watermark==0 and not h.Pending and q.FrameBytes==32 and not q.TryEnqueueFrame(frame(1)))

import clr
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallImuFifoConfiguration').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuIdentity,BlackwallImuRawFifo,BlackwallImuFifoThreshold,BlackwallImuFifoConfiguration
shared_peer=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,165,90,1000,True,2,4,0,166,'ffff',1000,True,'af2500000000',1000,True,'a5b6d7','a045000000',1000,True,0,'a5b6c7c8e9faab9c',initialIregReady=True)
shared_raw=BlackwallImuRawFifo(True,False,64,32);shared_threshold=BlackwallImuFifoThreshold(shared_raw);shared=BlackwallImuFifoConfiguration(shared_peer,shared_raw,shared_threshold)
check('inactive-smc-stays-with-odr',not shared.Contains(0xa258) and shared_peer.Odr.Read(0xa258)==0xc8 and shared_peer.Odr.TryWrite(0xa258,0xd8))
shared_peer.Configuration.ReadRegister(0x20);shared_peer.Configuration.TryWriteRegister(0x20,0xa5);advance(1001)
check('shared-smc-bank-activation',shared.TryBeginRead(0x1d,6) and len(shared.ReadChunk(6))==6 and shared.TryFinishRead() and shared.Contains(0xa258))
check('shared-smc-real-owner-value',shared.TimestampControl==shared_peer.Odr.PeekRegister(0xa258)==0xd8)
check('shared-smc-low-bits-preserve-odr',shared.BeginRead(0xa258) and shared.Read(0xa258)==0xd8 and shared.TryWrite(0xa258,Array[Byte]([0xdb])) and shared_peer.Odr.PeekRegister(0xa258)==0xdb)
check('shared-smc-odr-bit-preserves-low',shared.BeginRead(0xa258) and shared.Read(0xa258)==0xdb and shared.TryWrite(0xa258,Array[Byte]([0xcb])) and shared.TimestampControl==shared_peer.Odr.PeekRegister(0xa258)==0xcb)
check('shared-smc-reserved-change-rejected',shared.BeginRead(0xa258) and shared.Read(0xa258)==0xcb and not shared.TryWrite(0xa258,Array[Byte]([0xeb])) and shared.TimestampControl==0xcb)
Console.WriteLine('BLACKWALL_FIFO_REGISTERS '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_arm_executed=False)))
'''
(out/'test.py').write_text(SCRIPT);(out/'probe.resc').write_text('include @/work/model.cs\nmach create "fifo-registers"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode',timeout=90)
rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_FIFO_REGISTERS ')]
if len(rows)!=1:raise ValueError('Configuration unit did not complete; inspect saved log')
(out/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))
