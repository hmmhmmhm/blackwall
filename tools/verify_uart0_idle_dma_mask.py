"""Native reset-idle UART0 mask behavior; no firmware or physical device."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models
from verify_uart_hcpa import uart0_board

DRIVER='''import json,clr
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallUartAdapter').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallUartAdapter
m=monitor.Machine;u=m['sysbus.guard'].Uarts[0];checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
b=0x40039000
check('source-reset-DMA-idle-mask-accepted',u.TryWrite(b+0x38,0x1fd0,True))
check('complete-mask-retained',u.InterruptMask==0x1fd0 and u.InterruptMaskWrites==1)
check('mask-readback',u.TryRead(b+0x38,True)[1]==0x1fd0)
check('DMA-control-remains-reset',u.TryRead(b+0x48,True)[1]==0)
check('RX-data-remains-unsupported',not u.TryRead(b,True)[0])
check('no-DMA-or-RX-IRQ-fabricated',u.RawInterrupts&0x1fd0==0 and u.MaskedInterrupts==0 and not u.IRQ.IsSet)
for value in [1,2,3,8,15]:
    check('DMA-start-or-config-rejected-'+str(value),not u.TryWrite(b+0x48,value,True))
check('DMA-control-zero-accepted',u.TryWrite(b+0x48,0,True))
check('reserved-mask-rejected',not u.TryWrite(b+0x38,0x2000,True) and u.InterruptMask==0x1fd0)
check('unpowered-mask-rejected',not u.TryWrite(b+0x38,0,False) and u.InterruptMask==0x1fd0)
check('clear-upper-does-not-create-events',u.TryWrite(b+0x44,0x1800,True) and u.MaskedInterrupts==0)
check('mask-zero',u.TryWrite(b+0x38,0,True) and u.InterruptMask==0)
check('rearm',u.TryWrite(b+0x38,0x1fd0,True))
u.PowerDown()
check('powerdown-clears-state',u.InterruptMask==0 and u.MaskedInterrupts==0 and not u.IRQ.IsSet)
check('powerdown-retains-profile',u.TryWrite(b+0x38,0x1fd0,True))
u.Reset()
check('reset-clears-state',u.InterruptMask==0 and u.InterruptMaskWrites==0 and not u.IRQ.IsSet)
check('reset-retains-profile',u.TryWrite(b+0x38,0x1800,True))
for module in range(4):
    default=BlackwallUartAdapter(m,True,module)
    check('default-upper-mask-rejected-'+str(module),not default.TryWrite(default.BaseAddress+0x38,0x1800,True))
    check('default-lower-mask-accepted-'+str(module),default.TryWrite(default.BaseAddress+0x38,0x7ff,True))
for module,interrupts in [(0,False),(1,True),(2,True),(3,True)]:
    try:BlackwallUartAdapter(m,interrupts,module,True)
    except Exception as e:check('invalid-profile-rejected-'+str(module),'idle DMA masks require interrupt-enabled UART0' in str(e))
    else:raise Exception('invalid idle profile accepted')
Console.WriteLine('BLACKWALL_UART0_IDLE_MASK '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False,DMA_implemented=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    board=uart0_board((s/'missing-font-header-main-01/stock24-low/board.repl').read_text(),True)
    if not a.baseline:board+='    idleDmaInterrupts: true\n'
    (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board);(o/'test.py').write_text(DRIVER)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "UART0-idle-mask"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_UART0_IDLE_MASK ')]
    if len(rows)!=1:raise ValueError('Missing unit marker; inspect native log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))

if __name__=='__main__':main()
