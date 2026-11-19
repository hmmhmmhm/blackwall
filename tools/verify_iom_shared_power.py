"""Renode device lifecycle tests; no original firmware is executed."""
import argparse
import json
from pathlib import Path

from probe_runtime_reconnect import build
from iom_shared_power_model import compose,board_profile
from native_replay import IMAGE
from run_renode_m55_probe import execute

DRIVER='''
import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallPeripheralPower').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallPeripheralPower
m=monitor.Machine;g=m['sysbus.guard'];checks=[]
def check(n,v):
 if not v:raise ValueError(n)
 checks.append(n)
for module in range(8):
 mask=1<<(module+1);p=BlackwallPeripheralPower(mask,1,0,True);events=[]
 from System import Action
 p.PoweredOff+=Action(lambda:events.append(True))
 check('domain-'+str(module),p.IomDomainMask==(0x1e if module<4 else 0x1e0))
 check('on-'+str(module),p.TryWrite(mask,True) and p.ReadStatus()==mask)
 check('busy-gate-'+str(module),not p.TryWriteIomShared(0,True,False,True) and p.Phase=='on')
 check('gate-'+str(module),p.TryWriteIomShared(0,True,True,True) and p.Phase=='gated' and p.RequestWord==p.StatusWord==0 and events==[])
 check('unready-reopen-'+str(module),not p.TryWriteIomShared(mask,False,True,True))
 check('busy-reopen-'+str(module),not p.TryWriteIomShared(mask,True,False,True))
 check('no-domain-reopen-'+str(module),not p.TryWriteIomShared(mask,True,True,False))
 check('reopen-'+str(module),p.TryWriteIomShared(mask,True,True,True) and p.Phase=='on' and p.ReadStatus()==mask and events==[])
 check('gate-again-'+str(module),p.TryWriteIomShared(0,True,True,True))
 check('last-off-'+str(module),p.CompleteIomSharedPowerOff() and p.Phase=='powered-off' and events==[True] and p.PowerCycles==1)
 check('no-double-off-'+str(module),not p.CompleteIomSharedPowerOff() and events==[True])
 check('cold-restart-'+str(module),p.TryWrite(mask,True) and p.ReadStatus()==mask)
 p.Reset();check('reset-'+str(module),p.Phase=='off' and p.PowerCycles==0 and p.SharedIomGate)
for profile in (-1,1):
 p=BlackwallPeripheralPower(0x80,1,profile,True);p.TryWrite(0x80,True);p.ReadStatus()
 v=p.TryWriteIomShared(0,True,True,True)
 check('no-gate-profile-'+str(profile),p.Phase!='gated' and v==(profile==1))
for mask in (1,0x200,0x4000):
 try:BlackwallPeripheralPower(mask,1,0,True)
 except Exception:check('wrong-domain-'+str(mask),True)
 else:raise ValueError('Non-IOM gate accepted')
p=BlackwallPeripheralPower(0x80,1,0);p.TryWrite(0x80,True);p.ReadStatus()
check('default-off-disable',p.TryWriteIomShared(0,True,True,True) and p.Phase=='off-requested')
check('default-off-restart-denied',not p.TryWriteIomShared(0x80,True,True,True))
for stuck in (False,True):
 g.Reset();p=g.IomPowers[6];peer=g.IomPowers[4];other=g.IomPowers[2]
 for v in (p,peer,other):v.TryWrite(v.Mask,True);v.ReadStatus()
 i=m['sysbus.iom6'];i.WriteDoubleWord(0x118,1);before=int(i.PowerDowns)
 check('actual-gate-'+str(stuck),p.TryWriteIomShared(0,True,bool(i.Quiescent),True))
 check('gate-retains-register-'+str(stuck),i.ClockConfiguration==1 and i.PowerDowns==before)
 if stuck:
  # Explicit failed last-user response with a peer in the same modeled group.
  peer=BlackwallPeripheralPower(0x20,1,1,True);g.IomPowers[4]=peer;peer.TryWrite(0x20,True);peer.ReadStatus()
 check('last-peer-off-'+str(stuck),peer.TryWrite(0,True,True))
 g.ReadDoubleWord(0x20008)
 if stuck:check('stuck-retains-gated',p.Phase=='gated' and peer.Phase=='stuck-on' and i.PowerDowns==before)
 else:check('domain-off-resets-gated',p.Phase=='powered-off' and peer.Phase=='powered-off' and other.Phase=='on' and i.PowerDowns==before+1 and i.ClockConfiguration==0)
Console.WriteLine('BLACKWALL_IOM_SHARED_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_firmware_executed=False,ready_and_quiescent_unit_inputs_are_explicit=True,physical_retention_verified=False)))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args()
    build(a.simulator,a.output,1000)
    if not a.baseline:
        path=a.output/'strict.cs';path.write_text(compose(path.read_text()))
        path=a.output/'board.repl';path.write_text(board_profile(path.read_text()))
    (a.output/'test.py').write_text(DRIVER)
    (a.output/'unit.resc').write_text('include @/work/strict.cs\ninclude @/work/activation.cs\nmach create "iom-shared-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/unit.resc'],a.output,'renode',timeout=90)
    rows=[json.loads(l.split('BLACKWALL_IOM_SHARED_UNIT ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_IOM_SHARED_UNIT ')]
    if len(rows)!=1:raise ValueError(log[-2000:])
    (a.output/'unit-report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))


if __name__=='__main__':main()
