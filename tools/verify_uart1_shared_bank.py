"""Check UART/GPU/ADC shared-bank rejection using an existing main probe board."""
import argparse
import json
import re
from pathlib import Path

from run_renode_m55_probe import execute

ROOT = Path(__file__).resolve().parents[1]
DRIVER = '''import json
from System import Console
g=monitor.Machine['sysbus.guard']
h=monitor.Machine['sysbus.guard_high']
checks=[]
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
def state():
    return (str(g.GpuPower.Phase),int(g.GpuPower.RequestWord),int(g.GpuPower.StatusWord),
        str(g.AdcPower.Phase),int(g.AdcPower.RequestWord),int(g.AdcPower.StatusWord),
        str(g.UartPowers[1].Phase),int(g.UartPowers[1].RequestWord),int(g.UartPowers[1].StatusWord),
        int(g.DevicePowerReads),int(g.DevicePowerWrites),int(g.UartPowers[1].Requests),int(g.UartPowers[1].Responses),
        int(g.GpuPower.EnableReads),int(g.GpuPower.EnableWrites),int(g.GpuPower.StatusReads),int(g.GpuPower.Transitions),int(g.GpuPower.OffRequests),
        int(g.AdcPower.Requests),int(g.AdcPower.Responses),int(g.AdcPower.Cancellations),int(g.AdcPower.Transitions),int(g.AdcPower.OffRequests),int(g.UartPowers[1].OffRequests),int(g.UartPowers[1].PowerCycles),int(g.Uarts[1].PowerDowns),tuple((int(module),str(g.UartPowers[module].Phase),int(g.UartPowers[module].RequestWord),int(g.UartPowers[module].StatusWord),int(g.UartPowers[module].Requests),int(g.UartPowers[module].Responses),int(g.UartPowers[module].OffRequests),int(g.UartPowers[module].PowerCycles),int(g.Uarts[module].PowerDowns)) for module in g.UartPowers.Keys))
def blocked(name,action):
    before=state()
    access=int(g.AccessCount)+int(h.AccessCount)
    try:action()
    except Exception:pass
    else:raise Exception(name+' accepted')
    check(name,state()==before and int(g.AccessCount)+int(h.AccessCount)==access+1)
check('seed-gpu',g.GpuPower.TryWrite(0x40000,True))
check('seed-adc',g.AdcPower.TryWrite(0x2000,True,False))
check('seed-uart',g.UartPowers[1].TryWrite(0x400,True))
blocked('unknown-request-bit',lambda:g.WriteDoubleWord(0x20004,0x42401))
blocked('two-domain-change',lambda:g.WriteDoubleWord(0x20004,0x40000))
g.WriteDoubleWord(0x20004,0x42000)
check('cancel-uart-preserves-gpu-adc',g.GpuPower.RequestWord==0x40000 and g.AdcPower.RequestWord==0x2000 and g.UartPowers[1].RequestWord==0 and g.UartPowers[1].Phase=='cancelled')
g.WriteDoubleWord(0x20004,0x40000)
check('cancel-adc-preserves-gpu',g.GpuPower.RequestWord==0x40000 and g.AdcPower.RequestWord==0 and g.UartPowers[1].RequestWord==0)
g.WriteDoubleWord(0x20004,0)
check('cancel-gpu',g.GpuPower.RequestWord==0 and g.AdcPower.RequestWord==0 and g.UartPowers[1].RequestWord==0)
g.Reset()
g.GpuPower.TryWrite(0x40000,True);g.GpuPower.ReadStatus()
g.AdcPower.TryWrite(0x2000,True,False);g.AdcPower.TryReadStatus(True)
g.UartPowers[1].TryWrite(0x400,True);g.UartPowers[1].ReadStatus()
check('three-on',g.GpuPower.StatusWord==0x40000 and g.AdcPower.StatusWord==0x2000 and g.UartPowers[1].StatusWord==0x400)
blocked('unknown-on-state',lambda:g.WriteDoubleWord(0x20004,0x42401))
blocked('two-on-domain-change',lambda:g.WriteDoubleWord(0x20004,0x400))
g.Reset()
blocked('high-owner-off',lambda:h.WriteDoubleWord(0x15030,0x319))
check('high-off-control-unchanged',g.Uarts[1].Control==0x300 and g.Uarts[1].TxBytes.Count==0)
blocked('byte-width',lambda:g.WriteByte(0x20004,0))
Console.WriteLine('BLACKWALL_SHARED '+json.dumps(dict(passed=True,checks=checks,assertion_count=len(checks),scope='isolated fixture bank, not firmware or physical power')))
'''

LIFECYCLE = """g.Reset()
g.WriteDoubleWord(0x1f10c,0)
g.GpuPower.TryWrite(0x40000,True);g.GpuPower.ReadStatus()
g.AdcPower.TryWrite(0x2000,True);g.AdcPower.TryReadStatus(True)
g.UartPowers[1].TryWrite(0x400,True);g.UartPowers[1].ReadStatus()
u=g.Uarts[1]
u.TryWrite(0x4003a02c,0x70,True);u.TryWrite(0x4003a030,0x319,True);u.TryWrite(0x4003a038,0x471,True);u.TryWrite(0x4003a000,68,True)
blocked('life-active-off-block',lambda:g.WriteDoubleWord(0x20004,0x42000))
u.TryWrite(0x4003a044,0xffffffff,True);u.TryWrite(0x4003a030,0,True)
g.WriteDoubleWord(0x20004,0x42000)
check('life-fixture-request',g.UartPowers[1].Phase=='off-requested' and g.UartPowers[1].StatusWord==0x400 and u.PowerDowns==0)
blocked('life-off-request-mmio',lambda:h.WriteDoubleWord(0x15030,0x319))
check('life-shared-status',g.ReadDoubleWord(0x20008)==0x42000)
check('life-shared-domain-preserve',g.GpuPower.RequestWord==0x40000 and g.GpuPower.StatusWord==0x40000 and g.AdcPower.RequestWord==0x2000 and g.AdcPower.StatusWord==0x2000)
check('life-fixture-reset',g.UartPowers[1].Phase=='powered-off' and u.Control==0x300 and u.InterruptMask==0 and u.PowerDowns==1 and list(u.TxBytes)==[68])
g.ReadDoubleWord(0x20008)
check('life-powerdown-once',u.PowerDowns==1 and g.UartPowers[1].PowerCycles==1)
blocked('life-off-mmio',lambda:h.WriteDoubleWord(0x15030,0x319))
blocked('life-unready-reenable-fixture',lambda:g.WriteDoubleWord(0x20004,0x42400))
"""

MULTI = """if g.Uarts.ContainsKey(2):
    g.Reset()
    g.UartPowers[1].TryWrite(0x400,True);g.UartPowers[2].TryWrite(0x800,True)
    blocked('multi-two-port-change',lambda:g.WriteDoubleWord(0x20004,0))
    if not g.Uarts.ContainsKey(0):blocked('multi-disabled-port-bit',lambda:g.WriteDoubleWord(0x20004,0xe00))
    blocked('multi-high-owner-unready2',lambda:h.WriteDoubleWord(0x16030,8))
    g.UartPowers[2].ReadStatus()
    h.WriteDoubleWord(0x16030,8)
    check('multi-high-owner2',h.ReadDoubleWord(0x16030)==8 and g.Uarts[2].Control==8 and g.Uarts[1].Control==0x300)
    g.WriteDoubleWord(0x20004,0x800)
    check('multi-cancel1-preserves2',g.UartPowers[1].RequestWord==0 and g.UartPowers[2].RequestWord==0x800 and g.UartPowers[2].StatusWord==0x800 and g.Uarts[2].Control==8)
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--with-lifecycle', action='store_true')
    args = parser.parse_args()
    board = args.board.read_text().replace('BlackwallUart1Adapter','BlackwallUartAdapter')
    driver = DRIVER
    if args.with_lifecycle:
        if board.count('    uart1PowerResponse: 1')!=1:
            raise ValueError('Need active UART1 board')
        if '    uart1OffResponse:' not in board:
            board=board.replace('    uart1PowerResponse: 1','    uart1PowerResponse: 1\n    uart1OffResponse: 0')
        elif board.count('    uart1OffResponse: 0')!=1:raise ValueError('Need successful UART1 off profile')
        match=re.search(r'(?m)^uart1_adapter: [^\n]+\n(?:[ \t]+[^\n]*\n|\n)*',board)
        if not match:raise ValueError('UART1 adapter missing')
        block=re.sub(r'(?m)^    (?:interrupts:.*|IRQ -> .*)\n','',match.group())
        block+='    interrupts: true\n    IRQ -> nvic@16\n'
        board=board[:match.start()]+block+board[match.end():]
        driver=DRIVER.replace("Console.WriteLine('BLACKWALL_SHARED ",LIFECYCLE+MULTI+"Console.WriteLine('BLACKWALL_SHARED ")
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    sources = ['renode-strict-mmio.cs', 'renode-memory-policy.cs',
               'renode-system-control.cs', 'renode-reset-controller.cs', 'renode-watchdog.cs']
    (output/'strict.cs').write_text('\n'.join((ROOT/'tools'/s).read_text() for s in sources))
    (output/'board.repl').write_text(board)
    (output/'test.py').write_text(driver)
    (output/'probe.resc').write_text('include @/work/strict.cs\nmach create "uart-shared"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m',
                   '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL',
                   '--security-opt', 'no-new-privileges', '--mount',
                   f'type=bind,source={output},target=/work,readonly',
                   'blackwall-renode:1.17.0-local', '--disable-gui', '--console',
                   '-p', '-e', 'quit', '/work/probe.resc'], output, 'renode')
    rows = [json.loads(line.split('BLACKWALL_SHARED ', 1)[1])
            for line in log.splitlines() if line.startswith('BLACKWALL_SHARED ')]
    assert len(rows) == 1
    (output/'report.json').write_text(json.dumps(rows[0], indent=2)+'\n')
    print(json.dumps(rows[0]))


if __name__ == '__main__':
    main()
