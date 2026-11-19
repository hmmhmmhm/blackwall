"""Test explicit NOR RDID profile, FIFO consumption and default/stuck boundaries."""
import argparse,json,struct
from pathlib import Path
from verify_mspi1_pio_reset import models
from native_replay import IMAGE
from run_renode_m55_probe import execute

def board(text,identity='mx25u25643g',complete=True):
 needle='    profile: "idle-nor-reset"\n'
 if text.count(needle)!=1:raise ValueError('Unexpected PIO profile')
 text=text.replace(needle,needle+'    identityProfile: "'+identity+'"\n')
 if not complete:
  if text.count('    completeTransactions: true\n')!=1:raise ValueError('Unexpected completion profile')
  text=text.replace('    completeTransactions: true\n','    completeTransactions: false\n')
 return text
COMMON='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];p=g.Mspi1Power;q=g.Mspi1Config.Pio;i=g.Mspi1Config.Interrupts;checks=[]
def check(n,v):
    if not v:raise Exception(n+' '+repr(state()))
    checks.append(n)
def state():return (q.Control,q.Starts,q.Completions,q.Busy,q.RxEntries,q.ReadIdTransfers,q.FifoReads,q.Reads,q.Writes,i.Status,i.Writes)
def blocked(n,fn):
    old=state();count=g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,old==state() and g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount==count+1)
def ready():
    check('local-ready',p.TryWrite(0x8000,True));p.ReadStatus();g.WriteDoubleWord(0x3110,0xa4234)
    b.WriteDoubleWord(0x40061084,0x3010861);b.WriteDoubleWord(0x4006100c,0x9f)
def start():b.WriteDoubleWord(0x40061000,0x30441)
check('FIFO-reset',q.RxEntries==q.ReadIdTransfers==q.FifoReads==0)
blocked('unpowered-FIFO',lambda:b.ReadDoubleWord(0x40061014))
ready()
'''
ACTIVE='''check('profile-selected',q.IdentityProfile=='mx25u25643g')
blocked('wrong-length',lambda:b.WriteDoubleWord(0x40061000,0x40441))
b.WriteDoubleWord(0x4006100c,5)
blocked('unknown-status-command',start)
b.WriteDoubleWord(0x4006100c,0x9f)
start();check('start-not-data',q.Busy and q.RxEntries==q.ReadIdTransfers==0)
blocked('read-before-ready',lambda:b.ReadDoubleWord(0x40061014))
for n in range(10):check('entries-not-completion-'+str(n),b.ReadDoubleWord(0x4006101c)==0 and q.Completions==0)
'''
PHASES=[(5,"check('RX-not-early',q.Busy and q.RxEntries==0)\n"),
(5,"check('RX-ready',not q.Busy and q.RxEntries==1 and q.ReadIdTransfers==1 and q.Control==0x30442 and i.Status==1 and i.Writes==0)\nblocked('pending-frame-not-overwritten',start)\nblocked('FIFO-byte-width',lambda:b.ReadByte(0x40061014))\nword=b.ReadDoubleWord(0x40061014)\ncheck('ID-order-and-model-padding',word==0x003925c2)\ncheck('one-short-word-consumed',q.RxEntries==0 and q.FifoReads==1 and b.ReadDoubleWord(0x4006101c)==0)\nblocked('empty-FIFO',lambda:b.ReadDoubleWord(0x40061014))\nstart()\n"),
(10,"check('second-RDID',q.ReadIdTransfers==2 and q.RxEntries==1)\ng.Reset()\ncheck('reset-discards-FIFO',q.RxEntries==q.ReadIdTransfers==q.FifoReads==0)\nready();start();g.WriteDoubleWord(0x3110,0xa4214);g.WriteDoubleWord(0x3110,0xa4234)\n"),
(10,"check('RX-clock-change-aborts',q.Aborted==1 and not q.Busy and q.RxEntries==q.ReadIdTransfers==0)\nstart();g.Reset()\n"),
(20,"check('reset-cancels-RX',q.RxEntries==q.ReadIdTransfers==q.Completions==0 and not q.Busy)\n")]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--identity',choices=['mx25u25643g','none'],default='mx25u25643g');p.add_argument('--stuck',action='store_true');a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-xip-mixed-main-01/stock24/board.repl').read_text(),a.identity,not a.stuck));(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'))
 setup=COMMON+("check('none-profile',q.IdentityProfile=='none')\nblocked('none-does-not-invent-ID',start)\n" if a.identity=='none' else ACTIVE);phases=[] if a.identity=='none' else [(1000,"check('stuck-no-RX',q.Busy and q.RxEntries==q.ReadIdTransfers==0)\n")] if a.stuck else PHASES;(o/'setup.py').write_text(setup);resc='include @/work/strict.cs\nmach create "mspi-rdid"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 for n,(us,phase) in enumerate(phases):
  (o/f'phase-{n}.py').write_text(phase);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'result.py').write_text("Console.WriteLine('BLACKWALL_MSPI1_RDID_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='explicit manufacturer model or none/stuck; no physical identity or flash backing')))\n");(o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_MSPI1_RDID_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_RDID_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing RDID result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
