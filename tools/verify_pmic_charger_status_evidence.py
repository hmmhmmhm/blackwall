"""Audit saved status/native/regression evidence without repeating guest execution."""
import argparse,json,hashlib
from pathlib import Path
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state
from probe_pmic_charger_status_main import PLANS,MARKER,status_board
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output
 if o.exists():raise ValueError('Fresh evidence directory required')
 checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,name):
  rows=[json.loads(x.split(name+' ',1)[1]) for x in log.splitlines() if x.startswith(name+' ')]
  check(name+'-unique-'+str(len(checks)),len(rows)==1)
  return rows[0]
 root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes();b=s/'pmic-charger-status-main-01';base=s/'pmic-queued-main-01';old=(base/'root.cs').read_bytes()+b'\n'+(base/'timed.cs').read_bytes()
 check('current-root',(b/'root.cs').read_bytes()==root);check('current-timed',(b/'timed.cs').read_bytes()==timed);check('current-runner',(b/'runner.py').read_bytes()==(ROOT/'tools/probe_pmic_charger_status_main.py').read_bytes())
 red=(s/'pmic-charger-status-unit-01/renode.log').read_text();check('red-missing-api-preserved','takes at most 8 arguments (9 given)' in red and 'BLACKWALL_CHARGER_STATUS_UNIT {' not in red)
 for folder,name,count,source in [
  ('pmic-charger-status-unit-02','BLACKWALL_CHARGER_STATUS_UNIT',118,root),
  ('pmic-queued-unit-04','BLACKWALL_QUEUED_UNIT',401,root+b'\n'+timed),
  ('pmic-adc-conversion-unit-07','BLACKWALL_CONVERSION_UNIT',408,root+b'\n'+timed),
  ('pmic-timed-unit-12','BLACKWALL_TIMED_UNIT',240,root+b'\n'+timed)]:
  d=s/folder;log=(d/'renode.log').read_text();r=json.loads((d/'report.json').read_text())
  check(folder+'-raw',marker(log,name)==r and 'Renode is quitting' in log and '[ERROR]' not in log)
  check(folder+'-checks',r['passed'] and r['count']==count and len(set(r['checks']))==count)
  check(folder+'-current-source',(d/'peer.cs').read_bytes()==source)
 for name,key,profile in PLANS:
  d=b/name;src=base/key;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);pins=json.loads((d/'derived-inputs.json').read_text());validate_assets(d,pins['derived'])
  check(name+'-raw',r['observed']==v and r['image_id']==IMAGE and 'Renode is quitting' in log)
  check(name+'-immutable-main',(d/'main.bin').read_bytes()==(src/'main.bin').read_bytes())
  check(name+'-pmic-source',(d/'strict.cs').read_bytes().endswith(root+b'\n'+timed))
  frozen=(src/'strict.cs').read_bytes()
  check(name+'-only-pmic-suffix-changed',frozen.endswith(old) and (d/'strict.cs').read_bytes()==frozen[:-len(old)]+root+b'\n'+timed)
  check(name+'-board',(d/'board.repl').read_text()==status_board((src/'board.repl').read_text(),profile))
  check(name+'-runtime-only-observation',(d/'run.py').read_text()==(src/'run.py').read_text().replace('except Exception as error:\n',MARKER+'except Exception as error:\n'))
  for f in ['result.py','probe.resc','sram-fill.bin','itcm-fill.bin']:check(name+'-unchanged-'+f,(d/f).read_bytes()==(src/f).read_bytes())
  check(name+'-scope',not r['hardware_validated'] and not r['boot_verified'] and not r['installable'] and not r['additional_hypothesis']['charging_fsm'])
  q=r['queued'];status=r['charger_status'];check(name+'-status-raw',status==marker(log,'BLACKWALL_PMIC_CHARGER_STATUS'))
  check(name+'-queue-raw',q==marker(log,'BLACKWALL_PMIC_QUEUED'))
  check(name+'-timer-not-started',not r['timer']['running'] and r['timer']['starts']==0)
  check(name+'-same-adc-return',q['result_reads']==4 and q['result_bytes']==11 and q['result_payloads']==['C2-80-00-00','02-00-00-01','00-10','04'])
  guards=[g for g in v['guards'] if g['accesses']]
  if profile is None:
   check(name+'-unknown',status==dict(profile=None,addresses=[],values=[],reads=0,bytes=0,read_addresses=[],read_payloads=[]))
   check(name+'-boundary-preserved',boundary_state(v)==boundary_state(parse_log((src/'renode.log').read_text())))
   check(name+'-previous-queue',q['completed']==[1,1,1,0,0,0] and q['requests']==2 and q['auto_ibat']==1)
  else:
   value=int(profile=='battery-detected-idle-snapshot')
   check(name+'-one-byte-status',status==dict(profile=profile,addresses=[0x32d,0x332,0x333,0x334,0x336,0x337],values=[0,0,0,value,0,0],reads=1,bytes=1,read_addresses=[0x334],read_payloads=['01' if value else '00']))
   check(name+'-next-buck-pointer',len(guards)==1 and guards[0]['operation']=='peer-write-unsupported' and guards[0]['value']==0x40f and guards[0]['width']==2)
   check(name+'-second-conversions-not-loop-proof',q['completed']==[2,2,2,0,0,0] and q['order']==[0,2,1,0,2,1] and q['requests']==4 and q['auto_ibat']==2 and q['pending']==0 and q['active']=='idle')
 for f in FILES:
  if f!='board.repl':check('only-snapshot-diff-'+f,(b/'stock24'/f).read_bytes()==(b/'stock24-battery-detected'/f).read_bytes()==(b/'stock24-status-unknown'/f).read_bytes())
 for f in ['board.repl','strict.cs','result.py','probe.resc']:check('stock23-cfw-'+f,(b/'stock23'/f).read_bytes()==(b/'cfw'/f).read_bytes())
 check('stock23-cfw-runtime',(b/'stock23/run.py').read_text().replace('3758688','3829832')==(b/'cfw/run.py').read_text())
 feed=s/'recovery-pmic-feed-13';check('feed-current-runner',(feed/'runner.py').read_bytes()==(ROOT/'tools/verify_recovery_pmic_feed.py').read_bytes());check('feed-terminal-pass',json.loads((feed/'report.json').read_text())['passed'])
 for name in ['match','mismatch','busy','masked','pins']:
  d=feed/name;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text()
  check(name+'-feed-raw',r==marker(log,'BLACKWALL_RECOVERY_FEED') and 'Renode is quitting' in log and '[ERROR]' not in log)
  check(name+'-feed-current-source',root.decode()+'\n'+timed.decode() in (d/'strict.cs').read_text())
  check(name+'-feed-header',hashlib.sha256((d/'watchdog.h').read_bytes()).hexdigest()=='26aa9fef14d1fe36b1581df1c20c5c1e0818451f8d855dbfa8810bf8311ed93b')
  check(name+'-feed-behavior',r['mailbox']==[0x600d,int(name in ('match','masked')),int(name=='masked')] and r['kicks']==int(name in ('match','masked')) and r['pmic_guards']==r['iom_guards']==0)
 manifest=json.loads((s/'npmx-charger-status-research-01/sources.json').read_text());tree=json.loads((s/'npmx-research-01/tree.json').read_text())
 for item in manifest['files']:
  data=(s/'npmx-charger-status-research-01'/Path(item['path']).name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  check(item['path']+'-source-pin',hashlib.sha256(data).hexdigest()==item['sha256'] and blob==item['git_blob']==next(x['sha'] for x in tree['tree'] if x['path']==item['path']))
 o.mkdir(mode=0o700);(o/'verifier.py').write_bytes(Path(__file__).read_bytes());(o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='saved original ARM/status snapshots/regressions; no new execution/physical charging/full boot proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
