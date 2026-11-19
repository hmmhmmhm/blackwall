"""Test explicit local UART gating versus final HCPA domain power-down."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models
from verify_uart_hcpa import uart0_board

DRIVER='''import json,clr
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallUartPower').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallUartPower,BlackwallG2StartupFixture
m=monitor.Machine;g=m['sysbus.guard'];b=m.SystemBus;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
p=g.UartPowers[0];peer=g.UartPowers[1];u=g.Uarts[0]
baseline=BASELINE
stuck=STUCK
def write(power,value,ready,quiet,held):
    if baseline:return power.TryWrite(value,ready,quiet)
    return power.TryWriteShared(value,ready,quiet,held)
check('UART0-ready',p.TryWrite(0x200,True))
check('domain-on',b.ReadDoubleWord(0x40021008)&0x1e00==0x1e00)
check('peer-ready',peer.TryWrite(0x400,True))
b.ReadDoubleWord(0x40021008)
for off,val in [(0x24,13),(0x2c,0x70),(0x38,0x1fd0),(0x44,0xffffffff),(0x30,0)]:
    check('setup-'+str(off),u.TryWrite(0x40039000+off,val,True))
check('quiescent',u.Quiescent)
check('gate-request',write(p,0,True,u.Quiescent,True))
check('shared-port-gated-without-poll',p.Phase=='gated' and p.RequestWord==0 and p.StatusWord==0)
check('domain-held',b.ReadDoubleWord(0x40021008)&0x1e00==0x1e00)
check('no-reset-while-peer-on',u.PowerDowns==0 and u.TryRead(0x40039024,True)[1]==13 and u.InterruptMask==0x1fd0)
check('unready-reopen-rejected',not write(p,0x200,False,True,True) and p.Phase=='gated')
check('reopen-no-domain-cycle',write(p,0x200,True,True,True) and p.Phase=='on' and p.RequestWord==p.StatusWord==0x200)
check('reopen-retains-registers',u.PowerDowns==0 and u.TryRead(0x40039024,True)[1]==13 and u.InterruptMask==0x1fd0)
check('unsafe-gate-rejected',not write(p,0,True,False,True) and p.Phase=='on')
check('gate-again',write(p,0,True,True,True) and p.Phase=='gated')
check('peer-last-off',write(peer,0,True,True,False) and peer.Phase=='off-requested')
if stuck:
    check('stuck-domain-stays-on',b.ReadDoubleWord(0x40021008)&0x1e00==0x1e00 and peer.Phase=='stuck-on')
    check('stuck-domain-does-not-reset-gated',p.Phase=='gated' and u.PowerDowns==0 and u.InterruptMask==0x1fd0 and u.TryRead(0x40039024,True)[1]==13)
    check('unconfirmed-domain-reopen-rejected',not write(p,0x200,True,True,False) and p.Phase=='gated')
else:
    check('whole-domain-off',b.ReadDoubleWord(0x40021008)&0x1e00==0)
    check('gated-ports-reset-with-last-user',p.Phase=='powered-off' and peer.Phase=='powered-off' and u.PowerDowns==1 and g.Uarts[1].PowerDowns==1 and u.InterruptMask==0 and u.TryRead(0x40039024,True)[1]==0)
    check('cold-reenable',write(p,0x200,True,True,False) and p.Phase=='requested')
    check('cold-status',b.ReadDoubleWord(0x40021008)&0x1e00==0x1e00 and p.Phase=='on')
g.Reset()
check('reset-state',all(g.UartPowers[i].Phase=='off' and g.UartPowers[i].RequestWord==0 and g.Uarts[i].PowerDowns==0 for i in range(4)))
check('profile-preserved',g.UartHcpaGate)
for module in range(4):
    item=BlackwallUartPower(1,0,module);item.TryWrite(item.Mask,True);item.ReadStatus()
    check('module-gate-'+str(module),item.TryWriteShared(0,True,True,True) and item.Phase=='gated')
    check('module-restore-'+str(module),item.TryWriteShared(item.Mask,True,True,True) and item.Phase=='on' and not item.CompleteSharedPowerOff())
    item=BlackwallUartPower(1,-1,module);item.TryWrite(item.Mask,True);item.ReadStatus()
    check('unknown-off-profile-rejected-'+str(module),not item.TryWriteShared(0,True,True,True) and item.Phase=='on')
try:BlackwallG2StartupFixture(0x30000,0x40001000,uartHcpaGate=True)
except Exception as e:check('gate-without-shared-status-rejected','HCPA gate requires shared HCPA status' in str(e))
else:raise Exception('gate without shared status accepted')
Console.WriteLine('BLACKWALL_UART_HCPA_GATE '+json.dumps(dict(passed=True,count=len(checks),checks=checks,stuck_last_off=stuck,hardware_accessed=False,retention_hardware_verified=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');p.add_argument('--stuck-last-off',action='store_true');p.add_argument('--regression',choices=['uart','status']);a=p.parse_args();s,o=a.simulator,a.output
    if a.regression and (a.baseline or a.stuck_last_off):p.error('regression excludes gate test flags')
    o.mkdir(mode=0o700)
    board=uart0_board((s/'missing-font-header-main-01/stock24-low/board.repl').read_text(),True)+'    idleDmaInterrupts: true\n'
    if not (a.baseline or a.regression):board=board.replace('    uartHcpaStatus: true\n','    uartHcpaStatus: true\n    uartHcpaGate: true\n')
    if a.stuck_last_off:
        if board.count('    uart1OffResponse: 0\n')!=1:raise ValueError('Unexpected UART1 off profile')
        board=board.replace('    uart1OffResponse: 0\n','    uart1OffResponse: 1\n')
    driver=DRIVER.replace('BASELINE',str(a.baseline)).replace('STUCK',str(a.stuck_last_off));marker='BLACKWALL_UART_HCPA_GATE '
    if a.regression=='uart':
        from verify_uart1_adapter import DRIVER as driver
        marker='BLACKWALL_UART '
    elif a.regression=='status':
        from verify_uart_hcpa import DRIVER as driver
        marker='BLACKWALL_UART_HCPA '
    (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board);(o/'test.py').write_text(driver);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "HCPA-gate"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(marker)]
    if len(rows)!=1:raise ValueError('Missing gate marker; inspect native log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))

if __name__=='__main__':main()
