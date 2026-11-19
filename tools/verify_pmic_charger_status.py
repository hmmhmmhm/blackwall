"""Verify explicit read-only charger status snapshots and strict transaction boundaries."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
STATUS='''
def snap(profile):return BlackwallPmicRestoreProbe('source-reset-readonly',None,None,None,None,None,None,-1,profile)
addresses=[0x32d,0x332,0x333,0x334,0x336,0x337]
def point(a):write([a>>8,a&255]);p.FinishTransmission()
def read_status(a,n=1):
    point(a);v=list(p.Read(n));p.FinishTransmission();return v
for profile,value in [('source-reset-snapshot',0),('battery-detected-idle-snapshot',1)]:
    p=snap(profile)
    check(profile+'-selected',p.ChargerStatusProfile==profile and list(p.ChargerStatusAddresses)==addresses)
    expected=[0,0,0,value,0,0]
    check(profile+'-values',list(p.ChargerStatusValues)==expected)
    for a,v in zip(addresses,expected):check(profile+'-read-'+str(a),read_status(a)==[v])
    check(profile+'-error-pair',read_status(0x336,2)==[0,0])
    check(profile+'-temperature-status-group',read_status(0x332,3)==[0,0,value])
    point(0x334)
    for width in [0,-1,2,2147483647]:blocked(profile+'-reserved-width-'+str(width),lambda:p.Read(width))
    check(profile+'-read-after-rejected-overrun',list(p.Read(1))==[value]);p.FinishTransmission()
    for a in addresses+[0x335,0x338,0x330]:
        blocked(profile+'-readonly-'+str(a),lambda:write([a>>8,a&255,1]))
    for a in [0x335,0x338,0x330,0x300,0x301,0x302]:
        blocked(profile+'-unknown-pointer-'+str(a),lambda:write([a>>8,a&255]))
    point(0x334);p.Read(1)
    blocked(profile+'-read-overlap',lambda:p.Read(1));blocked(profile+'-write-overlap',lambda:write([3,0x36]));p.FinishTransmission()
    check(profile+'-read-counter',p.ChargerStatusReads==10 and p.ChargerStatusBytes==13)
    check(profile+'-read-payload',list(p.ChargerStatusReadAddresses)[-1]==0x334 and list(p.ChargerStatusReadPayloads)[-1]==('00' if value==0 else '01'))
    values=p.ChargerStatusValues;values[3]=99;check(profile+'-defensive-values',p.ChargerStatusValues[3]==value)
    p.Reset();check(profile+'-reset-is-fixture',list(p.ChargerStatusValues)==expected and p.ChargerStatusReads==0 and p.ChargerStatusBytes==0 and len(p.ChargerStatusReadAddresses)==0)
    # A repeated START that the existing subset does not model remains a guarded boundary.
    write([3,0x34]);blocked(profile+'-pending-pointer-read',lambda:p.Read(1));p.FinishTransmission()
    check(profile+'-recover-after-pending-read',list(p.Read(1))==[value]);p.FinishTransmission()
p=BlackwallPmicRestoreProbe('source-reset-readonly')
check('default-status-disabled',p.ChargerStatusProfile is None and len(p.ChargerStatusAddresses)==0)
for a in addresses:blocked('default-status-pointer-'+str(a),lambda:write([a>>8,a&255]))
for profile in ['', 'auto', 'source-reset', 'battery-present']:
    try:snap(profile)
    except Exception as e:check('invalid-status-profile-'+profile,'Explicit charger status snapshot' in str(e))
    else:raise Exception('invalid snapshot accepted')
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence directory required')
 o.mkdir(mode=0o700);driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+STATUS+"\nConsole.WriteLine('BLACKWALL_CHARGER_STATUS_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='fixed explicitly selected read-only snapshots, no physical charger FSM/main execution')))\n"
 compile(driver,'test.py','exec');(o/'test.py').write_text(driver);(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes());(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "charger-status"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
 rows=[json.loads(x.split('BLACKWALL_CHARGER_STATUS_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_CHARGER_STATUS_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing status unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
