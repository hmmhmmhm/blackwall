"""Verify source-bounded LDSW/LDO storage and request-only tasks without rail responses."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from verify_pmic_charger_status import STATUS
from verify_pmic_buck_storage import BUCK
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
LDSW='''
addresses=[0x805,0x806,0x807,0x808,0x809,0x80c,0x80d]
def ldsw(profile):return BlackwallPmicRestoreProbe('source-reset-readonly',None,None,None,None,None,None,-1,None,None,profile)
p=ldsw('source-reset-storage')
check('ldsw-reset-zero-config',p.LdswState=='source-reset-storage' and list(p.LdswKnownAddresses)==addresses and list(p.LdswKnownValues)==[0]*7)
check('ldsw-contiguous-config-read',read_config(0x805,5)==[0]*5 and read_config(0x80c,2)==[0,0])
for a,value in [(0x805,15),(0x806,15),(0x807,255),(0x808,1),(0x809,1),(0x80c,23),(0x80d,23)]:
    put(a,[value]);check('ldsw-config-store-'+str(a),read_config(a)==[value])
put(0x805,[9,10,255,1,0]);check('ldsw-group-burst',read_config(0x805,5)==[9,10,255,1,0])
write([8,5]);p.FinishTransmission();check('ldsw-direct-read-head',list(p.Read(4))==[9,10,255,1])
blocked('ldsw-split-tail-unmodeled',lambda:p.Read(1));p.FinishTransmission()
check('ldsw-new-transaction-after-split-guard',read_config(0x809)==[0])
for a,data in [(0x805,[16]),(0x806,[1,0,2]),(0x808,[1,1,0]),(0x80c,[4,24]),(0x803,[1,0]),(0x807,[0,1,2])]:
    before=(list(p.LdswKnownValues),p.LdswConfigWrites,p.LdswTaskWrites,p.RegisterWrites,list(p.LdswTaskRequests))
    blocked('ldsw-invalid-write-'+str(a),lambda:write([a>>8,a&255]+data))
    check('ldsw-invalid-atomic-'+str(a),before==(list(p.LdswKnownValues),p.LdswConfigWrites,p.LdswTaskWrites,p.RegisterWrites,list(p.LdswTaskRequests)))
p.Reset()
for a in range(0x800,0x804):
    put(a,[0]);check('ldsw-zero-task-'+str(a),sum(p.LdswTaskRequests)==a-0x800)
    put(a,[1]);check('ldsw-request-task-'+str(a),p.LdswTaskRequests[a-0x800]==1)
    blocked('ldsw-task-read-denied-'+str(a),lambda:write([a>>8,a&255]))
    blocked('ldsw-task-mask-'+str(a),lambda:write([a>>8,a&255,2]))
check('ldsw-four-requests',list(p.LdswTaskRequests)==[1]*4 and p.LdswTaskWrites==8 and p.LdswConfigWrites==0)
for a in [0x804,0x80a,0x80b,0x80e,0x208]:
    blocked('ldsw-status-gap-revision-read-'+str(a),lambda:write([a>>8,a&255]))
    blocked('ldsw-status-gap-revision-write-'+str(a),lambda:write([a>>8,a&255,1]))
write([8,9]);p.FinishTransmission()
for width in [0,-1,2,2147483647]:blocked('ldsw-invalid-read-'+str(width),lambda:p.Read(width))
check('ldsw-read-after-block',list(p.Read(1))==[0]);p.FinishTransmission()
copy=p.LdswKnownValues;copy[0]=99;check('ldsw-copy',p.LdswKnownValues[0]==0)
p.Reset();check('ldsw-reset-clears-requests',list(p.LdswKnownValues)==[0]*7 and list(p.LdswTaskRequests)==[0]*4 and p.LdswTaskWrites==0)
p=ldsw('guest-storage');check('ldsw-initial-unknown',len(p.LdswKnownAddresses)==0)
blocked('ldsw-unknown-mode-read',lambda:write([8,8]));put(0x808,[1]);check('ldsw-known-after-write',read_config(0x808)==[1] and list(p.LdswKnownAddresses)==[0x808])
p.Reset();check('ldsw-unknown-after-reset',len(p.LdswKnownAddresses)==0)
p=ldsw(None);blocked('ldsw-default-mode-strict',lambda:write([8,8]));blocked('ldsw-default-task-strict',lambda:write([8,0,1]))
for profile in ['','auto','npm1304-soft-start']:
    try:ldsw(profile)
    except Exception as e:check('ldsw-invalid-profile-'+profile,'Explicit LDSW storage' in str(e))
    else:raise Exception('invalid LDSW profile accepted')
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh output required')
 o.mkdir(mode=0o700);driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+STATUS+BUCK+LDSW+"\nConsole.WriteLine('BLACKWALL_LDSW_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='source-bounded configuration/task requests; no analog/status/GPIO/soft-start response')))\n";compile(driver,'test.py','exec');(o/'test.py').write_text(driver);(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes());(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "ldsw-storage"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_LDSW_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_LDSW_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing LDSW unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
