"""Bounded UART0 RX timeout tests using virtual time; no hardware or firmware writes."""
import argparse,json,shutil
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import clr,json
from System import Array,Byte,Console
from Antmicro.Renode.Utilities import TypeManager
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallUartAdapter').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallUartAdapter
m=monitor.Machine;checks=[];base=0x40039000
u=BlackwallUartAdapter(m,True,0,txInterruptQuirks=False,receiveFifo=True,receiveTimeout=True)
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def w(off,v):return u.TryWrite(base+off,v,True)
def r(off):
    ok,v=u.TryRead(base+off,True)
    if not ok:raise Exception('read rejected')
    return int(v)
def rx(data):return u.TryReceive(Array[Byte](data),True)
def advance(us):EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(us))
def setup():
    check('setup',w(0x24,3) and w(0x28,0) and w(0x2c,0x70) and w(0x34,0x12) and w(0x30,0x219))
setup();check('mask-zero',w(0x38,0));check('short12',rx(list(range(12))) and not u.IRQ.IsSet)
advance(63);check('not-early',r(0x3c)&0x40==0 and u.RxTimeoutEvents==0)
advance(1);check('32-bit-periods',r(0x3c)&0x40 and not u.IRQ.IsSet and u.RxTimeoutCycles==1536 and u.RxTimeoutEvents==1)
check('unmask',w(0x38,0x40) and u.IRQ.IsSet and r(0x40)&0x40)
check('partial-read-latched',r(0)==0 and u.RxPending==11 and u.RxTimeoutPending)
check('clear',w(0x44,0x40) and not u.RxTimeoutPending and not u.IRQ.IsSet)
advance(63);check('clear-not-immediate',not u.IRQ.IsSet)
advance(1);check('remaining-data-rearm',u.IRQ.IsSet)
check('drain-clears',list(r(0) for unused in range(11))==list(range(1,12)) and not u.RxTimeoutPending and not u.IRQ.IsSet)
advance(128);check('empty-no-ghost',not u.IRQ.IsSet and u.RxTimeoutEvents==2)
check('new-burst',rx(list(range(12))));advance(32);check('new-byte-restarts',rx([99]));advance(32);check('old-deadline-cancelled',not u.IRQ.IsSet)
advance(31);check('new-deadline-not-early',not u.IRQ.IsSet);advance(1);check('new-deadline',u.IRQ.IsSet and u.RxTimeoutEvents==3)
check('baud-change-rejected-buffered',not w(0x24,4) and r(0x24)==3)
check('drain13',list(r(0) for unused in range(13))==list(range(12))+[99] and not u.IRQ.IsSet)
check('reset-pending-input',rx([1,2,3]));advance(16);u.Reset();setup();advance(128);check('reset-cancels',u.RxPending==0 and u.RxTimeoutEvents==0 and not u.IRQ.IsSet)
check('power-pending-input',w(0x38,0x40) and rx([1,2,3]));advance(16);u.PowerDown();advance(128);check('power-cancels',u.RxPending==0 and not u.RxTimeoutPending and not u.IRQ.IsSet)
setup();check('disable-pending',w(0x38,0x40) and rx([1,2,3]));advance(16);check('clock-change-buffered-rejected',not w(0x30,0));check('disable',w(0x30,0x18));advance(128);check('disabled-no-timeout',u.RxPending==3 and not u.RxTimeoutPending and not u.IRQ.IsSet)
check('reenable',w(0x30,0x219));advance(63);check('reenable-not-early',not u.IRQ.IsSet);advance(1);check('reenable-timeout',u.IRQ.IsSet)
check('last-drain',list(r(0) for unused in range(3))==[1,2,3] and not u.IRQ.IsSet)
check('fractional-config',w(0x28,3) and rx([7,8,9]));advance(64);check('fractional-not-early',not u.IRQ.IsSet);advance(1);check('fractional-65us',u.IRQ.IsSet and u.RxTimeoutCycles==1560)
check('fractional-drain',list(r(0) for unused in range(3))==[7,8,9] and not u.IRQ.IsSet)
check('zero-divisor-config',w(0x24,0) and w(0x28,0));check('zero-divisor-receive-rejected',not rx([1]) and u.RxPending==0)
legacy=BlackwallUartAdapter(m,True,0,txInterruptQuirks=False,receiveFifo=True)
for off,v in [(0x24,3),(0x28,0),(0x2c,0x70),(0x34,0x12),(0x30,0x219),(0x38,0x50)]:check('legacy-config',legacy.TryWrite(base+off,v,True))
check('legacy-input',legacy.TryReceive(Array[Byte]([1,2,3]),True));advance(128);check('default-off',not legacy.ReceiveTimeout and not legacy.IRQ.IsSet)
for module,fifo in [(1,True),(0,False)]:
    try:BlackwallUartAdapter(m,True,module,receiveFifo=fifo,receiveTimeout=True)
    except Exception:check('invalid-profile',True)
    else:raise Exception('invalid timeout profile accepted')
Console.WriteLine('BLACKWALL_UART_TIMEOUT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='opt-in UART0 clean-byte RX, nominal24MHz/divisors, virtual time; no physical timing validation')))
'''
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve();o.mkdir(mode=0o700)
    shutil.copyfile(ROOT/'tools/renode-strict-mmio.cs',o/'strict.cs');(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "uart-timeout"\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_UART_TIMEOUT ')];assert len(rows)==1,'Inspect preserved timeout log'
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))
if __name__=='__main__':main()
