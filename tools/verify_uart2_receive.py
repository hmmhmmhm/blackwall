"""Bounded opt-in UART2 FIFO input using the existing PL011 adapter."""
import argparse,json,shutil
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
def bind_uart2_receive(source):
 old='if(receiveFifo && (module!=0 || !interrupts))throw new System.ArgumentException("RX FIFO requires interrupt-enabled UART0");'
 new='if(receiveFifo && ((module!=0 && module!=2) || !interrupts))throw new System.ArgumentException("RX FIFO requires interrupt-enabled UART0 or UART2");'
 if new in source:return source
 if source.count(old)!=1:raise ValueError('Unique UART FIFO profile gate required')
 return source.replace(old,new)
DRIVER='''import clr,json
from System import Array,Byte,Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallUartAdapter').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallUartAdapter
m=monitor.Machine;checks=[];base=0x4003b000
u=BlackwallUartAdapter(m,True,2,txInterruptQuirks=False,receiveFifo=True)
def check(n,v):
 if not v:raise Exception(n)
 checks.append(n)
def rx(values,power=True):return u.TryReceive(Array[Byte](values),power)
def w(off,value):return u.TryWrite(base+off,value,True)
def r(off):
 ok,value=u.TryRead(base+off,True)
 if not ok:raise Exception('read rejected')
 return int(value)
check('reset-input-denied',not rx([1]) and u.RxPending==0)
for off,value in [(0x24,13),(0x28,1),(0x2c,0x70),(0x34,0x12),(0x30,0x319),(0x38,0)]:check('setup-'+str(off),w(off,value))
check('off-denied',not rx([1],False) and u.RxPending==0)
check('empty-denied',not rx([]) and u.RxPending==0)
check('fifo32',rx(list(range(32))) and u.RxPending==32 and u.RxBytesInjected==32)
check('overflow-atomic',not rx([99]) and u.RxPending==32 and u.RxBytesInjected==32)
check('flags-nonempty',r(0x18)&0x10==0)
check('fifo-order',list(r(0) for unused in range(32))==list(range(32)) and u.RxBytesRead==32 and u.RxPending==0)
check('flags-empty',r(0x18)&0x10!=0)
check('empty-read-denied',not u.TryRead(base,True)[0])
check('masked-no-irq',not u.IRQ.IsSet)
check('power-pending',rx([1,2,3]));u.PowerDown();check('power-discards',u.RxPending==0 and u.RxDiscardedBytes==3)
u.Reset();check('reset-counters',u.RxPending==0 and u.RxBytesInjected==u.RxBytesRead==0)
legacy=BlackwallUartAdapter(m,True,2,txInterruptQuirks=False)
check('default-off',not legacy.ReceiveFifo and not legacy.TryReceive(Array[Byte]([1]),True))
for module in (1,3):
 try:BlackwallUartAdapter(m,True,module,receiveFifo=True)
 except Exception:check('unsupported-module-'+str(module),True)
 else:raise Exception('unsupported module accepted')
try:BlackwallUartAdapter(m,True,2,receiveFifo=True,receiveTimeout=True)
except Exception:check('uart2-no-hardware-timeout-profile',True)
else:raise Exception('unsupported timeout accepted')
Console.WriteLine('BLACKWALL_UART2_RX '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='UART2 opt-in clean-byte FIFO32; not electrical/case/physical timing validation')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists() or not o.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 o.mkdir(mode=0o700);shutil.copyfile(ROOT/'tools/renode-strict-mmio.cs',o/'strict.cs');(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "uart2-rx"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'native',timeout=120)
 rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_UART2_RX ')];r=rows[0] if len(rows)==1 else dict(passed=False)
 (o/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
if __name__=='__main__':main()
