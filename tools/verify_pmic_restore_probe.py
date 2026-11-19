"""Check the declared seven-byte read-only PMIC startup fixture and strict boundaries."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import clr,json
from System import Array,Byte,Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallPmicRestoreProbe').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallPmicRestoreProbe
p=BlackwallPmicRestoreProbe('source-reset-readonly');checks=[]
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
def state():return (p.Pointer,p.PointerWrites,p.DataReads,p.Finishes,p.ReturnedBytes,list(p.ReadAddresses),list(p.ReadValues))
def write(v):p.Write(Array[Byte](v))
def blocked(name,fn):
    old=state();before=p.AccessCount
    try:fn()
    except Exception as e:
        if 'PMIC restore unsupported' not in str(e):raise
    else:raise Exception(name+' accepted')
    check(name,state()==old and p.AccessCount==before+1)
blocked('unselected-read',lambda:p.Read(1));blocked('unselected-finish',lambda:p.FinishTransmission())
for n,data in enumerate([[],[5],[5,9,1],[5,11],[0,0],[3,9]]):blocked('bad-write-'+str(n),lambda:write(data))
blocked('null-write',lambda:p.Write(None))
plan=[(0x509,[0]),(0x50a,[1]),(0x308,[8,0]),(0x30a,[0xcf,1]),(0xb04,[3])]
for address,expected in plan:
    write([address>>8,address&255]);blocked('pending-read-'+str(address),lambda:p.Read(len(expected)))
    p.FinishTransmission();blocked('wrong-width-'+str(address),lambda:p.Read(3))
    check('exact-read-'+str(address),list(p.Read(len(expected)))==expected);p.FinishTransmission()
check('read-history',list(p.ReadAddresses)==[x[0] for x in plan] and list(p.ReadValues)==[0,1,8,0x1cf,3] and p.ReturnedBytes==7)
copy=p.ReadAddresses;copy[0]=0;check('history-copy',p.ReadAddresses[0]==0x509)
for n in range(11):
    write([5,9]);p.FinishTransmission();p.Read(1);p.FinishTransmission()
write([5,9]);p.FinishTransmission();blocked('bounded-history',lambda:p.Read(1))
p.Reset();check('reset',p.Pointer==-1 and p.PointerWrites==0 and p.DataReads==0 and p.AccessCount==0 and len(p.ReadAddresses)==0)
for profile in ['',None,'auto']:
    try:BlackwallPmicRestoreProbe(profile)
    except Exception as e:check('invalid-profile-'+str(profile),'Explicit PMIC restore profile' in str(e))
    else:raise Exception('implicit profile accepted')
Console.WriteLine('BLACKWALL_RESTORE_UNIT '+json.dumps(dict(passed=True,checks=checks,count=len(checks),scope='declared read-only register fixture, no physical PMIC or main execution')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Use new evidence directory')
 o.mkdir(mode=0o700);(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes());(o/'test.py').write_text(DRIVER);compile(DRIVER,'test.py','exec');(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "restore-fixture"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
 rows=[json.loads(x.split('BLACKWALL_RESTORE_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RESTORE_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing unit marker')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))
if __name__=='__main__':main()
