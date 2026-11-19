"""Verify strictly bounded synthetic INFOC serial slots; never real device data."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute

DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallOtpSerialSlots,BlackwallPeripheralPower,BlackwallOtpReadReadiness
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];p=g.OtpSerialSlots;rd=g.OtpReadReadiness;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():return (None if p is None else (p.Reads,p.LastAddress),rd.HostReads,rd.PtmReads,g.OtpPower.Phase,g.CryptoPower.Phase,g.OtpPower.Generation,g.CryptoPower.Generation)
def blocked(n,fn):
    old=state();count=g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount==count+1)
def powers():
    check('local-OTP-ready',g.OtpPower.TryWrite(0x08000000,True));g.OtpPower.ReadStatus()
    check('local-crypto-ready',g.CryptoPower.TryWrite(0x200000,True));g.CryptoPower.ReadStatus()
blocked('unpowered-word',lambda:b.ReadDoubleWord(0x400c2340));powers()
blocked('unobserved-readiness',lambda:b.ReadDoubleWord(0x400c2340))
if rd.HostIdle==-1:blocked('unknown-HOST',lambda:b.ReadDoubleWord(0x400c0a7c))
else:b.ReadDoubleWord(0x400c0a7c)
blocked('PTM-not-observed',lambda:b.ReadDoubleWord(0x400c2340))
if rd.PtmBusy==-1:blocked('unknown-PTM',lambda:b.ReadDoubleWord(0x40014ac4))
else:b.ReadDoubleWord(0x40014ac4)
if p is None:blocked('default-word-remains-unknown',lambda:b.ReadDoubleWord(0x400c2340))
elif rd.HostIdle!=1 or rd.PtmBusy!=0:blocked('busy-or-unknown-profile-word',lambda:b.ReadDoubleWord(0x400c2340))
else:
    expected=bytearray([255]*128)
    def seed(slot,text):expected[slot*16:slot*16+16]=bytearray(text.encode('ascii')+b'\\0\\0')
    if p.Profile in ['mock-first','mock-last']:seed(0,'S211MOCK000001')
    if p.Profile=='mock-last':seed(7,'P100MOCK000002')
    if p.Profile=='invalid-prefix':seed(0,'X211MOCK000001')
    if p.Profile=='invalid-digit':seed(0,'S211MOCK00000X')
    check('exact-window',p.Start==0x400c2340 and p.Length==128)
    for n in range(32):
        value=sum(int(expected[n*4+j])<<(8*j) for j in range(4))
        check('word-'+str(n),b.ReadDoubleWord(0x400c2340+n*4)==value)
    check('full-scan-count',p.Reads==32 and p.LastAddress==0x400c23bc)
    blocked('reserved-power-bit-no-generation-change',lambda:b.WriteDoubleWord(0x40021004,0x88200000))
    blocked('two-power-domain-change-rejected',lambda:b.WriteDoubleWord(0x40021004,0))
    for addr in [0x400c233c,0x400c23c0,0x400c2000]:blocked('outside-'+str(addr),lambda addr=addr:b.ReadDoubleWord(addr))
    for addr in [0x400c2341,0xfffffffffffffffc,0x400c233c,0x400c23c0]:
        old=state();ok,value=p.TryRead(addr);check('invalid-direct-'+str(addr),not ok and state()==old)
    blocked('write-prohibited',lambda:b.WriteDoubleWord(0x400c2340,0))
    blocked('byte-prohibited',lambda:b.ReadByte(0x400c2340))
    g.CryptoPower.Reset();blocked('power-loss-stops-window',lambda:b.ReadDoubleWord(0x400c2340))
    check('crypto-reenable',g.CryptoPower.TryWrite(0x200000,True));g.CryptoPower.ReadStatus()
    blocked('old-HOST-witness-invalid-after-crypto-reset',lambda:b.ReadDoubleWord(0x400c2340))
    b.ReadDoubleWord(0x400c0a7c)
    check('same-OTP-PTM-witness-remains-valid',p.TryRead(0x400c2340)[0])
    g.OtpPower.Reset();check('OTP-reenable',g.OtpPower.TryWrite(0x08000000,True));g.OtpPower.ReadStatus()
    blocked('old-OTP-witnesses-invalid-after-reset',lambda:b.ReadDoubleWord(0x400c2340))
    b.ReadDoubleWord(0x400c0a7c)
    blocked('old-PTM-witness-invalid-after-OTP-reset',lambda:b.ReadDoubleWord(0x400c2340))
    b.ReadDoubleWord(0x40014ac4)
    check('both-fresh-witnesses-work',p.TryRead(0x400c2340)[0])
    g.Reset();check('reset-counters',p.Reads==p.LastAddress==rd.HostReads==rd.PtmReads==0)
    powers();b.ReadDoubleWord(0x400c0a7c);b.ReadDoubleWord(0x40014ac4)
    check('profile-data-preserved-on-reset',b.ReadDoubleWord(0x400c2340)==sum(int(expected[j])<<(8*j) for j in range(4)))
    for owner,profile in [(None,'mock-first'),(rd,'unknown')]:
        try:BlackwallOtpSerialSlots(owner,profile)
        except Exception as e:check('invalid-profile-or-owner','OTP serial slots require' in str(e))
        else:raise Exception('invalid slots accepted')
    for off in [0,1]:
        op=BlackwallPeripheralPower(0x08000000,1,0);cp=BlackwallPeripheralPower(0x200000,1,off)
        ready=BlackwallOtpReadReadiness(op,cp,1,0);slots=BlackwallOtpSerialSlots(ready,'mock-first')
        op.TryWrite(op.Mask,True);op.ReadStatus();cp.TryWrite(cp.Mask,True);cp.ReadStatus()
        ready.TryRead(0x400c0a7c);ready.TryRead(0x40014ac4)
        check('local-valid-before-off-'+str(off),slots.TryRead(0x400c2340)[0])
        epoch=cp.Generation;counts=(ready.HostReads,ready.PtmReads)
        check('reject-off-without-quiescence-'+str(off),not cp.TryWrite(0,True) and cp.Generation==epoch and ready.HostObservedForCurrentPower)
        check('off-request-changes-generation-'+str(off),cp.TryWrite(0,True,True) and cp.Generation>epoch and not ready.HostObservedForCurrentPower and ready.PtmObservedForCurrentPower)
        check('off-pending-blocks-slot-'+str(off),not slots.TryRead(0x400c2340)[0] and counts==(ready.HostReads,ready.PtmReads))
        cp.ReadStatus()
        check('off-response-blocks-slot-'+str(off),not slots.TryRead(0x400c2340)[0] and cp.Phase==('powered-off' if off==0 else 'stuck-on'))
        if off==0:
            epoch=cp.Generation;check('reactivation-changes-generation',cp.TryWrite(cp.Mask,True) and cp.Generation>epoch);cp.ReadStatus()
            check('reactivation-requires-new-HOST',not slots.TryRead(0x400c2340)[0])
            ready.TryRead(0x400c0a7c);check('reactivation-new-HOST-works',slots.TryRead(0x400c2340)[0])
        ready.Reset();check('readiness-reset-invalidates-'+str(off),not ready.HostObservedForCurrentPower and not ready.PtmObservedForCurrentPower)
    pending=BlackwallPeripheralPower(0x200000,0,0);epoch=pending.Generation
    check('request-generation',pending.TryWrite(pending.Mask,True) and pending.Generation>epoch)
    epoch=pending.Generation;pending.ReadStatus();check('response-preserves-generation',pending.Generation==epoch)
    check('cancel-generation',pending.TryWrite(0,True) and pending.Generation>epoch)
    epoch=pending.Generation;pending.Reset();check('reset-generation-monotonic',pending.Generation>epoch and pending.Requests==pending.Responses==0)
Console.WriteLine('BLACKWALL_OTP_SERIAL_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='synthetic 128byte read-only profiles and local readiness mocks; no hardware OTP')))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--profile',choices=['none','empty','mock-first','mock-last','invalid-prefix','invalid-digit'],default='mock-first');p.add_argument('--foreign-readiness',action='store_true');p.add_argument('--host',type=int,choices=[-1,0,1],default=1);p.add_argument('--ptm',type=int,choices=[-1,0,1],default=0);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    board=(s/'otp-read-ready-main-01/stock24/board.repl').read_text()
    board=board.replace('    hostIdle: 1\n','    hostIdle: '+str(a.host)+'\n').replace('    ptmBusy: 0\n','    ptmBusy: '+str(a.ptm)+'\n')
    if a.ptm==1:board=board.replace('    ptmReadBudget: 0\n','    ptmReadBudget: 8\n')
    if a.profile!='none':
        board=board.replace('    baseAddress: 0x40001000\n','    baseAddress: 0x40001000\n    otpSerialSlots: otp_serial_slots\n')
        board+='\notp_serial_slots: Miscellaneous.BlackwallOtpSerialSlots @ none\n    readiness: otp_read_readiness\n    profile: "'+a.profile+'"\n'
    if a.foreign_readiness:
        if a.profile=='none':p.error('Foreign readiness requires selected slots')
        board=board.replace('    readiness: otp_read_readiness\n','    readiness: foreign_readiness\n')
        board+='\nforeign_readiness: Miscellaneous.BlackwallOtpReadReadiness @ none\n    otpPower: otp_power\n    cryptoPower: crypto_power\n    hostIdle: 1\n    ptmBusy: 0\n'
    (o/'board.repl').write_text(board);(o/'strict.cs').write_bytes(models(s));(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "OTP-serial"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    rejected_process=False
    try:
        log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    except RuntimeError as error:
        if not a.foreign_readiness or 'renode failed (133)' not in str(error):raise
        log=(o/'renode.log').read_text();rejected_process=True
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_OTP_SERIAL_UNIT ')]
    if a.foreign_readiness:
        if rows or 'OTP serial slots require identical readiness owner' not in log or 'Machine started.' in log:raise ValueError('Foreign readiness not rejected')
        rows=[dict(passed=True,count=1,checks=['foreign-readiness-rejected'],process_exit_133=rejected_process,scope='expected platform constructor rejection, no CPU execution')]
    if len(rows)!=1:raise ValueError('Missing serial slot result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
