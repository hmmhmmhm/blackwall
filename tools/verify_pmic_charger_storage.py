"""Verify digital charger config, partial knowledge and atomic writes without battery responses."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from verify_pmic_interrupt_registers import EXTRA
from verify_pmic_gpio_storage import GPIO
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
CHARGER='''
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage','guest-storage')
check('charger-explicit',p.GuestChargerStorage and list(p.ChargerKnownAddresses)==[0x308,0x309,0x30a,0x30b])
check('charger-initial-byte-read',read(0x309)==0 and read(0x30b)==1)
blocked('unknown-alias-before-write',lambda:write([3,4]))
w(0x307,2);check('partial-clear-keeps-unknown',list(p.ChargerAliasKnownMasks)==[0,2])
blocked('partial-alias-read-blocked',lambda:write([3,6]))
w(0x306,1);check('completed-alias-knowledge',read(0x306)==1 and list(p.ChargerAliasKnownMasks)==[0,3])
w(0x304,3);check('enable-set',read(0x304)==3)
w(0x305,1);check('enable-partial-clear',read(0x304)==2)
blocked('clear-alias-read-unimplemented',lambda:write([3,5]))
for address,value in [(0x350,1),(0x30c,7),(0x30d,4),(0x30e,1),(0x30f,1),(0x33c,1),(0x310,0xbb),(0x311,1),(0x31b,3)]:
    w(address,value);check('charger-config-'+str(address),read(address)==value)
write([3,8,0x21,1]);p.FinishTransmission();write([3,8]);p.FinishTransmission();check('two-byte-write-read',list(p.Read(2))==[0x21,1]);p.FinishTransmission()
for address,data in [(0x308,[0x22,2]),(0x31b,[1,0]),(0x304,[1,0])]:
    before=(list(p.ChargerKnownAddresses),list(p.ChargerKnownValues),p.ChargerWrites);blocked('invalid-burst-'+str(address),lambda:write([address>>8,address&255]+data));check('atomic-invalid-'+str(address),before==(list(p.ChargerKnownAddresses),list(p.ChargerKnownValues),p.ChargerWrites))
for address,value in [(0x350,2),(0x30c,16),(0x311,4)]:blocked('invalid-charger-mask-'+str(address),lambda:write([address>>8,address&255,value]))
for address in [0x300,0x301,0x302,0x332,0x334,0x336,0x337]:blocked('no-task-status-'+str(address),lambda:write([address>>8,address&255]))
copy=p.ChargerKnownValues;copy[0]=99;check('charger-copy',p.ChargerKnownValues[0]==0x21)
p.Reset();check('charger-reset-unknown',list(p.ChargerKnownAddresses)==[0x308,0x309,0x30a,0x30b] and list(p.ChargerAliasKnownMasks)==[0,0] and p.ChargerWrites==0)
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage');blocked('default-charger-strict',lambda:write([3,0x50,1]))
try:BlackwallPmicRestoreProbe('source-reset-readonly',None,None,'auto')
except Exception as e:check('explicit-charger-required','Explicit charger storage' in str(e))
else:raise Exception('implicit charger accepted')
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Use fresh evidence directory')
 o.mkdir(mode=0o700);driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+EXTRA+GPIO+CHARGER+"\nConsole.WriteLine('BLACKWALL_CHARGER_UNIT '+json.dumps(dict(passed=True,checks=checks,count=len(checks),scope='explicit digital config only; no charging, battery measurement, OTP write or main execution')))\n";compile(driver,'test.py','exec');(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes());(o/'test.py').write_text(driver);(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "charger-storage"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_CHARGER_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_CHARGER_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing charger unit marker')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
