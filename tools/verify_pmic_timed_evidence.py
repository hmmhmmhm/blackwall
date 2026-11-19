"""Audit saved PMIC timed native evidence without restarting execution or accessing hardware."""
import argparse, json, hashlib
from pathlib import Path
from native_replay import FILES, IMAGE, boundary_state, parse_log, validate_assets
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output
 if o.exists():raise ValueError('Use fresh output directory')
 checks=[]
 def check(name,ok):
  if not ok:raise ValueError(name)
  checks.append(name)
 unit=s/'pmic-timed-unit-05'; batch=s/'pmic-timed-main-03'
 root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes()
 check('unit-current-source',(unit/'peer.cs').read_bytes()==root+b'\n'+timed)
 u=json.loads((unit/'report.json').read_text());log=(unit/'renode.log').read_text()
 markers=[json.loads(x.split('BLACKWALL_TIMED_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_TIMED_UNIT ')]
 check('unit-marker-and-terminal',markers==[u] and 'Renode is quitting' in log)
 check('unit-checks',u['passed'] and u['count']==240 and len(set(u['checks']))==240)
 for name in ['latest-inner-guard-owner','stop-cancels-warning-and-expiry','restart-full-period','restart-warning','restart-expiry','nominal-warning-30718ms','nominal-expiry-30720ms','reset-request-freezes-target','read-holes-default-unknown','split-read-head','split-read-tail','split-read-overrun-blocked']:
  check(name,name in u['checks'])
 check('batch-current-root',(batch/'root.cs').read_bytes()==root)
 check('batch-current-timer',(batch/'timed.cs').read_bytes()==timed)
 summary=json.loads((batch/'report.json').read_text());check('batch-passed',summary['passed'] and len(summary['cases'])==4)
 for name in ['stock24','stock23','cfw','stock24-no-timer']:
  d=batch/name;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());pins=json.loads((d/'derived-inputs.json').read_text())
  validate_assets(d,pins['derived']);check(name+'-native-report',v==r['observed'] and r['image_id']==IMAGE)
  check(name+'-not-hardware',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
  base=s/'pmic-charger-main-01'/('stock24' if name=='stock24-no-timer' else name)
  check(name+'-main-unmodified',(d/'main.bin').read_bytes()==(base/'main.bin').read_bytes())
  if name=='stock24-no-timer':check('default-boundary-preserved',boundary_state(v)==boundary_state(parse_log((base/'renode.log').read_text())))
  else:
   t=r['timer'];check(name+'-setup',t['config_known'] and t['config']==10 and t['target_known'] and t['target']==15360 and t['strobes']==1 and t['timer_writes']==3)
   check(name+'-not-started',not t['running'] and not t['reset_requested'] and all(t[k]==0 for k in ['starts','kicks','warnings','reset_requests']) and t['read_hole_mock']==-1)
   guards=[g for g in v['guards'] if g['accesses']];check(name+'-next-strict',len(guards)==1 and guards[0]['operation']=='peer-write-unsupported' and guards[0]['value']==0x201)
 for f in ['board.repl','strict.cs','result.py','probe.resc']:check('stock23-cfw-'+f,(batch/'stock23'/f).read_bytes()==(batch/'cfw'/f).read_bytes())
 check('stock23-cfw-runtime',(batch/'stock23/run.py').read_text().replace('3758688','3829832')==(batch/'cfw/run.py').read_text())
 feed=s/'recovery-pmic-feed-06'
 check('feed-current-runner',(feed/'runner.py').read_bytes()==(ROOT/'tools/verify_recovery_pmic_feed.py').read_bytes())
 fs=json.loads((feed/'report.json').read_text());check('feed-five-cases',fs['passed'] and fs['cases']==5)
 for name in ['match','mismatch','busy','masked','pins']:
  d=feed/name;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text()
  markers=[json.loads(x.split('BLACKWALL_RECOVERY_FEED ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RECOVERY_FEED ')]
  check(name+'-feed-raw-terminal',markers==[r] and 'Renode is quitting' in log and '[ERROR]' not in log)
  check(name+'-pinned-header',hashlib.sha256((d/'watchdog.h').read_bytes()).hexdigest()=='26aa9fef14d1fe36b1581df1c20c5c1e0818451f8d855dbfa8810bf8311ed93b')
  elf=(d/'probe.elf').read_bytes();check(name+'-arm-elf',elf[:4]==b'\x7fELF' and elf[18:20]==b'\x28\x00')
  check(name+'-latest-timer',timed.decode() in (d/'strict.cs').read_text())
  success=name in ('match','masked');busy=name=='busy'
  check(name+'-feed-outcome',r['mailbox']==[0x600d,int(success),int(name=='masked')] and r['kicks']==int(success) and r['iom_guards']==r['pmic_guards']==0)
  check(name+'-power-request-versus-settle',r['power_request']==(256 if busy else 0) and r['power_status_before_settle']==(0 if name=='pins' else 256) and r['power_status']==(256 if busy else 0))
  check(name+'-debug-preserved',r['demcr']==0 and r['dwt']==0x40000000)
 o.mkdir(mode=0o700);(o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='saved virtual timer/native startup artifacts; compiled feed with explicit mock conditions; no full boot or hardware validation'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
