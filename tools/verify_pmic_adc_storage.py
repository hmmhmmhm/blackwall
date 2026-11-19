"""Verify PMIC ADC config storage without synthetic sensor results or conversion events."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from verify_pmic_interrupt_registers import EXTRA
from verify_pmic_gpio_storage import GPIO
from verify_pmic_charger_storage import CHARGER
from verify_pmic_vbus_storage import VBUS
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
ADC='''
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage','guest-storage','guest-storage','guest-storage')
check('pmic-adc-explicit',p.GuestAdcStorage and list(p.AdcConfigAddresses)==[0x509,0x50a] and list(p.AdcConfigValues)==[0,1])
check('pmic-adc-reset-fixture',read(0x509)==0 and read(0x50a)==1)
for address,mask in [(0x509,3),(0x50a,3),(0x50b,15),(0x50d,255),(0x524,1)]:
    if address not in [0x509,0x50a]:blocked('pmic-adc-unwritten-'+str(address),lambda:write([address>>8,address&255]))
    for value in [0,mask]:
        w(address,value);check('pmic-adc-readback-'+str(address)+'-'+str(value),read(address)==value)
    if mask<255:
        before=(list(p.AdcConfigValues),p.AdcConfigWrites,p.RegisterWrites)
        blocked('pmic-adc-mask-'+str(address),lambda:write([address>>8,address&255,mask+1]))
        check('pmic-adc-mask-atomic-'+str(address),before==(list(p.AdcConfigValues),p.AdcConfigWrites,p.RegisterWrites))
for address in [0x500,0x501,0x502,0x503,0x506,0x507,0x508,0x50c,0x510,0x511,0x512,0x513,0x514,0x515,0x51a]:
    blocked('pmic-adc-task-result-unknown-'+str(address),lambda:write([address>>8,address&255]))
    blocked('pmic-adc-task-result-unwritable-'+str(address),lambda:write([address>>8,address&255,1]))
blocked('pmic-adc-burst-blocked',lambda:write([5,9,0,1]))
copy=p.AdcConfigValues;copy[0]=99;check('pmic-adc-value-copy',p.AdcConfigValues[0]==3)
p.Reset();check('pmic-adc-reset',list(p.AdcConfigAddresses)==[0x509,0x50a] and list(p.AdcConfigValues)==[0,1] and p.AdcConfigWrites==0)
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage','guest-storage','guest-storage');blocked('pmic-adc-default-strict',lambda:write([5,10,3]))
try:BlackwallPmicRestoreProbe('source-reset-readonly',None,None,None,None,'auto')
except Exception as e:check('pmic-adc-explicit-required','Explicit PMIC ADC storage' in str(e))
else:raise Exception('auto ADC accepted')
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence directory required')
 o.mkdir(mode=0o700);(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes());driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+EXTRA+GPIO+CHARGER+VBUS+ADC+"\nConsole.WriteLine('BLACKWALL_PMIC_ADC_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks)))\n";compile(driver,'test.py','exec');(o/'test.py').write_text(driver);(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "pmic-adc"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_PMIC_ADC_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_PMIC_ADC_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing ADC unit marker; inspect log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
