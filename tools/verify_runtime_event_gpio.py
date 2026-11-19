"""Renode peer/GPIO lifecycle test; startup primer introspects commands, no firmware execution."""
import argparse
import json
from pathlib import Path
import re
from runtime_event_models import compose
from native_replay import IMAGE
from run_renode_m55_probe import execute

SCRIPT='''import json,clr
from System import Console
from System.Reflection import BindingFlags
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallEm9305EventPeer').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallGpioInterruptIdle,BlackwallEm9305EventPeer
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];q=g.GpioInterrupts;p=g.Em9305Reset.HciPeer;checks=[]
def check(name,value):
 if not value:raise Exception(name)
 checks.append(name)
def cfg(pin,value):
 b.WriteDoubleWord(0x40010400,0x73);b.WriteDoubleWord(0x40010000+4*pin,value);b.WriteDoubleWord(0x40010400,0)
def cs(high):b.WriteDoubleWord(0x4001044c if high else 0x40010468,1<<21)
def readframe():
 cs(False);p.BeginTransaction(2);a=int(p.Transmit(0x81));n=int(p.Transmit(0));p.FinishTransmission()
 if a!=0xc0:raise Exception('header')
 p.BeginReceive(n);data=[int(p.Transmit(0)) for unused in range(n)];p.FinishTransmission();cs(True);return data
def prime():
 cfg(149,0x183);cfg(117,0x93);b.WriteDoubleWord(0x40010560,1<<21);cs(True)
 p.QualifiedRelease(True);readframe()
 # This only primes retained startup state through normal transactions. It is
 # not an independent oracle for startup command contents.
 prop=p.GetType().GetProperty('CurrentCommand',BindingFlags.Instance|BindingFlags.NonPublic)
 while str(p.State)!='Complete':
  command=[int(x) for x in prop.GetValue(p,None)];offset=0
  while offset<len(command):
   cs(False);p.BeginTransaction(2);p.Transmit(0x42);capacity=int(p.Transmit(0));p.FinishTransmission()
   n=min(capacity,len(command)-offset);p.BeginTransaction(n)
   for v in command[offset:offset+n]:p.Transmit(v)
   p.FinishTransmission();cs(True);offset+=n
  while str(p.State)=='ReplyQueued':readframe()
check('runtime-opt-in',p.HasRuntimeConnectionScenario and q.RuntimePin117)
check('unreleased-rejected',not p.TryQueueRuntimeConnection() and not q.IRQ.IsSet)
default=BlackwallGpioInterruptIdle();check('default-input-off',not default.TrySetPin117(True,True) and not default.IRQ.IsSet)
check('default-event-off',not BlackwallEm9305EventPeer('04ff0101').TryQueueRuntimeConnection())
try:BlackwallEm9305EventPeer('04ff0101',runtimeConnectionEventHex='043e1301004000010011223344556618000000c80000')
except Exception:check('missing-startup-profile-rejected',True)
else:raise Exception('missing prerequisites accepted')
prime();check('startup-complete',p.CommandsAccepted==59 and p.Replies==60 and p.ReadyLevel==0 and not q.IRQ.IsSet)
cfg(117,0x53);check('wrong-config-rejected',not p.TryQueueRuntimeConnection());cfg(117,0x93)
b.WriteDoubleWord(0x40010560,0);check('masked-ingress-rejected',not p.TryQueueRuntimeConnection());b.WriteDoubleWord(0x40010560,1<<21)
check('event-queued',p.TryQueueRuntimeConnection() and p.RuntimeEventPending and p.ReadyLevel==1)
check('gpio-pending',b.ReadDoubleWord(0x40010564)==1<<21 and q.IRQ.IsSet and q.RisingEdges==1)
check('nvic59-wire',b.ReadDoubleWord(0xe000e204)&(1<<27)!=0)
check('duplicate-rejected',not p.TryQueueRuntimeConnection() and q.RisingEdges==1)
b.WriteDoubleWord(0x40010568,1);check('unrelated-clear-preserves',q.Pending117 and q.IRQ.IsSet)
b.WriteDoubleWord(0x40010560,0);check('mask-lowers-line',q.Pending117 and not q.IRQ.IsSet)
b.WriteDoubleWord(0x40010560,1<<21);check('unmask-restores-line',q.IRQ.IsSet)
b.WriteDoubleWord(0x40010568,1<<21);check('clear-lowers-line',not q.IRQ.IsSet and not q.Pending117 and p.ReadyLevel==1)
q.TrySetPin117(True,True);check('held-level-does-not-relatch',not q.IRQ.IsSet and q.RisingEdges==1)
cs(False);p.BeginTransaction(2);p.Transmit(0x81);cs(True)
check('partial-header-cs-retry',p.RuntimeEventPending and str(p.State)=='ReplyQueued' and p.Aborts==1)
before=(int(p.CommandsAccepted),int(p.Replies));data=readframe()
check('exact-runtime-event',data==list(bytearray.fromhex('043e1301004000010011223344556618000000c80000')))
check('runtime-consumed-on-cs',not p.RuntimeEventPending and p.RuntimeEventsConsumed==1 and str(p.State)=='Complete' and p.ReadyLevel==0)
check('startup-counts-preserved',before==(int(p.CommandsAccepted),int(p.Replies)))
check('one-event-only',not p.TryQueueRuntimeConnection())
g.Reset();check('reset-clears-ownership',not q.Pending117 and not q.IRQ.IsSet and not p.RuntimeEventPending and p.RuntimeEventsConsumed==0 and q.RisingEdges==0)
prime();check('new-reset-lifecycle-queued',p.TryQueueRuntimeConnection())
cs(False);p.BeginTransaction(2);p.Transmit(0x81);p.AbortTransaction()
check('controller-abort-fails-closed',str(p.State)=='Fault' and p.ReadyLevel==-1 and not p.TryQueueRuntimeConnection())
g.Reset();check('reset-after-abort',not q.IRQ.IsSet and not q.Pending117 and not p.RuntimeEventPending)
Console.WriteLine('BLACKWALL_RUNTIME_EVENT_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_firmware_executed=False,startup_primer_uses_same_class_command_getter=True)))
'''


def build(s,out):
    out.mkdir(mode=0o700)
    base=s/'tpl-time-native-01/stock24'
    (out/'strict.cs').write_text(compose(s,(base/'strict.cs').read_text()))
    board=(base/'board.repl').read_text()
    peer=re.search(r'^spi_header:.*?(?=^\S|\Z)',board,re.M|re.S).group(0)
    reset=re.search(r'^\w+: Miscellaneous.BlackwallEm9305ResetHypothesis.*?(?=^\S|\Z)',board,re.M|re.S).group(0)
    (out/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    -> cpu@0\ngpio_irq: Miscellaneous.BlackwallGpioInterruptIdle @ none\n    runtimePin117: true\n    -> nvic@59\nguard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40010000\n    baseAddress: 0x40010000\n    size: 0x1000\n    gpioConfigStorage: true\n    gpioInterruptIdle: true\n    gpioInterruptController: gpio_irq\n    gpioOutputLatch: true\n    em9305Reset: '+reset.split(':')[0]+'\n'+reset+'\n'+peer.replace('    eventHex:', '    runtimeConnectionEventHex: "043e1301004000010011223344556618000000c80000"\n    eventHex:')+'\nlink: Miscellaneous.BlackwallEm9305RuntimeLink @ none\n    peer: spi_header\n    owner: guard\n')
    (out/'test.py').write_text(SCRIPT)
    (out/'probe.resc').write_text('include @/work/strict.cs\nmach create "runtime-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if not a.output.resolve().is_relative_to(a.simulator.resolve()):p.error('Private simulator output required')
    build(a.simulator,a.output)
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=90)
    rows=[json.loads(x.split('BLACKWALL_RUNTIME_EVENT_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RUNTIME_EVENT_UNIT ')]
    assert len(rows)==1,log[-1800:]
    (a.output/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))


if __name__=='__main__':main()
