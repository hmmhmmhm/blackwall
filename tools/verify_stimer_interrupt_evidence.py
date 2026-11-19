"""Audit saved STIMER original ARM, register subset and RTC regression without guest replay."""
import argparse,json,hashlib
from pathlib import Path
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from probe_stimer_interrupt_main import PLANS,MARKER,board_for
from verify_stimer_interrupt_storage import DRIVER
from rtc_engine_source import load_engine
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output
 if o.exists():raise ValueError('Fresh output required')
 checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,name):
  rows=[json.loads(x.split(name+' ',1)[1]) for x in log.splitlines() if x.startswith(name+' ')]
  check(name+'-unique-'+str(len(checks)),len(rows)==1);return rows[0]
 b=s/'stimer-interrupt-main-03';base=s/'pmic-ldsw-main-01';old=(b/'old-core.cs').read_bytes();core=(ROOT/'tools/renode-strict-mmio.cs').read_bytes();addon=(ROOT/'tools/renode-stimer-interrupt-probe.cs').read_bytes()
 check('current-core',(b/'core.cs').read_bytes()==core);check('current-addon',(b/'addon.cs').read_bytes()==addon);check('current-runner',(b/'runner.py').read_bytes()==(ROOT/'tools/probe_stimer_interrupt_main.py').read_bytes())
 contract=s/'stimer-interrupt-contract-01';r=json.loads((contract/'report.json').read_text());check('source-contract',r['passed'] and r['count']==35 and not r['hardware_validated']);check('source-inspector-current',(contract/'inspector.py').read_bytes()==(ROOT/'tools/inspect_stimer_interrupt_contract.py').read_bytes());check('offset-compilation',(contract/'layout.o').stat().st_size>0 and not (contract/'compiler.log').read_text())
 for item in r['source_manifest']['files']:
  data=(s/'timer-source-research-01'/Path(item['path']).name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();check(item['path']+'-source-still-pinned',hashlib.sha256(data).hexdigest()==item['sha256'] and blob==item['git_blob'])
 check('reset-red-preserved','fixture-owner-reset' in (s/'stimer-interrupt-unit-03/renode.log').read_text())
 red=(s/'stimer-interrupt-unit-01/renode.log').read_text();check('missing-model-red','Cannot import name BlackwallStimerInterruptStorage' in red)
 failed=(s/'stimer-interrupt-main-01/stock24/renode.log').read_text();check('failed-observation-preserved',"Could not find node 'guard'" in failed and 'BLACKWALL_RUNTIME_ERROR' in failed)
 unit=s/'stimer-interrupt-unit-04';log=(unit/'renode.log').read_text();r=json.loads((unit/'report.json').read_text());check('unit-raw',marker(log,'BLACKWALL_STIMER_INTERRUPT_UNIT')==r and 'Renode is quitting' in log);check('unit27',r['passed'] and r['count']==27 and len(set(r['checks']))==27);check('unit-driver-current',(unit/'test.py').read_text()==DRIVER);check('unit-model-source',(unit/'strict.cs').read_bytes()==(b/'stock24/strict.cs').read_bytes())
 for name,key,enabled in PLANS:
  d=b/name;src=base/key;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-pinned-main',raw==(d/'main.bin').read_bytes()==(src/'main.bin').read_bytes())
  check(name+'-raw',r['observed']==v and r['image_id']==IMAGE and 'Renode is quitting' in log)
  frozen=(src/'strict.cs').read_bytes();check(name+'-only-core-addon-source',frozen.startswith(old) and (d/'strict.cs').read_bytes()==core+frozen[len(old):]+b'\n'+addon)
  check(name+'-board',(d/'board.repl').read_text()==board_for((src/'board.repl').read_text(),enabled));check(name+'-runtime-observation-only',(d/'run.py').read_text()==(src/'run.py').read_text().replace('except Exception as error:\n',MARKER+'except Exception as error:\n'))
  for file in ['result.py','probe.resc','sram-fill.bin','itcm-fill.bin']:check(name+'-same-'+file,(d/file).read_bytes()==(src/file).read_bytes())
  check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'] and not r['additional_hypotheses'][-1]['counter'] and not r['additional_hypotheses'][-1]['nvic_delivery'])
  state=r['stimer'];check(name+'-stimer-raw',state==marker(log,'BLACKWALL_STIMER_INTERRUPT'));guard=[x for x in v['guards'] if x['accesses']]
  if enabled:
   check(name+'-enable-write-completed',state==dict(enabled=True,enable=1,status=0,pending=False,reads=1,writes=1))
   check(name+'-next-stcfg',len(guard)==1 and guard[0]['address']==0x40008800 and guard[0]['operation']=='read' and guard[0]['width']==4)
  else:check(name+'-default-boundary',state==dict(enabled=False) and boundary_state(v)==boundary_state(parse_log((src/'renode.log').read_text())))
  check(name+'-pmic-unchanged',r['ldsw']==json.loads((src/'report.json').read_text())['ldsw'] and r['buck']==json.loads((src/'report.json').read_text())['buck'])
 for file in FILES:
  if file!='board.repl':check('control-only-board-'+file,(b/'stock24'/file).read_bytes()==(b/'stock24-no-stimer'/file).read_bytes())
 for file in ['board.repl','strict.cs','result.py','probe.resc']:check('stock23-cfw-'+file,(b/'stock23'/file).read_bytes()==(b/'cfw'/file).read_bytes())
 check('stock23-cfw-runtime',(b/'stock23/run.py').read_text().replace('3758688','3829832')==(b/'cfw/run.py').read_text())
 rtc=s/'rtc-adapter-stimer-regression-02';r=json.loads((rtc/'report.json').read_text());log=(rtc/'renode.log').read_text();check('rtc44-raw',marker(log,'BLACKWALL_RTC_ADAPTER')==r and r['passed'] and r['assertion_count']==44 and 'Renode is quitting' in log);check('rtc-current-core',(rtc/'strict.cs').read_text()==core.decode()+'\n'+load_engine()+'\n'+(ROOT/'tools/renode-rtc.cs').read_text())
 o.mkdir(mode=0o700);(o/'verifier.py').write_bytes(Path(__file__).read_bytes());(o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='saved source/compiled offsets/register subset/original ARM and RTC regression; no counter/NVIC/device/full boot proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
