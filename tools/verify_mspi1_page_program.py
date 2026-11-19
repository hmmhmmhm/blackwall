"""Exercise TX FIFO, wrapped page programming and device WIP on local NOR RAM."""
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
    for flag in ['disabled', 'read-only', 'protected', 'stuck', 'reset-pending', 'reset-wire', 'abort-wire', 'no-four-byte', 'streaming', 'hold-next']:
        p.add_argument('--' + flag, action='store_true')
    a = p.parse_args()
    s, o = a.simulator, a.output
    o.mkdir(mode=0o700)
    board = (s / 'mspi1-erase-main-01/stock24/board.repl').read_text()
    if not a.read_only:
        board += '    allowPageProgram: true\n'
    if not a.disabled:
        needle = '    profile: "idle-nor-reset"\n'
        if board.count(needle) != 1:
            raise ValueError('Unexpected PIO owner')
        board = board.replace(needle, needle + '    pageProgramMicroseconds: 100\n    completePageProgram: ' + str(not a.stuck).lower() + '\n')
    if a.protected:
        board = board.replace('    statusByte: 64\n', '    statusByte: 68\n')
    (o / 'board.repl').write_text(board)
    (o / 'strict.cs').write_bytes(models(s))
    (o / 'spin.bin').write_bytes(struct.pack('<II', 0x20001000, 0x10009) + bytes.fromhex('fee7'))
    setup = SETUP.replace('checks=[]', 'checks=[]\nc=g.Mspi1Config\nc.AttachRetentionPower(p)').replace('i.Status,i.Writes)', 'i.Status,i.Writes,q.TxEntries,q.TxFifoWrites,q.PageProgramStarts,q.PageProgramCompletions)') + HELPERS + ADDRESS_HELPERS + """
backing=q.ArrayBacking
def peek(address,length=4):
    ok,data=backing.TryRead(address,length)
    if not ok:raise Exception('peek out of range')
    return [int(x) for x in data]
def pp_start(address=0x1fc10fe,length=7):
    status_config();b.WriteDoubleWord(0x40061004,0);b.WriteDoubleWord(0x40061008,address)
    b.WriteDoubleWord(0x4006100c,2);b.WriteDoubleWord(0x40061000,(length<<16)|0xe1)
def tx(word):b.WriteDoubleWord(0x40061010,word)
check('initial-erased-page',peek(0x1fc1000)==[255]*4)
blocked('idle-TX-write-unknown',lambda:tx(0))
en4b()
"""
    steps = [(10, "check('four-byte-mode',q.FourByteAddressMode)\nblocked('PP-needs-WEL',pp_start)\nwren()\n")]
    if a.no_four_byte:
        setup = setup.replace('\nen4b()\n', '\nwren()\n')
        steps = [(10, "check('WEL-not-address-mode',q.WriteEnabled and not q.FourByteAddressMode)\nblocked('PP-needs-four-byte-mode',pp_start)\n")]
    elif a.disabled or a.read_only or a.protected:
        steps += [(10, "blocked('PP-policy-remains-guarded',pp_start)\ncheck('guarded-PP-no-content-change',peek(0x1fc1000)==[255]*4 and q.PageProgramStarts==q.PageProgramCompletions==0)\n")]
    elif a.hold_next:
        steps += [(10, """def reject_fault(name):
    before=(q.ProgramCompletionHeld,q.HeldProgramCompletions,q.PageProgramStarts,q.PageProgramCompletions)
    try:q.HoldNextProgramCompletion()
    except Exception:pass
    else:raise Exception('accepted '+name)
    check(name,before==(q.ProgramCompletionHeld,q.HeldProgramCompletions,q.PageProgramStarts,q.PageProgramCompletions))
check('fault-default-off',not q.ProgramCompletionHeld and q.HeldProgramCompletions==0)
q.HoldNextProgramCompletion()
check('fault-armed-once',q.ProgramCompletionHeld and q.HeldProgramCompletions==0)
reject_fault('duplicate-arm-denied')
q.Reset()
check('reset-disarms-unused-fault',not q.ProgramCompletionHeld and q.HeldProgramCompletions==0)
en4b()
"""), (10, 'wren()\n'),
                  (10, "q.HoldNextProgramCompletion()\npp_start(0x1fc3000,4);tx(0x44332211)\nreject_fault('wire-busy-arm-denied')\n"),
                  (10, """check('one-fault-consumed',not q.ProgramCompletionHeld and q.HeldProgramCompletions==1 and q.ProgramBusy and q.PageProgramStarts==1)
check('held-program-not-durable',q.PageProgramCompletions==0 and peek(0x1fc3000)==[255]*4 and q.CurrentStatusByte==0x43)
reject_fault('device-busy-arm-denied')
"""),
                  (1000, """check('held-past-deadline',q.ProgramBusy and q.PageProgramCompletions==0 and peek(0x1fc3000)==[255]*4)
g.Reset();backing.Reset()
check('reset-clears-held-operation',not q.ProgramBusy and not q.ProgramCompletionHeld and q.HeldProgramCompletions==0 and peek(0x1fc3000)==[255]*4)
ready();en4b()
"""), (10, 'wren()\n'),
                  (10, 'pp_start(0x1fc3000,4);tx(0x44332211)\n'),
                  (10, "check('next-operation-not-held',q.ProgramBusy and q.HeldProgramCompletions==0)\n"),
                  (100, "check('normal-after-reset',not q.ProgramBusy and q.PageProgramCompletions==1 and peek(0x1fc3000)==[17,34,51,68])\n")]
    elif a.streaming:
        steps += [(10, "pp_start(0x1fc2000,256)\nfor n in range(16):tx(0x0f0f0f0f)\ncheck('TX-capacity16',q.TxEntries==16 and b.ReadDoubleWord(0x40061018)==16)\nblocked('full-TX-FIFO-not-overwritten',lambda:tx(0))\n")]
        for block in range(4):
            code = "check('stream-drain-" + str(block) + "',q.TxEntries==0 and q.PageProgramStarts==" + str(int(block == 3)) + ')\n'
            if block < 3:
                code += 'for n in range(16):tx(0x0f0f0f0f)\n'
            steps.append((10, code))
        steps += [(100, "check('full-page-programmed',q.PageProgramCompletions==1 and peek(0x1fc2000,256)==[15]*256 and not q.WriteEnabled)\n")]
    else:
        steps += [(10, """for address,length in [(0x1fbffff,1),(0x1ff8000,1),(0xffffffff,1),(0x1fc1000,0),(0x1fc1000,257)]:
    blocked('PP-range-'+str(address)+'-'+str(length),lambda address=address,length=length:pp_start(address,length))
pp_start()
check('start-waits-for-data',q.Busy and q.TxEntries==0 and not q.ProgramBusy)
"""),
                  (10, "check('missing-TX-does-not-program',q.Busy and not q.ProgramBusy and q.PageProgramStarts==0 and peek(0x1fc1000)==[255]*4)\ntx(0x04030201)\n"),
                  (10, "check('partial-data-stays-controller-busy',q.Busy and q.TxEntries==0 and q.PageProgramStarts==0)\ntx(0xa9070605)\n"),
                  (10, """check('wire-complete-starts-device-program',not q.Busy and q.ProgramBusy and q.PageProgramStarts==1 and q.PageProgramCompletions==0 and q.CurrentStatusByte==0x43)
check('content-before-device-complete',peek(0x1fc1000)==[255]*4)
blocked('extra-TX-after-frame',lambda:tx(0))
status_start()
"""),
                  (10, """check('RDSR-program-busy',b.ReadDoubleWord(0x40061014)==0x43)
check('controller-off-while-device-programs',p.TryWrite(0,True,p.CanShutdown()));p.ReadStatus()
check('off-keeps-program-busy',q.ProgramBusy and peek(0x1fc1000)==[255]*4)
""")]
        if a.reset_wire:
            us, code = steps[3]
            steps = steps[:3] + [(us, code + "g.Reset();backing.Reset()\ncheck('wire-reset-clears-queued-and-staged-TX',not q.Busy and q.TxEntries==q.TxFifoWrites==q.PageProgramStarts==0)\nready();en4b()\n"),
                                (10, 'wren()\n'),
                                (10, 'pp_start(0x1fc3000,4);tx(0x44332211)\n'),
                                (10, "check('new-program-after-wire-reset',q.ProgramBusy and q.PageProgramStarts==1)\n"),
                                (100, "check('wire-reset-does-not-replay-old-bytes',q.PageProgramCompletions==1 and peek(0x1fc3000)==[17,34,51,68] and peek(0x1fc1000)==[255]*4 and peek(0x1fc10fe,2)==[255]*2)\n")]
        elif a.abort_wire:
            us, code = steps[2]
            steps = steps[:2] + [(us, code + 'g.WriteDoubleWord(0x3110,0xa4214);g.WriteDoubleWord(0x3110,0xa4234)\n'),
                                (10, "check('wire-abort-no-program',q.Aborted==1 and not q.Busy and q.TxEntries==0 and q.PageProgramStarts==0 and q.WriteEnabled and peek(0x1fc1000)==[255]*4)\n")]
        elif a.reset_pending:
            steps += [(1, "g.Reset();backing.Reset()\n"), (200, "check('reset-cancels-pending-program',not q.ProgramBusy and q.PageProgramCompletions==0 and peek(0x1fc1000)==[255]*4)\n")]
        elif a.stuck:
            steps += [(1000, "check('stuck-program-never-commits',q.ProgramBusy and q.CurrentStatusByte==0x43 and q.PageProgramCompletions==0 and peek(0x1fc1000)==[255]*4)\n")]
        else:
            steps += [(89, "check('program-not-early',q.ProgramBusy and peek(0x1fc1000)==[255]*4)\n"),
                      (1, """check('program-commits-and-clears-WEL',not q.ProgramBusy and not q.WriteEnabled and q.PageProgramCompletions==1 and q.CurrentStatusByte==0x40)
check('device-program-complete-has-no-controller-IRQ',not i.IRQ.IsSet)
check('page-wrap-and-TX-byte-order',peek(0x1fc10fe,2)==[1,2] and peek(0x1fc1000,5)==[3,4,5,6,7])
check('partial-word-padding-not-programmed',peek(0x1fc1005,1)==[255] and peek(0x1fc10fd,1)==[255])
p.TryWrite(0x8000,True);p.ReadStatus();wren()
"""),
                      (10, "pp_start();tx(0xffffffff);tx(0xffffffff)\n"),
                      (10, "check('second-program-started',q.ProgramBusy and q.PageProgramStarts==2)\n"),
                      (100, "check('program-cannot-restore-zero-bits',q.PageProgramCompletions==2 and peek(0x1fc1000,5)==[3,4,5,6,7] and peek(0x1fc10fe,2)==[1,2])\ng.Reset();backing.Reset()\ncheck('reset-preserves-programmed-bytes',q.PageProgramCompletions==0 and peek(0x1fc1000,5)==[3,4,5,6,7])\n")]
    (o / 'setup.py').write_text(setup)
    resc = 'include @/work/strict.cs\nmach create "page-program"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
    for n, (us, code) in enumerate(steps):
        (o / f'phase-{n}.py').write_text(code)
        (o / f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(' + str(us) + '))\n')
        resc += f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
    (o / 'result.py').write_text("Console.WriteLine('BLACKWALL_PROGRAM_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='local NOR RAM; bounded FIFO/page program, no physical timing or power-loss proof')))\n")
    (o / 'probe.resc').write_text(resc + 'include @/work/result.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={o},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], o, 'renode')
    matches = [json.loads(l.split(' ', 1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_PROGRAM_UNIT ')]
    if len(matches) != 1:
        raise ValueError('Missing program result; inspect preserved log')
    (o / 'report.json').write_text(json.dumps(matches[0], indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=matches[0]['count'])))


if __name__ == '__main__':
    main()
