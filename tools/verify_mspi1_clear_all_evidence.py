"""Audit HAL clear-all unit and original ARM replay evidence against current models."""
import argparse,json
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_clear_all import models,board,DRIVER

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(tag+' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 current=models(s);u=s/'mspi1-clear-all-unit-02';log=(u/'renode.log').read_text();r=json.loads((u/'report.json').read_text());check('unit82-marker',r==marker(log,'BLACKWALL_MSPI1_CLEAR_ALL_UNIT') and r['passed'] and r['count']==82);check('unit-current-source',(u/'strict.cs').read_bytes()==current);check('unit-current-driver',(u/'test.py').read_text()==DRIVER);check('unit-board',(u/'board.repl').read_text()==board((s/'mspi1-interrupts-unit-02/board.repl').read_text()));check('unit-terminal','Renode is quitting' in log and 'There was an error' not in log)
 root=s/'mspi1-clear-all-main-01'
 for name,key,pc in [('stock24','stock24',0x4e8a46),('stock23','stock23',0x4db672),('cfw','cfw',0x4db672),('stock24-no-clear-all','stock24',0x4e8a3e)]:
  d=root/name;prior=s/'timer14-main-01'/key;log=(d/'renode.log').read_text();v=parse_log(log);r=json.loads((d/'report.json').read_text());selected=name!='stock24-no-clear-all';check(name+'-observed',v==r['observed']);check(name+'-current-source',(d/'strict.cs').read_bytes()==current);check(name+'-board',(d/'board.repl').read_text()==board((prior/'board.repl').read_text(),selected));validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-saved-assets',True)
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',raw==(d/'main.bin').read_bytes());check(name+'-pc',v['pc']==pc);c=marker(log,'BLACKWALL_MSPI1_CLEAR_ALL');check(name+'-marker',c==r['clear_all']);check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable']);check(name+'-selection',c['selected']==selected)
  if selected:
   check(name+'-clear-state',c['all_clear_writes']==1 and c['enable']==c['status']==0 and not c['level']);g=[x for x in v['guards'] if x['accesses']];check(name+'-next-strict',len(g)==1 and g[0]['address']==0x40061000 and g[0]['operation']=='write' and g[0]['value']==0xc1);cfg=marker(log,'BLACKWALL_MSPI1_CONFIG')['registers'];check(name+'-next-instruction-config',cfg['12']==0x66 and cfg['132']==0x1410061 and cfg['8']==0)
  else:check(name+'-default-boundary',c['all_clear_writes']==0 and boundary_state(v)==boundary_state(parse_log((prior/'renode.log').read_text())))
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(root/'stock23'/f).read_bytes()==(root/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(root/'stock23/run.py').read_text().replace('3758688','3829832')==(root/'cfw/run.py').read_text())
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='source and saved original ARM evidence; physical reserved-bit behavior, bus transfer, boot/display unverified'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
