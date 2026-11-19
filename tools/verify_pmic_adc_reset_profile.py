"""Verify declared source reset config and update requests without automatic sensor conversions."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from verify_pmic_interrupt_registers import EXTRA
from verify_pmic_gpio_storage import GPIO
from verify_pmic_charger_storage import CHARGER
from verify_pmic_vbus_storage import VBUS
from verify_pmic_adc_storage import ADC
from verify_pmic_scratch_storage import SCRATCH
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
RESET='''
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage','guest-storage','guest-storage','source-reset-storage')
check('adc-source-reset-explicit',p.AdcSourceReset and list(p.AdcConfigAddresses)==[0x509,0x50a,0x50b,0x50d,0x524] and list(p.AdcConfigValues)==[0,1,3,0,0])
for address,value in [(0x509,0),(0x50a,1),(0x50b,3),(0x50d,0),(0x524,0)]:check('adc-source-reset-read-'+str(address),read(address)==value)
w(0x50c,0);check('adc-update-zero-noop',p.AdcAutoUpdateWrites==1 and p.AdcAutoUpdateRequests==0)
w(0x50b,6);w(0x50c,1);check('adc-update-request',p.AdcAutoUpdateRequests==1 and p.AdcAutoUpdateLastRequest==6 and read(0x50b)==6)
w(0x50b,9);check('adc-update-record-not-live-timer',p.AdcAutoUpdateLastRequest==6 and p.AdcAutoUpdateRequests==1)
w(0x50c,1);check('adc-update-second-request',p.AdcAutoUpdateRequests==2 and p.AdcAutoUpdateLastRequest==9)
before=(p.AdcAutoUpdateWrites,p.AdcAutoUpdateRequests,p.RegisterWrites)
blocked('adc-update-reserved-value',lambda:write([5,12,2]));check('adc-update-invalid-atomic',before==(p.AdcAutoUpdateWrites,p.AdcAutoUpdateRequests,p.RegisterWrites))
for address in [0x50c,0x500,0x501,0x510,0x511,0x512,0x513,0x514,0x515]:blocked('adc-source-no-task-result-read-'+str(address),lambda:write([address>>8,address&255]))
check('adc-no-conversion-event',list(p.EventState)==[0]*8 and not p.DigitalIrqPending)
p.Reset();check('adc-source-reset-reinstalls-fixture',list(p.AdcConfigValues)==[0,1,3,0,0] and p.AdcAutoUpdateRequests==p.AdcAutoUpdateWrites==0)
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage','guest-storage','guest-storage','guest-storage')
blocked('adc-guest-profile-unknown-interval',lambda:write([5,11]));blocked('adc-guest-profile-update-strict',lambda:write([5,12,1]))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence required')
 o.mkdir(mode=0o700);(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes());driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+EXTRA+GPIO+CHARGER+VBUS+ADC+SCRATCH+RESET+"\nConsole.WriteLine('BLACKWALL_ADC_RESET_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks)))\n";compile(driver,'test.py','exec');(o/'test.py').write_text(driver);(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "adc-reset"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_ADC_RESET_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_ADC_RESET_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing ADC reset unit marker')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
