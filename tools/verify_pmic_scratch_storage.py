"""Verify partial scratch knowledge and explicit mock without implementing boot monitor or reset."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from verify_pmic_interrupt_registers import EXTRA
from verify_pmic_gpio_storage import GPIO
from verify_pmic_charger_storage import CHARGER
from verify_pmic_vbus_storage import VBUS
from verify_pmic_adc_storage import ADC
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
SCRATCH='''
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage','guest-storage','guest-storage','guest-storage','guest-storage')
check('scratch-initial-unknown',p.GuestScratchStorage and list(p.ScratchKnownMasks)==[0,0] and p.Scratch0InitialMock==-1)
for address in [0xe00,0xe01,0xe02,0xe03,0xe04,0xe05]:blocked('scratch-initial-unknown-'+str(address),lambda:write([address>>8,address&255]))
for value in [0,0x9a,255]:
    w(0xe02,value);check('scratch1-readback-'+str(value),read(0xe02)==value and p.ScratchKnownMasks[1]==255)
w(0xe01,0x20);check('scratch0-partial',list(p.ScratchKnownMasks)==[254,255] and p.ScratchValues[0]==0x20)
blocked('scratch0-unknown-boot-bit',lambda:write([14,1]))
for address,value in [(0xe01,1),(0xe01,0xff),(0xe00,1),(0xe03,0),(0xe04,0),(0xe05,0)]:
    before=(list(p.ScratchValues),list(p.ScratchKnownMasks),p.ScratchWrites,p.RegisterWrites)
    blocked('scratch-unsupported-'+str(address)+'-'+str(value),lambda:write([address>>8,address&255,value]))
    check('scratch-unsupported-atomic-'+str(address)+'-'+str(value),before==(list(p.ScratchValues),list(p.ScratchKnownMasks),p.ScratchWrites,p.RegisterWrites))
blocked('scratch-burst-rejected',lambda:write([14,1,0,0]))
p.Reset();check('scratch-reset-fixture-unknown',list(p.ScratchKnownMasks)==[0,0] and p.ScratchWrites==0)
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle','guest-storage','guest-storage','guest-storage','guest-storage','guest-storage',0)
check('scratch0-explicit-zero',read(0xe01)==0 and list(p.ScratchKnownMasks)==[255,0])
w(0xe01,0x20);check('scratch0-preserves-explicit-disabled',read(0xe01)==0x20 and p.ScratchKnownMasks[0]==255)
copy=p.ScratchValues;copy[0]=1;mask=p.ScratchKnownMasks;mask[0]=0;check('scratch-copy',p.ScratchValues[0]==0x20 and p.ScratchKnownMasks[0]==255)
p.Reset();check('scratch-reset-reinstalls-declared-fixture',read(0xe01)==0 and list(p.ScratchKnownMasks)==[255,0])
p=BlackwallPmicRestoreProbe('source-reset-readonly');blocked('scratch-default-strict',lambda:write([14,2,0x9a]))
for scratch_profile,scratch_fixture in [(None,0),('auto',-1),('guest-storage',1)]:
    try:BlackwallPmicRestoreProbe('source-reset-readonly',None,None,None,None,None,scratch_profile,scratch_fixture)
    except Exception:check('scratch-invalid-profile-'+str(scratch_profile)+'-'+str(scratch_fixture),True)
    else:raise Exception('invalid scratch profile accepted')
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence required')
 o.mkdir(mode=0o700);(o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes());driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+EXTRA+GPIO+CHARGER+VBUS+ADC+SCRATCH+"\nConsole.WriteLine('BLACKWALL_SCRATCH_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks)))\n";compile(driver,'test.py','exec');(o/'test.py').write_text(driver);(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "scratch"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_SCRATCH_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_SCRATCH_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing scratch unit marker')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
