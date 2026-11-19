"""Audit pinned BUCK contracts and saved original ARM/regression runs, without guest replay."""
import argparse,json,hashlib,re
from pathlib import Path
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from probe_pmic_buck_main import PLANS,MARKER,buck_board
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output
 if o.exists():raise ValueError('Fresh evidence directory required')
 checks=[]
 def check(name,v):
  if not v:raise ValueError(name)
  checks.append(name)
 def marker(log,name):
  rows=[json.loads(x.split(name+' ',1)[1]) for x in log.splitlines() if x.startswith(name+' ')]
  check(name+'-unique-'+str(len(checks)),len(rows)==1)
  return rows[0]
 src=s/'npmx-buck-research-01';manifest=json.loads((src/'sources.json').read_text());tree=json.loads((s/'npmx-research-01/tree.json').read_text())
 check('pinned-source-commit',manifest['commit']==tree['sha']=='4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f')
 for item in manifest['files']:
  data=(src/Path(item['path']).name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  check(item['path']+'-source-pin',hashlib.sha256(data).hexdigest()==item['sha256'] and blob==item['git_blob']==next(x['sha'] for x in tree['tree'] if x['path']==item['path']))
 header=(src/'npm1300.h').read_text();sdk=(src/'npmx_buck.c').read_text();sdk_header=(src/'npmx_buck.h').read_text()
 registers=[('BUCK1NORMVOUT',0x408,2),('BUCK1RETVOUT',0x409,2),('BUCK2NORMVOUT',0x40a,8),('BUCK2RETVOUT',0x40b,8),('BUCKENCTRL',0x40c,0),('BUCKVRETCTRL',0x40d,0),('BUCKPWMCTRL',0x40e,0),('BUCKSWCTRLSEL',0x40f,0),('BUCKCTRL0',0x415,0)]
 check('buck-base','#define NPM_BUCK_BASE                     0x00000400UL' in header)
 for name,address,value in registers:
  decl=re.search(r'__IOM uint8_t\s+'+name+r';\s*/\*!< \(@ (0x[0-9A-F]+)\)',header);reset=re.search(r'#define BUCK_'+name+r'_ResetValue \((0x[0-9A-Fa-f]+)UL\)',header)
  check(name+'-rw-offset',decl is not None and int(decl[1],16)+0x400==address)
  check(name+'-reset',reset is not None and int(reset[1],16)==value)
 for index,name in enumerate(['BUCK1ENASET','BUCK1ENACLR','BUCK2ENASET','BUCK2ENACLR','BUCK1PWMSET','BUCK1PWMCLR','BUCK2PWMSET','BUCK2PWMCLR']):
  decl=re.search(r'__OM uint8_t\s+'+name+r';\s*/\*!< \(@ (0x[0-9A-F]+)\)',header)
  check(name+'-writeonly-task',decl is not None and int(decl[1],16)==index and name in sdk)
 for name in ['BUCK1VOUTSTATUS','BUCK2VOUTSTATUS','BUCKSTATUS']:check(name+'-readonly',bool(re.search(r'__IM uint8_t\s+'+name+r';',header)))
 check('voltage-24-alias-not-3v4',bool(re.search(r'BUCK_BUCK1NORMVOUT_BUCK1NORMVOUT_3V30 \(0x18UL\).*3.3V',header)))
 check('sdk-max-23',bool(re.search(r'NPMX_BUCK_VOLTAGE_MAX\s*= NPMX_BUCK_VOLTAGE_3V3',sdk_header)) and 'BUCK_BUCK1NORMVOUT_BUCK1NORMVOUT_3V3 (0x17UL)' in header)
 root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes();b=s/'pmic-buck-main-01';base=s/'pmic-charger-status-main-01';old=(base/'root.cs').read_bytes()+b'\n'+(base/'timed.cs').read_bytes()
 check('root-current',(b/'root.cs').read_bytes()==root);check('timed-current',(b/'timed.cs').read_bytes()==timed);check('runner-current',(b/'runner.py').read_bytes()==(ROOT/'tools/probe_pmic_buck_main.py').read_bytes())
 red=(s/'pmic-buck-unit-01/renode.log').read_text();check('red-missing-api','takes at most 9 arguments (10 given)' in red and 'BLACKWALL_BUCK_UNIT {' not in red)
 for folder,name,count,source in [('pmic-buck-unit-02','BLACKWALL_BUCK_UNIT',198,root),('pmic-queued-unit-05','BLACKWALL_QUEUED_UNIT',401,root+b'\n'+timed),('pmic-adc-conversion-unit-08','BLACKWALL_CONVERSION_UNIT',408,root+b'\n'+timed),('pmic-timed-unit-13','BLACKWALL_TIMED_UNIT',240,root+b'\n'+timed)]:
  d=s/folder;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text()
  check(folder+'-raw',r==marker(log,name) and 'Renode is quitting' in log and '[ERROR]' not in log)
  check(folder+'-checks',r['passed'] and r['count']==count and len(set(r['checks']))==count)
  check(folder+'-current-source',(d/'peer.cs').read_bytes()==source)
 for name,key,profile in PLANS:
  d=b/name;frozen=base/key;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);pins=json.loads((d/'derived-inputs.json').read_text());validate_assets(d,pins['derived'])
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  check(name+'-original-main',raw==(d/'main.bin').read_bytes()==(frozen/'main.bin').read_bytes())
  check(name+'-raw-report',r['observed']==v and r['image_id']==IMAGE and 'Renode is quitting' in log)
  original=(frozen/'strict.cs').read_bytes();check(name+'-only-pmic-source-change',original.endswith(old) and (d/'strict.cs').read_bytes()==original[:-len(old)]+root+b'\n'+timed)
  check(name+'-board',(d/'board.repl').read_text()==buck_board((frozen/'board.repl').read_text(),profile))
  check(name+'-runtime-only-observation',(d/'run.py').read_text()==(frozen/'run.py').read_text().replace('except Exception as error:\n',MARKER+'except Exception as error:\n'))
  for file in ['result.py','probe.resc','sram-fill.bin','itcm-fill.bin']:check(name+'-same-'+file,(d/file).read_bytes()==(frozen/file).read_bytes())
  check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'] and not r['additional_hypotheses'][1]['rail_response'])
  buck=r['buck'];check(name+'-buck-marker',buck==marker(log,'BLACKWALL_PMIC_BUCK') and buck['profile']==profile)
  check(name+'-other-components',r['charger_status']==marker(log,'BLACKWALL_PMIC_CHARGER_STATUS') and r['queued']==marker(log,'BLACKWALL_PMIC_QUEUED') and r['timer']==marker(log,'BLACKWALL_PMIC_TIMER'))
  check(name+'-adc-stopped-counts',r['queued']['completed']==[2,2,2,0,0,0] and r['queued']['result_reads']==4 and r['queued']['result_bytes']==11)
  check(name+'-watchdog-not-started',r['timer']['starts']==0 and not r['timer']['running'])
  guard=[g for g in v['guards'] if g['accesses']]
  if profile=='source-reset-storage':
   check(name+'-final-config',buck['addresses']==[x[1] for x in registers] and buck['values']==[2,2,21,8,0,0,0,2,0])
   check(name+'-guest-requests',buck['config_writes']==2 and buck['task_writes']==1 and buck['task_requests']==[0,0,1,0,0,0,0,0])
   peer=r['peer'];check(name+'-guest-write-history',peer['write_addresses'][-3:]==[0x40f,0x40a,0x402] and peer['write_values'][-3:]==[2,21,1])
   check(name+'-read-zero-selection',peer['read_addresses'][-1]==0x40f and peer['read_values'][-1]==0)
   check(name+'-next-ldsw',len(guard)==1 and guard[0]['operation']=='peer-write-unsupported' and guard[0]['value']==0x808 and guard[0]['width']==2)
  else:
   check(name+'-no-inferred-config',buck['addresses']==buck['values']==[] and buck['config_writes']==buck['task_writes']==0 and buck['task_requests']==[0]*8)
   check(name+'-unchanged-boundary',boundary_state(v)==boundary_state(parse_log((frozen/'renode.log').read_text())))
 for file in FILES:
  if file!='board.repl':check('control-same-'+file,(b/'stock24'/file).read_bytes()==(b/'stock24-buck-unknown'/file).read_bytes()==(b/'stock24-no-buck'/file).read_bytes())
 for file in ['board.repl','strict.cs','result.py','probe.resc']:check('stock23-cfw-'+file,(b/'stock23'/file).read_bytes()==(b/'cfw'/file).read_bytes())
 check('stock23-cfw-runtime',(b/'stock23/run.py').read_text().replace('3758688','3829832')==(b/'cfw/run.py').read_text())
 feed=s/'recovery-pmic-feed-14';check('feed-complete',json.loads((feed/'report.json').read_text())['passed']);check('feed-current-runner',(feed/'runner.py').read_bytes()==(ROOT/'tools/verify_recovery_pmic_feed.py').read_bytes())
 for name in ['match','mismatch','busy','masked','pins']:
  d=feed/name;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();check(name+'-feed-raw',r==marker(log,'BLACKWALL_RECOVERY_FEED') and 'Renode is quitting' in log and '[ERROR]' not in log)
  check(name+'-feed-current-source',root.decode()+'\n'+timed.decode() in (d/'strict.cs').read_text());check(name+'-feed-header',hashlib.sha256((d/'watchdog.h').read_bytes()).hexdigest()=='26aa9fef14d1fe36b1581df1c20c5c1e0818451f8d855dbfa8810bf8311ed93b')
  check(name+'-feed-outcome',r['mailbox']==[0x600d,int(name in ('match','masked')),int(name=='masked')] and r['kicks']==int(name in ('match','masked')) and r['pmic_guards']==r['iom_guards']==0)
 o.mkdir(mode=0o700);(o/'verifier.py').write_bytes(Path(__file__).read_bytes());(o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,source_manifest=manifest,scope='pinned source contract and saved original ARM/config/request evidence, no new guest/device execution/rail/full boot proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
