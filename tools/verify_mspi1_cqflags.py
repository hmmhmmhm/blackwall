"""Test selected mock buffer inputs, dynamic completion/index flags and unknown default."""
import argparse,json,struct
from pathlib import Path
from verify_mspi1_rdid import COMMON
from verify_mspi1_pio_reset import models
from native_replay import IMAGE
from run_renode_m55_probe import execute

def board(text,levels):
 if levels is None:return text
 needle='    profile: "source-reset-config"\n'
 if text.count(needle)!=1:raise ValueError('Unexpected CQ owner')
 return text.replace(needle,needle+'    cqInputLevels: '+str(levels)+'\n')
DRIVER='''c=g.Mspi1Config
TABLE=[0x300,0x1200,0x2100,0x3000]
def expect_flags(sw,completed=False,equal=True):
    return sw|TABLE[(INPUT_LEVELS^sw)&3]|(0x400 if completed else 0)|(0x4000 if equal else 0)
def flags():return b.ReadDoubleWord(0x400612b0)
'''
ACTIVE='''check('selected-mock-inputs',c.CqInputLevels==INPUT_LEVELS)
b.WriteDoubleWord(0x40061030,0xc0000070)
for sw in range(4):
    b.WriteDoubleWord(0x400612b4,0xff0000)
    b.WriteDoubleWord(0x400612b4,0x80|sw)
    check('SW-pair-truth-'+str(sw),flags()==expect_flags(0x80|sw))
b.WriteDoubleWord(0x400612c4,1)
check('indices-not-equal',flags()==expect_flags(0x83,equal=False))
b.WriteDoubleWord(0x400612c0,1)
check('indices-equal-again',flags()==expect_flags(0x83))
b.WriteDoubleWord(0x40061030,0xc00000f0)
check('disabled-route-always-zero',flags()==(0x83|TABLE[3]|0x4000))
for reserved in [12,13,14]:
    b.WriteDoubleWord(0x40061030,0xc0000000|(reserved<<4));blocked('reserved-route-'+str(reserved),flags)
b.WriteDoubleWord(0x40061030,0xc0000070)
blocked('full-flags-read-only',lambda:b.WriteDoubleWord(0x400612b0,0))
blocked('queue-execution-stays-unsupported',lambda:b.WriteDoubleWord(0x400612a0,1))
blocked('DMA-execution-stays-unsupported',lambda:b.WriteDoubleWord(0x40061100,1))
b.WriteDoubleWord(0x400612b4,0xff0000)
start();reads=q.Reads
for n in range(8):check('flags-not-PIO-completion-'+str(n),flags()==expect_flags(0) and q.Reads==reads and q.Busy)
'''
PHASES=[(5,"check('CMD-flag-not-early',flags()==expect_flags(0) and q.Busy and q.Reads==reads)\n"),(5,"check('CMD-flag-dynamic',flags()==expect_flags(0,completed=True) and not q.Busy and q.Reads==reads)\ncheck('signal-read-not-guest-read',q.CommandComplete and q.Reads==reads)\nb.WriteDoubleWord(0x40061000,2)\ncheck('STATUS-W1C-clears-CMD-flag',flags()==expect_flags(0) and not q.CommandComplete)\ncheck('FIFO-only-real-read',b.ReadDoubleWord(0x40061014)==0x3925c2 and q.Reads==reads+1)\ng.Reset()\ncheck('owner-reset-flags-counters',c.CqFlagReads==0 and c.LastCqFlags==0)\nready()\ncheck('owner-reset-signal-and-inputs',flags()==0x4300 and c.CqInputLevels==INPUT_LEVELS)\n")]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--levels',type=int,choices=range(4),default=0);p.add_argument('--unknown',action='store_true');a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);levels=None if a.unknown else a.levels;(o/'board.repl').write_text(board((s/'mspi1-write-disable-main-01/stock24/board.repl').read_text(),levels));(o/'strict.cs').write_bytes(models(s));(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'));setup=COMMON+'INPUT_LEVELS='+str(a.levels)+'\n'+DRIVER+("blocked('unknown-handshake-no-full-read',flags)\n" if a.unknown else ACTIVE);steps=[] if a.unknown else PHASES;(o/'setup.py').write_text(setup);resc='include @/work/strict.cs\nmach create "cq-flags"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 for n,(us,code) in enumerate(steps):
  (o/f'phase-{n}.py').write_text(code);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'result.py').write_text("Console.WriteLine('BLACKWALL_CQFLAGS_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='disabled CQ/DMA, explicit mock buffer pairing; no physical handshake, queue execution or IRQ proof')))\n");(o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_CQFLAGS_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing CQFLAGS result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
