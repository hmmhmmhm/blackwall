"""Test MSPI1 source-reset config storage and strict execution boundaries."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def models(s):
 old=(s/'mspi1-config-contract-01/base-core.cs').read_bytes();frozen=(s/'mspi1-clock-main-01/stock24/strict.cs').read_bytes()
 if not frozen.startswith(old):raise ValueError('Frozen core differs')
 extra=ROOT/'tools/renode-mspi1-config.cs'
 return (ROOT/'tools/renode-strict-mmio.cs').read_bytes()+frozen[len(old):]+(b'\n'+extra.read_bytes() if extra.exists() else b'')
def board(text,enabled=True):
 if not enabled:return text
 needle='    baseAddress: 0x40001000\n'
 if text.count(needle)!=1 or 'mspi1_config:' in text:raise ValueError('Unexpected owner')
 return text.replace(needle,needle+'    mspi1Config: mspi1_config\n')+'\nmspi1_config: Miscellaneous.BlackwallMspi1ConfigStorage @ none\n    profile: "source-reset-config"\n'
DRIVER='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];tail=m['sysbus.guard_iom7_tail'];c=g.Mspi1Config;p=g.Mspi1Power;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():return (c.Reads,c.Writes,tuple((x.Key,x.Value) for x in c.Values),p.Phase,p.RequestWord,p.StatusWord)
def blocked(n,fn):
    old=state();count=g.AccessCount+tail.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount+tail.AccessCount==count+1)
blocked('unpowered-read',lambda:b.ReadDoubleWord(0x40061090))
blocked('unpowered-write',lambda:b.WriteDoubleWord(0x40061090,0))
check('local-ready-mock',p.TryWrite(0x8000,True));p.ReadStatus()
check('clock-gate-is-off',not g.Mspi1Clock.Enabled)
for pair in c.Values:
    check('reset-'+str(pair.Key),b.ReadDoubleWord(0x40061000+pair.Key)==pair.Value)
b.WriteDoubleWord(0x40061090,0x80);check('xip-config-without-enable',b.ReadDoubleWord(0x40061090)==0x80)
blocked('xip-enable',lambda:b.WriteDoubleWord(0x40061090,0x81))
blocked('dma-enable',lambda:b.WriteDoubleWord(0x40061100,1))
blocked('scramble-enable',lambda:b.WriteDoubleWord(0x4006109c,0x80000000))
blocked('peripheral-reset-change',lambda:b.WriteDoubleWord(0x40061030,0x800000f0))
blocked('fifo-reset',lambda:b.WriteDoubleWord(0x40061030,0xe00000f0))
blocked('reserved-xip-bit',lambda:b.WriteDoubleWord(0x40061090,2))
for off in [0,0x10,0x14,0x18,0x1c,0x104,0x200,0x204,0x208,0x20c,0x2a0,0x2a8,0x2ac]:
    blocked('strict-read-'+str(off),lambda off=off:b.ReadDoubleWord(0x40061000+off))
    blocked('strict-write-'+str(off),lambda off=off:b.WriteDoubleWord(0x40061000+off,0))
b.WriteDoubleWord(0x40061030,0xc00000f1);check('apb-config-preserve-reset',b.ReadDoubleWord(0x40061030)==0xc00000f1)
b.WriteDoubleWord(0x40061108,0x20080000);check('dma-address-only',b.ReadDoubleWord(0x40061108)==0x20080000)
blocked('byte-width',lambda:b.ReadByte(0x40061090));blocked('halfword-width',lambda:b.WriteWord(0x40061090,0))
g.Reset();check('owner-reset',c.Reads==c.Writes==0 and c.Values[0x90]==0 and c.Values[0x30]==0xc00000f0)
Console.WriteLine('BLACKWALL_MSPI1_CONFIG_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='local ready-input mock config storage; not native original main or bus activity')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700)
 (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-clock-main-01/stock24/board.repl').read_text()));(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "mspi-config"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_MSPI1_CONFIG_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_CONFIG_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing config unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
