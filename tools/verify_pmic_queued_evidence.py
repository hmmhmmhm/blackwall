"""Audit saved conversion native runs, source pins and unchanged ARM inputs without restarting them."""
import argparse,json,hashlib,struct,re
from probe_pmic_configuration_main import queued_board
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
 root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes();b=s/'pmic-queued-main-01'
 check('root-current',(b/'root.cs').read_bytes()==root);check('timed-current',(b/'timed.cs').read_bytes()==timed)
 for folder,marker,count in [('pmic-queued-unit-03','BLACKWALL_QUEUED_UNIT',401),('pmic-adc-conversion-unit-06','BLACKWALL_CONVERSION_UNIT',408),('pmic-timed-unit-11','BLACKWALL_TIMED_UNIT',240)]:
  d=s/folder;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();rows=[json.loads(x.split(marker+' ',1)[1]) for x in log.splitlines() if x.startswith(marker+' ')]
  check(folder+'-raw',rows==[r] and 'Renode is quitting' in log);check(folder+'-checks',r['passed'] and r['count']==count and len(set(r['checks']))==count)
  check(folder+'-source',(d/'peer.cs').read_bytes()==root+b'\n'+timed)
 for name in ['stock24','stock23','cfw','stock24-no-queued','stock24-results-unknown']:
  d=b/name;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());pins=json.loads((d/'derived-inputs.json').read_text());validate_assets(d,pins['derived'])
  check(name+'-raw',r['observed']==v and r['image_id']==IMAGE)
  src=s/'pmic-adc-conversion-main-01'/('stock24' if name.startswith('stock24') else name)
  check(name+'-main',(d/'main.bin').read_bytes()==(src/'main.bin').read_bytes())
  check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
  check(name+'-pmic-source',(d/'strict.cs').read_bytes().endswith(root+b'\n'+timed))
  guards=[g for g in v['guards'] if g['accesses']]
  if name=='stock24-no-queued':
   check(name+'-default',boundary_state(v)==boundary_state(parse_log((src/'renode.log').read_text())) and not r['queued']['enabled'] and r['conversion']['enabled'])
  else:
   q=r['queued'];unknown=name=='stock24-results-unknown'
   check(name+'-model',q['enabled'] and q['samples']==[778,512,5,466,611,0] and q['completed']==[1,1,1,0,0,0] and q['order']==[0,2,1] and q['active']=='idle' and q['pending']==0 and q['requests']==2 and q['auto_ibat']==1)
   check(name+'-values',q['values']==[4,194,128,0,0,2,0,0,1,0,16])
   expected=queued_board((src/'board.repl').read_text(),[778,512,5,466,611,0],None if unknown else 'source-reset')
   check(name+'-current-builder',expected==(d/'board.repl').read_text())
   if unknown:
    check(name+'-unknown-mask',q['result_reset'] is None and q['known_masks']==[255,255,255,0,0,15,0,0,255,0,48])
    check(name+'-no-result-return',q['result_reads']==q['result_bytes']==0 and q['result_payloads']==[])
    check(name+'-read-block',len(guards)==1 and guards[0]['operation']=='peer-read-unsupported' and guards[0]['address']==0x511 and guards[0]['width']==4)
   else:
    check(name+'-reset-known-not-measured',q['result_reset']=='source-reset' and q['known_masks']==[255]*11 and q['completed'][3:]==[0,0,0])
    check(name+'-read-payloads',q['result_reads']==4 and q['result_bytes']==11 and q['result_addresses']==[0x511,0x515,0x519,0x510] and q['result_payloads']==['C2-80-00-00','02-00-00-01','00-10','04'])
    check(name+'-next-status-block',len(guards)==1 and guards[0]['operation']=='peer-write-unsupported' and guards[0]['value']==0x334 and guards[0]['width']==2)
    w=r['observed']['sram_windows'][0];check(name+'-ram-floats',w['base']==0x2007fa84 and bytes(w['bytes'])[:12]==struct.pack('<fff',3.798,0.004,25.009))
 for f in FILES:
  if f!='board.repl':check('result-profile-same-'+f,(b/'stock24'/f).read_bytes()==(b/'stock24-results-unknown'/f).read_bytes())
 check('only-result-profile-board-diff',(b/'stock24/board.repl').read_text().replace('    resultResetProfile: "source-reset"\n','')==(b/'stock24-results-unknown/board.repl').read_text())
 unit=s/'pmic-queued-unit-03';labels=json.loads((unit/'report.json').read_text())['checks']
 for label in ['queue-no-preemption','queue-ntc-before-automatic-ibat','queue-result-stream-4-4-2','queue-stream-overrun-atomic','queue-snapshot-tail-stable','queue-next-transaction-sees-new-result','queue-trace-ring-does-not-stop-traffic','queue-no-late-completion']:check(label,label in labels)
 variant=queued_board((s/'pmic-adc-conversion-main-01/stock24/board.repl').read_text(),[0,1,2,3,4,5],None)
 for key,value in [('vbatCode',0),('ntcCode',1),('ibatCode',2),('dieTempCode',3),('vsysCode',4),('vbusCode',5)]:check('builder-'+key,re.findall(r'^    '+key+r': (\d+)$',variant,re.M)==[str(value)])
 alt=s/'pmic-queued-sensitivity-01/stock24';ar=json.loads((alt/'report.json').read_text());al=parse_log((alt/'renode.log').read_text());validate_assets(alt,json.loads((alt/'derived-inputs.json').read_text())['derived'])
 check('sensitivity-raw-report',al==ar['observed'] and ar['queued']['samples']==[819,512,10,466,611,0])
 for f in FILES:
  if f!='board.repl':check('sensitivity-same-'+f,(b/'stock24'/f).read_bytes()==(alt/f).read_bytes())
 check('sensitivity-only-two-fields',(alt/'board.repl').read_text().replace('    vbatCode: 819','    vbatCode: 778').replace('    ibatCode: 10','    ibatCode: 5')==(b/'stock24/board.repl').read_text())
 check('sensitivity-current-builder',queued_board((s/'pmic-adc-conversion-main-01/stock24/board.repl').read_text(),[819,512,10,466,611,0],'source-reset')==(alt/'board.repl').read_text())
 w=ar['observed']['sram_windows'][0];check('sensitivity-ram-floats',w['base']==0x2007fa84 and bytes(w['bytes'])[:12]==struct.pack('<fff',3.999,0.008,25.009))
 check('sensitivity-wire',ar['queued']['result_payloads']==['CC-80-00-00','03-00-00-02','00-20','04'])
 check('single-case-not-cross-model',json.loads((alt.parent/'report.json').read_text())['stock_cfw_compared'] is False)
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
 feed=s/'recovery-pmic-feed-12';check('feed-current-runner',(feed/'runner.py').read_bytes()==(ROOT/'tools/verify_recovery_pmic_feed.py').read_bytes());check('feed-complete',json.loads((feed/'report.json').read_text())['passed'])
 for name in ['match','mismatch','busy','masked','pins']:
  d=feed/name;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();rows=[json.loads(x.split('BLACKWALL_RECOVERY_FEED ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RECOVERY_FEED ')]
  check(name+'-feed-raw',rows==[r] and 'Renode is quitting' in log and '[ERROR]' not in log)
  check(name+'-feed-current-source',root.decode()+'\n'+timed.decode() in (d/'strict.cs').read_text())
  check(name+'-feed-header',hashlib.sha256((d/'watchdog.h').read_bytes()).hexdigest()=='26aa9fef14d1fe36b1581df1c20c5c1e0818451f8d855dbfa8810bf8311ed93b')
  check(name+'-feed-result',r['mailbox']==[0x600d,int(name in ('match','masked')),int(name=='masked')] and r['kicks']==int(name in ('match','masked')) and not r['iom_guards'] and not r['pmic_guards'])
 o.mkdir(mode=0o700);(o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='saved queued ADC fixture/native data and grouped raw-input RAM sensitivity; no field units/full boot/physical proof and compiled feed mocks; no physical/analog/full boot proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
