"""Test bounded zero-turnaround RDID under ideal SDR, plus default and missing-ID controls."""
import argparse,json,struct
from pathlib import Path
from verify_mspi1_rdid import COMMON
from verify_mspi1_sampling_profile import board
from verify_mspi1_pio_reset import models
from native_replay import IMAGE
from run_renode_m55_probe import execute
SETUP=COMMON+'''b.WriteDoubleWord(0x40061084,0x3010061)
'''
def phases():
 steps=[(5,"check('zero-RX-not-early',q.Busy and q.RxEntries==0 and q.ReadIdTransfers==0)\n"),(5,"check('zero-RX-complete',not q.Busy and q.RxEntries==1 and q.ReadIdTransfers==1 and q.Control==0x30442)\nblocked('unread-zero-frame-protected',start)\ncheck('zero-ID-bytes',b.ReadDoubleWord(0x40061014)==0x3925c2)\nblocked('zero-empty-FIFO',lambda:b.ReadDoubleWord(0x40061014))\ng.Reset();ready()\nb.WriteDoubleWord(0x40061084,0x2010061)\nstart()\n")]
 for phase in range(8):
  code="check('zero-phase-complete-"+str(phase)+"',not q.Busy and q.RxEntries==1 and q.ReadIdTransfers=="+str(phase+1)+")\ncheck('zero-phase-ID-"+str(phase)+"',b.ReadDoubleWord(0x40061014)==0x3925c2 and q.CompletedSamplingMask=="+str((1<<(phase+1))-1)+")\n"
  if phase<7:code+='b.WriteDoubleWord(0x40061084,'+str(0x2010061|((phase+1)<<22))+')\nstart()\n'
  else:
   for turn in [1,7,9,63]:code+='b.WriteDoubleWord(0x40061084,'+str(0x3010061|(turn<<8))+')\nblocked("unsupported-turnaround-'+str(turn)+'",start)\n'
   code+="b.WriteDoubleWord(0x40061084,0x3010061)\nb.WriteDoubleWord(0x4006100c,5)\nblocked('zero-unknown-command',start)\nb.WriteDoubleWord(0x4006100c,0x9f)\nblocked('zero-wrong-length',lambda:b.WriteDoubleWord(0x40061000,0x40441))\nb.WriteDoubleWord(0x40061084,0x1010061)\nblocked('zero-other-config-strict',start)\nb.WriteDoubleWord(0x40061084,0x3010061)\nstart();g.WriteDoubleWord(0x3110,0xa4214);g.WriteDoubleWord(0x3110,0xa4234)\n"
  steps.append((10,code))
 steps+=[(10,"check('zero-clock-change-aborts',q.Aborted==1 and q.ReadIdTransfers==8 and q.RxEntries==0 and not q.Busy)\nstart();g.Reset()\n"),(20,"check('zero-reset-cancels',q.ReadIdTransfers==q.Completions==q.CompletedSamplingMask==0 and not q.Busy)\n")]
 return steps
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--fixed',action='store_true');p.add_argument('--none',action='store_true');a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);b=board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),not a.fixed)
 if a.none:b=b.replace('    identityProfile: "mx25u25643g"\n','    identityProfile: "none"\n')
 (o/'board.repl').write_text(b);(o/'strict.cs').write_bytes(models(s));(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'))
 setup=SETUP+("blocked('zero-without-profile-or-identity',start)\n" if a.fixed or a.none else "start()\ncheck('zero-start-pending',q.Busy and q.RxEntries==0)\nblocked('zero-read-before-complete',lambda:b.ReadDoubleWord(0x40061014))\n");steps=[] if a.fixed or a.none else phases();(o/'setup.py').write_text(setup);resc='include @/work/strict.cs\nmach create "zero-turnaround"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 for n,(us,code) in enumerate(steps):
  (o/f'phase-{n}.py').write_text(code);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'result.py').write_text("Console.WriteLine('BLACKWALL_ZERO_RDID '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='ideal digital RDID, zero turnaround; no physical validation or backing')))\n");(o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_ZERO_RDID ')]
 if len(rows)!=1:raise ValueError('Missing zero-turnaround result; inspect saved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
