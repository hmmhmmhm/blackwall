"""Exercise the strict UART1 adapter with the pinned Renode runtime, no firmware/devices."""
import argparse,json,shutil
from pathlib import Path
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import clr,json
from Antmicro.Renode.Utilities import TypeManager
from System import Console
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallUartAdapter').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallUartAdapter,BlackwallUartPower,BlackwallMemoryRegister
checks=[]
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
u=BlackwallUartAdapter(monitor.Machine)
check('off-read',not u.TryRead(0x4003a030,False)[0] and u.Control==0x300)
check('off-write',not u.TryWrite(0x4003a030,0,False) and u.Control==0x300)
check('reset-empty',u.TryRead(0x4003a018,True)[1]==0x90)
check('disabled-tx',not u.TryWrite(0x4003a000,65,True) and u.TxBytes.Count==0)
for off,val in [(0x2c,0x70),(0x24,13),(0x28,1),(0x30,0x319)]:check('config-'+str(off),u.TryWrite(0x4003a000+off,val,True))
check('clock-readback',u.TryRead(0x4003a030,True)[1]==0x319 and u.VirtualBaud>0)
for integer,fraction,expected in [(0,0,0),(0,1,96000000),(0,2,48000000),(0,3,32000000),(0,63,1523809),(1,0,1500000),(13,1,115246)]:
    u.TryWrite(0x4003a024,integer,True);u.TryWrite(0x4003a028,fraction,True)
    check('baud-'+str(integer)+'-'+str(fraction),u.VirtualBaud==expected)
u.TryWrite(0x4003a024,13,True);u.TryWrite(0x4003a028,1,True)
check('tx-A',u.TryWrite(0x4003a000,65,True) and list(u.TxBytes)==[65])
for name,addr,val in [('byte-range',0,256),('flow',0x30,0x8319),('loopback',0x30,0x399),('irda',0x30,0x31b),('irq',0x38,1),('dma',0x48,1),('dma-address',0x4c,0),('break',0x2c,0x71),('reserved',0x30,0x10000),('fifo-level',0x34,7)]:
    check(name,not u.TryWrite(0x4003a000+addr,val,True) and u.TxBytes.Count==1)
check('unchanged-control',u.Control==0x319)
check('rx-data-blocked',not u.TryRead(0x4003a000,True)[0])
check('ID-blocked',not u.TryRead(0x4003afe0,True)[0])
check('unaligned-blocked',not u.TryRead(0x4003a031,True)[0])
check('clear-defined',u.TryWrite(0x4003a044,0x1fff,True))
check('clear-reserved',not u.TryWrite(0x4003a044,0x2000,True))
check('clock-off-config',u.TryWrite(0x4003a030,0x301,True))
check('clock-off-tx',not u.TryWrite(0x4003a000,66,True) and u.TxBytes.Count==1)
u.Reset();u.TryWrite(0x4003a02c,0x70,True);u.TryWrite(0x4003a030,0x319,True)
for i in range(4096):
    if not u.TryWrite(0x4003a000,i&255,True):raise Exception('bounded TX fill')
check('capture-cap',not u.TryWrite(0x4003a000,0,True) and u.TxBytes.Count==4096)
for mode in (0,1):
    p=BlackwallUartPower(mode)
    check('power-unready-'+str(mode),not p.TryWrite(0x400,False))
    check('power-request-'+str(mode),p.TryWrite(0x400,True) and p.StatusWord==0)
    check('power-response-'+str(mode),p.ReadStatus()==(0x400 if mode else 0) and p.Responses==1)
    check('power-reconfigure-'+str(mode),not p.TryWrite(0x800,True) and p.RequestWord==0x400)
u.Reset()
r=BlackwallMemoryRegister(0x810000)
check('spare-disabled',not u.TryClockSpare(r,0x10000,True) and r.Value==0x810000)
u.TryWrite(0x4003a030,8,True)
check('spare-unready',not u.TryClockSpare(r,0x10000,False) and r.Writes==0)
check('spare-other-field',not u.TryClockSpare(r,0,True) and r.Value==0x810000)
check('spare-clear',u.TryClockSpare(r,0x10000,True) and r.Value==0x10000 and r.Writes==1 and u.ClockSpareClears==1)
check('spare-repeat',not u.TryClockSpare(r,0x10000,True) and r.Writes==1)
u.Reset()
check('spare-reset',u.ClockSpareClears==0)
u=BlackwallUartAdapter(monitor.Machine,True)
check('irq-mode-reset',u.InterruptsEnabled and u.InterruptMask==0 and not u.IRQ.IsSet and not u.TxComplete)
u.TryWrite(0x4003a02c,0x70,True);u.TryWrite(0x4003a030,0x319,True)
check('irq-mask471',u.TryWrite(0x4003a038,0x471,True) and u.InterruptMask==0x471 and u.IRQ.IsSet and u.MaskedInterrupts==0x20)
check('irq-clear-tx',u.TryWrite(0x4003a044,0x20,True) and not u.IRQ.IsSet)
check('irq-txcmp-mask',u.TryWrite(0x4003a038,1,True) and not u.IRQ.IsSet)
check('irq-tx-cause',u.TryWrite(0x4003a000,65,True) and list(u.TxBytes)==[65] and u.RawInterrupts==0x21 and u.MaskedInterrupts==1 and u.TxCompletions==1 and u.IRQ.IsSet)
check('irq-clear-preserve-cmp',u.TryWrite(0x4003a044,0x20,True) and u.RawInterrupts==1 and u.IRQ.IsSet)
check('irq-cmp-clear',u.TryWrite(0x4003a044,1,True) and u.RawInterrupts==0 and not u.IRQ.IsSet)
check('irq-rx-only-idle',u.TryWrite(0x4003a038,0x450,True) and not u.IRQ.IsSet)
check('irq-dma-mask-blocked',not u.TryWrite(0x4003a038,0x800,True) and u.InterruptMask==0x450)
check('irq-reserved-mask-blocked',not u.TryWrite(0x4003a038,0x2000,True) and u.InterruptMask==0x450)
check('irq-register-readbacks',u.TryRead(0x4003a038,True)[1]==0x450 and u.TryRead(0x4003a03c,True)[1]==0 and u.TryRead(0x4003a040,True)[1]==0)
u.TryWrite(0x4003a000,66,True)
check('irq-masked-raw-retained',u.RawInterrupts==0x21 and u.MaskedInterrupts==0 and not u.IRQ.IsSet)
check('irq-unmask-pending',u.TryWrite(0x4003a038,1,True) and u.IRQ.IsSet)
check('irq-mask-all',u.TryWrite(0x4003a038,0,True) and not u.IRQ.IsSet and u.RawInterrupts==0x21)
check('irq-transition-counters',u.IRQAssertions==3 and u.IRQTransitions==6 and u.TxCompletions==2)
u.Reset()
check('irq-reset-counters',u.InterruptMask==0 and not u.TxComplete and u.TxCompletions==0 and u.InterruptClears==0 and u.IRQAssertions==0 and not u.IRQ.IsSet)
u.TryWrite(0x4003a02c,0x70,True);u.TryWrite(0x4003a030,0x319,True);u.TryWrite(0x4003a038,0x471,True);u.TryWrite(0x4003a000,67,True)
check('irq-clear-all-command',u.TryWrite(0x4003a044,0xffffffff,True) and u.RawInterrupts==0 and not u.IRQ.IsSet and not u.TxComplete)
check('irq-clear-reserved-still-blocked',not u.TryWrite(0x4003a044,0x2000,True))
for mode in (0,1):
    p=BlackwallUartPower(1,mode)
    check('life-on-'+str(mode),p.TryWrite(0x400,True) and p.ReadStatus()==0x400)
    check('life-active-block-'+str(mode),not p.TryWrite(0,True,False) and p.RequestWord==0x400 and p.OffRequests==0)
    check('life-off-request-'+str(mode),p.TryWrite(0,True,True) and p.RequestWord==0 and p.StatusWord==0x400)
    check('life-off-response-'+str(mode),p.ReadStatus()==(0 if mode==0 else 0x400) and p.OffRequests==1 and p.PowerCycles==(1 if mode==0 else 0))
    p.ReadStatus()
    check('life-response-once-'+str(mode),p.Responses==2)
    check('life-unready-block-'+str(mode),not p.TryWrite(0x400,False) and p.RequestWord==0)
    if mode==0:
        check('life-reenable',p.TryWrite(0x400,True) and p.StatusWord==0 and p.ReadStatus()==0x400 and p.Requests==2 and p.Responses==3)
        check('life-second-off',p.TryWrite(0,True,True) and p.ReadStatus()==0 and p.PowerCycles==2 and p.OffRequests==2)
    else:check('life-stuck-reenable-block',not p.TryWrite(0x400,True) and p.Phase=='stuck-on')
p=BlackwallUartPower(1)
p.TryWrite(0x400,True);p.ReadStatus()
check('life-default-off-block',not p.TryWrite(0,True,True) and p.OffRequests==0)
u=BlackwallUartAdapter(monitor.Machine,True)
u.TryWrite(0x4003a02c,0x70,True);u.TryWrite(0x4003a030,0x319,True);u.TryWrite(0x4003a038,0x471,True);u.TryWrite(0x4003a000,68,True)
check('life-pending-not-quiescent',not u.Quiescent)
u.TryWrite(0x4003a044,0xffffffff,True);u.TryWrite(0x4003a030,0,True)
check('life-quiescent',u.Quiescent)
w=int(u.Writes);u.PowerDown()
check('life-register-reset-history',u.Control==0x300 and u.InterruptMask==0 and not u.IRQ.IsSet and list(u.TxBytes)==[68] and u.Writes==w and u.PowerDowns==1 and u.TxCompletions==1)
u.TryWrite(0x4003a030,8,True)
r=BlackwallMemoryRegister(0x10000)
check('life-reset-registers',[int(u.TryRead(0x4003a000+offset,True)[1]) for offset in [0x20,0x24,0x28,0x2c,0x34,0x38,0x48]]==[0,0,0,0,0x12,0,0])
check('life-new-spare-epoch',u.TryClockSpare(r,0x10000,True))
ports=[BlackwallUartAdapter(monitor.Machine,True,module) for module in range(4)]
for module,u in enumerate(ports):
    base=0x40039000+module*0x1000
    check('module-map-'+str(module),u.Module==module and u.BaseAddress==base and u.IrqNumber==15+module and u.Owns(base) and not u.Owns(base+0x1000))
    u.TryWrite(base+0x2c,0x70,True);u.TryWrite(base+0x30,0x319,True);u.TryWrite(base+0x38,1,True)
    before=[(list(other.TxBytes),int(other.Control),bool(other.IRQ.IsSet)) for other in ports]
    check('module-tx-'+str(module),u.TryWrite(base,65+module,True) and list(u.TxBytes)==[65+module] and u.IRQ.IsSet)
    check('module-isolation-'+str(module),all(index==module or (list(other.TxBytes),int(other.Control),bool(other.IRQ.IsSet))==before[index] for index,other in enumerate(ports)))
    check('module-neighbor-block-'+str(module),not u.TryWrite(base+0x1030,0,True) and u.Control==0x319)
    p=BlackwallUartPower(1,0,module)
    check('module-power-'+str(module),p.Mask==(0x200<<module) and p.TryWrite(p.Mask,True) and p.ReadStatus()==p.Mask and p.TryWrite(0,True,True) and p.ReadStatus()==0)
for module in (-1,4):
    try:BlackwallUartAdapter(monitor.Machine,True,module)
    except Exception:check('invalid-adapter-module-'+str(module),True)
    else:raise Exception('invalid adapter accepted')
    try:BlackwallUartPower(1,0,module)
    except Exception:check('invalid-power-module-'+str(module),True)
    else:raise Exception('invalid power accepted')
r=BlackwallMemoryRegister(0x3c10000)
for module,u in enumerate(ports):
    u.Reset();u.TryWrite(u.BaseAddress+0x30,8,True)
    expected=int(r.Value)&~(0x400000<<module)
    check('module-spare-'+str(module),u.TryClockSpare(r,expected,True) and r.Value==expected)
Console.WriteLine('BLACKWALL_UART '+json.dumps(dict(passed=True,assertion_count=len(checks),checks=checks,scope='isolated adapter/power; no firmware or physical UART validation')))
'''
RX_DRIVER = """import clr,json
from Antmicro.Renode.Utilities import TypeManager
from System import Console,Array,Byte
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallUartAdapter').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallUartAdapter
m=monitor.Machine;checks=[];base=0x40039000
u=BlackwallUartAdapter(m,True,0,txInterruptQuirks=False,receiveFifo=True)
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def w(off,value):return u.TryWrite(base+off,value,True)
def r(off):
    value=u.TryRead(base+off,True)
    if not value[0]:raise Exception('read rejected '+hex(off))
    return int(value[1])
def rx(data,powered=True):return u.TryReceive(Array[Byte](data),powered)
check('profile',u.ReceiveFifo and u.RxPending==0)
check('disabled-reject',not rx([1]) and u.RxPending==0)
check('config',w(0x2c,0x70) and w(0x24,13) and w(0x28,1) and w(0x34,0) and w(0x30,0x219) and w(0x38,0x10))
check('off-reject',not rx([1],False) and u.RxPending==0)
check('empty-reject',not rx([]) and u.RxPending==0)
check('overflow-atomic',not rx(list(range(33))) and u.RxPending==0 and u.RxBytesInjected==0)
check('below-threshold',rx([1,2,3]) and u.RxPending==3 and r(0x18)&0x10==0 and r(0x3c)&0x10==0 and not u.IRQ.IsSet)
check('threshold',rx([4]) and u.RxPending==4 and r(0x3c)&0x10 and u.IRQ.IsSet)
check('clear-level-not-drop',w(0x44,0x10) and u.IRQ.IsSet)
check('first-byte',r(0)==1 and u.RxPending==3 and not u.IRQ.IsSet)
check('drain',r(0)==2 and r(0)==3 and r(0)==4 and u.RxPending==0 and r(0x18)&0x10 and u.RxBytesRead==4)
check('empty-dr-reject',not u.TryRead(base,True)[0])
h=14695981039346656037
for b in (1,2,3,4):h=((h^b)*1099511628211)&0xffffffffffffffff
check('read-sequence-hash',int(u.RxReadHash)==h)
check('mask-buffered',w(0x38,0) and rx(list(range(32))) and u.RxPending==32 and not u.IRQ.IsSet and r(0x18)&0x40)
check('full-reject-atomic',not rx([99]) and u.RxPending==32)
check('unmask-pending',w(0x38,0x10) and u.IRQ.IsSet)
check('fifo-mode-change-reject',not w(0x2c,0x60) and u.RxPending==32)
check('drain-full',list(r(0) for unused in range(32))==list(range(32)) and u.RxPending==0 and not u.IRQ.IsSet)
check('fifo-disabled-one',w(0x2c,0x60) and not rx([1,2]) and rx([9]) and u.RxPending==1 and u.IRQ.IsSet and r(0)==9)
check('reset',w(0x2c,0x70) and rx([1,2,3,4]))
u.Reset();check('reset-clears',u.RxPending==u.RxBytesRead==u.RxBytesInjected==0 and not u.IRQ.IsSet and int(u.RxReadHash)==14695981039346656037)
check('reconfigure',w(0x2c,0x70) and w(0x30,0x219) and w(0x38,0x10) and rx([9,8,7,6]))
u.PowerDown();check('powerdown-clears',u.RxPending==0 and r(0x18)&0x10 and not u.IRQ.IsSet)
u.Reset()
check('native-half-config',w(0x2c,0x70) and w(0x34,0x12) and w(0x30,0x319) and w(0x38,0x50) and int(u.ReceiveLevelSelection)==2)
check('native-short12-no-irq',rx(list(range(12))) and u.RxPending==12 and not u.IRQ.IsSet and r(0x3c)&0x50==0)
check('native-split15-no-irq',rx([12,13,14]) and u.RxPending==15 and not u.IRQ.IsSet)
check('native-split16-irq',rx([15]) and u.RxPending==16 and u.IRQ.IsSet)
check('native-half-drain',list(r(0) for unused in range(16))==list(range(16)) and u.RxPending==0 and not u.IRQ.IsSet)
legacy=BlackwallUartAdapter(m,True,0,txInterruptQuirks=False)
check('default-off',not legacy.ReceiveFifo and not legacy.TryReceive(Array[Byte]([1]),True) and not legacy.TryRead(base,True)[0])
for module in (1,2,3):
    try:BlackwallUartAdapter(m,True,module,receiveFifo=True)
    except Exception:check('invalid-module-'+str(module),True)
    else:raise Exception('RX profile accepted on wrong module')
Console.WriteLine('BLACKWALL_UART '+json.dumps(dict(passed=True,assertion_count=len(checks),checks=checks,scope='Explicit UART0 FIFO clean-byte input; no RX timeout, error frames or physical timing')))
"""

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--rx-fifo',action='store_true');a=p.parse_args();o=a.output.resolve();o.mkdir(mode=0o700)
    shutil.copy2(ROOT/'tools/renode-strict-mmio.cs',o/'strict.cs');(o/'test.py').write_text(RX_DRIVER if a.rx_fifo else DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "uart1-unit"\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','blackwall-renode:1.17.0-local','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(x.split('BLACKWALL_UART ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_UART ')];assert len(rows)==1
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))
if __name__=='__main__':main()
