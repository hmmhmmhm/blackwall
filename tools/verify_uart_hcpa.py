"""Test opt-in UART HCPA shared status without firmware or devices."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models


def uart0_board(text,shared):
    needle='    uart1: uart1_adapter\n'
    if text.count(needle)!=1 or 'uart0_adapter:' in text:raise ValueError('Unexpected UART0 board')
    text=text.replace(needle,'    uart0: uart0_adapter\n    uart0PowerResponse: 1\n    uart0OffResponse: 0\n'+('    uartHcpaStatus: true\n' if shared else '')+needle)
    return text+'\nuart0_adapter: Miscellaneous.BlackwallUartAdapter\n    module: 0\n    interrupts: true\n    IRQ -> nvic@15\n'


DRIVER='''import json,clr
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallG2StartupFixture
m=monitor.Machine;g=m['sysbus.guard'];b=m.SystemBus;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
shared=g.UartHcpaStatus
check('four-explicit-ports',g.Uarts.Count==4 and g.UartPowers[0].Mask==0x200)
check('UART0-map-IRQ',g.Uarts[0].BaseAddress==0x40039000 and g.Uarts[0].IrqNumber==15)
check('all-off',b.ReadDoubleWord(0x40021008)&0x1e00==0)
check('synthetic-ready-UART0',g.UartPowers[0].TryWrite(0x200,True))
check('UART0-request-only',b.ReadDoubleWord(0x40021004)&0x1e00==0x200)
check('UART0-status-domain',b.ReadDoubleWord(0x40021008)&0x1e00==(0x1e00 if shared else 0x200))
check('inactive-logical-port-stays-off',g.UartPowers[1].RequestWord==0 and g.UartPowers[1].Phase=='off')
check('no-fabricated-UART1-request',g.UartPowers[1].Requests==0 and g.UartPowers[1].Responses==0)
check('synthetic-ready-UART1',g.UartPowers[1].TryWrite(0x400,True))
check('two-requests',b.ReadDoubleWord(0x40021004)&0x1e00==0x600)
check('two-status',b.ReadDoubleWord(0x40021008)&0x1e00==(0x1e00 if shared else 0x600))
check('off-UART0-local-quiescent-mock',g.UartPowers[0].TryWrite(0,True,True))
check('one-left-domain-on',b.ReadDoubleWord(0x40021008)&0x1e00==(0x1e00 if shared else 0x400))
check('off-resets-only-UART0',g.Uarts[0].PowerDowns==1 and g.Uarts[1].PowerDowns==0)
check('off-UART1-local-quiescent-mock',g.UartPowers[1].TryWrite(0,True,True))
check('last-off-domain',b.ReadDoubleWord(0x40021008)&0x1e00==0)
check('off-resets-UART1',g.Uarts[1].PowerDowns==1)
old=[g.UartPowers[i].Responses for i in range(4)];b.ReadDoubleWord(0x40021008)
check('read-does-not-repeat-transitions',old==[g.UartPowers[i].Responses for i in range(4)])
check('reenable-UART0',g.UartPowers[0].TryWrite(0x200,True))
check('reenable-domain',b.ReadDoubleWord(0x40021008)&0x1e00==(0x1e00 if shared else 0x200))
g.Reset();check('reset-preserves-profile',g.UartHcpaStatus==shared and all(g.UartPowers[i].RequestWord==g.UartPowers[i].StatusWord==0 for i in range(4)))
for mask in [0x200,0x400,0x800,0x1000]:
    check('GPU-seed',g.GpuPower.TryWrite(0x40000,True));g.GpuPower.ReadStatus()
    module={0x200:0,0x400:1,0x800:2,0x1000:3}[mask];g.UartPowers[module].TryWrite(mask,True)
    check('non-UART-status-preserved-'+str(module),b.ReadDoubleWord(0x40021008)==0x40000+(0x1e00 if shared else mask))
    g.Reset()
try:BlackwallG2StartupFixture(0x30000,0x40001000,uartHcpaStatus=True)
except Exception as e:check('incomplete-profile-rejected','HCPA status requires four explicit UART adapters' in str(e))
else:raise Exception('incomplete HCPA profile accepted')
Console.WriteLine('BLACKWALL_UART_HCPA '+json.dumps(dict(passed=True,count=len(checks),checks=checks,shared=shared,scope='synthetic per-port power/quiescence mocks and shared readback; not physical domain proof')))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--independent',action='store_true');a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(uart0_board((s/'missing-font-header-main-01/stock24-low/board.repl').read_text(),not a.independent));(o/'test.py').write_text(DRIVER)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "UART-HCPA-status"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_UART_HCPA ')]
    if len(rows)!=1:raise ValueError('Missing HCPA unit marker; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'],shared=rows[0]['shared'])))


if __name__=='__main__':main()
