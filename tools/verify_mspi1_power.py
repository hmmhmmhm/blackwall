"""Verify shared power ownership and rejection, with explicit local ready-input mocks."""
import argparse,json
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
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];tail=m['sysbus.guard_iom7_tail'];p=g.Mspi1Power;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():
    return (p.Phase,p.RequestWord,p.StatusWord,p.Requests,p.Responses,p.OffRequests,p.PowerCycles,g.DevicePowerWrites,g.DevicePowerReads,tuple((u.Key,u.Value.RequestWord,u.Value.StatusWord,u.Value.Phase,u.Value.Requests,u.Value.Responses) for u in g.UartPowers),tuple((i.Key,i.Value.RequestWord,i.Value.StatusWord,i.Value.Phase) for i in g.IomPowers),g.GpuPower.RequestWord,g.AdcPower.RequestWord)
def blocked(n,fn):
    old=state();count=g.AccessCount+tail.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,old==state() and g.AccessCount+tail.AccessCount==count+1)
check('mspi1-owner-mask',p is not None and p.Mask==0x8000 and p.RequestWord==p.StatusWord==0)
blocked('unready-main-rail-blocked',lambda:g.WriteDoubleWord(0x20004,0x8000))
blocked('unselected-mspi0-blocked',lambda:g.WriteDoubleWord(0x20004,0x4000))
# Standalone bank test seeds only its ready-input mocks. Native prefix tests do not seed these.
check('mock-uart-ready',g.UartPowers[1].TryWrite(0x400,True));g.UartPowers[1].ReadStatus()
check('mock-mspi-ready',p.TryWrite(0x8000,True))
check('combined-request-read',g.ReadDoubleWord(0x20004)==0x8400 and p.Phase=='requested')
check('first-status-response',g.ReadDoubleWord(0x20008)==0x8400 and p.Phase=='on' and p.Responses==1)
check('repeat-status-is-not-new-response',g.ReadDoubleWord(0x20008)==0x8400 and p.Responses==1)
g.WriteDoubleWord(0x20004,0x8400);check('same-word-idempotent',p.Requests==1 and g.UartPowers[1].RequestWord==0x400)
blocked('unknown-bit-atomic',lambda:g.WriteDoubleWord(0x20004,0xc400))
blocked('two-domain-change-atomic',lambda:g.WriteDoubleWord(0x20004,0))
blocked('no-shutdown-proof',lambda:g.WriteDoubleWord(0x20004,0x400))
blocked('bus-mspi-register-still-strict',lambda:b.ReadDoubleWord(0x40061000))
g.Reset();check('owner-reset',p.Phase=='off' and p.RequestWord==p.StatusWord==p.Requests==p.Responses==0 and g.UartPowers[1].RequestWord==0)
check('mock-request-for-cancellation',p.TryWrite(0x8000,True));g.WriteDoubleWord(0x20004,0);check('cancel-pending-domain',p.Phase=='cancelled' and p.RequestWord==0)
stuck=BlackwallPeripheralPower(0x8000,0);check('mock-stuck-request',stuck.TryWrite(0x8000,True));check('stuck-never-becomes-ready',stuck.ReadStatus()==0 and stuck.Phase=='stuck-off' and stuck.Responses==1)
check('stuck-cancel',stuck.TryWrite(0,True) and stuck.Phase=='cancelled')
prerequisites=dict(powerMode='lp',startupControls=True,spotStorage=True,halStorage=True,buckOverrideStorage=True,buckStartStorage=True,coreLdoReduction=True,memLdoSetup=True,buckResponse=3,vddfTempcoStorage=True,mcuClockResponse=0,gfxPowerStorage=True,hfrcForceControl=True,gpuPowerPreparation=True,gpuPowerResponse=1,adcCalibrationControl=True,adcPowerResponse=1)
valid=BlackwallPeripheralPower(0x8000,1);owner=BlackwallG2StartupFixture(0x23000,0x40001000,mspi1Power=valid,**prerequisites);check('isolated-valid-owner',owner.Mspi1Power==valid)
for mask in [0x4000,0x10000]:
    try:BlackwallG2StartupFixture(0x23000,0x40001000,mspi1Power=BlackwallPeripheralPower(mask,1),**prerequisites)
    except Exception as e:check('wrong-mask-or-owner-'+str(mask),'MSPI1 requires matching mask' in str(e))
    else:raise Exception('invalid owner accepted')
try:BlackwallG2StartupFixture(0x23000,0x40001000,mspi1Power=BlackwallPeripheralPower(0x8000,1))
except Exception as e:check('shared-bank-prerequisite-required','MSPI1 requires matching mask' in str(e))
else:raise Exception('owner without GPU/ADC accepted')
Console.WriteLine('BLACKWALL_MSPI1_POWER_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='shared bank/local ready-input mocks; no MSPI bus, physical rail or original main')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve()
 if o.exists():raise ValueError('Fresh output required')
 old=(s/'mspi1-source-research-01/base-core.cs').read_bytes();frozen=(s/'stimer-clock-main-01/stock24/strict.cs').read_bytes();core=(ROOT/'tools/renode-strict-mmio.cs').read_bytes()
 if not frozen.startswith(old):raise ValueError('Frozen core differs')
 o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(core+frozen[len(old):]);(o/'board.repl').write_text(attach((s/'stimer-clock-main-01/stock24/board.repl').read_text(),'active'));(o/'test.py').write_text(DRIVER);compile(DRIVER,'test.py','exec');(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "mspi1-power"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_MSPI1_POWER_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_POWER_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing MSPI1 unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
