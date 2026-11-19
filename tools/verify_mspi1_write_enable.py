"""Test opt-in idle WEL transitions without implementing NOR content or NV writes."""
import argparse,json,struct
from pathlib import Path
from verify_mspi1_status_byte import SETUP,board as status_board
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute
from native_replay import IMAGE

def board(text,seed=64,enabled=True,complete=True):
 text=status_board(text,seed)
 if enabled:text=text.replace('    profile: "idle-nor-reset"\n','    profile: "idle-nor-reset"\n    emulateWriteEnableLatch: true\n')
 if not complete:text=text.replace('    completeTransactions: true\n','    completeTransactions: false\n')
 return text
HELPERS='''def wren():
    status_config();b.WriteDoubleWord(0x4006100c,6);b.WriteDoubleWord(0x40061000,0xc1)
def status_start():status_config();b.WriteDoubleWord(0x40061000,0x10441)
def reset_wire(v):
    b.WriteDoubleWord(0x40061084,0x1410061);b.WriteDoubleWord(0x4006100c,v);b.WriteDoubleWord(0x40061000,0xc1)
'''
def phases(seed):
 latched=seed|2
 return [(5,"check('WREN-not-early',q.Busy and not q.WriteEnabled and q.WriteEnableTransfers==0)\n"),(5,"check('WREN-completed',not q.Busy and q.WriteEnabled and q.WriteEnableTransfers==1 and q.CurrentStatusByte=="+str(latched)+" and q.RxEntries==0 and q.Control==0xc2)\nstatus_start()\n"),(10,"check('RDSR-exposes-WEL-preserves-NV',b.ReadDoubleWord(0x40061014)=="+str(latched)+" and q.WriteEnabled and q.StatusReadTransfers==1)\nwren()\n"),(10,"check('WREN-repeat-idempotent',q.WriteEnabled and q.WriteEnableTransfers==2 and q.CurrentStatusByte=="+str(latched)+")\nreset_wire(0x66)\n"),(10,"check('RSTEN-preserves-WEL',q.ResetArmed and q.WriteEnabled)\nreset_wire(0)\n"),(10,"check('NOP-cancels-RSTEN-preserves-WEL',not q.ResetArmed and q.WriteEnabled)\nreset_wire(0x99)\n"),(10,"check('unarmed-reset-preserves-WEL',q.IgnoredResets==1 and q.WriteEnabled and not q.Recovering)\nreset_wire(0x66)\n"),(10,"check('rearmed-WEL-preserved',q.ResetArmed and q.WriteEnabled)\nreset_wire(0x99)\n"),(10,"check('armed-reset-clears-only-WEL',q.Resets==1 and not q.WriteEnabled and q.CurrentStatusByte=="+str(seed)+" and q.Recovering)\nblocked('reset-recovery-blocks-WREN',wren)\n"),(100,"check('reset-recovery-complete',not q.Recovering)\nstatus_start()\n"),(10,"check('reset-NV-status-preserved',b.ReadDoubleWord(0x40061014)=="+str(seed)+" and not q.WriteEnabled)\nwren();g.WriteDoubleWord(0x3110,0xa4214);g.WriteDoubleWord(0x3110,0xa4234)\n"),(10,"check('WREN-clock-change-aborts',q.Aborted==1 and q.WriteEnableTransfers==2 and not q.WriteEnabled and not q.Busy)\nwren();g.Reset()\n"),(20,"check('owner-reset-cancels-WREN',q.WriteEnableTransfers==0 and not q.WriteEnabled and not q.Busy and q.CurrentStatusByte=="+str(seed)+")\nready();wren()\n"),(10,"check('after-owner-reset-WREN',q.WriteEnabled and q.WriteEnableTransfers==1)\nfor cmd in [1,2,4,0xb7,0x20]:\n    b.WriteDoubleWord(0x4006100c,cmd);blocked('unsupported-device-command-'+str(cmd),lambda:b.WriteDoubleWord(0x40061000,0xc1))\ncheck('unsupported-commands-preserve-latch',q.WriteEnabled and q.CurrentStatusByte=="+str(latched)+")\ng.Reset()\ncheck('owner-reset-clears-volatile-latch',not q.WriteEnabled and q.CurrentStatusByte=="+str(seed)+")\n")]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--seed',type=int,default=64);p.add_argument('--disabled',action='store_true');p.add_argument('--stuck',action='store_true');a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);(o/'board.repl').write_text(board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),a.seed,not a.disabled,not a.stuck));(o/'strict.cs').write_bytes(models(s));(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'));setup=SETUP+HELPERS;steps=[]
 if a.disabled:setup+="blocked('default-no-WREN-model',wren)\n"
 else:
  setup+="check('explicit-latch-profile',q.EmulateWriteEnableLatch and q.StatusByte=="+str(a.seed)+" and q.CurrentStatusByte=="+str(a.seed)+" and not q.WriteEnabled)\nCtor=type(q)\nfor invalid in [-1,1,2,3,65,66,255]:\n    try:Ctor(m,'idle-nor-reset',p,g.Mspi1Clock,i,True,'mx25u25643g','ideal-sdr',invalid,True)\n    except Exception as e:check('invalid-latch-seed-'+str(invalid),'Latch mode requires known idle WIP/WEL0' in str(e))\n    else:raise Exception('invalid seed accepted')\nwren()\ncheck('WREN-start-not-latched',q.Busy and not q.WriteEnabled and q.RxEntries==0)\nblocked('WREN-pending-read',lambda:b.ReadDoubleWord(0x40061014))\n";steps=[(1000,"check('WREN-stuck-no-latch',q.Busy and not q.WriteEnabled and q.WriteEnableTransfers==0)\n")] if a.stuck else phases(a.seed)
 (o/'setup.py').write_text(setup);resc='include @/work/strict.cs\nmach create "write-enable"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 for n,(us,code) in enumerate(steps):
  (o/f'phase-{n}.py').write_text(code);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'result.py').write_text("Console.WriteLine('BLACKWALL_WREN_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='opt-in idle WEL latch; no NOR content, NV writes or physical behavior')))\n");(o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_WREN_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing WREN unit result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
