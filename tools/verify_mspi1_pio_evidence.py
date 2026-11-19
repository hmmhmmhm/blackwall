"""Audit current PIO sources, synthetic tests and unchanged original ARM replay inputs."""
import argparse,json
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models,board,SETUP,PHASES

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(tag+' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError('Missing '+tag)
  return rows[0]
 current=models(s)
 for name,count,complete in [('mspi1-pio-unit-05',26,True),('mspi1-pio-stuck-01',12,False)]:
  d=s/name;log=(d/'renode.log').read_text();r=json.loads((d/'report.json').read_text());check(name+'-marker',r==marker(log,'BLACKWALL_MSPI1_PIO_UNIT') and r['passed'] and r['count']==count);check(name+'-source',(d/'strict.cs').read_bytes()==current);check(name+'-setup',(d/'setup.py').read_text()==SETUP);check(name+'-board',(d/'board.repl').read_text()==board((s/'mspi1-clear-all-main-01/stock24/board.repl').read_text(),complete=complete));check(name+'-terminal','Renode is quitting' in log and 'There was an error' not in log)
  phases=PHASES if complete else [(1000,"check('stuck-no-completion',q.Busy and q.Starts==1 and q.Completions==0 and not q.ResetArmed and not q.Recovering)\n")]
  for n,(us,phase) in enumerate(phases):check(name+'-phase-'+str(n),(d/f'phase-{n}.py').read_text()==phase and 'FromMicroseconds('+str(us)+')' in (d/f'advance-{n}.py').read_text())
 root=s/'mspi1-pio-main-02'
 for name,key,pc in [('stock24','stock24',0x4e75d6),('stock23','stock23',0x4da202),('cfw','cfw',0x4da202),('stock24-no-pio','stock24',0x4e8a46)]:
  d=root/name;prior=s/'mspi1-clear-all-main-01'/key;log=(d/'renode.log').read_text();v=parse_log(log);r=json.loads((d/'report.json').read_text());selected=name!='stock24-no-pio';check(name+'-report',v==r['observed']);check(name+'-source',(d/'strict.cs').read_bytes()==current);check(name+'-board',(d/'board.repl').read_text()==board((prior/'board.repl').read_text(),selected));validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-derived',True)
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-raw-main',raw==(d/'main.bin').read_bytes());check(name+'-pc',v['pc']==pc);q=marker(log,'BLACKWALL_MSPI1_PIO');check(name+'-marker',q==r['pio'] and q['selected']==selected);check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
  if selected:
   check(name+'-two-completions-reset',q['starts']==q['completions']==q['reads']==q['writes']==2 and q['resets']==1 and q['aborted']==q['ignored_resets']==0 and q['control']==0xc2 and not q['busy'] and not q['armed'] and not q['recovering']);g=[x for x in v['guards'] if x['accesses']];check(name+'-next-XIP-write',len(g)==1 and g[0]['operation']=='write' and g[0]['address']==0x40061090 and g[0]['value']==0x205ed)
   irq=marker(log,'BLACKWALL_MSPI1_CLEAR_ALL');check(name+'-IRQ-state',irq['writes']==10 and irq['all_clear_writes']==4 and irq['enable']==0x1a80 and irq['status']==0 and not irq['level'])
  else:check(name+'-default-boundary',boundary_state(v)==boundary_state(parse_log((prior/'renode.log').read_text())))
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(root/'stock23'/f).read_bytes()==(root/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(root/'stock23/run.py').read_text().replace('3758688','3829832')==(root/'cfw/run.py').read_text())
 reg=s/'mspi1-pio-regressions-01';r=json.loads((reg/'report.json').read_text());check('regression98',r['passed'] and sum(x['count'] for x in r['cases'])==98)
 for x,tag in zip(r['cases'],['BLACKWALL_MSPI1_CLEAR_ALL_UNIT','BLACKWALL_MSPI1_CLOCK_UNIT']):
  d=reg/x['name'];v=marker((d/'renode.log').read_text(),tag);check(x['name']+'-regression-marker',v['passed'] and v['count']==x['count']);check(x['name']+'-source',(d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==x['source_sha256']);check(x['name']+'-fixtures',all(digest(d/n)==h for n,h in x['fixtures'].items()))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='virtual idle NOR model and original execution evidence, no physical reset/clock/identity/backing or boot/display proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
