"""Test disabled MSPI CQ initialization without executing command memory."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def models(s):
 old=(s/'mspi1-cq-research-01/base-config.cs').read_bytes();frozen=(s/'mspi1-config-main-01/stock24/strict.cs').read_bytes()
 if frozen.count(old)!=1:raise ValueError('Frozen config differs')
 if not frozen.startswith((ROOT/'tools/renode-strict-mmio.cs').read_bytes()):raise ValueError('Frozen core differs from current source')
 return frozen.replace(old,(ROOT/'tools/renode-mspi1-config.cs').read_bytes())
def board(text,enabled=True):
 needle='    profile: "source-reset-config"\n'
 if text.count(needle)!=1 or 'commandQueueInit:' in text:raise ValueError('Unexpected config profile')
 return text.replace(needle,needle+'    commandQueueInit: true\n') if enabled else text
DRIVER='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];tail=m['sysbus.guard_iom7_tail'];c=g.Mspi1Config;p=g.Mspi1Power;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():return (c.Reads,c.Writes,c.CqReads,c.CqWrites,tuple((x.Key,x.Value) for x in c.CqValues),p.Phase)
def blocked(n,fn):
    before=state();count=g.AccessCount+tail.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==before and g.AccessCount+tail.AccessCount==count+1)
check('selected-profile',c.CommandQueueInit)
blocked('unpowered-cq-read',lambda:b.ReadDoubleWord(0x400612c0))
blocked('unpowered-cq-write',lambda:b.WriteDoubleWord(0x400612c0,0))
check('local-ready-mock',p.TryWrite(0x8000,True));p.ReadStatus()
for off in [0x2a0,0x2a8,0x2ac,0x2b8,0x2c0,0x2c4]:check('cq-reset-'+str(off),b.ReadDoubleWord(0x40061000+off)==0)
b.WriteDoubleWord(0x400612c0,255);b.WriteDoubleWord(0x400612c4,255);check('eight-bit-index',b.ReadDoubleWord(0x400612c0)==b.ReadDoubleWord(0x400612c4)==255)
blocked('wide-index',lambda:b.WriteDoubleWord(0x400612c0,256))
b.WriteDoubleWord(0x400612b8,0x4000);check('pause-mask',b.ReadDoubleWord(0x400612b8)==0x4000)
b.WriteDoubleWord(0x400612a8,0x20080000);check('queue-address',b.ReadDoubleWord(0x400612a8)==0x20080000)
blocked('unaligned-address',lambda:b.WriteDoubleWord(0x400612a8,0x20080002))
b.WriteDoubleWord(0x400612a0,2);check('priority-without-execution',b.ReadDoubleWord(0x400612a0)==2)
blocked('enable-needs-engine',lambda:b.WriteDoubleWord(0x400612a0,3))
blocked('poweroff-needs-engine',lambda:b.WriteDoubleWord(0x400612a0,4))
blocked('autoclear-needs-engine',lambda:b.WriteDoubleWord(0x400612a0,8))
blocked('pauseop-needs-engine',lambda:b.WriteDoubleWord(0x400612a0,16))
b.WriteDoubleWord(0x400612b4,0x80);check('software-set',c.CqValues[0x2b0]==0x80)
b.WriteDoubleWord(0x400612b4,0x8000);check('software-toggle',c.CqValues[0x2b0]==0)
b.WriteDoubleWord(0x400612b4,0x800080);check('set-wins-clear',c.CqValues[0x2b0]==0x80)
b.WriteDoubleWord(0x400612b4,0x800000);check('software-clear',c.CqValues[0x2b0]==0)
blocked('toggle-conflict-unknown',lambda:b.WriteDoubleWord(0x400612b4,0x101))
blocked('software-reserved',lambda:b.WriteDoubleWord(0x400612b4,0x1000000))
blocked('hardware-flags-unknown',lambda:b.ReadDoubleWord(0x400612b0))
blocked('flags-are-not-storage-write',lambda:b.WriteDoubleWord(0x400612b0,1))
blocked('command-alias-read',lambda:b.ReadDoubleWord(0x400612b4))
blocked('status-write',lambda:b.WriteDoubleWord(0x400612ac,0))
blocked('pio-still-strict',lambda:b.WriteDoubleWord(0x40061000,0))
blocked('byte-width',lambda:b.WriteByte(0x400612c0,0))
g.Reset();check('owner-reset',c.CqReads==c.CqWrites==0 and all(x.Value==0 for x in c.CqValues))
Console.WriteLine('BLACKWALL_MSPI1_CQ_INIT_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='disabled CQ initialization/local ready mock; no memory fetch, command execution, IRQ or original main')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700)
 (o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-config-main-01/stock24/board.repl').read_text()));(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "mspi-cq-init"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_MSPI1_CQ_INIT_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_CQ_INIT_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing CQ init marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
