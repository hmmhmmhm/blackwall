"""Test local sector erase content, WEL/WIP and retained external supply semantics."""
import argparse
import json
import struct
from pathlib import Path
from verify_mspi1_status_byte import SETUP
from verify_mspi1_write_enable import HELPERS
from verify_mspi1_address_mode import ADDRESS_HELPERS
from verify_mspi1_pio_reset import models
from native_replay import IMAGE
from run_renode_m55_probe import execute


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--disabled', action='store_true')
    p.add_argument('--stuck', action='store_true')
    p.add_argument('--read-only', action='store_true')
    p.add_argument('--protected', action='store_true')
    p.add_argument('--reset-pending', action='store_true')
    p.add_argument('--abort-wire', action='store_true')
    p.add_argument('--no-four-byte', action='store_true')
    a = p.parse_args()
    s, o = a.simulator, a.output
    o.mkdir(mode=0o700)
    board = (s / 'mspi1-array-main-02/stock24/board.repl').read_text()
    board = board.replace('    profile: "erased-range"\n', '    profile: "synthetic-ramp"\n')
    if not a.read_only:
        board += '    allowSectorErase: true\n'
    if not a.disabled:
        needle = '    profile: "idle-nor-reset"\n'
        if board.count(needle) != 1:
            raise ValueError('Unexpected PIO owner')
        board = board.replace(needle, needle + '    sectorEraseMicroseconds: 100\n    completeSectorErase: ' + str(not a.stuck).lower() + '\n')
    if a.protected:
        board = board.replace('    statusByte: 64\n', '    statusByte: 68\n')
    (o / 'board.repl').write_text(board)
    (o / 'strict.cs').write_bytes(models(s))
    (o / 'spin.bin').write_bytes(struct.pack('<II', 0x20001000, 0x10009) + bytes.fromhex('fee7'))
    setup = SETUP.replace('checks=[]', 'checks=[]\nc=g.Mspi1Config\nc.AttachRetentionPower(p)') + HELPERS + ADDRESS_HELPERS + """
backing=q.ArrayBacking
def peek(address):
    ok,data=backing.TryRead(address,4)
    if not ok:raise Exception('peek out of declared range')
    return [int(x) for x in data]
def erase_start(address=0x1fc1123):
    status_config();b.WriteDoubleWord(0x40061004,0);b.WriteDoubleWord(0x40061008,address)
    b.WriteDoubleWord(0x4006100c,0x20);b.WriteDoubleWord(0x40061000,0xe1)
check('initial-synthetic-content',peek(0x1fc1000)==[0,1,2,3])
en4b()
"""
    steps = [(10, "check('four-byte-address-mode',q.FourByteAddressMode)\nblocked('erase-needs-WEL',erase_start)\nwren()\n")]
    if a.disabled or a.read_only or a.protected:
        steps += [(10, "blocked('unsupported-erase-remains-guarded',erase_start)\ncheck('guarded-content-unchanged',peek(0x1fc1000)==[0,1,2,3] and not q.EraseBusy and q.SectorEraseStarts==q.SectorEraseCompletions==0)\n")]
    else:
        steps += [(10, """check('WEL-set-before-erase',q.WriteEnabled)
for address in [0x1fbffff,0x1ff8000,0xffffffff]:
    blocked('erase-range-'+str(address),lambda address=address:erase_start(address))
erase_start()
check('wire-start-is-not-device-erase',q.Busy and not q.EraseBusy and q.SectorEraseStarts==0)
"""),
                  (5, "check('wire-not-early',q.Busy and not q.EraseBusy and peek(0x1fc1000)==[0,1,2,3])\n"),
                  (5, """check('wire-complete-starts-device-WIP',not q.Busy and q.EraseBusy and q.WriteEnabled and q.CurrentStatusByte==0x43 and q.SectorEraseStarts==1 and q.SectorEraseCompletions==0)
check('device-content-not-early',peek(0x1fc1000)==[0,1,2,3])
blocked('WREN-during-erase-unknown',wren)
status_start()
"""),
                  (10, """check('RDSR-during-erase',b.ReadDoubleWord(0x40061014)==0x43 and q.EraseBusy)
check('controller-off-during-external-erase',p.TryWrite(0,True,p.CanShutdown()))
p.ReadStatus()
check('controller-off-keeps-device-busy',p.Phase=='powered-off' and q.EraseBusy and q.WriteEnabled and peek(0x1fc1000)==[0,1,2,3])
""")]
        if a.reset_pending:
            steps += [(1, "g.Reset();backing.Reset()\ncheck('pending-scenario-reset-no-content-change',not q.EraseBusy and peek(0x1fc1000)==[0,1,2,3])\n"),
                      (200, "check('no-stale-erase-event-after-reset',q.SectorEraseCompletions==0 and peek(0x1fc1000)==[0,1,2,3])\n")]
        elif a.stuck:
            steps += [(1000, "check('stuck-device-never-acknowledges',q.EraseBusy and q.WriteEnabled and q.SectorEraseCompletions==0 and peek(0x1fc1000)==[0,1,2,3])\ng.Reset()\ncheck('scenario-reset-cancels-pending-erase',not q.EraseBusy and peek(0x1fc1000)==[0,1,2,3])\n")]
        else:
            steps += [(89, "check('device-not-early-while-controller-off',q.EraseBusy and q.SectorEraseCompletions==0 and peek(0x1fc1000)==[0,1,2,3])\n"),
                      (1, """check('device-erase-completes',not q.EraseBusy and not q.WriteEnabled and q.CurrentStatusByte==0x40 and q.SectorEraseCompletions==1)
check('entire-sector-erased',all(peek(0x1fc1000+n)==[255]*4 for n in range(0,4096,4)))
check('neighbor-sectors-preserved',peek(0x1fc0ffc)==[252,253,254,255] and peek(0x1fc2000)==[0,1,2,3])
check('external-complete-no-controller-IRQ',not i.IRQ.IsSet)
check('restart-controller',p.TryWrite(0x8000,True));p.ReadStatus()
blocked('erase-completion-clears-WEL',erase_start)
g.Reset();backing.Reset()
check('scenario-reset-preserves-committed-NOR',peek(0x1fc1000)==[255]*4 and peek(0x1fc2000)==[0,1,2,3] and q.SectorEraseStarts==q.SectorEraseCompletions==0)
""")]
    if a.no_four_byte:
        if setup.count('\nen4b()\n') != 1:
            raise ValueError('Unexpected address-mode fixture')
        setup = setup.replace('\nen4b()\n', '\nwren()\n')
        steps = [(10, "check('WEL-without-four-byte-mode',q.WriteEnabled and not q.FourByteAddressMode)\nblocked('legacy-SE20-needs-four-byte-mode',erase_start)\ncheck('address-mode-guard-no-side-effects',not q.EraseBusy and q.SectorEraseStarts==0 and q.WriteEnabled and peek(0x1fc1000)==[0,1,2,3])\n")]
    if a.abort_wire:
        us, code = steps[1]
        steps = [steps[0], (us, code + 'g.WriteDoubleWord(0x3110,0xa4214);g.WriteDoubleWord(0x3110,0xa4234)\n'),
                 (10, "check('aborted-wire-starts-no-erase',q.Aborted==1 and not q.Busy and not q.EraseBusy and q.SectorEraseStarts==q.SectorEraseCompletions==0 and q.WriteEnabled and peek(0x1fc1000)==[0,1,2,3])\n")]
    (o / 'setup.py').write_text(setup)
    resc = 'include @/work/strict.cs\nmach create "sector-erase"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
    for n, (us, code) in enumerate(steps):
        (o / f'phase-{n}.py').write_text(code)
        (o / f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(' + str(us) + '))\n')
        resc += f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
    (o / 'result.py').write_text("Console.WriteLine('BLACKWALL_ERASE_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='RAM-backed emulator only; erase latency/power loss not hardware validated')))\n")
    (o / 'probe.resc').write_text(resc + 'include @/work/result.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={o},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], o, 'renode')
    matches = [json.loads(l.split(' ', 1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_ERASE_UNIT ')]
    if len(matches) != 1:
        raise ValueError('Missing erase result; inspect preserved log')
    (o / 'report.json').write_text(json.dumps(matches[0], indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=matches[0]['count'])))


if __name__ == '__main__':
    main()
