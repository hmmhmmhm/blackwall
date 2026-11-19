"""Test opt-in repeated RDSR bytes under a logical SDR transport hypothesis."""
import argparse
import json
import struct
from pathlib import Path
from verify_mspi1_status_byte import SETUP
from verify_mspi1_pio_reset import models
from native_replay import IMAGE
from run_renode_m55_probe import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--disabled', action='store_true')
    parser.add_argument('--busy-seed', action='store_true')
    parser.add_argument('--stuck', action='store_true')
    a = parser.parse_args()
    s, o = a.simulator, a.output
    o.mkdir(mode=0o700)
    board = (s / 'mspi1-xip-restore-main-02/stock24/board.repl').read_text()
    needle = '    profile: "idle-nor-reset"\n'
    if board.count(needle) != 1:
        raise ValueError('Unexpected PIO owner')
    if not a.disabled:
        board = board.replace(needle, needle + '    continuousStatusRead: true\n')
    if a.busy_seed:
        if board.count('    statusByte: 64\n') != 1:
            raise ValueError('Unexpected status seed')
        board = board.replace('    statusByte: 64\n', '    statusByte: 65\n').replace('    emulateWriteEnableLatch: true\n', '    emulateWriteEnableLatch: false\n').replace('    configurationByte: 0\n', '    configurationByte: -1\n')
    if a.stuck:
        board = board.replace('    completeTransactions: true\n', '    completeTransactions: false\n')
    (o / 'board.repl').write_text(board)
    (o / 'strict.cs').write_bytes(models(s))
    (o / 'spin.bin').write_bytes(struct.pack('<II', 0x20001000, 0x10009) + bytes.fromhex('fee7'))
    setup = SETUP.replace('checks=[]', 'checks=[]\nc=g.Mspi1Config\nc.AttachRetentionPower(p)') + """def stream_start(sampling=4):
    b.WriteDoubleWord(0x40061084,0x10861|(sampling<<22))
    b.WriteDoubleWord(0x4006100c,5)
    b.WriteDoubleWord(0x40061000,0x10441)
"""
    steps = []
    if a.disabled:
        setup += "blocked('default-repeated-status-unknown',stream_start)\n"
    elif a.stuck:
        setup += 'stream_start()\n'
        steps = [(1000, "check('stuck-no-status-or-discard',q.Busy and q.StatusReadTransfers==q.ContinuousStatusTransfers==q.StatusDiscardedBytes==q.RxEntries==0)\n")]
    else:
        seed = 65 if a.busy_seed else 64
        setup += """check('continuous-status-selected',q.ContinuousStatusRead and q.StatusDiscardedBytes==0)
for bad in [0x1010761,0x1010961,0x3010861,0x101c861,0x1020861,0x1010865,0x10108e1]:
    b.WriteDoubleWord(0x40061084,bad)
    blocked('bounded-geometry-'+str(bad),lambda:b.WriteDoubleWord(0x40061000,0x10441))
b.WriteDoubleWord(0x40061084,0x1010861)
blocked('wrong-RX-length',lambda:b.WriteDoubleWord(0x40061000,0x20441))
b.WriteDoubleWord(0x4006100c,0x15)
blocked('RDCR-not-enabled-by-RDSR-profile',lambda:b.WriteDoubleWord(0x40061000,0x10441))
stream_start(0)
check('start-does-not-discard-or-return-data',q.Busy and q.StatusDiscardedBytes==q.RxEntries==0)
"""
        steps.append((5, "check('stream-not-early',q.Busy and q.StatusReadTransfers==q.ContinuousStatusTransfers==q.StatusDiscardedBytes==q.RxEntries==0)\n"))
        for sampling in range(8):
            code = "check('sampling-" + str(sampling) + "-completed',not q.Busy and q.ContinuousStatusTransfers==" + str(sampling + 1) + ' and q.StatusDiscardedBytes==' + str(sampling + 1) + ' and q.StatusReadTransfers==' + str(sampling + 1) + ' and q.RxEntries==1)\n'
            code += "blocked('unread-status-not-overwritten-" + str(sampling) + "',lambda:b.WriteDoubleWord(0x40061000,0x10441))\n"
            code += "check('repeated-status-byte-" + str(sampling) + "',b.ReadDoubleWord(0x40061014)==" + str(seed) + ')\n'
            if sampling < 7:
                code += 'stream_start(' + str(sampling + 1) + ')\n'
            steps.append((5 if sampling == 0 else 10, code))
        steps[-1] = steps[-1][0], steps[-1][1] + "stream_start();g.WriteDoubleWord(0x3110,0xa4214);g.WriteDoubleWord(0x3110,0xa4234)\n"
        steps += [(10, """check('aborted-stream-no-discard',q.Aborted==1 and not q.Busy and q.StatusDiscardedBytes==8 and q.ContinuousStatusTransfers==8 and q.RxEntries==0)
check('history-off-request',p.TryWrite(0,True,p.CanShutdown()))
p.ReadStatus()
check('history-preserved-controller-off',p.Phase=='powered-off' and q.StatusDiscardedBytes==q.ContinuousStatusTransfers==q.StatusReadTransfers==8 and q.Aborted==1)
check('history-restart',p.TryWrite(0x8000,True))
p.ReadStatus()
stream_start();g.Reset()
"""),
                  (20, "check('reset-cancels-stream-and-history',not q.Busy and q.StatusDiscardedBytes==q.ContinuousStatusTransfers==q.StatusReadTransfers==q.RxEntries==0)\n")]
    (o / 'setup.py').write_text(setup)
    resc = 'include @/work/strict.cs\nmach create "continuous-status"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
    for n, (us, code) in enumerate(steps):
        (o / f'phase-{n}.py').write_text(code)
        (o / f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(' + str(us) + '))\n')
        resc += f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
    (o / 'result.py').write_text("Console.WriteLine('BLACKWALL_CONTINUOUS_STATUS_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='logical repeated byte, ideal SDR; pin routing and actual sampling unverified')))\n")
    (o / 'probe.resc').write_text(resc + 'include @/work/result.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={o},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], o, 'renode')
    rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_CONTINUOUS_STATUS_UNIT ')]
    if len(rows) != 1:
        raise ValueError('Missing stream result; inspect preserved log')
    (o / 'report.json').write_text(json.dumps(rows[0], indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=rows[0]['count'])))


if __name__ == '__main__':
    main()
