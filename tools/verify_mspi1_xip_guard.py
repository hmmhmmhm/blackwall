"""Verify XIP control checks and all-unknown aperture access rejection; no backing bytes."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def models(s):
 old=(s/'mspi1-xip-research-01/base-config.cs').read_bytes();frozen=(s/'mspi1-cq-init-main-01/stock24/strict.cs').read_bytes()
 if frozen.count(old)!=1 or not frozen.startswith((ROOT/'tools/renode-strict-mmio.cs').read_bytes()):raise ValueError('Frozen model differs')
 return frozen.replace(old,(ROOT/'tools/renode-mspi1-config.cs').read_bytes())
def board(text,enabled=True):
 needle='    profile: "source-reset-config"\n'
 if text.count(needle)!=1 or 'xip_guard:' in text:raise ValueError('Unexpected XIP owner')
 if not enabled:return text
 return text.replace(needle,needle+'    xipGuard: xip_guard\n')+'\nxip_guard: Miscellaneous.BlackwallMspi1XipGuard @ sysbus 0x80000000\n    power: mspi1_power\n    clock: mspi1_clock\n'
DRIVER='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];tail=m['sysbus.guard_iom7_tail'];c=g.Mspi1Config;x=c.XipGuard;p=g.Mspi1Power;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():return (c.Reads,c.Writes,tuple((v.Key,v.Value) for v in c.Values),x.Enabled,x.EnableRequests,x.Transitions,p.Phase,p.RequestWord,p.StatusWord)
def blocked(n,fn):
    before=state();count=g.AccessCount+tail.AccessCount+x.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==before and g.AccessCount+tail.AccessCount+x.AccessCount==count+1)
check('fixed-window',x.Size==0x4000000 and x.ApertureBase==0x80000000 and x.ApertureLength==0x2000000 and not x.Enabled)
blocked('unpowered-enable',lambda:b.WriteDoubleWord(0x40061090,1))
blocked('disabled-data-read',lambda:b.ReadDoubleWord(0x80000000))
check('local-ready-mock',p.TryWrite(0x8000,True));p.ReadStatus()
b.WriteDoubleWord(0x40061080,0x19);b.WriteDoubleWord(0x40061090,0x5ec)
blocked('clock-off-enable',lambda:b.WriteDoubleWord(0x40061090,0x5ed))
g.WriteDoubleWord(0x3110,0xa4234)
b.WriteDoubleWord(0x40061080,9);blocked('writable-window-rejected',lambda:b.WriteDoubleWord(0x40061090,0x5ed))
b.WriteDoubleWord(0x40061080,0x18);blocked('wrong-aperture-size',lambda:b.WriteDoubleWord(0x40061090,0x5ed))
b.WriteDoubleWord(0x40061080,0x2000019);blocked('wrong-aperture-base',lambda:b.WriteDoubleWord(0x40061090,0x5ed))
b.WriteDoubleWord(0x40061080,0x19)
blocked('format-change-on-enable',lambda:b.WriteDoubleWord(0x40061090,0x5fd))
b.WriteDoubleWord(0x40061090,0x5ed);check('enable-control-only',x.Enabled and x.EnableRequests==1 and x.Transitions==1 and c.Values[0x90]==0x5ed)
b.WriteDoubleWord(0x40061090,0x5ed);check('repeat-enable',x.Enabled and x.EnableRequests==2 and x.Transitions==1)
blocked('live-aperture-change',lambda:b.WriteDoubleWord(0x40061080,0x18))
for off in [0,0x1fffffc,0x2000000,0x3fffffc]:blocked('unknown-data-'+str(off),lambda off=off:b.ReadDoubleWord(0x80000000+off))
blocked('byte-read',lambda:b.ReadByte(0x80000000));blocked('word-read',lambda:b.ReadWord(0x80000000));blocked('quad-read',lambda:b.ReadQuadWord(0x80000000))
blocked('readonly-write',lambda:b.WriteDoubleWord(0x80000000,0x1234));blocked('byte-write',lambda:b.WriteByte(0x80000000,1))
blocked('dma-still-strict',lambda:b.WriteDoubleWord(0x40061100,1))
blocked('pio-still-strict',lambda:b.WriteDoubleWord(0x40061000,1))
b.WriteDoubleWord(0x40061090,0x5ec);check('disable-control',not x.Enabled and c.Values[0x90]==0x5ec)
blocked('disabled-again-no-data',lambda:b.ReadDoubleWord(0x80000000))
g.Reset();check('owner-reset',not x.Enabled and x.EnableRequests==x.Transitions==x.AccessCount==0 and c.Values[0x90]==0)
Console.WriteLine('BLACKWALL_MSPI1_XIP_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='local ready-input mock/control/unknown-byte rejection, no flash backing or original main')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700)
 (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-cq-init-main-01/stock24/board.repl').read_text()));(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "mspi-xip-guard"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(z.split('BLACKWALL_MSPI1_XIP_UNIT ',1)[1]) for z in log.splitlines() if z.startswith('BLACKWALL_MSPI1_XIP_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing XIP guard unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
