"""Exercise controller-only power loss with explicitly retained external NOR supply."""
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

STEPS = [
    (10, """check('WREN-completed',q.WriteEnabled and not q.Busy)
en4b()
"""),
    (10, """check('retained-precondition',q.WriteEnabled and q.FourByteAddressMode)
rdcr()
"""),
    (10, """check('unread-FIFO-rejects-off',q.RxEntries==1 and not c.CanPowerDown() and not p.TryWrite(0,True,c.CanPowerDown()))
check('consume-config',b.ReadDoubleWord(0x40061014)==0x20)
b.WriteDoubleWord(0x40061200,1)
check('pending-IRQ-before-off',i.IRQ.IsSet)
check('idle-allows-off',c.CanPowerDown() and p.TryWrite(0,True,c.CanPowerDown()))
check('request-not-completion',p.Phase=='off-requested' and c.ControllerPowerDowns==0 and q.WriteEnabled and i.IRQ.IsSet)
p.ReadStatus()
if STUCK:
    check('stuck-on-no-controller-reset',p.Phase=='stuck-on' and p.StatusWord==0x8000 and c.ControllerPowerDowns==0 and q.WriteEnabled and q.FourByteAddressMode and i.IRQ.IsSet)
else:
    check('off-response-resets-controller',p.Phase=='powered-off' and p.StatusWord==0 and c.ControllerPowerDowns==1 and q.Control==0 and q.RxEntries==0 and not q.Busy)
    check('off-clears-IRQ',i.Enable==i.Status==0 and not i.IRQ.IsSet)
    check('off-preserves-external-state',q.WriteEnabled and q.FourByteAddressMode and q.CurrentStatusByte==0x42 and q.CurrentConfigurationByte==0x20)
    check('off-preserves-history',q.WriteEnableTransfers==q.Enter4ByteTransfers==q.ConfigurationReadTransfers==1 and q.Completions==3)
    check('off-resets-config-only',c.Values[0x84]==0x20001 and c.CqValues[0x2b0]==0)
    blocked('off-MMIO-stays-guarded',lambda:b.ReadDoubleWord(0x40061000))
    check('power-back-on',p.TryWrite(0x8000,True))
    p.ReadStatus()
    rdcr()
"""),
    (10, """if not STUCK:
    check('NOR-state-readable-after-controller-restart',b.ReadDoubleWord(0x40061014)==0x20 and q.WriteEnabled)
    reset_wire(0x66)
"""),
    (10, """if not STUCK:
    check('reset-enable-before-poweroff',q.ResetArmed)
    check('second-off-request',p.TryWrite(0,True,c.CanPowerDown()))
    p.ReadStatus()
    check('reset-enable-is-external-state',q.ResetArmed and c.ControllerPowerDowns==2)
    p.TryWrite(0x8000,True);p.ReadStatus();reset_wire(0x99)
"""),
    (10, """if not STUCK:
    check('NOR-recovery-rejects-off',q.Recovering and not c.CanPowerDown() and not p.TryWrite(0,True,c.CanPowerDown()))
"""),
    (100, """if not STUCK:
    check('recovery-completes',not q.Recovering and c.CanPowerDown())
g.Reset()
check('global-reset-clears-NOR-and-history',not q.WriteEnabled and not q.FourByteAddressMode and not q.ResetArmed and c.ControllerPowerDowns==q.Completions==0)
"""),
]

RESTORE_CHECKS = """    x=c.XipGuard
    blocked('restore-requires-AXI-ready',lambda:b.WriteDoubleWord(0x40061090,0xed))
    b.WriteDoubleWord(0x40061080,0x19)
    g.WriteDoubleWord(0x3110,0xa4214)
    blocked('restore-clock-off',lambda:b.WriteDoubleWord(0x40061090,0xed))
    g.WriteDoubleWord(0x3110,0xa4234)
    for bad in [0xef,0xe5,0x2ed,0xced]:
        blocked('restore-invalid-fields-'+str(bad),lambda bad=bad:b.WriteDoubleWord(0x40061090,bad))
    check('rejected-restores-do-not-enable',not x.Enabled and c.XipRestoreWrites==0 and c.Values[0x90]==0)
    if RESTORE_DEFAULT:
        blocked('default-atomic-restore-stays-guarded',lambda:b.WriteDoubleWord(0x40061090,0xed))
    else:
        b.WriteDoubleWord(0x40061090,0xed)
        check('atomic-restore-enables-guard-only',x.Enabled and c.Values[0x90]==0xed and c.XipRestoreWrites==1)
        b.WriteDoubleWord(0x40061090,0xec)
        blocked('one-restore-per-power-loss',lambda:b.WriteDoubleWord(0x40061090,0x5ed))
        check('restore-token-not-reused',not x.Enabled and c.XipRestoreWrites==1 and c.Values[0x90]==0xec)
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--stuck', action='store_true')
    parser.add_argument('--unknown', action='store_true')
    parser.add_argument('--wrong-owner', action='store_true')
    restore = parser.add_mutually_exclusive_group()
    restore.add_argument('--xip-restore', action='store_true')
    restore.add_argument('--restore-default', action='store_true')
    args = parser.parse_args()
    s, o = args.simulator, args.output
    o.mkdir(mode=0o700)
    board = (s / 'mspi1-cqflags-main-02/stock24/board.repl').read_text()
    needle = '    mask: 0x8000\n    profile: 1\n'
    if board.count(needle) != 1:
        raise ValueError('Unexpected MSPI power owner')
    if not args.unknown:
        board = board.replace(needle, needle + '    offProfile: ' + str(int(args.stuck)) + '\n')
    if args.xip_restore:
        needle = '    profile: "source-reset-config"\n'
        if board.count(needle) != 1:
            raise ValueError('Unexpected config owner')
        board = board.replace(needle, needle + '    xipRestoreStorage: true\n')
    (o / 'board.repl').write_text(board)
    (o / 'strict.cs').write_bytes(models(s))
    (o / 'spin.bin').write_bytes(struct.pack('<II', 0x20001000, 0x10009) + bytes.fromhex('fee7'))
    attach = '' if args.unknown or args.wrong_owner else 'c.AttachRetentionPower(p)\n'
    setup = SETUP.replace('checks=[]', 'checks=[]\nc=g.Mspi1Config\n' + attach)
    setup += HELPERS + ADDRESS_HELPERS + 'STUCK=' + str(args.stuck) + '\n'
    if args.wrong_owner:
        setup += """import clr
clr.AddReference(p.GetType().Assembly)
from System import ArgumentException
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallPeripheralPower
other=BlackwallPeripheralPower(0x8000,1,0)
rejected=False
try:c.AttachRetentionPower(other)
except ArgumentException:rejected=True
check('wrong-power-owner-rejected',rejected and other.ShutdownReady is None and not p.CanShutdown())
g.Reset()
c.AttachRetentionPower(p)
check('real-owner-attaches-after-rejection',p.CanShutdown() and c.CanPowerDown())
duplicate=False
try:c.AttachRetentionPower(p)
except ArgumentException:duplicate=True
check('duplicate-owner-rejected',duplicate)
"""
        steps = []
    elif args.unknown:
        setup += "check('unknown-off-stays-blocked',not p.TryWrite(0,True,p.CanShutdown()) and p.Phase=='on')\n"
        steps = []
    else:
        setup += "check('attachment-shutdown-ready',p.CanShutdown())\nwren()\ncheck('busy-off-before-completion',not c.CanPowerDown() and not p.TryWrite(0,True,c.CanPowerDown()))\n"
        steps = list(STEPS)
        if args.xip_restore or args.restore_default:
            setup += 'RESTORE_DEFAULT=' + str(args.restore_default) + '\n'
            us, code = steps[2]
            needle = '    rdcr()\n'
            if code.count(needle) != 1:
                raise ValueError('Unexpected restart fixture')
            steps[2] = us, code.replace(needle, RESTORE_CHECKS + needle)
            us, code = steps[-1]
            steps[-1] = us, code + "check('global-reset-clears-restore-token',c.XipRestoreWrites==0)\nready()\nb.WriteDoubleWord(0x40061080,0x19)\nblocked('global-reset-revokes-atomic-restore',lambda:b.WriteDoubleWord(0x40061090,0xed))\n"
    (o / 'setup.py').write_text(setup)
    resc = 'include @/work/strict.cs\nmach create "mspi-power-off"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
    for n, (us, code) in enumerate(steps):
        (o / f'phase-{n}.py').write_text(code)
        (o / f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(' + str(us) + '))\n')
        resc += f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
    (o / 'result.py').write_text("Console.WriteLine('BLACKWALL_MSPI_POWER_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='controller-only digital power loss with retained external supply hypothesis; no physical proof')))\n")
    (o / 'probe.resc').write_text(resc + 'include @/work/result.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={o},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], o, 'renode')
    rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines()
            if line.startswith('BLACKWALL_MSPI_POWER_UNIT ')]
    if len(rows) != 1:
        raise ValueError('Missing power lifecycle result; inspect preserved log')
    (o / 'report.json').write_text(json.dumps(rows[0], indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=rows[0]['count'])))


if __name__ == '__main__':
    main()
