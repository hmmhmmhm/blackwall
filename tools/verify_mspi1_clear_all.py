"""Test explicit HAL MSPI clear-all while preserving strict handling of other unknown bits."""
import argparse,json
from pathlib import Path
from verify_timer14 import models as prior_models
from verify_mspi1_interrupts import DRIVER as PRIOR_DRIVER
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def models(s):
 old=(s/'mspi1-clear-all-research-01/base-config.cs').read_bytes();data=prior_models(s)
 if data.count(old)!=1:raise ValueError('Frozen config differs')
 return data.replace(old,(ROOT/'tools/renode-mspi1-config.cs').read_bytes())
def board(text,enabled=True):
 needle='    profile: "source-reset"\n    IRQ -> nvic@21\n'
 if text.count(needle)!=1:raise ValueError('Unexpected MSPI IRQ profile')
 return text.replace(needle,'    profile: "source-reset"\n    allowAllClear: '+str(enabled).lower()+'\n    IRQ -> nvic@21\n')
DRIVER=PRIOR_DRIVER[:PRIOR_DRIVER.index("Console.WriteLine('BLACKWALL_MSPI1_INTERRUPTS_UNIT")]+'''
check('clear-all-selected',i.AllowAllClear and i.ClearAllWrites==0)
check('ready-again',p.TryWrite(0x8000,True));p.ReadStatus()
b.WriteDoubleWord(0x40061200,0x3fff);b.WriteDoubleWord(0x4006120c,0x3fff)
check('all-status-set',i.Status==0x3fff and i.IRQ.IsSet)
b.WriteDoubleWord(0x40061208,0xffffffff)
check('HAL-clear-all',i.Status==0 and i.Enable==0x3fff and not i.IRQ.IsSet and i.ClearAllWrites==1)
b.WriteDoubleWord(0x40061208,0xffffffff)
check('clear-all-idempotent',i.Status==0 and i.ClearAllWrites==2)
blocked('enable-all-still-strict',lambda:b.WriteDoubleWord(0x40061200,0xffffffff))
blocked('set-all-still-strict',lambda:b.WriteDoubleWord(0x4006120c,0xffffffff))
blocked('other-reserved-clear-still-strict',lambda:b.WriteDoubleWord(0x40061208,0x80000001))
g.Reset();check('clear-all-owner-reset',i.ClearAllWrites==i.Status==i.Enable==0 and not i.IRQ.IsSet)
Console.WriteLine('BLACKWALL_MSPI1_CLEAR_ALL_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='HAL exact FFFFFFFF clear command only; reserved behavior not generalized, software events, no physical transfer')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-interrupts-unit-02/board.repl').read_text()));(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "mspi-clear-all"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');r=[json.loads(x.split('BLACKWALL_MSPI1_CLEAR_ALL_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_CLEAR_ALL_UNIT ')]
 if len(r)!=1:raise ValueError('Missing clear-all result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(r[0],indent=2)+'\n');print(json.dumps(dict(passed=r[0]['passed'],count=r[0]['count'])))
if __name__=='__main__':main()
