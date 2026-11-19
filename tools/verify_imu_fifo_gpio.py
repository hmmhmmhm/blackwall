"""Verify FIFO INT1 wiring through the retained GPIO38 owner and real IOM status reads."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from runtime_event_models import gpio_class
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
S=args.simulator.resolve();out=args.output.resolve()
if out.exists() or not out.is_relative_to(S) or out.is_relative_to(ROOT):p.error('New private simulator output required')
out.mkdir(mode=0o700);(out/'runner-source.py').write_bytes(Path(__file__).read_bytes())
model=(S/'mspi0-rx-main-01/stock24/strict.cs').read_text();previous=gpio_class(model);model=model.replace(previous,gpio_class((ROOT/'tools/renode-strict-mmio.cs').read_text()),1)
for before,after in [('BlackwallCpuNormalSleep cpuNormalSleep = null)','BlackwallCpuNormalSleep cpuNormalSleep = null, BlackwallGpioInterruptIdle gpioInterruptController = null)'),('GpioInterrupts = gpioInterruptIdle ? new BlackwallGpioInterruptIdle() : null;','GpioInterrupts = gpioInterruptIdle ? (gpioInterruptController ?? new BlackwallGpioInterruptIdle()) : null;')]:
 if model.count(before)!=1:raise ValueError('Changed retained GPIO owner constructor')
 model=model.replace(before,after,1)
for n in ['renode-imu-raw-fifo.cs','renode-imu-fifo-threshold.cs','renode-imu-fifo-transport.cs','renode-imu-int1-gpio.cs']:
 f=ROOT/'tools'/n
 if f.exists():model+='\n'+f.read_text()
model+='''
namespace Antmicro.Renode.Peripherals.Miscellaneous {
using System;using Antmicro.Renode.Peripherals.I2C;
public sealed class BlackwallImuGpioStatusFixture:II2CPeripheral {
private int pointer;
public void Write(byte[] data){if(data==null || data.Length!=1 || data[0]!=0x19)throw new ArgumentException("Fixture register");pointer=data[0];}
public byte[] Read(int count=1){if(pointer!=0x19 || count!=2)throw new ArgumentException("Fixture read");return new byte[]{0x40,0x20};}
public void FinishTransmission(){}
public void Reset(){pointer=0;}
}}
'''
(out/'model.cs').write_text(model)
(out/'board.repl').write_text('''cpu: CPU.CortexM @ sysbus
    cpuType: "cortex-m55"
    nvic: nvic
nvic: IRQControllers.NVIC @ sysbus 0xe000e000
    -> cpu@0
gpio: Miscellaneous.BlackwallGpioInterruptIdle @ none
    runtimePin38: true
    IRQ38 -> nvic@57
guard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40010000
    baseAddress: 0x40010000
    size: 0x1000
    gpioConfigStorage: true
    gpioInterruptIdle: true
    gpioInterruptController: gpio
power: Miscellaneous.BlackwallPeripheralPower
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
peer: Miscellaneous.BlackwallImuGpioStatusFixture @ none
transport: Miscellaneous.BlackwallImuFifoTransport @ iom 0x69
    owner: iom
    startupPeer: peer
    rawFifo: raw
    threshold: threshold
''')
SCRIPT='''import clr,json
from System import Array,Byte,Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallImuInt1Gpio').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuInt1Gpio,BlackwallG2StartupFixture,BlackwallGpioInterruptIdle
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
m=monitor.Machine;b=m.SystemBus;i=m['sysbus.iom'];t=m['sysbus.iom.transport'];raw=t.RawFifo;h=t.Threshold;g=m['sysbus.guard'].GpioInterrupts;sink=BlackwallImuInt1Gpio(m,m['sysbus.guard'],3);h.IRQ.Connect(sink,0);checks=[]
def check(n,v):
 if not v:raise Exception(n)
 checks.append(n)
def cfg(value):
 b.WriteDoubleWord(0x40010400,0x73);b.WriteDoubleWord(0x40010098,value);b.WriteDoubleWord(0x40010400,0)
def frame(n):return Array[Byte]([0x68]+[n]*15)
def w(o,v):b.WriteDoubleWord(0x40054000+o,v)
def status():
 w(0x208,0x7fff);w(0x10c,0x19);w(0x120,0x101);w(0x208,0x7fff);w(0x120,0x202)
 return int(b.ReadDoubleWord(0x40054108))&0xffff
check('initial-low',not sink.High and not g.Pin38High and not g.Pending38 and not h.Pending)
try:BlackwallImuInt1Gpio(m,None,3)
except Exception:check('missing-owner-rejected',True)
else:raise Exception('missing owner accepted')
off_owner=BlackwallG2StartupFixture(0x1000,0x40010000,gpioConfigStorage=True,gpioInterruptIdle=True)
check('default-owner-profile',off_owner.GpioConfig is not None and off_owner.GpioInterrupts is not None and not off_owner.GpioInterrupts.RuntimePin38)
try:BlackwallImuInt1Gpio(m,off_owner,3)
except Exception:check('default-off-owner-rejected',True)
else:raise Exception('default-off owner accepted')
try:sink.OnGPIO(1,True)
except Exception:check('wrong-input-number-rejected',not sink.High and not g.Pending38)
else:raise Exception('unknown input accepted')
check('power',i.Power.TryWrite(32,True) and i.Power.ReadStatus()==32)
for o,v in [(0x118,1),(0x11c,0x10),(0x2c0,0x23040),(0x2c4,0x69),(0x200,1)]:w(o,v)
cfg(0x93)
check('below-watermark',raw.TryEnqueueFrame(frame(1)) and not h.IRQ.IsSet and not sink.High and not g.Pending38)
check('threshold-source-high',raw.TryEnqueueFrame(frame(2)) and h.IRQ.IsSet and sink.High and g.Pin38High)
check('masked-latches-pending',g.Pending38 and g.Pin38RisingEdges==1 and not g.IRQ38.IsSet and b.ReadDoubleWord(0x40010544)==0x40)
b.WriteDoubleWord(0x40010540,0x40)
check('unmask-drives-nvic57',g.IRQ38.IsSet and b.ReadDoubleWord(0xe000e204)&(1<<25)!=0)
b.WriteDoubleWord(0x40010548,1)
check('unrelated-w1c-preserves',g.Pending38 and g.IRQ38.IsSet)
b.WriteDoubleWord(0x40010548,0x40)
check('w1c-only-controller',not g.Pending38 and not g.IRQ38.IsSet and g.Pin38High and sink.High and h.Pending and h.IRQ.IsSet)
check('held-high-no-edge',raw.TryEnqueueFrame(frame(3)) and h.EventsRaised==2 and g.Pin38RisingEdges==1 and not g.Pending38)
check('iom-status-clears-source',status()==0x2042 and not h.Pending and not h.IRQ.IsSet and not sink.High and not g.Pin38High and raw.PacketCount==3)
check('new-event-new-edge',raw.TryEnqueueFrame(frame(4)) and g.Pending38 and g.Pin38RisingEdges==2 and sink.High)
check('capacity-rejection-no-extra-edge',not raw.TryEnqueueFrame(frame(5)) and g.Pin38RisingEdges==2)
check('source-clear-preserves-controller-latch',status()==0x2042 and not sink.High and not g.Pin38High and g.Pending38 and g.IRQ38.IsSet)
b.WriteDoubleWord(0x40010548,0x40)
check('both-cleared',not h.Pending and not g.Pending38 and not g.IRQ38.IsSet)
raw.Reset();g.Reset();sink.Reset();cfg(0x53);b.WriteDoubleWord(0x40010540,0x40)
check('wrong-pad-source-still-stores',raw.TryEnqueueFrame(frame(1)) and raw.TryEnqueueFrame(frame(2)) and sink.High and h.Pending and raw.PacketCount==2)
check('wrong-pad-no-controller-edge',sink.RejectedTransitions==1 and not g.Pin38High and not g.Pending38 and not g.IRQ38.IsSet)
cfg(0x93)
check('reconfiguration-does-not-invent-edge',not g.Pending38 and not g.Pin38High and sink.High)
check('wrong-pad-source-ack-lowers',status()==0x2042 and not sink.High and not h.Pending)
check('next-real-rise-accepted',raw.TryEnqueueFrame(frame(3)) and g.Pending38 and g.IRQ38.IsSet and g.Pin38RisingEdges==1)
raw.Reset()
check('device-reset-lowers-source-only',not h.Pending and not sink.High and not g.Pin38High and g.Pending38)
g.Reset();sink.Reset()
check('whole-fixture-reset',not sink.High and not g.Pending38 and not g.IRQ38.IsSet and sink.RejectedTransitions==0)
m['sysbus.cpu'].IsHalted=True
pulse_gpio=BlackwallGpioInterruptIdle(runtimePin38=True)
pulse_owner=BlackwallG2StartupFixture(0x1000,0x40010000,gpioConfigStorage=True,gpioInterruptIdle=True,gpioInterruptController=pulse_gpio)
pulse_owner.GpioConfig.TryWrite(0x40010400,0x73);pulse_owner.GpioConfig.TryWrite(0x40010098,0x93)
pulse_gpio.TryWrite(0x40010540,0x40)
pulse=BlackwallImuInt1Gpio(m,pulse_owner,0xa1)
check('pulse-source-profile',pulse.PulseMode and pulse.InterruptConfiguration==0xa1 and pulse.PulseMicroseconds==8)
def advance(us):EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(us))
pulse.OnGPIO(0,True)
check('pulse-initial-rise',pulse.High and pulse.PinHigh and pulse_gpio.Pin38High and pulse_gpio.Pending38 and pulse_gpio.Pin38RisingEdges==1)
advance(7)
check('pulse-before-expiry',pulse.PinHigh and pulse_gpio.Pin38High)
advance(2)
check('pulse-expiry-status-still-high',pulse.High and not pulse.PinHigh and not pulse_gpio.Pin38High and pulse_gpio.Pending38 and pulse_gpio.IRQ38.IsSet)
pulse_gpio.TryWrite(0x40010548,0x40);pulse.OnGPIO(0,True)
check('pulse-held-source-no-repeat',not pulse_gpio.Pending38 and pulse_gpio.Pin38RisingEdges==1)
pulse.OnGPIO(0,False);pulse.OnGPIO(0,True);pulse.OnGPIO(0,False)
check('pulse-early-ack-preserves-minimum',not pulse.High and pulse.PinHigh and pulse_gpio.Pin38High and pulse_gpio.Pin38RisingEdges==2)
advance(9)
check('pulse-early-ack-expiry',not pulse.High and not pulse.PinHigh and not pulse_gpio.Pin38High)
pulse.OnGPIO(0,True);pulse.Reset();advance(9)
check('pulse-reset-cancels-timer',not pulse.High and not pulse.PinHigh and not pulse_gpio.Pin38High and pulse.RejectedTransitions==0)
try:BlackwallImuInt1Gpio(m,pulse_owner,0xa0)
except Exception:check('active-low-profile-rejected',True)
else:raise Exception('unsupported polarity accepted')
slow=BlackwallImuInt1Gpio(m,pulse_owner,1,100);slow.OnGPIO(0,True);advance(99)
check('pulse100-before-expiry',slow.PinHigh);advance(2)
check('pulse100-expiry',slow.High and not slow.PinHigh)
Console.WriteLine('BLACKWALL_FIFO_GPIO '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_arm_executed=False)))
'''
(out/'test.py').write_text(SCRIPT);(out/'probe.resc').write_text('include @/work/model.cs\nmach create "fifo-gpio"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode',timeout=90)
rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_FIFO_GPIO ')]
if len(rows)!=1:raise ValueError('GPIO unit did not complete; inspect saved log')
(out/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))
