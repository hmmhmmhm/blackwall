"""Exercise the inherited IOM FIFO with a bounded, explicit IMU identity peer."""
import argparse
import json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute

ROOT = Path(__file__).resolve().parents[1]
DRIVER = '''import json
from System import Console,Array,Byte
m=monitor.Machine;i=m['sysbus.iom'];p=m['sysbus.iom.peer'];b=m.SystemBus;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def w(o,v):b.WriteDoubleWord(0x40054000+o,v)
def r(o):return b.ReadDoubleWord(0x40054000+o)
def blocked(n,fn,operation):
    old=(p.Pointer,p.PointerWrites,p.IdentityReads,p.ReturnedBytes,p.Finishes)
    access=i.AccessCount
    try:fn()
    except Exception as e:
        if 'Blackwall unsupported IOM' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,i.AccessCount==access+1 and i.LastOperation==operation and old==(p.Pointer,p.PointerWrites,p.IdentityReads,p.ReturnedBytes,p.Finishes))
check('initial',p.Pointer==-1 and p.PointerWrites==p.IdentityReads==0)
check('power',i.Power.TryWrite(32,True) and i.Power.ReadStatus()==32)
w(0x118,1);w(0x11c,0x10);w(0x2c0,0x23040);w(0x2c4,0x69);w(0x200,1)
blocked('unselected-read',lambda:p.Read(1),'peer-read')
for data in [[],[0],[0x7f],[0x72,0x81],[0x72,0,0]]:
    blocked('invalid-write-'+str(data),lambda data=data:p.Write(Array[Byte](data)),'peer-write')
w(0x10c,0x72);w(0x120,0x101)
check('register-select',p.Pointer==0x72 and p.PointerWrites==1 and p.Finishes==1 and i.Commands==1)
check('write-completion',r(0x204)&1 and i.IRQ.IsSet and r(0x12c)&31==0)
w(0x208,0x7fff)
check('cleared',not i.IRQ.IsSet and r(0x204)==0)
blocked('wrong-read-length',lambda:p.Read(4),'peer-read')
w(0x120,0x102)
check('read-completion',i.Commands==2 and p.IdentityReads==1 and p.ReturnedBytes==1 and p.Finishes==2 and i.IRQ.IsSet)
check('backend-word-padding',r(0x100)>>16&255==4)
check('identity-word',r(0x108)==0x81 and r(0x100)>>16&255==0)
blocked('consumed-response',lambda:p.Read(1),'peer-read')
check('no-cq',not i.CommandQueue.Enabled and i.CommandQueue.Pairs==0)
i.ResetThroughInterface()
check('controller-reset-independent',p.IdentityReads==1 and p.Pointer==0x72)
p.Reset()
check('peer-reset',p.Pointer==-1 and p.PointerWrites==p.IdentityReads==p.ReturnedBytes==p.Finishes==0)
blocked('post-reset-read',lambda:p.Read(1),'peer-read')
p.Write(Array[Byte]([0x72]))
check('reselect-after-reset',list(p.Read(1))==[0x81] and p.IdentityReads==1)
Console.WriteLine('BLACKWALL_IMU_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False,scope='Explicit WHOAMI fixture and inherited I2C backend; no real IMU/reset/config')))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--reset-board', action='store_true')
    p.add_argument('--extended-observer', action='store_true')
    a = p.parse_args()
    a.output.mkdir(mode=0o700)
    source = (a.simulator / 'mspi0-rx-main-01/stock24/strict.cs').read_text()
    if a.extended_observer:
        old=(a.simulator/'imu-i2cm-research-01/observer-4096.cs').read_text()
        if source.count(old)!=1:raise ValueError('Changed observer baseline')
        source=source.replace(old,(ROOT/'tools/renode-execution-observer.cs').read_text())
    addon = ROOT / 'tools/renode-imu-identity.cs'
    if addon.exists():
        source += '\n' + addon.read_text()
    (a.output / 'strict.cs').write_text(source)
    (a.output / 'board.repl').write_text('power: Miscellaneous.BlackwallPeripheralPower\n    mask: 32\n    profile: 1\n    offProfile: 0\niom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40054000\n    power: power\n    module: 4\npeer: Miscellaneous.BlackwallImuIdentity @ iom 0x69\n    owner: iom\n    profile: "icm45608-whoami-only"\n')
    if a.reset_board:
        with (a.output / 'board.repl').open('a') as stream:
            stream.write('reset_peer: Miscellaneous.BlackwallImuIdentity @ none\n    owner: iom\n    profile: "icm45608-reset-lifecycle"\n    identityByte: 129\n    initialInterface: 165\n    initialDrive: 90\n')
    (a.output / 'test.py').write_text(DRIVER)
    (a.output / 'probe.resc').write_text('include @/work/strict.cs\nmach create "imu-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={a.output},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], a.output, 'renode')
    rows = [json.loads(x.split(' ', 1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_IMU_UNIT ')]
    if len(rows) != 1:
        raise ValueError('Missing IMU unit result; inspect preserved log')
    (a.output / 'report.json').write_text(json.dumps(rows[0], indent=2) + '\n')
    print(json.dumps(dict(passed=rows[0]['passed'], count=rows[0]['count'])))


if __name__ == '__main__':
    main()
