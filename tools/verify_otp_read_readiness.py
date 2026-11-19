"""Test power-gated read-only readiness flags and a finite busy observation budget."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute

DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallOtpReadReadiness,BlackwallPeripheralPower
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];p=g.OtpReadReadiness;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():return (p.HostReads,p.PtmReads,g.OtpPower.Phase,g.CryptoPower.Phase)
def blocked(n,fn):
    old=state();count=g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount==count+1)
blocked('off-HOST',lambda:b.ReadDoubleWord(0x400c0a7c))
blocked('off-PTM',lambda:b.ReadDoubleWord(0x40014ac4))
check('local-OTP-ready',g.OtpPower.TryWrite(0x08000000,True));g.OtpPower.ReadStatus()
blocked('HOST-needs-crypto',lambda:b.ReadDoubleWord(0x400c0a7c))
check('local-crypto-request',g.CryptoPower.TryWrite(0x200000,True))
blocked('HOST-request-not-status',lambda:b.ReadDoubleWord(0x400c0a7c));g.CryptoPower.ReadStatus()
if p.HostIdle==-1:blocked('unknown-HOST',lambda:b.ReadDoubleWord(0x400c0a7c))
else:
    check('HOST-profile-word',b.ReadDoubleWord(0x400c0a7c)==0x3b8|p.HostIdle)
    check('HOST-repeat',b.ReadDoubleWord(0x400c0a7c)==0x3b8|p.HostIdle and p.HostReads==2)
if p.PtmBusy==-1:blocked('unknown-PTM',lambda:b.ReadDoubleWord(0x40014ac4))
elif p.PtmBusy==0:
    check('clear-PTM',b.ReadDoubleWord(0x40014ac4)==0 and p.PtmReads==1)
else:
    for n in range(p.PtmReadBudget):check('busy-PTM-'+str(n),b.ReadDoubleWord(0x40014ac4)==1)
    blocked('busy-budget-next-read-guard',lambda:b.ReadDoubleWord(0x40014ac4))
    check('budget-exhausted-no-extra-count',p.PtmBudgetExhausted and p.PtmReads==p.PtmReadBudget)
for addr in [0x400c0a7c,0x40014ac4]:
    blocked('write-rejected-'+str(addr),lambda addr=addr:b.WriteDoubleWord(addr,0))
    blocked('byte-width-'+str(addr),lambda addr=addr:b.ReadByte(addr))
blocked('OTP-word-remains-unknown',lambda:b.ReadDoubleWord(0x400c2340))
g.OtpPower.Reset();blocked('HOST-needs-OTP',lambda:b.ReadDoubleWord(0x400c0a7c));blocked('PTM-needs-OTP',lambda:b.ReadDoubleWord(0x40014ac4))
check('OTP-ready-again',g.OtpPower.TryWrite(0x08000000,True));g.OtpPower.ReadStatus();g.CryptoPower.Reset()
blocked('HOST-needs-crypto-again',lambda:b.ReadDoubleWord(0x400c0a7c))
if p.PtmBusy==0:check('PTM-independent-of-crypto',b.ReadDoubleWord(0x40014ac4)==0)
g.Reset();check('counters-reset',p.HostReads==p.PtmReads==0 and not p.PtmBudgetExhausted)
for host,ptm,budget in [(2,-1,0),(-2,-1,0),(-1,2,0),(-1,1,0),(-1,0,1),(-1,1,4097)]:
    try:BlackwallOtpReadReadiness(g.OtpPower,g.CryptoPower,host,ptm,budget)
    except Exception as e:check('invalid-profile-'+str(host)+'-'+str(ptm)+'-'+str(budget),'OTP read readiness' in str(e))
    else:raise Exception('invalid profile accepted')
for otp,cp in [(None,g.CryptoPower),(g.OtpPower,None),(BlackwallPeripheralPower(0x8000,1),g.CryptoPower),(g.OtpPower,BlackwallPeripheralPower(0x8000,1))]:
    try:BlackwallOtpReadReadiness(otp,cp,1,0,0)
    except Exception as e:check('invalid-power-dependency','OTP read readiness' in str(e))
    else:raise Exception('invalid dependency accepted')
Console.WriteLine('BLACKWALL_OTP_READ_READY_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='local power-ready mocks, reset-shaped flags and finite observation budget; no OTP data')))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--host',type=int,choices=[-1,0,1],default=1);p.add_argument('--ptm',type=int,choices=[-1,0,1],default=0);p.add_argument('--budget',type=int,default=0);p.add_argument('--foreign-owner',choices=['otp','crypto']);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    board=(s/'crypto-power-main-01/stock24/board.repl').read_text();board=board.replace('    baseAddress: 0x40001000\n','    baseAddress: 0x40001000\n    otpReadReadiness: otp_read_readiness\n')
    board+='\notp_read_readiness: Miscellaneous.BlackwallOtpReadReadiness @ none\n    otpPower: otp_power\n    cryptoPower: crypto_power\n    hostIdle: '+str(a.host)+'\n    ptmBusy: '+str(a.ptm)+'\n    ptmReadBudget: '+str(a.budget)+'\n'
    if a.foreign_owner:
        reference='otpPower: otp_power' if a.foreign_owner=='otp' else 'cryptoPower: crypto_power'
        start=board.index('\notp_read_readiness:')
        board=board[:start]+board[start:].replace('    '+reference+'\n','    '+reference.split(':')[0]+': foreign_power\n')
        board+='\nforeign_power: Miscellaneous.BlackwallPeripheralPower @ none\n    mask: '+('0x08000000' if a.foreign_owner=='otp' else '0x200000')+'\n    profile: 1\n'
    (o/'board.repl').write_text(board);(o/'strict.cs').write_bytes(models(s));(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "OTP-read-ready"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    rejected_process=False
    try:
        log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    except RuntimeError as error:
        if not a.foreign_owner or 'renode failed (133)' not in str(error):raise
        log=(o/'renode.log').read_text();rejected_process=True
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_OTP_READ_READY_UNIT ')]
    if a.foreign_owner:
        if rows or 'OTP read readiness requires identical power owners' not in log or 'Machine started.' in log:raise ValueError('Foreign owner was not rejected')
        rows=[dict(passed=True,count=1,checks=['foreign-'+a.foreign_owner+'-identity-rejected'],process_exit_133=rejected_process,scope='expected platform constructor rejection, no CPU execution')]
    if len(rows)!=1:raise ValueError('Missing readiness result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
