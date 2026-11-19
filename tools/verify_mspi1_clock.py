"""Check source-reset MSPI1 clock field storage; no clock or MSPI engine."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def models(s):
 old=(s/'mspi1-power-main-01/core.cs').read_bytes();frozen=(s/'mspi1-power-main-01/stock24/strict.cs').read_bytes()
 if not frozen.startswith(old):raise ValueError('Frozen model prefix differs')
 extra=ROOT/'tools/renode-mspi1-clock.cs'
 return (ROOT/'tools/renode-strict-mmio.cs').read_bytes()+frozen[len(old):]+(b'\n'+extra.read_bytes() if extra.exists() else b'')
def board(text,enabled=True):
 if not enabled:return text
 needle='    baseAddress: 0x40001000\n'
 if text.count(needle)!=1 or 'mspi1_clock:' in text:raise ValueError('Unexpected owner')
 return text.replace(needle,needle+'    mspi1Clock: mspi1_clock\n')+'\nmspi1_clock: Miscellaneous.BlackwallMspi1ClockStorage @ none\n    profile: "source-reset-storage"\n'
DRIVER='''import json
from System import Console
m=monitor.Machine;g=m['sysbus.guard'];c=g.Mspi1Clock;tail=m['sysbus.guard_iom7_tail'];checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():return (c.Value,c.Reads,c.Writes,g.Mspi1Power.Phase,g.Mspi1Power.RequestWord,g.Mspi1Power.StatusWord)
def blocked(n,fn):
    old=state();count=g.AccessCount+tail.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount+tail.AccessCount==count+1)
check('source-reset',c.Value==0xa4214 and not c.Enabled and c.Selection==8)
check('read-reset',g.ReadDoubleWord(0x3110)==0xa4214 and c.Reads==1)
g.WriteDoubleWord(0x3110,0xa4214);check('same-word',c.Writes==1 and c.Value==0xa4214)
g.WriteDoubleWord(0x3110,0xa4234);check('enable',c.Enabled and c.Selection==8)
g.WriteDoubleWord(0x3110,0xa41f4);check('select-seven-preserve-other-modules',c.Enabled and c.Selection==7 and (c.Value&~0x3e0)==(0xa4214&~0x3e0))
blocked('reserved-bit',lambda:g.WriteDoubleWord(0x3110,c.Value|0x100000))
blocked('other-module-gate',lambda:g.WriteDoubleWord(0x3110,c.Value^1))
blocked('other-module-selection',lambda:g.WriteDoubleWord(0x3110,c.Value^2))
blocked('unsupported-mspi1-selection',lambda:g.WriteDoubleWord(0x3110,(c.Value&~0x3c0)|(9<<6)))
blocked('byte-read',lambda:g.ReadByte(0x3110))
blocked('byte-write',lambda:g.WriteByte(0x3110,0))
blocked('word-write',lambda:g.WriteWord(0x3110,0))
blocked('mspi-bus-still-strict',lambda:m.SystemBus.ReadDoubleWord(0x40061000))
g.WriteDoubleWord(0x3110,0xa41d4);check('gate-off',not c.Enabled and c.Selection==7)
check('no-power-side-effects',g.Mspi1Power.RequestWord==g.Mspi1Power.StatusWord==0 and g.Mspi1Power.Phase=='off')
g.Reset();check('owner-reset',c.Value==0xa4214 and c.Reads==c.Writes==0 and not c.Enabled)
Console.WriteLine('BLACKWALL_MSPI1_CLOCK_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='isolated source-reset register storage, not clock generation or original firmware')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve()
 o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-power-main-01/stock24/board.repl').read_text()));(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "mspi-clock"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
 rows=[json.loads(x.split('BLACKWALL_MSPI1_CLOCK_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_CLOCK_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing clock unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))
if __name__=='__main__':main()
