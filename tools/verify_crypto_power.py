"""Check explicit CRYPTO power/NVM flags; no engine, keys, OTP bytes or devices."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute

DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallG2StartupFixture,BlackwallPeripheralPower
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];p=g.CryptoPower;o=g.OtpPower;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():
    return (None if p is None else (p.Phase,p.RequestWord,p.StatusWord,p.Requests,p.Responses),o.Phase,o.RequestWord,o.StatusWord,g.CryptoNvmReads,g.DevicePowerReads,g.DevicePowerWrites,g.UartPowers[1].Phase,g.UartPowers[1].RequestWord,g.Mspi1Power.RequestWord)
def blocked(n,fn):
    old=state();count=g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount==count+1)
blocked('unpowered-NVM-unavailable',lambda:b.ReadDoubleWord(0x400c1f10))
if p is None:blocked('default-crypto-still-unknown',lambda:g.WriteDoubleWord(0x20004,0x200000))
else:
    check('explicit-mask',p.Mask==0x200000)
    blocked('no-OTP-ready',lambda:g.WriteDoubleWord(0x20004,0x200000))
    check('seed-OTP-ready',o.TryWrite(0x08000000,True));o.ReadStatus()
    blocked('no-buck-ready',lambda:g.WriteDoubleWord(0x20004,0x08200000))
    check('seed-UART-ready',g.UartPowers[1].TryWrite(0x400,True));g.UartPowers[1].ReadStatus()
    check('local-crypto-request',p.TryWrite(0x200000,True))
    blocked('requested-not-ready-NVM',lambda:b.ReadDoubleWord(0x400c1f10))
    check('combined-request',g.ReadDoubleWord(0x20004)==0x08200400)
    check('combined-status',g.ReadDoubleWord(0x20008)==(0x08200400 if p.Profile==1 else 0x08000400))
    check('response-once',p.Responses==1);g.ReadDoubleWord(0x20008);check('no-repeat-response',p.Responses==1)
    if p.Profile==1 and g.CryptoNvmIdle!=-1:
        check('selected-NVM-bit',b.ReadDoubleWord(0x400c1f10)==g.CryptoNvmIdle and g.CryptoNvmReads==1)
        check('NVM-stable',b.ReadDoubleWord(0x400c1f10)==g.CryptoNvmIdle and g.CryptoNvmReads==2)
    else:blocked('stuck-or-unknown-NVM',lambda:b.ReadDoubleWord(0x400c1f10))
    blocked('NVM-write-not-supported',lambda:b.WriteDoubleWord(0x400c1f10,1))
    blocked('NVM-byte-read',lambda:b.ReadByte(0x400c1f10))
    blocked('other-crypto-register-unknown',lambda:b.ReadDoubleWord(0x400c0000))
    blocked('reserved-atomic',lambda:g.WriteDoubleWord(0x20004,0x88200400))
    blocked('two-changes-atomic',lambda:g.WriteDoubleWord(0x20004,0x400))
    g.WriteDoubleWord(0x20004,0x08200400);check('same-word-idempotent',p.Requests==1)
    if p.Profile==1:blocked('no-crypto-off',lambda:g.WriteDoubleWord(0x20004,0x08000400))
    o.Reset();blocked('NVM-requires-OTP-on',lambda:b.ReadDoubleWord(0x400c1f10))
    g.Reset();check('owner-reset',p.Phase==o.Phase=='off' and p.Requests==p.Responses==g.CryptoNvmReads==0)
    blocked('reset-NVM-blocked',lambda:b.ReadDoubleWord(0x400c1f10))
    prerequisites=dict(powerMode='lp',startupControls=True,spotStorage=True,halStorage=True,buckOverrideStorage=True,buckStartStorage=True,coreLdoReduction=True,memLdoSetup=True,buckResponse=3,vddfTempcoStorage=True,mcuClockResponse=0,gfxPowerStorage=True,hfrcForceControl=True,gpuPowerPreparation=True,gpuPowerResponse=1,adcCalibrationControl=True,adcPowerResponse=1)
    for mask,off,idle in [(0x8000,-1,1),(0x200000,0,1),(0x200000,1,1),(0x200000,-1,2)]:
        try:BlackwallG2StartupFixture(0x23000,0x40001000,otpPower=BlackwallPeripheralPower(0x08000000,1),cryptoPower=BlackwallPeripheralPower(mask,1,off),cryptoNvmIdle=idle,**prerequisites)
        except Exception as e:check('invalid-owner-'+str(mask)+'-'+str(off)+'-'+str(idle),'CRYPTO requires' in str(e))
        else:raise Exception('invalid crypto owner accepted')
    for args in [dict(cryptoPower=BlackwallPeripheralPower(0x200000,1)),dict(cryptoNvmIdle=1)]:
        try:BlackwallG2StartupFixture(0x23000,0x40001000,**dict(prerequisites,**args))
        except Exception as e:check('missing-OTP-or-crypto-owner','CRYPTO requires' in str(e))
        else:raise Exception('owner without prerequisites accepted')
Console.WriteLine('BLACKWALL_CRYPTO_POWER_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='explicit readiness flags/local ready mocks only')))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--response',choices=['active','stuck-off','unknown'],default='active');p.add_argument('--idle',type=int,choices=[-1,0,1],default=1)
    a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    board=(s/'otp-power-main-02/stock24/board.repl').read_text()
    if a.response!='unknown':
        board=board.replace('    baseAddress: 0x40001000\n','    baseAddress: 0x40001000\n    cryptoPower: crypto_power\n    cryptoNvmIdle: '+str(a.idle)+'\n')
        board+='\ncrypto_power: Miscellaneous.BlackwallPeripheralPower @ none\n    mask: 0x200000\n    profile: '+str(int(a.response=='active'))+'\n'
    (o/'board.repl').write_text(board);(o/'strict.cs').write_bytes(models(s));(o/'test.py').write_text(DRIVER)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "crypto-power"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_CRYPTO_POWER_UNIT ')]
    if len(rows)!=1:raise ValueError('Missing crypto power result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
