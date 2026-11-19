"""Audit mixed-mode storage sources, replay boundaries and preserved unknown-byte guards."""
import argparse,json
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from verify_mspi1_xip_mixed import board,DRIVER

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(tag+' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 current=models(s);u=s/'mspi1-xip-mixed-unit-02';log=(u/'renode.log').read_text();r=json.loads((u/'report.json').read_text());check('unit63-raw',r==marker(log,'BLACKWALL_MSPI1_XIP_MIXED_UNIT') and r['passed'] and r['count']==63);check('unit-source',(u/'strict.cs').read_bytes()==current);check('unit-driver',(u/'test.py').read_text()==DRIVER);check('unit-board',(u/'board.repl').read_text()==board((s/'mspi1-xip-turnaround-main-01/stock24/board.repl').read_text()));check('unit-terminal','Renode is quitting' in log and 'There was an error' not in log)
 root=s/'mspi1-xip-mixed-main-01'
 for name,key,pc in [('stock24','stock24',0x4e8a46),('stock23','stock23',0x4db672),('cfw','cfw',0x4db672),('stock24-no-mixed','stock24',0x4e683a)]:
  d=root/name;prior=s/'mspi1-xip-turnaround-main-01'/key;log=(d/'renode.log').read_text();v=parse_log(log);r=json.loads((d/'report.json').read_text());selected=name!='stock24-no-mixed';check(name+'-observed',v==r['observed']);check(name+'-source',(d/'strict.cs').read_bytes()==current);check(name+'-board',(d/'board.repl').read_text()==board((prior/'board.repl').read_text(),selected));validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-derived',True)
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-main-bytes',raw==(d/'main.bin').read_bytes());check(name+'-pc',v['pc']==pc);t=marker(log,'BLACKWALL_MSPI1_XIP_MIXED');check(name+'-marker',t==r['mixed'] and t['selected']==selected);check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
  if selected:
   check(name+'-storage',t['changes']==1 and t['value']==0x200ed and t['turnaround_changes']==3 and t['reads']==54 and t['writes']==69);g=[x for x in v['guards'] if x['accesses']];check(name+'-next-strict',len(g)==1 and g[0]['address']==0x40061000 and g[0]['value']==0x30441 and g[0]['operation']=='write');x=marker(log,'BLACKWALL_MSPI1_XIP');check(name+'-no-XIP-backing-access',x['guard_accesses']==0 and not x['backing_data'] and x['enabled'])
   cfg=marker(log,'BLACKWALL_MSPI1_CONFIG')['registers'];check(name+'-RDID-request-config',cfg['12']==0x9f and cfg['132']==0x3010861 and cfg['4']==0)
  else:check(name+'-default-boundary',t['changes']==0 and boundary_state(v)==boundary_state(parse_log((prior/'renode.log').read_text())))
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(root/'stock23'/f).read_bytes()==(root/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(root/'stock23/run.py').read_text().replace('3758688','3829832')==(root/'cfw/run.py').read_text())
 reg=s/'mspi1-xip-mixed-regressions-01';r=json.loads((reg/'report.json').read_text());check('regression65',r['passed'] and sum(x['count'] for x in r['cases'])==65)
 for x,tag in zip(r['cases'],['BLACKWALL_MSPI1_XIP_TURNAROUND_UNIT','BLACKWALL_MSPI1_PIO_UNIT']):
  d=reg/x['name'];v=marker((d/'renode.log').read_text(),tag);check(x['name']+'-regression-marker',v['passed'] and v['count']==x['count']);check(x['name']+'-source',(d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==x['source_sha256']);check(x['name']+'-fixtures',all(digest(d/n)==h for n,h in x['fixtures'].items()))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='guarded configuration storage and original requests; physical timing, flash data, XIP execution and boot/display unverified'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
