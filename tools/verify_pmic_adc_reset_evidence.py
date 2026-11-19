"""Audit saved ADC reset-profile native runs, source pins and unchanged ARM inputs without restarting them."""
import argparse,json,hashlib,ast,copy
from types import SimpleNamespace
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
 root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes();b=s/'pmic-adc-reset-main-01'
 check('root-current',(b/'root.cs').read_bytes()==root);check('timed-current',(b/'timed.cs').read_bytes()==timed)
 for folder,marker,count in [('pmic-adc-reset-unit-02','BLACKWALL_ADC_RESET_UNIT',369),('pmic-timed-unit-09','BLACKWALL_TIMED_UNIT',240)]:
  d=s/folder;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();rows=[json.loads(x.split(marker+' ',1)[1]) for x in log.splitlines() if x.startswith(marker+' ')]
  check(folder+'-raw',rows==[r] and 'Renode is quitting' in log);check(folder+'-checks',r['passed'] and r['count']==count and len(set(r['checks']))==count)
  check(folder+'-source',(d/'peer.cs').read_bytes()==root+(b'\n'+timed if 'timed' in folder else b''))
 old_tree=ast.parse((b/'runner.py').read_text());new_tree=ast.parse((ROOT/'tools/probe_pmic_configuration_main.py').read_text());normalized=copy.deepcopy(new_tree)
 calls=[n for n in ast.walk(normalized) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='dict' and any(k.arg=='component' for k in n.keywords)]
 check('single-input-metadata-call',len(calls)==1)
 actual_expr=next(k.value for k in calls[0].keywords if k.arg=='actual_adc_state')
 calls[0].keywords=[k for k in calls[0].keywords if k.arg!='actual_adc_state']
 next(k for k in calls[0].keywords if k.arg=='storage').value=ast.parse("'guest-storage' if enabled else None",mode='eval').body
 check('runner-only-metadata-changed',ast.dump(normalized)==ast.dump(old_tree))
 corrected=[]
 for name in ['stock24','stock23','cfw','stock24-no-adc-reset']:
  d=b/name;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());pins=json.loads((d/'derived-inputs.json').read_text());validate_assets(d,pins['derived'])
  check(name+'-raw',r['observed']==v and r['image_id']==IMAGE)
  src=s/'pmic-scratch-main-01'/('stock24' if name=='stock24-no-adc-reset' else name)
  check(name+'-main',(d/'main.bin').read_bytes()==(src/'main.bin').read_bytes())
  check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
  check(name+'-pmic-source',(d/'strict.cs').read_bytes().endswith(root+b'\n'+timed))
  guards=[g for g in v['guards'] if g['accesses']]
  control=name=='stock24-no-adc-reset'
  profile='guest-storage' if control else 'source-reset-storage'
  check(name+'-actual-board-profile','    adcState: "'+profile+'"' in (d/'board.repl').read_text())
  corrected.append(dict(name=name,actual_adc_state=profile,old_storage=pins['storage'],board_sha256=hashlib.sha256((d/'board.repl').read_bytes()).hexdigest(),old_metadata_sha256=hashlib.sha256((d/'derived-inputs.json').read_bytes()).hexdigest()))
  check(name+'-reported-profile',r['update']['source_reset']==(not control) and r['scratch']['initial_mock']==0 and pins['scratch0_initial_mock']==0)
  check(name+'-future-metadata',eval(compile(ast.Expression(actual_expr),'metadata','eval'),{'d':d})==profile)
  if control:
   check(name+'-default',boundary_state(v)==boundary_state(parse_log((src/'renode.log').read_text())) and r['update']['update_requests']==0 and r['adc']['writes']==1)
  else:
   check(name+'-adc-state',r['update']==dict(source_reset=True,addresses=[0x509,0x50a,0x50b,0x50d,0x524],values=[0,3,3,0,1],writes=4,update_writes=2,update_requests=2,last_request=3))
   history=[(x,y) for x,y in zip(r['peer']['write_addresses'],r['peer']['write_values']) if 0x500<=x<=0x524]
   check(name+'-adc-sequence',history==[(0x50a,3),(0x50b,3),(0x50c,1),(0x50b,3),(0x50c,1),(0x524,1)])
   check(name+'-strict',len(guards)==1 and guards[0]['operation']=='peer-write-unsupported' and guards[0]['value']==0x500 and guards[0]['width']==3)
   check(name+'-no-sensor-results',not any(0x510<=x<=0x51a for x in r['peer']['read_addresses']) and r['peer']['event_state']==[0]*8)
   check(name+'-timer-not-started',r['timer']['starts']==0 and not r['timer']['running'])
 for f in FILES:
  if f!='board.repl':check('control-same-'+f,(b/'stock24'/f).read_bytes()==(b/'stock24-no-adc-reset'/f).read_bytes())
 check('only-profile-board-diff',(b/'stock24/board.repl').read_text().replace('    adcState: "source-reset-storage"','    adcState: "guest-storage"')==(b/'stock24-no-adc-reset/board.repl').read_text())
 for f in ['board.repl','strict.cs','result.py','probe.resc']:check('stock23-cfw-'+f,(b/'stock23'/f).read_bytes()==(b/'cfw'/f).read_bytes())
 check('stock23-cfw-run',(b/'stock23/run.py').read_text().replace('3758688','3829832')==(b/'cfw/run.py').read_text())
 sources=json.loads((s/'npmx-vbus-research-01/sources.json').read_text());tree=json.loads((s/'npmx-research-01/tree.json').read_text())
 for f in sources['files']:
  data=(s/'npmx-vbus-research-01'/Path(f['path']).name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  check(f['path']+'-sha',hashlib.sha256(data).hexdigest()==f['sha256']);check(f['path']+'-git',blob==f['git_blob']==next(x['sha'] for x in tree['tree'] if x['path']==f['path']))
 pins=json.loads((s/'npmx-research-01/sources.json').read_text())
 for rel in ['adk/npm1300.h','drivers/src/npmx_adc.c']:
  data=(s/'npmx-research-01'/rel).read_bytes();f=next(x for x in pins['files'] if x['path']==rel)
  check(rel+'-sha',hashlib.sha256(data).hexdigest()==f['sha256'])
  check(rel+'-blob',hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==f['git_blob']==next(x['sha'] for x in tree['tree'] if x['path']==rel))
 feed=s/'recovery-pmic-feed-10';check('feed-current-runner',(feed/'runner.py').read_bytes()==(ROOT/'tools/verify_recovery_pmic_feed.py').read_bytes());check('feed-complete',json.loads((feed/'report.json').read_text())['passed'])
 for name in ['match','mismatch','busy','masked','pins']:
  d=feed/name;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();rows=[json.loads(x.split('BLACKWALL_RECOVERY_FEED ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RECOVERY_FEED ')]
  check(name+'-feed-raw',rows==[r] and 'Renode is quitting' in log and '[ERROR]' not in log)
  check(name+'-feed-current-source',root.decode()+'\n'+timed.decode() in (d/'strict.cs').read_text())
  check(name+'-feed-header',hashlib.sha256((d/'watchdog.h').read_bytes()).hexdigest()=='26aa9fef14d1fe36b1581df1c20c5c1e0818451f8d855dbfa8810bf8311ed93b')
  check(name+'-feed-result',r['mailbox']==[0x600d,int(name in ('match','masked')),int(name=='masked')] and r['kicks']==int(name in ('match','masked')) and not r['iom_guards'] and not r['pmic_guards'])
 o.mkdir(mode=0o700);(o/'actual-profiles.json').write_text(json.dumps(dict(corrections=corrected,reason='original storage field did not describe inherited ADC profile; board/runtime authoritative'),indent=2)+'\n');(o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='saved original ARM/explicit ADC reset profile and compiled feed mocks; no physical/analog/full boot proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
