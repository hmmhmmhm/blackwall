"""Distinguish PL011 enable compatibility IRQs from actual TX/FIFO causes."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute

DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallUartAdapter').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallUartAdapter
m=monitor.Machine;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
for module in range(4):
    u=BlackwallUartAdapter(m,True,module) if BASELINE else BlackwallUartAdapter(m,True,module,txInterruptQuirks=False)
    base=int(u.BaseAddress)
    for offset,value in [(0x2c,0x70),(0x24,1),(0x28,40),(0x44,0x20),(0x38,0x20)]:check('config-'+str(module)+'-'+str(offset),u.TryWrite(base+offset,value,True))
    check('pre-enable-no-cause-'+str(module),u.RawInterrupts==0 and not u.IRQ.IsSet)
    check('enable-'+str(module),u.TryWrite(base+0x30,0x319,True))
    check('no-new-TX-cause-on-enable-'+str(module),u.RawInterrupts&0x20==0 and not u.IRQ.IsSet)
    check('explicit-profile-'+str(module),not u.TxInterruptQuirks and u.TxEnableQuirkSuppressions==1)
    check('actual-byte-still-raises-TX-'+str(module),u.TryWrite(base,65+module,True) and list(u.TxBytes)==[65+module] and u.RawInterrupts&0x21==0x21 and u.IRQ.IsSet)
    before=int(u.TxEnableQuirkSuppressions);u.TryWrite(base+0x30,0x318,True);u.TryWrite(base+0x30,0x319,True)
    check('pending-TX-not-erased-'+str(module),u.RawInterrupts&0x20==0x20 and u.IRQ.IsSet and u.TxEnableQuirkSuppressions==before)
    u.TryWrite(base+0x44,0x20,True);u.TryWrite(base+0x38,1,True);u.TryWrite(base+0x30,0x318,True);u.TryWrite(base+0x30,0x319,True)
    check('TX-complete-not-erased-'+str(module),u.RawInterrupts==1 and u.IRQ.IsSet and u.TxEnableQuirkSuppressions==before+1)
    u.TryWrite(base+0x44,1,True);u.TryWrite(base+0x38,0x20,True);u.TryWrite(base+0x2c,0x60,True)
    check('FIFO-event-still-raises-TX-'+str(module),u.RawInterrupts&0x20==0x20 and u.IRQ.IsSet)
    u.PowerDown();check('powerdown-policy-preserved-'+str(module),not u.TxInterruptQuirks and not u.IRQ.IsSet and u.RawInterrupts==0)
    u.Reset();check('reset-policy-preserved-'+str(module),not u.TxInterruptQuirks and u.TxEnableQuirkSuppressions==0 and u.RawInterrupts==0)
    legacy=BlackwallUartAdapter(m,True,module);legacy.TryWrite(base+0x2c,0x70,True);legacy.TryWrite(base+0x38,0x20,True);legacy.TryWrite(base+0x30,0x319,True)
    check('legacy-default-unchanged-'+str(module),legacy.TxInterruptQuirks and legacy.RawInterrupts&0x20==0x20 and legacy.IRQ.IsSet)
Console.WriteLine('BLACKWALL_UART_ENABLE_IRQ '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False,Apollo_TX_event_timing_verified=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args();o=a.output;o.mkdir(mode=0o700)
    (o/'strict.cs').write_bytes(Path(__file__).with_name('renode-strict-mmio.cs').read_bytes());(o/'test.py').write_text(DRIVER.replace('BASELINE',str(a.baseline)));(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "UART-enable-IRQ"\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_UART_ENABLE_IRQ ')]
    if len(rows)!=1:raise ValueError('Missing UART enable marker; inspect native log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))

if __name__=='__main__':main()
