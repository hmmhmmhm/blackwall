"""Check source-based event W1S/W1C banks under explicitly idle synthetic inputs."""
import argparse,json
from pathlib import Path
from verify_pmic_restore_probe import DRIVER
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
EXTRA='''
p=BlackwallPmicRestoreProbe('source-reset-readonly','explicit-idle')
def w(address,value):
    write([address>>8,address&255,value]);p.FinishTransmission()
def read(address):
    write([address>>8,address&255]);p.FinishTransmission();value=list(p.Read(1))[0];p.FinishTransmission();return value
check('idle-explicit',p.InterruptRegistersEnabled and not p.DigitalIrqPending and list(p.EventState)==[0]*8 and list(p.EnableState)==[0]*8)
for index,base,mask in [(0,2,255),(1,6,63),(2,10,63),(3,14,7),(4,18,15),(5,22,63),(6,26,63),(7,34,31)]:
    w(base,255);check('event-set-'+str(index),read(base)==mask and not p.DigitalIrqPending)
    w(base+2,255);check('enable-set-'+str(index),read(base+2)==mask and p.DigitalIrqPending)
    w(base+1,1);check('event-partial-clear-'+str(index),read(base)==mask-1 and p.DigitalIrqPending)
    w(base+3,255);check('enable-clear-'+str(index),read(base+2)==0 and not p.DigitalIrqPending)
    w(base+1,255);check('event-clear-'+str(index),read(base)==0 and not p.DigitalIrqPending)
old=state();n=p.AccessCount
try:write([0,1,1])
except Exception:check('task-reset-still-blocked',state()==old and p.AccessCount==n+1)
else:raise Exception('reset accepted')
for address in [0,1,30,31,32,33,38]:blocked('unknown-pointer-'+str(address),lambda:write([0,address]))
for n in range(24):w(3,255)
blocked('write-history-bounded',lambda:write([0,3,255]))
p.Reset();check('irq-reset',not p.DigitalIrqPending and p.RegisterWrites==0 and list(p.EventState)==[0]*8 and list(p.EnableState)==[0]*8)
try:BlackwallPmicRestoreProbe('source-reset-readonly','auto')
except Exception as e:check('no-implicit-interrupt-state','Explicit interrupt state' in str(e))
else:raise Exception('implicit state accepted')
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Use fresh evidence directory')
 o.mkdir(mode=0o700);driver=DRIVER[:DRIVER.index("Console.WriteLine('BLACKWALL_RESTORE_UNIT ")]+EXTRA+"\nConsole.WriteLine('BLACKWALL_INTERRUPT_UNIT '+json.dumps(dict(passed=True,checks=checks,count=len(checks),scope='declared idle W1S/W1C banks; no physical IRQ, GPIO or main execution')))\n";compile(driver,'test.py','exec')
 (o/'peer.cs').write_bytes((ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes());(o/'test.py').write_text(driver);(o/'probe.resc').write_text('include @/work/peer.cs\nmach create "interrupt-bank"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
 rows=[json.loads(x.split('BLACKWALL_INTERRUPT_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_INTERRUPT_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing IRQ unit marker')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))
if __name__=='__main__':main()
