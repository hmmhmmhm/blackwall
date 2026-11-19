"""Test explicit STIMER interrupt storage through the strict mapped fixture; no counter or IRQ delivery."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallG2StartupFixture,BlackwallStimerInterruptStorage
checks=[]
def check(n,ok):
    if not ok:raise Exception(n)
    checks.append(n)
s=BlackwallStimerInterruptStorage('source-reset-storage')
q=BlackwallG2StartupFixture(0x23000,0x40001000,stimer=s)
def read(a):return q.ReadDoubleWord(a-0x40001000)
def write(a,v):q.WriteDoubleWord(a-0x40001000,v)
def blocked(n,fn):
    before=(s.Enable,s.Status,s.Reads,s.Writes);count=q.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,before==(s.Enable,s.Status,s.Reads,s.Writes) and q.AccessCount==count+1)
check('explicit-reset',read(0x40008900)==0 and read(0x40008904)==0 and not s.Pending)
write(0x40008900,1);check('guest-enable-no-event',s.Enable==1 and not s.Pending)
write(0x4000890c,3);check('software-event-set',read(0x40008904)==3 and s.Pending)
write(0x40008908,1);check('clear-only-selected',read(0x40008904)==2 and not s.Pending)
write(0x40008900,2);check('enable-existing-event',s.Pending)
write(0x4000890c,0);write(0x40008908,0);check('zero-alias-no-effect',s.Status==2)
write(0x40008904,0);check('explicit-zero-status-reset',s.Status==0 and not s.Pending)
for a in [0x40008900,0x40008904,0x40008908,0x4000890c]:blocked('reserved-bit-'+str(a),lambda:write(a,0x2000))
blocked('nonzero-status-assignment-unmodeled',lambda:write(0x40008904,1))
for a in [0x40008908,0x4000890c,0x40008910,0x40008804]:blocked('unmodeled-read-'+str(a),lambda:read(a))
blocked('byte-access',lambda:q.ReadByte(0x7900));blocked('word-access',lambda:q.WriteWord(0x7900,1));blocked('unaligned',lambda:read(0x40008901))
write(0x40008900,0x1fff);write(0x4000890c,0x1fff);check('all-defined-fields',s.Status==0x1fff and s.Pending)
write(0x40008908,0x1fff);check('clear-all-defined-fields',s.Status==0 and not s.Pending)
s.Reset();check('storage-reset',s.Enable==s.Status==s.Reads==s.Writes==0 and not s.Pending)
write(0x40008900,1);write(0x4000890c,1);q.Reset();check('fixture-owner-reset',s.Enable==s.Status==s.Reads==s.Writes==0 and not s.Pending)
default=BlackwallG2StartupFixture(0x23000,0x40001000)
try:default.ReadDoubleWord(0x7900)
except Exception as e:check('default-strict','BLACKWALL unsupported' in str(e))
else:raise Exception('default unexpectedly supports stimer')
for profile in [None,'','auto']:
    try:BlackwallStimerInterruptStorage(profile)
    except Exception as e:check('invalid-profile-'+str(profile),'Explicit STIMER interrupt storage' in str(e))
    else:raise Exception('implicit profile accepted')
Console.WriteLine('BLACKWALL_STIMER_INTERRUPT_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='digital storage/pending only; no counter, compare, capture or NVIC delivery')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence output required')
 frozen=(a.simulator/'pmic-ldsw-main-01/stock24/strict.cs').read_bytes();old=(a.simulator/'source-backup-stimer-base.cs').read_bytes() if (a.simulator/'source-backup-stimer-base.cs').exists() else (ROOT/'tools/renode-strict-mmio.cs').read_bytes()
 if not frozen.startswith(old):raise ValueError('Frozen core prefix differs')
 core=(ROOT/'tools/renode-strict-mmio.cs').read_bytes();addon=ROOT/'tools/renode-stimer-interrupt-probe.cs';strict=core+frozen[len(old):]+(b'\n'+addon.read_bytes() if addon.exists() else b'')
 o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(strict);(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "stimer-interrupt"\ninclude @/work/test.py\nquit\n');compile(DRIVER,'test.py','exec')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_STIMER_INTERRUPT_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_STIMER_INTERRUPT_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing STIMER unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
