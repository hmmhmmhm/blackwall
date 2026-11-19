"""Verify bounded guest VBUS configuration storage; no analog power/current/status responses."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from verify_pmic_interrupt_registers import EXTRA
from verify_pmic_gpio_storage import GPIO
from verify_pmic_charger_storage import CHARGER
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
VBUS='''
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage','guest-storage','guest-storage')
check('vbus-explicit-unknown',p.GuestVbusStorage and not p.VbusCurrentKnown and not p.VbusSuspendKnown)
for address in [0x201,0x203,0x200,0x202,0x204,0x205,0x206,0x207]:blocked('vbus-initial-unknown-'+str(address),lambda:write([address>>8,address&255]))
blocked('vbus-apply-needs-known',lambda:write([2,0,1]))
w(0x200,0);check('vbus-zero-task',p.VbusApplyRequests==0 and not p.VbusCurrentKnown)
for value in [0,1]+list(range(5,16)):
    w(0x201,value);check('vbus-current-'+str(value),read(0x201)==value and p.VbusCurrentKnown)
w(0x200,1);check('vbus-apply-request-only',p.VbusApplyRequests==1 and read(0x201)==15)
for value in [0,1]:
    w(0x203,value);check('vbus-suspend-'+str(value),read(0x203)==value and p.VbusSuspendKnown)
for address,value in [(0x201,2),(0x201,3),(0x201,4),(0x201,16),(0x201,255),(0x200,2),(0x203,2)]:
    before=(p.VbusCurrent,p.VbusSuspend,p.VbusWrites,p.VbusApplyRequests,p.RegisterWrites)
    blocked('vbus-invalid-'+str(address)+'-'+str(value),lambda:write([address>>8,address&255,value]))
    check('vbus-invalid-atomic-'+str(address)+'-'+str(value),before==(p.VbusCurrent,p.VbusSuspend,p.VbusWrites,p.VbusApplyRequests,p.RegisterWrites))
for address in [0x200,0x202,0x204,0x205,0x206,0x207]:blocked('vbus-task-status-unreadable-'+str(address),lambda:write([address>>8,address&255]))
blocked('vbus-burst-not-supported',lambda:write([2,1,5,0]))
p.Reset();check('vbus-reset-unknown',not p.VbusCurrentKnown and not p.VbusSuspendKnown and p.VbusWrites==0 and p.VbusApplyRequests==0)
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage','guest-storage');blocked('vbus-default-strict',lambda:write([2,1,5]))
try:BlackwallPmicRestoreProbe('source-reset-readonly',None,None,None,'auto')
except Exception as e:check('vbus-explicit-required','Explicit VBUS storage' in str(e))
else:raise Exception('implicit vbus accepted')
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence directory required')
 o.mkdir(mode=0o700);(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes())
 driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+EXTRA+GPIO+CHARGER+VBUS+"\nConsole.WriteLine('BLACKWALL_VBUS_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks)))\n"
 compile(driver,'test.py','exec');(o/'test.py').write_text(driver);(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "pmic-vbus"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_VBUS_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_VBUS_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing VBUS marker; inspect saved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
