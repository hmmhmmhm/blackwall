"""Bounded synthetic SRAM DMA-to-UART data/IRQ flow; no physical devices."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute

DRIVER='''import clr,json
from System import Console
m=monitor.Machine;u=m['sysbus.guard'].Uarts[0];b=m.SystemBus;checks=[];base=0x40039000;target=0x20001003
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
for index,value in enumerate([17,34,51]):b.WriteByte(target+index,value)
for offset,value in [(0x2c,0x70),(0x24,1),(0x28,40),(0x30,0x319),(0x38,0x1800),(0x44,0xffffffff)]:
    check('config-'+str(offset),u.TryWrite(base+offset,value,True))
if not BASELINE:check('HAL-priority-before-target',u.TryWrite(base+0x48,8,True))
check('DMA-SRAM-target-supported',u.TryWrite(base+0x4c,target,True))
check('count',u.TryWrite(base+0x50,3,True))
check('priority-is-not-start',u.TryWrite(base+0x48,8,True) and len(u.TxBytes)==0 and not u.IRQ.IsSet)
check('start-TX',u.TryWrite(base+0x48,10,True))
if STALLED:
    check('stall-not-fabricated-completion',u.DmaTx.Busy and u.DmaTx.Starts==1 and u.DmaTx.Completions==0 and len(u.DmaTx.Transfers)==0 and len(u.TxBytes)==0 and u.TryRead(base+4,True)[1]==0 and u.RawInterrupts&0x1800==0 and not u.IRQ.IsSet)
    check('busy-blocks-configuration',not u.TryWrite(base+0x4c,target+1,True) and not u.TryWrite(base+0x50,1,True))
    check('cancel-stall',u.TryWrite(base+0x48,0,True) and not u.DmaTx.Busy and u.DmaTx.Cancellations==1 and len(u.TxBytes)==0)
else:
    check('actual-SRAM-bytes-delivered',list(u.TxBytes)==[17,34,51] and u.DmaTx.TransferredBytes==3)
    check('transfer-record-retains-source-bytes',len(u.DmaTx.Transfers)==1 and u.DmaTx.Transfers[0].Target==target and list(u.DmaTx.Transfers[0].Data)==[17,34,51])
    check('completion-follows-bytes',not u.DmaTx.Busy and u.DmaTx.Starts==u.DmaTx.Completions==1 and u.TryRead(base+4,True)[1]==0x10)
    check('DMA-complete-IRQ',u.MaskedInterrupts==0x800 and u.IRQ.IsSet)
    check('active-registers-immutable',not u.TryWrite(base+0x4c,target+1,True) and not u.TryWrite(base+0x50,1,True))
    check('clear-IRQ-not-status',u.TryWrite(base+0x44,0x800,True) and not u.IRQ.IsSet and u.TryRead(base+4,True)[1]==0x10)
    check('software-clears-status',u.TryWrite(base+4,0,True) and u.TryRead(base+4,True)[1]==0)
    check('stop',u.TryWrite(base+0x48,0,True))
    check('fresh-config-required',not u.TryWrite(base+0x48,10,True) and list(u.TxBytes)==[17,34,51])
    check('status-cannot-be-fabricated',not u.TryWrite(base+4,0x10,True))
    check('mask-off',u.TryWrite(base+0x38,0,True))
    u.TryWrite(base+0x4c,target,True);u.TryWrite(base+0x50,3,True);u.TryWrite(base+0x48,2,True)
    check('masked-raw-DMA-cause-retained',len(u.TxBytes)==6 and u.RawInterrupts&0x800==0x800 and not u.IRQ.IsSet)
    check('unmask-pending-complete',u.TryWrite(base+0x38,0x800,True) and u.IRQ.IsSet)
    u.TryWrite(base+0x44,0xffffffff,True);u.TryWrite(base+4,0,True);u.TryWrite(base+0x48,0,True)
    u.TryWrite(base+0x4c,0x2037ffff,True);u.TryWrite(base+0x50,2,True)
    check('whole-range-validated-before-data',not u.TryWrite(base+0x48,10,True) and len(u.TxBytes)==6)
    check('zero-count-config',u.TryWrite(base+0x50,0,True))
    check('zero-count-cannot-start',not u.TryWrite(base+0x48,10,True))
    b.WriteByte(0x2037ffff,127);u.TryWrite(base+0x50,1,True)
    check('last-SRAM-byte',u.TryWrite(base+0x48,10,True) and list(u.TxBytes)[-1]==127 and u.DmaTx.TransferredBytes==7)
    u.TryWrite(base+0x44,0xffffffff,True);u.TryWrite(base+4,0,True);u.TryWrite(base+0x48,0,True)
for value in [1,3,4,9,12,16]:check('unsupported-control-'+str(value),not u.TryWrite(base+0x48,value,True))
for value in [0,0x1fffffff,0x20380000,0x438000,0x40039000]:check('non-SRAM-target-'+hex(value),not u.TryWrite(base+0x4c,value,True))
check('count-width',not u.TryWrite(base+0x50,4096,True))
check('unpowered-configuration',not u.TryWrite(base+0x4c,target,False))
check('RX-DR-remains-unsupported',not u.TryRead(base,True)[0])
u.PowerDown();check('powerdown-clears-DMA-config',u.TryRead(base+0x48,True)[1]==0 and u.TryRead(base+0x4c,True)[1]==0 and u.TryRead(base+0x50,True)[1]==0 and not u.IRQ.IsSet)
u.Reset();check('reset-counters',u.DmaTx.Starts==u.DmaTx.Completions==u.DmaTx.TransferredBytes==0 and len(u.TxBytes)==0)
Console.WriteLine('BLACKWALL_UART_DMA_TX '+json.dumps(dict(passed=True,count=len(checks),checks=checks,stalled=STALLED,hardware_accessed=False,physical_DMA_timing_verified=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');p.add_argument('--stalled',action='store_true');p.add_argument('--regression',action='store_true');a=p.parse_args();s,o=a.simulator,a.output
    if a.regression and (a.baseline or a.stalled):p.error('regression excludes DMA scenario flags')
    o.mkdir(mode=0o700)
    source=s/'dcache-address-main-01/stock24';model=(source/'strict.cs').read_bytes();board=(source/'board.repl').read_text()
    if not a.baseline:
        old=(s/'source-model-uart-dma-01/base-core.cs').read_bytes();new=Path(__file__).with_name('renode-strict-mmio.cs').read_bytes()
        if not model.startswith(old):raise ValueError('Expected frozen UART baseline core')
        model=new+model[len(old):]+b'\n'+Path(__file__).with_name('renode-uart-dma.cs').read_bytes()
        board=board.replace('    idleDmaInterrupts: true\n','    idleDmaInterrupts: true\n    dmaTx: uart0_dma\n')+'\nuart0_dma: Miscellaneous.BlackwallUartDmaTx\n    profile: "sram-tx-'+('stalled' if a.stalled else 'complete')+'"\n'
    driver=DRIVER.replace('STALLED',str(a.stalled)).replace('BASELINE',str(a.baseline));marker='BLACKWALL_UART_DMA_TX '
    if a.regression:
        from verify_uart1_adapter import DRIVER as driver
        marker='BLACKWALL_UART '
    (o/'strict.cs').write_bytes(model);(o/'board.repl').write_text(board);(o/'test.py').write_text(driver);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "UART-DMA-flow"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(marker)]
    if len(rows)!=1:raise ValueError('Missing DMA unit marker; inspect native log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0].get('count',rows[0].get('assertion_count')),stalled=a.stalled)))

if __name__=='__main__':main()
