"""Audit guarded XIP control, preserved original inputs, and synthetic unknown-load abort."""
import argparse,hashlib,json,struct
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_xip_guard import models,board,DRIVER
from verify_mspi1_xip_cpu_read import SETUP,REPORT
from probe_mspi1_xip_main import PLANS,MARKER,observe_guard
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;m=s/'mspi1-xip-guard-main-01';checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def saved_marker(path,tag):
  rows=[json.loads(z.split(tag+' ',1)[1]) for z in (path/'renode.log').read_text().splitlines() if z.startswith(tag+' ')]
  check(path.name+' raw-marker-report',rows==[json.loads((path/'report.json').read_text())]);return rows[0]
 research=s/'mspi1-xip-research-01';manifest=json.loads((research/'sources.json').read_text());check('source-commit',manifest['commit']=='61b293a49db34030c545f99101f7ebf6a3050314')
 for f in manifest['files']:check(f['path']+' source',hashlib.sha256((research/Path(f['path']).name).read_bytes()).hexdigest()==f['sha256'])
 contract=json.loads((s/'mspi1-xip-contract-05/report.json').read_text());check('prior-source-contract',contract['passed'] and contract['count']==58 and not contract['backing_data_proven'] and all(c['base']==0x80000000 and c['size']==0x2000000 and c['readonly'] for c in contract['cases']))
 unit=s/'mspi1-xip-guard-unit-02';r=saved_marker(unit,'BLACKWALL_MSPI1_XIP_UNIT');check('unit-count',r['passed'] and r['count']==len(r['checks'])==26);check('unit-current-models',(unit/'strict.cs').read_bytes()==models(s));check('unit-current-driver',(unit/'test.py').read_text()==DRIVER)
 cpu=s/'mspi1-xip-cpu-read-01';r=saved_marker(cpu,'BLACKWALL_MSPI1_XIP_CPU_READ');check('synthetic-cpu-fault',r['passed'] and r['count']==5 and r['pc']==0x1000c and r['address']==0x80000000 and r['width']==4)
 check('cpu-current-models',(cpu/'strict.cs').read_bytes()==models(s));check('cpu-setup',(cpu/'setup.py').read_text()==SETUP and (cpu/'report.py').read_text()==REPORT);check('cpu-board',(cpu/'board.repl').read_text()==board((s/'mspi1-cq-init-main-01/stock24/board.repl').read_text()))
 guest=struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('0022024801685a22fee70000')+struct.pack('<I',0x80000000);check('synthetic-guest',(cpu/'guest.bin').read_bytes()==guest)
 for name,key,enabled in PLANS:
  d=m/name;src=s/'mspi1-cq-init-main-01'/key;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());prior=parse_log((src/'renode.log').read_text());check(name+' report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);checks.append(name+' hashes')
  check(name+' models',(d/'strict.cs').read_bytes()==models(s));check(name+' board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),enabled))
  runtime=(src/'run.py').read_text();result=(src/'result.py').read_text()
  if enabled:runtime=observe_guard(runtime);result=observe_guard(result)
  check(name+' observation-only-runtime',(d/'run.py').read_text()==runtime.replace('except Exception as error:\n',MARKER+'except Exception as error:\n'));check(name+' result-inventory-only',(d/'result.py').read_text()==result)
  bundle='stock-2.4.0.24.bin' if key.startswith('stock24') else {'stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+' original-main',raw==(d/'main.bin').read_bytes())
  for f in ['probe.resc','sram-fill.bin','itcm-fill.bin']:check(name+' frozen '+f,(d/f).read_bytes()==(src/f).read_bytes())
  x=r['xip'];check(name+' profile',x['selected']==enabled)
  if enabled:
   check(name+' guard-inventory',len([g for g in v['guards'] if g['name']=='xip_guard' and g['accesses']==0])==1)
   check(name+' guarded-unknown-window',x['base']==0x80000000 and x['length']==0x2000000 and x['guard_size']==0x4000000 and x['guard_accesses']==0 and not x['backing_data'])
  if not enabled or key=='stock24-stuck-off':
   check(name+' default-failure-boundary',boundary_state(v)==boundary_state(prior))
   if enabled:check(name+' no-unpowered-enable',not x['enabled'] and x['requests']==x['transitions']==0)
  else:
   check(name+' control-recorded',x['enabled'] and x['requests']==x['transitions']==1)
   guards=[g for g in v['guards'] if g['accesses']];check(name+' next-interrupt-clear',len(guards)==1 and guards[0]['address']==0x40061208 and guards[0]['operation']=='write' and guards[0]['value']==0x1a80)
  check(name+' no-completion-claim',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock-cfw '+f,(m/'stock23'/f).read_bytes()==(m/'cfw'/f).read_bytes())
 check('stock-cfw-runtime',(m/'stock23/run.py').read_text().replace('3758688','3829832')==(m/'cfw/run.py').read_text())
 for dirname,tag,count in [('mspi1-xip-config-regression-01','BLACKWALL_MSPI1_CONFIG_UNIT',67),('mspi1-xip-cq-regression-01','BLACKWALL_MSPI1_CQ_INIT_UNIT',33)]:
  d=s/dirname;r=saved_marker(d,tag);check(dirname+' count',r['passed'] and r['count']==count);check(dirname+' models',(d/'strict.cs').read_bytes()==models(s))
 a.output.mkdir(mode=0o700);(a.output/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='guarded control and unknown-data rejection; no backing, XIP instruction fetch, full boot/display or physical proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
