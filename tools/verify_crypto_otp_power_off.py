"""Exercise opt-in idle-only CRYPTO/OTP power lifecycle without CPU or hardware."""
import argparse
import json
from pathlib import Path
from native_replay import IMAGE
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute

DRIVER = '''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallCryptoOtpPowerLifecycle,BlackwallOtpReadReadiness
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];op=g.OtpPower;cp=g.CryptoPower;rd=g.OtpReadReadiness;lc=g.CryptoOtpPowerLifecycle;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():return (op.Phase,cp.Phase,op.RequestWord,cp.RequestWord,op.Generation,cp.Generation,op.OffRequests,cp.OffRequests,rd.HostReads,rd.PtmReads,g.DevicePowerWrites)
def blocked(n,fn):
    old=state();count=g.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount==count+1)
def request(owner):check('local-on-request',owner.TryWrite(owner.Mask,True));owner.ReadStatus()
def word():return b.ReadDoubleWord(0x40021004)
def stop(owner):b.WriteDoubleWord(0x40021004,word()&~owner.Mask)
request(op);request(cp)
check('default-no-lifecycle' if lc is None else 'identical-readiness',lc is None or lc.Readiness==rd)
blocked('unobserved-crypto-off',lambda:stop(cp))
b.ReadDoubleWord(0x400c0a7c)
blocked('PTM-not-observed-off',lambda:stop(cp))
b.ReadDoubleWord(0x40014ac4)
if lc is None:
    blocked('default-crypto-off-unknown',lambda:stop(cp))
else:
    check('crypto-ready-OTP-not-ready',lc.CanShutdownCrypto() and not lc.CanShutdownOtp())
    blocked('OTP-before-crypto-off',lambda:stop(op))
    blocked('two-domains-off',lambda:b.WriteDoubleWord(0x40021004,word()&~(op.Mask|cp.Mask)))
    stop(cp);check('crypto-off-requested',cp.Phase=='off-requested' and not rd.HostObservedForCurrentPower)
    blocked('OTP-before-crypto-response',lambda:stop(op))
    b.ReadDoubleWord(0x40021008)
    if cp.OffProfile==1:
        check('crypto-stuck-on',cp.Phase=='stuck-on' and cp.StatusWord==cp.Mask)
        blocked('OTP-after-crypto-stuck-on',lambda:stop(op))
    else:
        check('crypto-powered-off',cp.Phase=='powered-off' and cp.StatusWord==0 and cp.PowerCycles==1)
        check('PTM-witness-survives-crypto-off',rd.PtmObservedForCurrentPower and lc.CanShutdownOtp())
        stop(op);check('OTP-off-requested',op.Phase=='off-requested' and not rd.PtmObservedForCurrentPower)
        b.ReadDoubleWord(0x40021008)
        check('OTP-off-result',op.Phase==('stuck-on' if op.OffProfile==1 else 'powered-off'))
        if op.OffProfile==0:
            request(op);request(cp)
            check('reactivated-no-old-witness',not rd.HostObservedForCurrentPower and not rd.PtmObservedForCurrentPower)
            blocked('reactivated-needs-observation',lambda:stop(cp))
            b.ReadDoubleWord(0x400c0a7c);b.ReadDoubleWord(0x40014ac4)
            check('reactivated-fresh-witness',lc.CanShutdownCrypto())
    for bad in [None,BlackwallOtpReadReadiness(op,cp,0,0),BlackwallOtpReadReadiness(op,cp,1,1,8)]:
        try:BlackwallCryptoOtpPowerLifecycle(bad)
        except Exception as e:check('invalid-idle-profile','requires explicit idle' in str(e))
        else:raise Exception('bad lifecycle accepted')
g.Reset();check('reset-no-readiness',not rd.HostObservedForCurrentPower and not rd.PtmObservedForCurrentPower)
Console.WriteLine('BLACKWALL_CRYPTO_OTP_OFF_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='idle-only local power bank; no CPU, crypto engine, OTP writes or hardware')))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--crypto-off', choices=['off', 'stuck-on'], default='off')
    p.add_argument('--otp-off', choices=['off', 'stuck-on'], default='off')
    p.add_argument('--default', action='store_true')
    p.add_argument('--foreign-readiness', action='store_true')
    p.add_argument('--unlinked', action='store_true')
    a = p.parse_args()
    if a.default and (a.foreign_readiness or a.unlinked):
        p.error('Malformed owner tests require selected lifecycle')
    s, o = a.simulator, a.output
    o.mkdir(mode=0o700)
    board = (s/'otp-read-ready-main-01/stock24/board.repl').read_text()
    if not a.default:
        board = board.replace('    baseAddress: 0x40001000\n', '    baseAddress: 0x40001000\n    cryptoOtpPowerLifecycle: crypto_otp_lifecycle\n')
        for mask, profile in [('0x08000000', a.otp_off), ('0x200000', a.crypto_off)]:
            needle = '    mask: '+mask+'\n    profile: 1\n'
            if board.count(needle) != 1:
                raise ValueError('Unexpected power owner '+mask)
            board = board.replace(needle, needle+'    offProfile: '+str(int(profile=='stuck-on'))+'\n')
        board += '\ncrypto_otp_lifecycle: Miscellaneous.BlackwallCryptoOtpPowerLifecycle @ none\n    readiness: otp_read_readiness\n'
        if a.foreign_readiness:
            board=board.replace('    readiness: otp_read_readiness\n','    readiness: foreign_readiness\n')
            board+='\nforeign_readiness: Miscellaneous.BlackwallOtpReadReadiness @ none\n    otpPower: otp_power\n    cryptoPower: crypto_power\n    hostIdle: 1\n    ptmBusy: 0\n'
        if a.unlinked:
            board=board.replace('    cryptoOtpPowerLifecycle: crypto_otp_lifecycle\n','')
    (o/'board.repl').write_text(board)
    (o/'strict.cs').write_bytes(models(s))
    (o/'test.py').write_text(DRIVER)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "crypto-otp-off"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    rejected_process=False
    try:
        log = execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    except RuntimeError as error:
        if not (a.foreign_readiness or a.unlinked) or 'renode failed (133)' not in str(error):raise
        log=(o/'renode.log').read_text();rejected_process=True
    rows = [json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_CRYPTO_OTP_OFF_UNIT ')]
    if a.foreign_readiness or a.unlinked:
        message='OTP requires matching mask' if a.unlinked else 'CRYPTO OTP lifecycle requires identical readiness owner'
        if rows or message not in log or 'Machine started.' in log:raise ValueError('Malformed owner was not rejected')
        rows=[dict(passed=True,count=1,checks=['malformed-owner-rejected'],process_exit_133=rejected_process,scope='expected constructor rejection; no CPU execution')]
    if len(rows)!=1:
        raise ValueError('Missing off result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n')
    print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':
    main()
