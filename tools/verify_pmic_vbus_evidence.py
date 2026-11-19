"""Audit saved VBUS native runs, source pins and unchanged ARM inputs without restarting them."""
import argparse,json,hashlib
from pathlib import Path
from native_replay import IMAGE,FILES,parse_log,validate_assets,boundary_state
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output
 if o.exists():raise ValueError('Fresh evidence output required')
 checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes();b=s/'pmic-vbus-main-01'
 check('root-current',(b/'root.cs').read_bytes()==root);check('timed-current',(b/'timed.cs').read_bytes()==timed)
 for folder,marker,count in [('pmic-vbus-unit-01','BLACKWALL_VBUS_UNIT',252),('pmic-timed-unit-06','BLACKWALL_TIMED_UNIT',240)]:
  d=s/folder;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();rows=[json.loads(x.split(marker+' ',1)[1]) for x in log.splitlines() if x.startswith(marker+' ')]
  check(folder+'-raw',rows==[r] and 'Renode is quitting' in log);check(folder+'-checks',r['passed'] and r['count']==count and len(set(r['checks']))==count)
  check(folder+'-source',(d/'peer.cs').read_bytes()==root+(b'\n'+timed if 'timed' in folder else b''))
 for name in ['stock24','stock23','cfw','stock24-no-vbus']:
  d=b/name;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());pins=json.loads((d/'derived-inputs.json').read_text());validate_assets(d,pins['derived'])
  check(name+'-raw',r['observed']==v and r['image_id']==IMAGE)
  src=s/'pmic-timed-main-03'/('stock24' if name=='stock24-no-vbus' else name)
  check(name+'-main',(d/'main.bin').read_bytes()==(src/'main.bin').read_bytes())
  check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
  check(name+'-pmic-source',(d/'strict.cs').read_bytes().endswith(root+b'\n'+timed))
  guards=[g for g in v['guards'] if g['accesses']]
  if name=='stock24-no-vbus':check(name+'-default',boundary_state(v)==boundary_state(parse_log((src/'renode.log').read_text())) and r['vbus']['writes']==0)
  else:
   check(name+'-vbus',r['vbus']==dict(enabled=True,current_known=True,current=5,suspend_known=False,suspend=0,writes=2,apply_requests=1))
   check(name+'-history',r['peer']['write_addresses'][-2:]==[0x201,0x200] and r['peer']['write_values'][-2:]==[5,1])
   check(name+'-strict',len(guards)==1 and guards[0]['operation']=='peer-write-unsupported' and guards[0]['value']==0x50a)
   check(name+'-timer-not-started',r['timer']['starts']==0 and not r['timer']['running'] and r['timer']['target']==0x3c00)
 for f in ['board.repl','strict.cs','result.py','probe.resc']:check('stock23-cfw-'+f,(b/'stock23'/f).read_bytes()==(b/'cfw'/f).read_bytes())
 check('stock23-cfw-run',(b/'stock23/run.py').read_text().replace('3758688','3829832')==(b/'cfw/run.py').read_text())
 sources=json.loads((s/'npmx-vbus-research-01/sources.json').read_text());tree=json.loads((s/'npmx-research-01/tree.json').read_text())
 for f in sources['files']:
  data=(s/'npmx-vbus-research-01'/Path(f['path']).name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  check(f['path']+'-sha',hashlib.sha256(data).hexdigest()==f['sha256']);check(f['path']+'-git',blob==f['git_blob']==next(x['sha'] for x in tree['tree'] if x['path']==f['path']))
 feed=s/'recovery-pmic-feed-07';check('feed-current-runner',(feed/'runner.py').read_bytes()==(ROOT/'tools/verify_recovery_pmic_feed.py').read_bytes());check('feed-complete',json.loads((feed/'report.json').read_text())['passed'])
 for name in ['match','mismatch','busy','masked','pins']:
  d=feed/name;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();rows=[json.loads(x.split('BLACKWALL_RECOVERY_FEED ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RECOVERY_FEED ')]
  check(name+'-feed-raw',rows==[r] and 'Renode is quitting' in log and '[ERROR]' not in log)
  check(name+'-feed-current-source',root.decode()+'\n'+timed.decode() in (d/'strict.cs').read_text())
  check(name+'-feed-header',hashlib.sha256((d/'watchdog.h').read_bytes()).hexdigest()=='26aa9fef14d1fe36b1581df1c20c5c1e0818451f8d855dbfa8810bf8311ed93b')
  check(name+'-feed-result',r['mailbox']==[0x600d,int(name in ('match','masked')),int(name=='masked')] and r['kicks']==int(name in ('match','masked')) and not r['iom_guards'] and not r['pmic_guards'])
 o.mkdir(mode=0o700);(o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='saved original ARM/VBUS config and compiled feed mocks; no physical/analog/full boot proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
