"""Verify PMIC BUCK configuration storage and task requests without rail responses."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from verify_pmic_charger_status import STATUS
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
BUCK='''
addresses=[0x408,0x409,0x40a,0x40b,0x40c,0x40d,0x40e,0x40f,0x415]
def buck(profile):return BlackwallPmicRestoreProbe('source-reset-readonly',None,None,None,None,None,None,-1,None,profile)
def put(a,data):write([a>>8,a&255]+data);p.FinishTransmission()
def read_config(a,n=1):write([a>>8,a&255]);p.FinishTransmission();v=list(p.Read(n));p.FinishTransmission();return v
p=buck('source-reset-storage')
check('buck-explicit-reset',p.BuckState=='source-reset-storage' and list(p.BuckKnownAddresses)==addresses and list(p.BuckKnownValues)==[2,2,8,8,0,0,0,0,0])
check('buck-reset-read-group',read_config(0x408,8)==[2,2,8,8,0,0,0,0])
for a,value in [(0x408,0),(0x409,24),(0x40a,23),(0x40b,1),(0x40c,255),(0x40d,255),(0x40e,255),(0x40f,3),(0x415,15)]:
    put(a,[value]);check('buck-scalar-store-'+str(a),read_config(a)==[value])
put(0x408,[1,2,3,4,5,6,7,3]);check('buck-config-burst',read_config(0x408,8)==[1,2,3,4,5,6,7,3])
for a,values in [(0x408,[3,25]),(0x40e,[5,4]),(0x40f,[1,0]),(0x415,[16]),(0x407,[1,2])]:
    before=(list(p.BuckKnownValues),p.BuckConfigWrites,p.BuckTaskWrites,p.RegisterWrites)
    blocked('buck-invalid-write-'+str(a),lambda:write([a>>8,a&255]+values))
    check('buck-invalid-write-atomic-'+str(a),before==(list(p.BuckKnownValues),p.BuckConfigWrites,p.BuckTaskWrites,p.RegisterWrites))
p.Reset()
for a in range(0x400,0x408):
    put(a,[0]);check('buck-zero-task-no-request-'+str(a),sum(p.BuckTaskRequests)==a-0x400)
    put(a,[1]);check('buck-task-request-'+str(a),p.BuckTaskRequests[a-0x400]==1)
    blocked('buck-task-read-denied-'+str(a),lambda:write([a>>8,a&255]))
    blocked('buck-task-mask-'+str(a),lambda:write([a>>8,a&255,2]))
check('buck-eight-requests',list(p.BuckTaskRequests)==[1]*8 and p.BuckTaskWrites==16 and p.BuckConfigWrites==0)
for a in [0x410,0x411,0x412,0x414,0x416,0x434]:
    blocked('buck-rail-status-pointer-denied-'+str(a),lambda:write([a>>8,a&255]))
    blocked('buck-rail-status-write-denied-'+str(a),lambda:write([a>>8,a&255,1]))
write([4,15]);p.FinishTransmission()
blocked('buck-read-crosses-unknown-status',lambda:p.Read(2));check('buck-read-after-crossing-rejected',list(p.Read(1))==[0]);p.FinishTransmission()
copy=p.BuckKnownValues;copy[0]=99;check('buck-copy',p.BuckKnownValues[0]==2)
p.Reset();check('buck-reset-clears-requests',list(p.BuckTaskRequests)==[0]*8 and p.BuckTaskWrites==p.BuckConfigWrites==0)
p=buck('guest-storage')
check('buck-unknown-reset',len(p.BuckKnownAddresses)==0)
blocked('buck-unknown-selection-read',lambda:write([4,15]));put(0x40f,[2]);check('buck-known-after-guest-write',read_config(0x40f)==[2] and list(p.BuckKnownAddresses)==[0x40f])
p.Reset();check('buck-unknown-reset-restored',len(p.BuckKnownAddresses)==0)
p=buck(None);blocked('buck-default-strict',lambda:write([4,15]));blocked('buck-default-task-strict',lambda:write([4,0,1]))
for profile in ['','auto','source-reset']:
    try:buck(profile)
    except Exception as e:check('buck-invalid-profile-'+profile,'Explicit BUCK storage' in str(e))
    else:raise Exception('invalid BUCK profile accepted')
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh output required')
 o.mkdir(mode=0o700);driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+STATUS+BUCK+"\nConsole.WriteLine('BLACKWALL_BUCK_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='configuration storage and task requests only, no rail/voltage/PWM/GPIO response')))\n";compile(driver,'test.py','exec');(o/'test.py').write_text(driver);(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes());(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "buck-storage"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_BUCK_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_BUCK_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing BUCK unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
