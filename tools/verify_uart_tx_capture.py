"""Exercise real UART/DMA classes past the observed4088+21 byte history boundary."""
import argparse
import hashlib
import json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_uart_dma_tx import DRIVER


def digest(data):
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return value


STRESS = '''
u.Reset()
payload=[(index*29+7)&255 for index in range(4088)]
for index,value in enumerate(payload):b.WriteByte(target+index,value)
for offset,value in [(0x2c,0x70),(0x24,1),(0x28,40),(0x30,0x319),(0x38,0x1800),(0x44,0xffffffff)]:
 check('stress-config-'+str(offset),u.TryWrite(base+offset,value,True))
def send(count):
 for offset,value in [(0x44,0xffffffff),(4,0),(0x48,0),(0x4c,target),(0x50,count)]:
  check('stress-prepare-'+str(count)+'-'+str(offset),u.TryWrite(base+offset,value,True))
 return u.TryWrite(base+0x48,10,True)
check('first4088-emitted',send(4088) and list(u.TxBytes)==payload)
if DISABLED:
 check('default4096-budget-preserved',not send(21) and len(u.TxBytes)==4088 and u.DmaTx.Starts==u.DmaTx.Completions==1)
else:
 check('second21-emitted-past-history-budget',send(21))
 check('actual-second-DMA-source-bytes',list(u.DmaTx.Transfers[1].Data)==payload[:21])
 check('bounded-prefix-unchanged',list(u.TxBytes)==payload+payload[:8])
 check('cumulative-count-and-drops',u.TxBytesTotal==4109 and u.TxBytesDropped==13 and u.TxHistoryTruncated)
 check('whole-stream-hash',int(u.TxBytesHash)==HASH4109)
 check('DMA-completion-not-fabricated',u.DmaTx.Starts==u.DmaTx.Completions==2 and u.DmaTx.TransferredBytes==4109 and u.DmaTx.RawInterrupts==0x800 and u.IRQ.IsSet)
 check('PIO-past-history-budget',u.TryWrite(base,0x55,True) and u.TxBytesTotal==4110 and u.TxBytesDropped==14)
 check('PIO-hash-included',int(u.TxBytesHash)==HASH4110)
 before=(int(u.TxBytesTotal),int(u.TxBytesHash),int(u.DmaTx.TransferredBytes))
 check('bad-PIO-denied',not u.TryWrite(base,256,True))
 check('unpowered-PIO-denied',not u.TryWrite(base,1,False))
 check('byte-width-preserved',not u.TryWrite(base+0x50,4096,True))
 check('invalid-calls-do-not-emit',before==(int(u.TxBytesTotal),int(u.TxBytesHash),int(u.DmaTx.TransferredBytes)))
 u.PowerDown();check('powerdown-keeps-history',u.TxBytesTotal==4110 and u.TxBytesDropped==14 and not u.TryWrite(base,1,True))
 u.Reset();check('reset-clears-history-and-hash',u.TxBytesTotal==u.TxBytesDropped==len(u.TxBytes)==0 and not u.TxHistoryTruncated and int(u.TxBytesHash)==14695981039346656037)
Console.WriteLine('BLACKWALL_UART_CAPTURE_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,disabled=DISABLED,original_firmware_executed=False)))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--baseline', action='store_true')
    p.add_argument('--disabled', action='store_true')
    args = p.parse_args()
    s, out = args.simulator, args.output
    if out.exists() or not out.resolve().is_relative_to(s.resolve()):
        raise ValueError('Fresh private output required')
    ref = s / 'sustained-uart-inspection-native-01/stock24'
    model, board = (ref / 'strict.cs').read_text(), (ref / 'board.repl').read_text()
    if not args.baseline:
        from uart_tx_capture_model import component
        old, new = component()
        if model.count(old) != 1:
            raise ValueError('One pinned UART component required')
        model = model.replace(old, new, 1)
        if not args.disabled:
            anchor = 'uart0_adapter: Miscellaneous.BlackwallUartAdapter\n'
            if board.count(anchor) != 1:
                raise ValueError('One UART0 adapter required')
            board = board.replace(anchor, anchor + '    boundedTxCapture: true\n', 1)
    payload = bytes((i * 29 + 7) & 255 for i in range(4088))
    code = DRIVER.split("Console.WriteLine('BLACKWALL_UART_DMA_TX '")[0]
    code = code.replace('STALLED', 'False').replace('BASELINE', 'False') + STRESS
    code = code.replace('DISABLED', repr(args.disabled)).replace('HASH4109', str(digest(payload + payload[:21]))).replace('HASH4110', str(digest(payload + payload[:21] + b'\x55')))
    compile(code, 'capture-unit.py', 'exec')
    out.mkdir(mode=0o700)
    for name, value in [('strict.cs', model), ('board.repl', board), ('test.py', code)]:
        (out / name).write_text(value)
    (out / 'probe.resc').write_text('include @/work/strict.cs\nmach create "uart-history"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={out},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], out, 'renode', timeout=120)
    rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_UART_CAPTURE_UNIT ')]
    if len(rows) != 1:
        raise ValueError('Missing UART history result; inspect saved log')
    rows[0]['pins'] = {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in ['strict.cs', 'board.repl', 'test.py']}
    (out / 'report.json').write_text(json.dumps(rows[0], indent=2) + '\n')
    print(json.dumps(dict(passed=True, checks=rows[0]['count'])))


if __name__ == '__main__':
    main()
