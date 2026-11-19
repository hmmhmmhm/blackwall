"""Audit config storage against pinned metadata and saved native ARM artifacts."""
import argparse,json,re
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from inspect_mspi1_config_contract import collect
from verify_mspi1_config import models,board,DRIVER
from probe_mspi1_config_main import PLANS,MARKER
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;m=s/'mspi1-config-main-01';checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 _,regs=collect(s);check('source-count',len(regs)==43)
 specs=re.findall(r'new Spec\((0x[0-9a-f]+)u,(0x[0-9a-f]+)u,(0x[0-9a-f]+)u\), // (\w+)',(ROOT/'tools/renode-mspi1-config.cs').read_text())
 expected=[(r['offset'],r['reset'],r['mask'],r['name']) for r in regs if r['selected']]
 check('model-table-source-match',[(int(o,0),int(r,0),int(mask,0),n) for o,r,mask,n in specs]==expected)
 unit=s/'mspi1-config-unit-02';check('unit-current-models',(unit/'strict.cs').read_bytes()==models(s));check('unit-current-driver',(unit/'test.py').read_text()==DRIVER)
 rows=[json.loads(x.split('BLACKWALL_MSPI1_CONFIG_UNIT ',1)[1]) for x in (unit/'renode.log').read_text().splitlines() if x.startswith('BLACKWALL_MSPI1_CONFIG_UNIT ')]
 check('unit-marker-report',rows==[json.loads((unit/'report.json').read_text())]);check('unit-count',rows[0]['passed'] and rows[0]['count']==len(rows[0]['checks'])==67)
 for name,key,enabled in PLANS:
  d=m/name;src=s/'mspi1-clock-main-01'/key;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());prior=parse_log((src/'renode.log').read_text())
  check(name+' parsed-report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);checks.append(name+' asset-hashes')
  check(name+' current-models',(d/'strict.cs').read_bytes()==models(s));check(name+' board-derivation',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),enabled));check(name+' observation-only-runtime',(d/'run.py').read_text()==(src/'run.py').read_text().replace('except Exception as error:\n',MARKER+'except Exception as error:\n'))
  bundle='stock-2.4.0.24.bin' if key.startswith('stock24') else {'stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+' original-main',raw==(d/'main.bin').read_bytes())
  for f in ['result.py','probe.resc','sram-fill.bin','itcm-fill.bin']:check(name+' frozen '+f,(d/f).read_bytes()==(src/f).read_bytes())
  c=r['config'];guards=[g for g in v['guards'] if g['accesses']]
  if not enabled:check(name+' default-boundary',c==dict(enabled=False) and boundary_state(v)==boundary_state(prior))
  elif key=='stock24-stuck-off':
   check(name+' blocked-unpowered',c['reads']==c['writes']==0 and c['registers']=={str(r['offset']):r['reset'] for r in regs if r['selected']} and boundary_state(v)==boundary_state(prior))
  else:
   check(name+' config-counts',c['reads']==13 and c['writes']==20)
   check(name+' strict-cq-index-write',len(guards)==1 and guards[0]['address']==0x400612c0 and guards[0]['operation']=='write' and guards[0]['value']==0 and guards[0]['width']==4)
  check(name+' no-completion-claim',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
  check(name+' power-phase',r['power']['phase']==('stuck-off' if key=='stock24-stuck-off' else 'on'))
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock-cfw '+f,(m/'stock23'/f).read_bytes()==(m/'cfw'/f).read_bytes())
 check('stock-cfw-runtime',(m/'stock23/run.py').read_text().replace('3758688','3829832')==(m/'cfw/run.py').read_text())
 a.output.mkdir(mode=0o700);(a.output/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='source table and saved native artifacts; no bus/physical/full boot/display proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
