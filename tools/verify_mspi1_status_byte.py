"""Test explicit immutable status-byte fixtures and default unknown status boundary."""
import argparse,json,struct
from pathlib import Path
from verify_mspi1_rdid import COMMON
from verify_mspi1_sampling_profile import board as sampling_board
from verify_mspi1_pio_reset import models
from native_replay import IMAGE
from run_renode_m55_probe import execute

def board(text,status=None,identity=True):
 text=sampling_board(text)
 if status is not None:text=text.replace('    profile: "idle-nor-reset"\n','    profile: "idle-nor-reset"\n    statusByte: '+str(status)+'\n')
 if not identity:text=text.replace('    identityProfile: "mx25u25643g"\n','    identityProfile: "none"\n')
 return text
SETUP=COMMON+'''def status_start():b.WriteDoubleWord(0x40061000,0x10441)
def status_config():
    b.WriteDoubleWord(0x40061084,0x3010061)
    b.WriteDoubleWord(0x4006100c,5)
status_config()
'''
def phases(status):
 return [(5,"check('status-not-early',q.Busy and q.RxEntries==q.StatusReadTransfers==0)\n"),(5,"check('status-ready',not q.Busy and q.RxEntries==1 and q.StatusReadTransfers==1 and q.ReadIdTransfers==0 and q.Control==0x10442 and i.Status==1 and i.Writes==0)\nblocked('status-unread-overwrite',status_start)\ncheck('status-byte-and-zero-padding',b.ReadDoubleWord(0x40061014)=="+str(status)+")\nblocked('status-empty-FIFO',lambda:b.ReadDoubleWord(0x40061014))\nstatus_start()\n"),(10,"check('repeated-status-not-cleared',b.ReadDoubleWord(0x40061014)=="+str(status)+" and q.StatusReadTransfers==2 and q.ReadIdTransfers==0)\nstatus_start();g.WriteDoubleWord(0x3110,0xa4214);g.WriteDoubleWord(0x3110,0xa4234)\n"),(10,"check('status-clock-abort',q.Aborted==1 and not q.Busy and q.StatusReadTransfers==2 and q.RxEntries==0)\nstatus_start();g.Reset()\n"),(20,"check('status-reset-cancels-event',not q.Busy and q.StatusReadTransfers==q.Completions==q.RxEntries==0 and q.StatusByte=="+str(status)+")\nready();status_config();status_start()\n"),(10,"check('status-fixture-after-reset',b.ReadDoubleWord(0x40061014)=="+str(status)+" and q.StatusReadTransfers==1)\nb.WriteDoubleWord(0x4006100c,0x9f);b.WriteDoubleWord(0x40061000,0x30441)\n"),(10,"check('ID-still-separate',b.ReadDoubleWord(0x40061014)==0x3925c2 and q.ReadIdTransfers==1 and q.StatusReadTransfers==1)\nstatus_config();status_start()\n"),(10,"check('status-FIFO-discarded-on-reset',q.RxEntries==1)\ng.Reset()\ncheck('status-owner-reset-clears-FIFO',q.RxEntries==q.StatusReadTransfers==0 and q.StatusByte=="+str(status)+")\n")]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--status',type=int);p.add_argument('--none',action='store_true');p.add_argument('--stuck',action='store_true');a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);b=board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),a.status,not a.none)
 if a.stuck:b=b.replace('    completeTransactions: true\n','    completeTransactions: false\n')
 (o/'board.repl').write_text(b);(o/'strict.cs').write_bytes(models(s));(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'));setup=SETUP;steps=[]
 if a.status is None or a.none:setup+="blocked('unknown-or-no-identity-status',status_start)\n"
 else:
  setup+="check('explicit-status-fixture',q.StatusByte=="+str(a.status)+")\nblocked('status-wrong-length',lambda:b.WriteDoubleWord(0x40061000,0x20441))\nb.WriteDoubleWord(0x40061084,0x3010861)\nblocked('status-unsupported-turnaround',status_start)\nstatus_config();b.WriteDoubleWord(0x4006100c,0x35)\nblocked('status-unknown-command',status_start)\nstatus_config();status_start()\ncheck('status-start-not-data',q.Busy and q.RxEntries==q.StatusReadTransfers==0)\nblocked('status-premature-FIFO',lambda:b.ReadDoubleWord(0x40061014))\n";steps=[(1000,"check('status-stuck-no-completion',q.Busy and q.StatusReadTransfers==q.RxEntries==0)\n")] if a.stuck else phases(a.status)
 (o/'setup.py').write_text(setup);resc='include @/work/strict.cs\nmach create "status-byte"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 for n,(us,code) in enumerate(steps):
  (o/f'phase-{n}.py').write_text(code);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'result.py').write_text("Console.WriteLine('BLACKWALL_STATUS_BYTE '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='immutable explicit byte fixture, not observed device state or NV storage')))\n");(o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_STATUS_BYTE ')]
 if len(rows)!=1:raise ValueError('Missing status-byte result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
