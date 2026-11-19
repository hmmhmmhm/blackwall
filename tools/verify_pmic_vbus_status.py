"""Verify explicit VBUS-present/absent snapshots with strict read-only framing."""
import argparse
import json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from native_replay import IMAGE
from run_renode_m55_probe import execute

ROOT=Path(__file__).resolve().parents[1]
STATUS='''
def snapshot(profile):
    return BlackwallPmicRestoreProbe('source-reset-readonly',None,None,None,None,None,None,-1,None,None,None,profile)
for profile,value in [('test-vbus-absent',0),('test-vbus-present',1)]:
    p=snapshot(profile)
    check(profile+'-selected',p.VbusStatusProfile==profile and p.VbusStatusValue==value and p.VbusStatusReads==0)
    write([2,7]);blocked(profile+'-pending-pointer-read',lambda:p.Read(1));p.FinishTransmission()
    for count in [0,-1,2,3,2147483647]:blocked(profile+'-bad-width-'+str(count),lambda:p.Read(count))
    check(profile+'-exact-read',list(p.Read(1))==[value] and p.VbusStatusReads==1)
    blocked(profile+'-pending-data-read',lambda:p.Read(1));blocked(profile+'-pending-write',lambda:write([2,7]))
    p.FinishTransmission()
    before=(p.VbusStatusValue,p.VbusStatusReads,p.VbusWrites,p.VbusApplyRequests,p.RegisterWrites)
    for byte in range(256):blocked(profile+'-readonly-'+str(byte),lambda:write([2,7,byte]))
    check(profile+'-rejected-writes-preserve-state',before==(p.VbusStatusValue,p.VbusStatusReads,p.VbusWrites,p.VbusApplyRequests,p.RegisterWrites))
    for address in [0x200,0x201,0x203,0x205,0x206,0x208]:blocked(profile+'-unrelated-unknown-'+str(address),lambda:write([address>>8,address&255]))
    blocked(profile+'-fragment',lambda:write([2]));blocked(profile+'-burst',lambda:write([2,7,0,0]))
    for n in range(15):
        write([2,7]);p.FinishTransmission();check(profile+'-repeat-'+str(n),list(p.Read(1))==[value]);p.FinishTransmission()
    write([2,7]);p.FinishTransmission();blocked(profile+'-bounded-history',lambda:p.Read(1))
    check(profile+'-only-committed-reads-counted',p.VbusStatusReads==16 and p.DataReads==16 and p.ReturnedBytes==16)
    p.Reset();check(profile+'-reset-keeps-declared-fixture',p.VbusStatusProfile==profile and p.VbusStatusValue==value and p.VbusStatusReads==0 and p.Pointer==-1)
p=BlackwallPmicRestoreProbe('source-reset-readonly')
check('default-status-unknown',p.VbusStatusProfile is None and p.VbusStatusValue==-1 and p.VbusStatusReads==0)
blocked('default-pointer-strict',lambda:write([2,7]));blocked('default-read-strict',lambda:p.Read(1))
for profile in ['', 'auto', 'source-reset', 'present', 'test-vbus-63']:
    try:snapshot(profile)
    except Exception as error:check('invalid-profile-'+profile,'Explicit test-only VBUS status snapshot' in str(error))
    else:raise Exception('invalid VBUS snapshot accepted')
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
    if o.exists():raise ValueError('Fresh evidence directory required')
    o.mkdir(mode=0o700)
    driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+STATUS+"\nConsole.WriteLine('BLACKWALL_VBUS_STATUS_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False)))\n"
    compile(driver,'test.py','exec');(o/'test.py').write_text(driver)
    (o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes())
    (o/'probe.resc').write_text('include @/work/peer.cs\nmach create "vbus-status-unit"\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=None)
    rows=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_VBUS_STATUS_UNIT ')]
    if len(rows)!=1:raise ValueError('Missing VBUS status marker; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))


if __name__=='__main__':main()
