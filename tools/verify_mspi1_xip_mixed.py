"""Verify guarded mixed-mode storage with an all-unknown XIP aperture."""
import argparse,json
from pathlib import Path
from verify_mspi1_pio_reset import models
from verify_mspi1_xip_turnaround import DRIVER as PRIOR_DRIVER
from native_replay import IMAGE
from run_renode_m55_probe import execute

def board(text,enabled=True):
 needle='    profile: "source-reset-config"\n'
 if text.count(needle)!=1:raise ValueError('Unexpected config owner')
 return text.replace(needle,needle+'    xipMixedStorage: '+str(enabled).lower()+'\n')
DRIVER=PRIOR_DRIVER[:PRIOR_DRIVER.index("Console.WriteLine('BLACKWALL_MSPI1_XIP_TURNAROUND_UNIT")].replace('p.StatusWord,c.TurnaroundWrites)','p.StatusWord,c.TurnaroundWrites,c.MixedWrites)')+'''
check('mixed-selected-reset',c.XipMixedStorage and c.MixedWrites==0)
check('mixed-ready',p.TryWrite(0x8000,True));p.ReadStatus();g.WriteDoubleWord(0x3110,0xa4234)
b.WriteDoubleWord(0x40061080,0x19);b.WriteDoubleWord(0x40061090,0x5ec);b.WriteDoubleWord(0x40061090,0x5ed);b.WriteDoubleWord(0x40061090,0x205ed)
b.WriteDoubleWord(0x40061090,0x200ed)
check('D4-to-NORMAL',c.Values[0x90]==0x200ed and c.MixedWrites==1 and c.TurnaroundWrites==1 and x.EnableRequests==1 and x.Transitions==1)
for mode in [1,3,5,7,9,11,0]:
    b.WriteDoubleWord(0x40061090,0x200ed|(mode<<8))
    check('documented-mode-'+str(mode),c.Values[0x90]==(0x200ed|(mode<<8)))
for mode in [2,4,6,8,10,12,13,14,15]:blocked('reserved-mode-'+str(mode),lambda mode=mode:b.WriteDoubleWord(0x40061090,0x200ed|(mode<<8)))
blocked('mixed-no-data',lambda:b.ReadDoubleWord(0x80000000))
b.WriteDoubleWord(0x40061090,0x5ed)
check('combined-format-and-turnaround',c.Values[0x90]==0x5ed and c.MixedWrites==9 and c.TurnaroundWrites==2)
g.WriteDoubleWord(0x3110,0xa4214)
blocked('mixed-clock-off',lambda:b.WriteDoubleWord(0x40061090,0xed))
g.WriteDoubleWord(0x3110,0xa4234)
b.WriteDoubleWord(0x40061084,0x1410061);b.WriteDoubleWord(0x4006100c,0x66);b.WriteDoubleWord(0x40061000,0xc1)
blocked('mixed-PIO-busy',lambda:b.WriteDoubleWord(0x40061090,0xed))
g.Reset();check('mixed-owner-reset',c.MixedWrites==c.TurnaroundWrites==0 and c.Values[0x90]==0 and not x.Enabled)
Console.WriteLine('BLACKWALL_MSPI1_XIP_MIXED_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='documented mixed field storage only; no SPI lane data, XIP bytes or physical flash')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-xip-turnaround-main-01/stock24/board.repl').read_text()));(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "xip-turnaround"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_MSPI1_XIP_MIXED_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_XIP_MIXED_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing timing result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
