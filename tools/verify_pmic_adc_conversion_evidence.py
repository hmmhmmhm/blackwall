"""Audit saved conversion native runs, source pins and unchanged ARM inputs without restarting them."""
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
 root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes();b=s/'pmic-adc-conversion-main-01'
 check('root-current',(b/'root.cs').read_bytes()==root);check('timed-current',(b/'timed.cs').read_bytes()==timed)
 for folder,marker,count in [('pmic-adc-conversion-unit-05','BLACKWALL_CONVERSION_UNIT',408),('pmic-timed-unit-10','BLACKWALL_TIMED_UNIT',240)]:
  d=s/folder;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();rows=[json.loads(x.split(marker+' ',1)[1]) for x in log.splitlines() if x.startswith(marker+' ')]
  check(folder+'-raw',rows==[r] and 'Renode is quitting' in log);check(folder+'-checks',r['passed'] and r['count']==count and len(set(r['checks']))==count)
  check(folder+'-source',(d/'peer.cs').read_bytes()==root+b'\n'+timed)
 for name in ['stock24','stock23','cfw','stock24-no-conversion','stock24-shared-bits-unknown']:
  d=b/name;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());pins=json.loads((d/'derived-inputs.json').read_text());validate_assets(d,pins['derived'])
  check(name+'-raw',r['observed']==v and r['image_id']==IMAGE)
  src=s/'pmic-adc-reset-main-01'/('stock24' if name.startswith('stock24') else name)
  check(name+'-main',(d/'main.bin').read_bytes()==(src/'main.bin').read_bytes())
  check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
  check(name+'-pmic-source',(d/'strict.cs').read_bytes().endswith(root+b'\n'+timed))
  guards=[g for g in v['guards'] if g['accesses']]
  if name=='stock24-no-conversion':
   check(name+'-default',boundary_state(v)==boundary_state(parse_log((src/'renode.log').read_text())) and r['conversion']==dict(enabled=False))
  else:
   c=r['conversion'];unknown=name=='stock24-shared-bits-unknown'
   check(name+'-conversion-prefix',c['enabled'] and c['vbat_code']==778 and c['ibat_code']==5 and c['conversion_us']==250 and c['requests']==1 and c['repeated_drops']==0 and c['vbat_done']==1 and c['ibat_done']==0 and c['phase']=='ibat')
   expected_masks=[0,255,0,0,0,3 if unknown else 255,0,0,0,0,0 if unknown else 207]
   check(name+'-partial-known',c['values']==[0,194,0,0,0,2,0,0,0,0,0] and c['known_masks']==expected_masks and c['zero_bits_mock']==(-1 if unknown else 0))
   check(name+'-next-unimplemented-task',len(guards)==1 and guards[0]['value']==0x501 and guards[0]['width']==3)
   check(name+'-only-vbat-task-accepted',r['peer']['write_addresses'][-1]==0x500 and r['peer']['write_values'][-1]==1 and 0x501 not in r['peer']['write_addresses'])
   check(name+'-event-not-irq',r['peer']['event_state']==[1,0,0,0,0,0,0,0] and r['peer']['enable_state'][0]==0 and not r['peer']['digital_irq_pending'])
   check(name+'-no-original-result-read',not any(0x510<=x<=0x51a for x in r['peer']['read_addresses']))
   check(name+'-watchdog-not-started',r['timer']['starts']==0 and not r['timer']['running'])
  check(name+'-guard-operation',len(guards)==1 and guards[0]['operation']=='peer-write-unsupported')
 for f in FILES:
  if f!='board.repl':check('shared-mock-same-'+f,(b/'stock24'/f).read_bytes()==(b/'stock24-shared-bits-unknown'/f).read_bytes())
 check('only-shared-mock-board-diff',(b/'stock24/board.repl').read_text().replace('    sharedResultBitsZeroMock: 0\n','')==(b/'stock24-shared-bits-unknown/board.repl').read_text())
 first=json.loads((b/'stock24/report.json').read_text());second=json.loads((b/'stock24-shared-bits-unknown/report.json').read_text())
 check('shared-mock-prefix-boundary-same',boundary_state(first['observed'])==boundary_state(second['observed']) and first['peer']==second['peer'])
 unit=s/'pmic-adc-conversion-unit-05';log=(unit/'renode.log').read_text()
 precision=[json.loads(x.split('BLACKWALL_TIME_PRECISION ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_TIME_PRECISION ')]
 check('time-input-precision-observation',precision==[dict(integer_249us_ticks=249000,string_249us_delta_ticks=248999)])
 exact=[json.loads(x.split('BLACKWALL_ADC_TIME ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_ADC_TIME ')]
 check('exact-vbat-time',len(exact)==1 and exact[0]['virtual_ticks']==250000 and exact[0]['vbat_done']==1)
 checks_done=json.loads((unit/'report.json').read_text())['checks']
 for label in ['conversion-clock-exact-250us','conversion-clock-exact-500us','conversion-active-config-atomic','conversion-ibat-config-write-blocked','conversion-ibat-packing','conversion-reset-no-late-result','conversion-unknown-lsb-read-blocked']:check(label,label in checks_done)
 for f in ['board.repl','strict.cs','result.py','probe.resc']:check('stock23-cfw-'+f,(b/'stock23'/f).read_bytes()==(b/'cfw'/f).read_bytes())
 check('stock23-cfw-run',(b/'stock23/run.py').read_text().replace('3758688','3829832')==(b/'cfw/run.py').read_text())
 sources=json.loads((s/'npmx-errlog-research-01/sources.json').read_text());tree=json.loads((s/'npmx-research-01/tree.json').read_text())
 for f in sources['files']:
  data=(s/'npmx-errlog-research-01'/Path(f['path']).name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  check(f['path']+'-sha',hashlib.sha256(data).hexdigest()==f['sha256']);check(f['path']+'-git',blob==f['git_blob']==next(x['sha'] for x in tree['tree'] if x['path']==f['path']))
 pins=json.loads((s/'npmx-research-01/sources.json').read_text())
 for rel in ['adk/npm1300.h','drivers/src/npmx_adc.c']:
  data=(s/'npmx-research-01'/rel).read_bytes();f=next(x for x in pins['files'] if x['path']==rel)
  check(rel+'-sha',hashlib.sha256(data).hexdigest()==f['sha256'])
  check(rel+'-blob',hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==f['git_blob']==next(x['sha'] for x in tree['tree'] if x['path']==rel))
 feed=s/'recovery-pmic-feed-11';check('feed-current-runner',(feed/'runner.py').read_bytes()==(ROOT/'tools/verify_recovery_pmic_feed.py').read_bytes());check('feed-complete',json.loads((feed/'report.json').read_text())['passed'])
 for name in ['match','mismatch','busy','masked','pins']:
  d=feed/name;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();rows=[json.loads(x.split('BLACKWALL_RECOVERY_FEED ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RECOVERY_FEED ')]
  check(name+'-feed-raw',rows==[r] and 'Renode is quitting' in log and '[ERROR]' not in log)
  check(name+'-feed-current-source',root.decode()+'\n'+timed.decode() in (d/'strict.cs').read_text())
  check(name+'-feed-header',hashlib.sha256((d/'watchdog.h').read_bytes()).hexdigest()=='26aa9fef14d1fe36b1581df1c20c5c1e0818451f8d855dbfa8810bf8311ed93b')
  check(name+'-feed-result',r['mailbox']==[0x600d,int(name in ('match','masked')),int(name=='masked')] and r['kicks']==int(name in ('match','masked')) and not r['iom_guards'] and not r['pmic_guards'])
 o.mkdir(mode=0o700);(o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='saved original ARM/conversion fixture; paired completion unit-only; no original result consumption and compiled feed mocks; no physical/analog/full boot proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
