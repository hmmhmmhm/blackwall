"""Verify optional MSPI0 ownership and atomic shared-bank rejection, offline only."""
import argparse
import json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from mspi1_power_board import attach

ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallG2StartupFixture,BlackwallPeripheralPower
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];p=g.Mspi0Power;q=g.Mspi1Power;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():
    return (p.Phase,p.RequestWord,p.StatusWord,p.Requests,p.Responses,p.Generation,q.Phase,q.RequestWord,q.StatusWord,q.Requests,q.Responses,g.DevicePowerReads,g.DevicePowerWrites,tuple((x.Key,x.Value.RequestWord,x.Value.StatusWord,x.Value.Phase) for x in g.UartPowers),g.GpuPower.RequestWord,g.AdcPower.RequestWord)
def blocked(n,fn):
    before=state();count=g.AccessCount
    try:fn()
    except Exception as error:
        if 'BLACKWALL unsupported' not in str(error):raise
    else:raise Exception(n+' accepted')
    check(n,before==state() and g.AccessCount==count+1)
check('mspi0-explicit-mask',p is not None and p.Mask==0x4000 and q.Mask==0x8000)
blocked('rail-prerequisite',lambda:g.WriteDoubleWord(0x20004,0x4000))
# These are explicit unit ready-input mocks. Native runs initialize through original ARM.
check('mock-uart-ready',g.UartPowers[1].TryWrite(0x400,True));g.UartPowers[1].ReadStatus()
check('mock-mspi1-ready',q.TryWrite(0x8000,True));q.ReadStatus()
check('mock-mspi0-request',p.TryWrite(0x4000,True))
check('combined-enable',g.ReadDoubleWord(0x20004)==0xc400 and p.Phase=='requested')
check('combined-status',g.ReadDoubleWord(0x20008)==0xc400 and p.Phase=='on' and p.Responses==1)
check('status-idempotent',g.ReadDoubleWord(0x20008)==0xc400 and p.Responses==1)
g.WriteDoubleWord(0x20004,0xc400);check('same-word-idempotent',p.Requests==q.Requests==1)
blocked('reserved-bit-atomic',lambda:g.WriteDoubleWord(0x20004,0x1c400))
blocked('two-domain-change-atomic',lambda:g.WriteDoubleWord(0x20004,0x400))
blocked('shutdown-without-contract',lambda:g.WriteDoubleWord(0x20004,0x8400))
blocked('bus-remains-guarded',lambda:g.ReadDoubleWord(0x5f000))
g.Reset();check('reset-both-domains',p.Phase==q.Phase=='off' and p.RequestWord==q.RequestWord==0)
check('mock-cancel-request',p.TryWrite(0x4000,True));g.WriteDoubleWord(0x20004,0)
check('cancel-pending',p.Phase=='cancelled' and p.StatusWord==p.RequestWord==0)
stuck=BlackwallPeripheralPower(0x4000,0);check('mock-stuck-request',stuck.TryWrite(0x4000,True))
check('stuck-status',stuck.ReadStatus()==0 and stuck.Phase=='stuck-off')
prerequisites=dict(powerMode='lp',startupControls=True,spotStorage=True,halStorage=True,buckOverrideStorage=True,buckStartStorage=True,coreLdoReduction=True,memLdoSetup=True,buckResponse=3,vddfTempcoStorage=True,mcuClockResponse=0,gfxPowerStorage=True,hfrcForceControl=True,gpuPowerPreparation=True,gpuPowerResponse=1,adcCalibrationControl=True,adcPowerResponse=1)
valid=BlackwallPeripheralPower(0x4000,1);owner=BlackwallG2StartupFixture(0x23000,0x40001000,mspi0Power=valid,**prerequisites)
check('isolated-owner',owner.Mspi0Power==valid)
for mask,off in [(0x8000,-1),(0x10000,-1),(0x4000,0),(0x4000,1)]:
    try:BlackwallG2StartupFixture(0x23000,0x40001000,mspi0Power=BlackwallPeripheralPower(mask,1,off),**prerequisites)
    except Exception as error:check('bad-owner-'+str(mask)+'-'+str(off),'MSPI0 requires matching mask' in str(error))
    else:raise Exception('invalid MSPI0 owner accepted')
try:BlackwallG2StartupFixture(0x23000,0x40001000,mspi0Power=BlackwallPeripheralPower(0x4000,1))
except Exception as error:check('shared-bank-required','MSPI0 requires matching mask' in str(error))
else:raise Exception('owner without ADC/GPU accepted')
Console.WriteLine('BLACKWALL_MSPI0_POWER_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False)))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve()
    if o.exists():raise ValueError('Fresh evidence directory required')
    old=(s/'mspi1-source-research-01/base-core.cs').read_bytes();frozen=(s/'stimer-clock-main-01/stock24/strict.cs').read_bytes()
    if not frozen.startswith(old):raise ValueError('Changed fixed unit source')
    board=attach((s/'stimer-clock-main-01/stock24/board.repl').read_text(),'active')
    needle='    mspi1Power: mspi1_power\n'
    if board.count(needle)!=1:raise ValueError('Missing shared bank anchor')
    board=board.replace(needle,needle+'    mspi0Power: mspi0_power\n')+'\nmspi0_power: Miscellaneous.BlackwallPeripheralPower @ none\n    mask: 0x4000\n    profile: 1\n'
    o.mkdir(mode=0o700);(o/'strict.cs').write_bytes((ROOT/'tools/renode-strict-mmio.cs').read_bytes()+frozen[len(old):])
    (o/'board.repl').write_text(board);(o/'test.py').write_text(DRIVER)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "mspi0-power-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=None)
    rows=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_MSPI0_POWER_UNIT ')]
    if len(rows)!=1:raise ValueError('Missing MSPI0 unit result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))


if __name__=='__main__':main()
