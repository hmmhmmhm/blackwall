"""Verify the opt-in missing-magic diagnostic and strict XIP rejection boundaries."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models

DRIVER = '''import json,clr
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallMspi1XipGuard').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMspi1XipGuard
m=monitor.Machine;g=m['sysbus.guard'];b=m.SystemBus;x=m['sysbus.xip_guard'];checks=[]
pc0=0x47605a;pc1=0x476134
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def rejected(n,offset,pc,base):
    old=(x.FontHeaderReads,x.LastFontHeaderPc)
    ok,value=x.TryReadMissingFontHeader(offset,pc,base)
    check(n,not ok and (x.FontHeaderReads,x.LastFontHeaderPc)==old)
check('explicit-profile',x.FontHeaderProfile=='missing-font-magic-only')
rejected('unpowered',0x100000,pc0,0x80100000)
check('synthetic-power-on',g.Mspi1Power.TryWrite(0x8000,True));g.Mspi1Power.ReadStatus()
rejected('clock-off',0x100000,pc0,0x80100000)
g.WriteDoubleWord(0x3110,0xa4234)
rejected('XIP-disabled',0x100000,pc0,0x80100000)
check('enable',x.TryEnable(0x19))
ok,value=x.TryReadMissingFontHeader(0x100000,pc0,0x80100000)
check('first-missing-magic-word',ok and value==0xffffffff and x.FontHeaderReads==1 and x.LastFontHeaderPc==pc0)
rejected('first-replay',0x100000,pc0,0x80100000)
rejected('wrong-consumer',0x700000,pc1+2,0x80700000)
rejected('wrong-base-register',0x700000,pc1,0x80100000)
rejected('header-tail-unknown',0x700004,pc1,0x80700000)
rejected('negative-offset',-4,pc1,0x80700000)
x.Disable();rejected('disabled-second',0x700000,pc1,0x80700000)
check('reenable',x.TryEnable(0x19))
g.WriteDoubleWord(0x3110,0xa4214);rejected('clock-off-second',0x700000,pc1,0x80700000)
g.WriteDoubleWord(0x3110,0xa4234)
ok,value=x.TryReadMissingFontHeader(0x700000,pc1,0x80700000)
check('second-missing-magic-word',ok and value==0xffffffff and x.FontHeaderReads==2)
rejected('exhausted',0x700000,pc1,0x80700000)
x.Disable();x.TryEnable(0x19);rejected('toggle-not-replenish',0x100000,pc0,0x80100000)
x.Reset();check('reset-budget-and-control',x.FontHeaderReads==0 and x.LastFontHeaderPc==0 and not x.Enabled)
x.TryEnable(0x19)
rejected('second-before-first',0x700000,pc1,0x80700000)
for name,fn in [('host-read',lambda:b.ReadDoubleWord(0x80100000)),('byte-read',lambda:b.ReadByte(0x80100000)),('word-read',lambda:b.ReadWord(0x80100000)),('quad-read',lambda:b.ReadQuadWord(0x80100000)),('header-write',lambda:b.WriteDoubleWord(0x80100000,0)),('other-XIP',lambda:b.ReadDoubleWord(0x80000000)),('aperture-tail',lambda:b.ReadDoubleWord(0x83fffffc))]:
    before=x.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(name+' accepted')
    check(name,x.AccessCount==before+1 and x.FontHeaderReads==0)
for profile,p0,p1 in [('other',pc0,pc1),('missing-font-magic-only',pc0+1,pc1),('missing-font-magic-only',pc0,pc0),('missing-font-magic-only',0x1000,pc1),('missing-font-magic-only',pc0,0x800000)]:
    try:BlackwallMspi1XipGuard(m,g.Mspi1Power,g.Mspi1Clock,profile,p0,p1)
    except Exception as e:check('invalid-profile','Missing-font diagnostic requires' in str(e))
    else:raise Exception('invalid profile accepted')
default=BlackwallMspi1XipGuard(m,g.Mspi1Power,g.Mspi1Clock)
default.TryEnable(0x19);ok,value=default.TryReadMissingFontHeader(0x100000,pc0,0x80100000)
check('default-remains-unknown',not ok and default.FontHeaderReads==0)
Console.WriteLine('BLACKWALL_MISSING_FONT_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='direct finite diagnostic guards and bus rejection, no original main or actual font data')))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--legacy-control',action='store_true');a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    board=(s/'timer0-shared-main-02/stock24-low/board.repl').read_text()
    needle='xip_guard: Miscellaneous.BlackwallMspi1XipGuard @ sysbus 0x80000000\n'
    if board.count(needle)!=1:raise ValueError('Unexpected XIP board')
    board=board.replace(needle,needle+'    fontHeaderProfile: "missing-font-magic-only"\n    primaryHeaderReadPc: 0x47605a\n    secondaryHeaderReadPc: 0x476134\n')
    driver=DRIVER;marker='BLACKWALL_MISSING_FONT_UNIT'
    if a.legacy_control:
        from verify_mspi1_xip_guard import DRIVER as legacy_driver,board as legacy_board
        board=legacy_board((s/'mspi1-cq-init-main-01/stock24/board.repl').read_text())
        driver=legacy_driver;marker='BLACKWALL_MSPI1_XIP_UNIT'
    (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board);(o/'test.py').write_text(driver)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "missing-font-diagnostic"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(marker+' ')]
    if len(rows)!=1:raise ValueError('Missing diagnostic unit marker; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
