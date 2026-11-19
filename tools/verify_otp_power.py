"""Test optional OTP power ownership without OTP bytes, programming, or hardware access."""
import argparse
import json
from pathlib import Path
from native_replay import IMAGE
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute

DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallG2StartupFixture,BlackwallPeripheralPower
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];p=g.OtpPower;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():
    return (None if p is None else (p.Phase,p.RequestWord,p.StatusWord,p.Requests,p.Responses),g.DevicePowerReads,g.DevicePowerWrites,g.GpuPower.RequestWord,g.AdcPower.RequestWord,g.UartPowers[1].RequestWord,g.UartPowers[1].Phase,g.Mspi1Power.RequestWord,g.Mspi1Power.Phase)
def blocked(n,fn):
    old=state();count=g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount==count+1)
if p is None:
    blocked('default-OTP-still-unknown',lambda:g.WriteDoubleWord(0x20004,0x08000000))
else:
    check('explicit-mask',p.Mask==0x08000000 and p.Phase=='off')
    blocked('unready-OTP-request',lambda:g.WriteDoubleWord(0x20004,0x08000000))
    check('seed-UART1',g.UartPowers[1].TryWrite(0x400,True));g.UartPowers[1].ReadStatus()
    blocked('unready-preserves-UART1',lambda:g.WriteDoubleWord(0x20004,0x08000400))
    check('local-ready-input-request',p.TryWrite(0x08000000,True))
    check('combined-request-no-status',g.ReadDoubleWord(0x20004)==0x08000400 and p.StatusWord==0)
    check('first-response',g.ReadDoubleWord(0x20008)==(0x08000400 if p.Profile==1 else 0x400) and p.Responses==1)
    g.ReadDoubleWord(0x20008);check('response-once',p.Responses==1)
    g.WriteDoubleWord(0x20004,0x08000400);check('same-word-no-restart',p.Requests==1)
    blocked('reserved-bit-atomic',lambda:g.WriteDoubleWord(0x20004,0x88000400))
    blocked('two-changes-atomic',lambda:g.WriteDoubleWord(0x20004,0))
    blocked('crypto-remains-unknown',lambda:g.WriteDoubleWord(0x20004,0x08200400))
    blocked('no-OTP-register-access',lambda:b.ReadDoubleWord(0x40014aa0))
    if p.Profile==1:blocked('OTP-off-not-implemented',lambda:g.WriteDoubleWord(0x20004,0x400))
    else:
        g.WriteDoubleWord(0x20004,0x400);check('cancel-stuck-preserves-UART',p.Phase=='cancelled' and g.UartPowers[1].RequestWord==0x400)
    g.Reset();check('owner-reset',p.Phase=='off' and p.RequestWord==p.StatusWord==p.Requests==p.Responses==0)
    check('pending-for-cancel',p.TryWrite(0x08000000,True));g.WriteDoubleWord(0x20004,0);check('pending-cancel',p.Phase=='cancelled')
    prerequisites=dict(powerMode='lp',startupControls=True,spotStorage=True,halStorage=True,buckOverrideStorage=True,buckStartStorage=True,coreLdoReduction=True,memLdoSetup=True,buckResponse=3,vddfTempcoStorage=True,mcuClockResponse=0,gfxPowerStorage=True,hfrcForceControl=True,gpuPowerPreparation=True,gpuPowerResponse=1,adcCalibrationControl=True,adcPowerResponse=1)
    for mask,off in [(0x8000,-1),(0x08000000,0),(0x08000000,1)]:
        try:BlackwallG2StartupFixture(0x23000,0x40001000,otpPower=BlackwallPeripheralPower(mask,1,off),**prerequisites)
        except Exception as e:check('invalid-owner-'+str(mask)+'-'+str(off),'OTP requires matching mask' in str(e))
        else:raise Exception('invalid OTP owner accepted')
    try:BlackwallG2StartupFixture(0x23000,0x40001000,otpPower=BlackwallPeripheralPower(0x08000000,1))
    except Exception as e:check('shared-bank-required','OTP requires matching mask' in str(e))
    else:raise Exception('OTP owner without shared bank accepted')
Console.WriteLine('BLACKWALL_OTP_POWER_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='local ready mocks and shared bank; no OTP data/fuses/crypto/hardware')))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--response',choices=['active','stuck-off','unknown'],default='active')
    a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    board=(s/'mspi1-rx-stream-main-01/stock24/board.repl').read_text()
    if a.response!='unknown':
        board=board.replace('    baseAddress: 0x40001000\n','    baseAddress: 0x40001000\n    otpPower: otp_power\n')
        board+='\notp_power: Miscellaneous.BlackwallPeripheralPower @ none\n    mask: 0x08000000\n    profile: '+str(int(a.response=='active'))+'\n'
    (o/'board.repl').write_text(board);(o/'strict.cs').write_bytes(models(s));(o/'test.py').write_text(DRIVER)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "OTP-power"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_OTP_POWER_UNIT ')]
    if len(rows)!=1:raise ValueError('Missing OTP power result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
