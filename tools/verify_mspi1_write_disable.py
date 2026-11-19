"""Test completed WRDI clears only WEL in the opt-in idle NOR latch model."""
import argparse,ast,json,struct
from pathlib import Path
from verify_mspi1_status_byte import SETUP
from verify_mspi1_write_enable import HELPERS
from verify_mspi1_address_mode import ADDRESS_HELPERS,board as address_board
from verify_mspi1_pio_reset import models
from native_replay import IMAGE
from run_renode_m55_probe import execute
WRDI_HELPER='''def wrdi():
    status_config();b.WriteDoubleWord(0x4006100c,4);b.WriteDoubleWord(0x40061000,0xc1)
'''
def board(text,enabled=True,complete=True,seed=64):
 b=address_board(text,0,complete).replace('    statusByte: 64\n','    statusByte: '+str(seed)+'\n')
 return b if enabled else b.replace('    emulateWriteEnableLatch: true\n','    emulateWriteEnableLatch: false\n')
def phases(seed=64):
 result=[(10,"check('WREN-precondition',q.WriteEnabled and q.CurrentStatusByte==@WEL_STATUS@)\nen4b()\n"),(10,"check('mode-before-WRDI',q.FourByteAddressMode and q.WriteEnabled)\nwrdi()\ncheck('WRDI-start-not-clear',q.Busy and q.WriteEnabled and q.WriteDisableTransfers==0)\n"),(5,"check('WRDI-not-early',q.Busy and q.WriteEnabled)\n"),(5,"check('WRDI-clears-only-WEL',not q.Busy and not q.WriteEnabled and q.CurrentStatusByte==@SEED_STATUS@ and q.FourByteAddressMode and q.CurrentConfigurationByte==0x20 and q.WriteDisableTransfers==1 and q.RxEntries==0)\nstatus_start()\n"),(10,"check('RDSR-after-WRDI',b.ReadDoubleWord(0x40061014)==@SEED_STATUS@)\nrdcr()\n"),(10,"check('RDCR-after-WRDI',b.ReadDoubleWord(0x40061014)==0x20)\nwrdi()\n"),(10,"check('WRDI-repeat-idempotent',not q.WriteEnabled and q.WriteDisableTransfers==2 and q.FourByteAddressMode)\nwren()\n"),(10,"check('WREN-reenable',q.WriteEnabled)\nwrdi();g.WriteDoubleWord(0x3110,0xa4214);g.WriteDoubleWord(0x3110,0xa4234)\n"),(10,"check('WRDI-abort-preserves-WEL',q.Aborted==1 and q.WriteEnabled and q.WriteDisableTransfers==2 and q.FourByteAddressMode)\nwrdi();g.Reset()\n"),(20,"check('owner-reset-cancels-WRDI',q.WriteDisableTransfers==0 and not q.WriteEnabled and not q.Busy and not q.FourByteAddressMode)\nready();reset_wire(0x66)\n"),(10,"check('WRDI-before-reset-latch',q.ResetArmed)\nwrdi()\n"),(10,"check('WRDI-cancels-reset-enable',not q.ResetArmed and not q.WriteEnabled and q.WriteDisableTransfers==1)\nstatus_config();b.WriteDoubleWord(0x4006100c,4)\nblocked('WRDI-wrong-length',lambda:b.WriteDoubleWord(0x40061000,0x100c1))\nb.WriteDoubleWord(0x40061084,0x3010861)\nblocked('WRDI-wrong-config',lambda:b.WriteDoubleWord(0x40061000,0xc1))\nfor cmd in [1,2,3,0xe9]:\n    b.WriteDoubleWord(0x4006100c,cmd);blocked('unsupported-device-command-'+str(cmd),lambda:b.WriteDoubleWord(0x40061000,0xc1))\n")]
 return [(us,code.replace('@WEL_STATUS@',hex(seed|2)).replace('@SEED_STATUS@',hex(seed))) for us,code in result]
def validate_fixture_addresses(steps):
 allowed={0x40061000,0x4006100c,0x40061014,0x40061084,0x3110};count=0
 for us,code in steps:
  for node in ast.walk(ast.parse(code)):
   if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ('ReadDoubleWord','WriteDoubleWord','ReadByte') and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,int):
    if node.args[0].value not in allowed:raise ValueError('Unapproved fixture MMIO address '+hex(node.args[0].value))
    count+=1
 return count
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--nv',action='store_true');p.add_argument('--disabled',action='store_true');p.add_argument('--stuck',action='store_true');a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);(o/'board.repl').write_text(board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),not a.disabled,not a.stuck,252 if a.nv else 64));(o/'strict.cs').write_bytes(models(s));(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'));setup=SETUP+HELPERS+ADDRESS_HELPERS+WRDI_HELPER;steps=[]
 if a.disabled:setup+="blocked('disabled-WRDI',wrdi)\n"
 elif a.stuck:setup+="wrdi()\n";steps=[(1000,"check('stuck-WRDI-no-completion',q.Busy and q.WriteDisableTransfers==0)\n")]
 else:setup+="wren()\n";steps=phases(252 if a.nv else 64)
 validate_fixture_addresses([(0,setup)]+steps)
 (o/'setup.py').write_text(setup);resc='include @/work/strict.cs\nmach create "write-disable"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 for n,(us,code) in enumerate(steps):
  (o/f'phase-{n}.py').write_text(code);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'result.py').write_text("Console.WriteLine('BLACKWALL_WRDI_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='opt-in WRDI WEL clear only; no array or NV writes or physical proof')))\n");(o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_WRDI_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing WRDI result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
