"""Verify saved clock main derivation, original bytes and strict boundaries."""
import argparse,json
from pathlib import Path
from native_replay import FILES,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_clock import models,board,DRIVER
from probe_mspi1_clock_main import PLANS,MARKER
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;m=s/'mspi1-clock-main-01';checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 unit=s/'mspi1-clock-unit-02';check('current-unit-driver',(unit/'test.py').read_text()==DRIVER);check('unit-current-models',(unit/'strict.cs').read_bytes()==models(s))
 log=(unit/'renode.log').read_text();rows=[json.loads(x.split('BLACKWALL_MSPI1_CLOCK_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_CLOCK_UNIT ')]
 check('unit-marker',rows==[json.loads((unit/'report.json').read_text())]);check('unit-count',rows[0]['passed'] and rows[0]['count']==len(rows[0]['checks'])==16)
 for name,key,enabled in PLANS:
  d=m/name;src=s/('mspi1-power-stuck-main-01' if key=='stock24-stuck-off' else 'mspi1-power-main-01')/key;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());prior=parse_log((src/'renode.log').read_text())
  check(name+' parsed-report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);checks.append(name+' hashes')
  check(name+' models',(d/'strict.cs').read_bytes()==models(s));check(name+' board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),enabled));check(name+' observation-only-runtime',(d/'run.py').read_text()==(src/'run.py').read_text().replace('except Exception as error:\n',MARKER+'except Exception as error:\n'))
  bundle='stock-2.4.0.24.bin' if key.startswith('stock24') else {'stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+' original-main',raw==(d/'main.bin').read_bytes())
  for f in ['result.py','probe.resc','sram-fill.bin','itcm-fill.bin']:check(name+' frozen '+f,(d/f).read_bytes()==(src/f).read_bytes())
  if enabled:
   c=r['clock'];check(name+' clock-state',c['value']==0xa4234 and c['gate'] and c['selection']==8 and c['reads']==c['writes']==2)
   guards=[g for g in v['guards'] if g['accesses']];check(name+' strict-ms pi-register',len(guards)==1 and guards[0]['address']==0x40061090 and guards[0]['operation']=='read')
  else:check(name+' default-boundary',boundary_state(v)==boundary_state(prior) and r['clock']==dict(enabled=False))
  check(name+' no-completion-claim',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
  check(name+' power-response',r['power']['phase']==('stuck-off' if key=='stock24-stuck-off' else 'on') and r['power']['status']==(0 if key=='stock24-stuck-off' else 0x8000))
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock-cfw '+f,(m/'stock23'/f).read_bytes()==(m/'cfw'/f).read_bytes())
 check('stock-cfw-runtime',(m/'stock23/run.py').read_text().replace('3758688','3829832')==(m/'cfw/run.py').read_text())
 a.output.mkdir(mode=0o700);(a.output/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='saved artifacts; source metadata contract audited separately; no hardware/full boot/display'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
