"""Test bounded logical QREAD4B and FIFO ordering without inventing device contents."""
import argparse
import json
import struct
from pathlib import Path
from verify_mspi1_status_byte import SETUP
from verify_mspi1_pio_reset import models
from native_replay import IMAGE
from run_renode_m55_probe import execute


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--unknown', action='store_true')
    p.add_argument('--stuck', action='store_true')
    p.add_argument('--erased', action='store_true')
    p.add_argument('--no-qe', action='store_true')
    p.add_argument('--busy-seed', action='store_true')
    a = p.parse_args()
    s, o = a.simulator, a.output
    o.mkdir(mode=0o700)
    board = (s / 'mspi1-continuous-status-main-01/stock24/board.repl').read_text()
    if not a.unknown:
        needle = '    profile: "idle-nor-reset"\n'
        if board.count(needle) != 1:
            raise ValueError('Unexpected PIO owner')
        profile = 'erased-range' if a.erased else 'synthetic-ramp'
        board = board.replace(needle, needle + '    arrayBacking: nor_read_window\n')
        board += '\nnor_read_window: Miscellaneous.BlackwallNorReadWindow @ none\n    profile: "' + profile + '"\n    start: 0x1fc0000\n    length: 0x38000\n'
    if a.stuck:
        board = board.replace('    completeTransactions: true\n', '    completeTransactions: false\n')
    if a.no_qe:
        board = board.replace('    statusByte: 64\n', '    statusByte: 0\n')
    if a.busy_seed:
        board = board.replace('    statusByte: 64\n', '    statusByte: 65\n').replace('    emulateWriteEnableLatch: true\n', '    emulateWriteEnableLatch: false\n').replace('    configurationByte: 0\n', '    configurationByte: -1\n')
    (o / 'board.repl').write_text(board)
    (o / 'strict.cs').write_bytes(models(s))
    (o / 'spin.bin').write_bytes(struct.pack('<II', 0x20001000, 0x10009) + bytes.fromhex('fee7'))
    setup = SETUP.replace('i.Status,i.Writes)', 'i.Status,i.Writes,q.ArrayReadTransfers,q.ArrayBytesRead,q.LastArrayAddress)') + """def array_start(address=0x1fc0001,length=7):
    b.WriteDoubleWord(0x40061008,address)
    b.WriteDoubleWord(0x40061000,(length<<16)|0x461)
b.WriteDoubleWord(0x40061084,0x1010861)
b.WriteDoubleWord(0x40061004,5)
b.WriteDoubleWord(0x4006100c,0x6c)
"""
    steps = []
    if a.unknown or a.no_qe or a.busy_seed:
        setup += "blocked('unknown-or-no-QE-no-array',array_start)\n"
    elif a.stuck:
        setup += 'array_start()\n'
        steps = [(1000, "check('stuck-array-no-data',q.Busy and q.ArrayReadTransfers==q.ArrayBytesRead==q.RxEntries==0)\n")]
    else:
        setup += """check('explicit-opcode-needs-no-EN4B',not q.FourByteAddressMode)
for address,length in [(0x1fbffff,1),(0x1ff7ffd,4),(0x1ff8000,1),(0xfffffff8,16),(0x1fc0000,0),(0x1fc0000,65)]:
    blocked('range-or-capacity-'+str(address)+'-'+str(length),lambda address=address,length=length:array_start(address,length))
b.WriteDoubleWord(0x40061004,0)
blocked('array-requires-data-quad',array_start)
b.WriteDoubleWord(0x40061004,5)
b.WriteDoubleWord(0x40061084,0x1010841)
blocked('array-requires-four-address-bytes',array_start)
b.WriteDoubleWord(0x40061084,0x1010861)
for bit in [1,2,4,8,16]:
    b.WriteDoubleWord(0x40061088,0x3820|bit)
    blocked('array-timing-controls-unsupported-'+str(bit),array_start)
b.WriteDoubleWord(0x40061088,0x3820)
b.WriteDoubleWord(0x4006100c,0x6b)
blocked('three-byte-opcode-unsupported',array_start)
b.WriteDoubleWord(0x4006100c,0x6c)
array_start()
check('array-start-not-data',q.Busy and q.RxEntries==q.ArrayReadTransfers==0)
"""
        word1, word2 = ('0xffffffff', '0x00ffffff') if a.erased else ('0x04030201', '0x00070605')
        steps = [(5, "check('array-not-early',q.Busy and q.RxEntries==0)\n"),
                 (5, """check('array-completes-two-words',not q.Busy and q.RxEntries==2 and q.ArrayReadTransfers==1 and q.ArrayBytesRead==7)
blocked('unread-array-not-overwritten',array_start)
check('word1-order',b.ReadDoubleWord(0x40061014)==@WORD1@ and q.RxEntries==1)
check('word2-order-and-zero-padding',b.ReadDoubleWord(0x40061014)==@WORD2@ and q.RxEntries==0)
blocked('empty-array-FIFO',lambda:b.ReadDoubleWord(0x40061014))
array_start(0x1ff7fc0,64)
""".replace('@WORD1@', word1).replace('@WORD2@', word2)),
                 (10, """check('bounded-FIFO-full',q.RxEntries==16)
for n in range(16):
    expected=0xffffffff if ERASED else sum(((0xc0+n*4+k)&255)<<(8*k) for k in range(4))
    check('full-FIFO-word-'+str(n),b.ReadDoubleWord(0x40061014)==expected)
check('full-FIFO-drained',q.RxEntries==0 and q.ArrayBytesRead==71)
array_start(0x1ff7fff,1)
"""),
                 (10, "check('last-byte-in-window',b.ReadDoubleWord(0x40061014)==0xff)\narray_start();g.WriteDoubleWord(0x3110,0xa4214);g.WriteDoubleWord(0x3110,0xa4234)\n"),
                 (10, "check('abort-array-no-data',q.Aborted==1 and q.ArrayReadTransfers==3 and q.ArrayBytesRead==72 and q.RxEntries==0)\narray_start();g.Reset()\n"),
                 (20, "check('reset-clears-pending-array',not q.Busy and q.RxEntries==q.ArrayReadTransfers==q.ArrayBytesRead==0)\n")]
        setup += 'ERASED=' + str(a.erased) + '\n'
    (o / 'setup.py').write_text(setup)
    resc = 'include @/work/strict.cs\nmach create "bounded-array"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
    for n, (us, code) in enumerate(steps):
        (o / f'phase-{n}.py').write_text(code)
        (o / f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(' + str(us) + '))\n')
        resc += f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
    (o / 'result.py').write_text("Console.WriteLine('BLACKWALL_ARRAY_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='explicit read-only range and logical QREAD4B; no device dump or physical lanes')))\n")
    (o / 'probe.resc').write_text(resc + 'include @/work/result.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={o},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], o, 'renode')
    matches = [json.loads(l.split(' ', 1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_ARRAY_UNIT ')]
    if len(matches) != 1:
        raise ValueError('Missing array result; inspect preserved log')
    (o / 'report.json').write_text(json.dumps(matches[0], indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=matches[0]['count'])))


if __name__ == '__main__':
    main()
