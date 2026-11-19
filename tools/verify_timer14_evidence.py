"""Audit saved Timer14 evidence against current source and immutable original main assets."""
import argparse,json
from pathlib import Path
from native_replay import parse_log,validate_assets,digest,boundary_state
from verify_timer14 import models,SETUP,PHASES,board
from pinned_main import load_pinned_main

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  found=[json.loads(x.split(tag+' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(found)!=1:raise ValueError('Missing '+tag)
  return found[0]
 current=models(s);unit=s/'timer14-unit-06';log=(unit/'renode.log').read_text();r=json.loads((unit/'report.json').read_text());check('unit27-marker',r==marker(log,'BLACKWALL_TIMER14_UNIT') and r['passed'] and r['count']==27);check('unit-source-current',(unit/'strict.cs').read_bytes()==current);check('unit-setup-current',(unit/'setup.py').read_text()==SETUP)
 for n,(us,phase) in enumerate(PHASES):check('unit-phase-'+str(n),(unit/f'phase-{n}.py').read_text()==phase and 'FromMicroseconds('+str(us)+')' in (unit/f'advance-{n}.py').read_text())
 root=s/'timer14-main-01';reports={}
 for name,key,pc,counter in [('stock24','stock24',0x4e8a3e,2),('stock23','stock23',0x4db66a,3),('cfw','cfw',0x4db66a,3),('stock24-no-timer14','stock24',0x5070d4,None)]:
  d=root/name;log=(d/'renode.log').read_text();v=parse_log(log);r=json.loads((d/'report.json').read_text());reports[name]=r;check(name+'-saved-report',v==r['observed']);check(name+'-source-current',(d/'strict.cs').read_bytes()==current);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-derived-assets',True)
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-bytes',raw==(d/'main.bin').read_bytes());check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable']);t=marker(log,'BLACKWALL_TIMER14');check(name+'-timer-marker',t==r['timer14']);check(name+'-pc',v['pc']==pc)
  prior=s/'mspi1-interrupts-main-01'/key;check(name+'-board',(d/'board.repl').read_text()==(board((prior/'board.repl').read_text()) if counter is not None else (prior/'board.repl').read_text()))
  if counter is None:check(name+'-unchanged-boundary',not t['selected'] and boundary_state(v)==boundary_state(parse_log((prior/'renode.log').read_text())))
  else:
   check(name+'-timer-state',t['selected'] and t['control']==0xa10 and t['counter']==counter and t['compare0']==t['compare1']==0xffffffff and t['writes']==9 and t['frequency']==32768 and t['global_enable']==0xffff and t['status']==t['enable']==0 and not t['running'] and not t['level']);g=[x for x in v['guards'] if x['accesses']];check(name+'-next-strict-write',len(g)==1 and g[0]['address']==0x40061208 and g[0]['operation']=='write' and g[0]['value']==0xffffffff)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(root/'stock23'/f).read_bytes()==(root/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(root/'stock23/run.py').read_text().replace('3758688','3829832')==(root/'cfw/run.py').read_text())
 regression_dirs=[]
 for base,name,tag,count in [('timer14-regressions-01','mspi1-interrupts-unit-02','BLACKWALL_MSPI1_INTERRUPTS_UNIT',73),('timer14-regressions-02','stimer-clock-unit-04','BLACKWALL_STIMER_CLOCK_UNIT',33)]:
  d=s/base/name;regression_dirs.append(d);x=json.loads((d/'report.json').read_text());r=marker((d/'renode.log').read_text(),tag);check(name+'-raw-result',r['passed'] and r['count']==count and x['count']==count);check(name+'-source-current',(d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==x['source_sha256']);check(name+'-fixtures',all(digest(d/n)==h for n,h in x['fixtures'].items()))
 for d in [unit]+regression_dirs:
  log=(d/'renode.log').read_text();expected='[WARNING] Translation cache size 536870912 is larger than maximum allowed 134217728. It will be clamped to maximum'
  check(d.name+'-terminal-no-errors','Renode is quitting' in log and not any('There was an error' in line or '[ERROR]' in line or ('[WARNING]' in line and not line.endswith(expected)) for line in log.splitlines()))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='saved source and native evidence audit; no hardware/full boot/display proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
