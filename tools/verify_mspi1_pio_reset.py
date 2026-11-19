"""Verify bounded virtual PIO/NOR reset state transitions without any physical device."""
import argparse,json,struct
from pathlib import Path
from verify_mspi1_clear_all import models as base_models
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def models(s):
 data=base_models(s);old=(s/'mspi1-pio-research-01/base-clock.cs').read_bytes()
 if data.count(old)!=1:raise ValueError('Frozen clock differs')
 data=data.replace(old,(ROOT/'tools/renode-mspi1-clock.cs').read_bytes());p=ROOT/'tools/renode-mspi1-pio.cs'
 return data+(b'\n'+p.read_bytes() if p.exists() else b'')
def board(text,enabled=True,complete=True):
 needle='    profile: "source-reset-config"\n'
 if text.count(needle)!=1:raise ValueError('Unexpected config owner')
 if not enabled:return text
 return text.replace(needle,needle+'    pio: mspi1_pio\n')+'\nmspi1_pio: Miscellaneous.BlackwallMspi1PioReset @ none\n    profile: "idle-nor-reset"\n    power: mspi1_power\n    clock: mspi1_clock\n    interrupts: mspi1_interrupts\n    completeTransactions: '+str(complete).lower()+'\n'
SETUP='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];p=g.Mspi1Power;q=g.Mspi1Config.Pio;i=g.Mspi1Config.Interrupts;checks=[]
def check(n,v):
    if not v:raise Exception(n+' '+repr(state()))
    checks.append(n)
def state():return (q.Control,q.Starts,q.Completions,q.ResetArmed,q.Recovering,q.Resets,q.IgnoredResets,i.Status,q.Reads,q.Writes)
def blocked(n,fn):
    old=state();count=g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,old==state() and g.AccessCount+m['sysbus.guard_iom7_tail'].AccessCount==count+1)
def instr(v):b.WriteDoubleWord(0x4006100c,v)
def start(v):instr(v);b.WriteDoubleWord(0x40061000,0xc1)
check('reset',q.Control==q.Starts==q.Completions==0 and not q.ResetArmed and not q.Recovering)
blocked('unpowered-control',lambda:b.WriteDoubleWord(0x40061000,0xc1))
check('local-ready',p.TryWrite(0x8000,True));p.ReadStatus()
blocked('clock-off',lambda:b.WriteDoubleWord(0x40061000,0xc1))
g.WriteDoubleWord(0x3110,0xa4234)
b.WriteDoubleWord(0x40061084,0x1410061)
instr(0x9f);blocked('unknown-ID-command',lambda:b.WriteDoubleWord(0x40061000,0xc1))
instr(0x66);blocked('data-transfer',lambda:b.WriteDoubleWord(0x40061000,0x100c1))
start(0x66)
check('start-is-not-completion',q.Busy and q.Completions==0 and not q.ResetArmed and (q.Control&2)==0)
for n in range(20):b.ReadDoubleWord(0x40061000)
check('reads-do-not-complete',q.Busy and q.Completions==0)
epoch=g.Mspi1Clock.ChangeEpoch
g.WriteDoubleWord(0x3110,0xa4234)
check('same-clock-write-preserves-epoch',g.Mspi1Clock.ChangeEpoch==epoch)
blocked('busy-restart',lambda:b.WriteDoubleWord(0x40061000,0xc1))
blocked('busy-reconfigure',lambda:b.WriteDoubleWord(0x40061084,0))
'''
PHASES=[(5,"check('not-early',q.Busy and not q.ResetArmed)\n"),
(5,"check('66-completes-and-arms',not q.Busy and q.Completions==1 and q.ResetArmed and q.Control==0xc2 and i.Status==1)\ncheck('hardware-event-not-MMIO-write',i.Writes==0 and not i.IRQ.IsSet)\nb.WriteDoubleWord(0x40061200,1)\ncheck('hardware-event-NVIC21',i.IRQ.IsSet and (b.ReadDoubleWord(0xe000e200)&(1<<21))!=0)\nb.WriteDoubleWord(0x40061000,2)\ncheck('STATUS-W1C',q.Control==0xc0 and q.ResetArmed)\nb.WriteDoubleWord(0x40061208,0xffffffff)\nstart(0)\n"),
(10,"check('NOP-invalidates-latch',not q.ResetArmed and q.Completions==2)\nstart(0x99)\n"),
(10,"check('unarmed-reset-ignored',q.IgnoredResets==1 and q.Resets==0 and not q.Recovering)\nstart(0x66)\n"),
(10,"check('rearmed',q.ResetArmed)\nstart(0x99)\n"),
(10,"check('wire-done-reset-recovering',q.Completions==5 and q.Resets==1 and q.Recovering and not q.Busy and not q.ResetArmed and (q.Control&2)!=0)\ninstr(0x66)\nblocked('recovery-still-unknown',lambda:b.WriteDoubleWord(0x40061000,0xc1))\n"),
(99,"check('recovery-not-early',q.Recovering)\n"),
(1,"check('recovery-finished',not q.Recovering)\nstart(0x66)\ng.WriteDoubleWord(0x3110,0xa4214)\ng.WriteDoubleWord(0x3110,0xa4234)\n"),
(10,"check('transient-clock-off-aborts',q.Aborted==1 and not q.Busy and q.Completions==5 and not q.ResetArmed)\ng.WriteDoubleWord(0x3110,0xa4234)\nstart(0x66)\ng.Reset()\ncheck('owner-reset-cancels',not q.Busy and not q.ResetArmed and q.Starts==q.Completions==q.Resets==q.Reads==q.Writes==0)\n"),
(200,"check('no-post-reset-event',q.Completions==0 and not q.ResetArmed and i.Status==0)\n")]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--stuck',action='store_true');a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-clear-all-main-01/stock24/board.repl').read_text(),complete=not a.stuck));(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'));(o/'setup.py').write_text(SETUP);resc='include @/work/strict.cs\nmach create "mspi-pio-reset"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 phases=[(1000,"check('stuck-no-completion',q.Busy and q.Starts==1 and q.Completions==0 and not q.ResetArmed and not q.Recovering)\n")] if a.stuck else PHASES
 for n,(us,phase) in enumerate(phases):
  (o/f'phase-{n}.py').write_text(phase);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'result.py').write_text("Console.WriteLine('BLACKWALL_MSPI1_PIO_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='synthetic idle NOR, 10us controller and 100us recovery hypotheses; no physical transfer or ID/backing')))\n");(o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_MSPI1_PIO_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_PIO_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing PIO result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
