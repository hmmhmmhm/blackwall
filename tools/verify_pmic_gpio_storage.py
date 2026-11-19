"""Exercise guest-written GPIO configuration without inventing pin levels or IRQ wiring."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from verify_pmic_interrupt_registers import EXTRA
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
GPIO='''
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage')
check('gpio-initial-unknown',p.GuestGpioStorage and len(p.GpioKnownAddresses)==0 and not p.InterruptOutputModeConfigured)
for index in range(30):
    address=0x600+index;blocked('unwritten-pointer-'+str(index),lambda:write([6,index]))
    value=index+5 if index<5 else 1
    w(address,value);check('readback-'+str(index),read(address)==value)
check('gpio-known-complete',list(p.GpioKnownAddresses)==list(range(0x600,0x61e)) and p.GpioWrites==30)
check('gpio1-mode-not-irq',not p.InterruptOutputModeConfigured)
w(0x601,5);check('gpio1-irq-intent',p.InterruptOutputModeConfigured and not p.DigitalIrqPending)
for address,value in [(0x600,10),(0x600,16),(0x605,2),(0x61d,2)]:
    before=list(p.GpioValues);blocked('invalid-config-'+str(address)+'-'+str(value),lambda:write([6,address-0x600,value]));check('invalid-keeps-gpio-'+str(address)+'-'+str(value),before==list(p.GpioValues))
for address in [0x61e,0x61f,0x620]:blocked('pin-status-unknown-'+str(address),lambda:write([address>>8,address&255]))
copy=p.GpioValues;copy[0]=99;check('gpio-values-copy',p.GpioValues[0]==5)
p.Reset();check('gpio-reset-unknown',p.GpioWrites==0 and len(p.GpioKnownAddresses)==0 and not p.InterruptOutputModeConfigured)
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle');blocked('default-gpio-still-unsupported',lambda:write([6,1,5]))
try:BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','auto')
except Exception as e:check('explicit-gpio-required','Explicit GPIO storage' in str(e))
else:raise Exception('implicit GPIO accepted')
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Use fresh evidence directory')
 o.mkdir(mode=0o700);driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+EXTRA+GPIO+"\nConsole.WriteLine('BLACKWALL_GPIO_UNIT '+json.dumps(dict(passed=True,checks=checks,count=len(checks),scope='guest-written GPIO config only, no pin level, physical power or IRQ wiring')))\n";compile(driver,'test.py','exec');(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes());(o/'test.py').write_text(driver);(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "gpio-storage"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_GPIO_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_GPIO_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing GPIO unit marker')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))
if __name__=='__main__':main()
