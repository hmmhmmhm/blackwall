"""Audit explicit digital sampling, original scan masks/output and continuous host observation."""
import argparse,json,struct
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from verify_mspi1_sampling_profile import board,COMMON,ACTIVE,phases
from verify_mspi1_sampling_none import DRIVER as NONE_DRIVER
from probe_mspi1_sampling_main import observation,LIVE_WAIT
from verify_sampling_wait import run as wait_case
CASES=[('stock24','stock24','mspi1-ideal-sampling-main-01',True,'legacy'),('stock23','stock23','mspi1-ideal-sampling-main-04',True,'until-paused'),('cfw','cfw','mspi1-ideal-sampling-main-04',True,'until-paused'),('stock24-fixed','stock24','mspi1-ideal-sampling-main-04',False,'until-paused')]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 current=models(s)
 for name,count,ideal in [('mspi1-sampling-unit-02',51,True),('mspi1-sampling-fixed-01',33,False)]:
  d=s/name;log=(d/'renode.log').read_text();r=json.loads((d/'report.json').read_text());check(name+'-raw-result',r==marker(log,'BLACKWALL_MSPI1_SAMPLING_UNIT') and r['passed'] and r['count']==count);check(name+'-current-source',(d/'strict.cs').read_bytes()==current);check(name+'-setup',(d/'setup.py').read_text()==COMMON+ACTIVE);check(name+'-board',(d/'board.repl').read_text()==board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),ideal))
  for n,(us,phase) in enumerate(phases(ideal)):check(name+'-phase-'+str(n),(d/f'phase-{n}.py').read_text()==phase and 'FromMicroseconds('+str(us)+')' in (d/f'advance-{n}.py').read_text())
 d=s/'mspi1-sampling-none-01';r=json.loads((d/'report.json').read_text());check('ideal-no-identity5',r==marker((d/'renode.log').read_text(),'BLACKWALL_SAMPLING_NONE') and r['passed'] and r['count']==5);check('none-current-source',(d/'strict.cs').read_bytes()==current);check('none-driver',(d/'test.py').read_text()==NONE_DRIVER);check('none-board',(d/'board.repl').read_text()==board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text()).replace('    identityProfile: "mx25u25643g"\n','    identityProfile: "none"\n'))
 reports={}
 for name,key,folder,ideal,wait_mode in CASES:
  d=s/folder/name;src=s/'mspi1-sampling-context-01'/key;log=(d/'renode.log').read_text();v=parse_log(log);r=json.loads((d/'report.json').read_text());reports[name]=r;baseline=json.loads((src/'report.json').read_text());check(name+'-report',r['passed'] and v==r['observed']);check(name+'-source',(d/'strict.cs').read_bytes()==current);check(name+'-board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),ideal));validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-assets',True)
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',raw==(d/'main.bin').read_bytes());runtime,capture=observation((src/'run.py').read_text(),raw,baseline['metadata'],baseline['selected_observation'],wait_mode);check(name+'-observations-and-wait-only',(d/'run.py').read_text()==runtime and r['capture']==capture);q=marker(log,'BLACKWALL_MSPI1_SAMPLING');ob=marker(log,'BLACKWALL_OBSERVATION');check(name+'-markers',q==r['sampling'] and ob==r['selected_observation']);check(name+'-selected-events-no-loss',ob['capacity']==4096 and ob['dropped_events']==0 and len(ob['events'])==ob['sequence']);points={x['label']:x for x in ob['points']};check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
  if ideal:
   check(name+'-scan-frames',q['profile']=='ideal-sdr' and q['id_frames']==q['fifo_reads']==1152 and q['completions']==q['starts']==1154 and q['completed_mask']==0xf0 and q['pending']==0 and not q['busy']);check(name+'-pass-matrix',r['pass_masks']==[0xffffffff]*36 and all(points['scan-matrix-'+str(n)]['hits']==1 for n in range(3)));snapshot=points['scan-return']['snapshot'];event=next(x for x in ob['events'] if x['label']=='scan-return');check(name+'-source-return-and-output',points['scan-return']['hits']==1 and event['r0']==0 and event['address']==capture['return_point'] and snapshot['address']==capture['output'] and struct.pack('<2I',*snapshot['words'])[:6].hex()==r['selection']=='010000010e20')
   snapshots=[points['scan-matrix-'+str(n)]['snapshot'] for n in range(3)]
   check(name+'-raw-matrix-snapshots',all(x['address']==capture['matrix']+64*n and len(x['words'])==[16,16,4][n] for n,x in enumerate(snapshots)) and [word for x in snapshots for word in x['words']]==r['pass_masks'])
   incoming=[x for x in ob['events'] if x['label']=='classifier-input'];result=[x for x in ob['events'] if x['label']=='classifier-result'];check(name+'-native-classifier',len(incoming)==len(result)==1152 and all(x['r0']==0xc22539 and y['r0']==0 and x['sequence']<y['sequence'] for x,y in zip(incoming,result)));check(name+'-selected-events',ob['sequence']==3787)
   cfg=marker(log,'BLACKWALL_MSPI1_CONFIG')['registers'];check(name+'-next-zero-turnaround',cfg['132']==0x3010061 and cfg['12']==0x9f and cfg['144']==0xed);g=[x for x in v['guards'] if x['accesses']];check(name+'-next-strict',len(g)==1 and g[0]['address']==0x40061000 and g[0]['value']==0x30441 and g[0]['operation']=='write')
  else:check(name+'-default-boundary',boundary_state(v)==boundary_state(baseline['observed']) and q['profile']=='fixed-capture' and q['id_frames']==288 and q['completed_mask']==16 and r['selection'] is None and r['pass_masks']==[] and points['scan-return']['hits']==0)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(s/CASES[1][2]/'stock23'/f).read_bytes()==(s/CASES[2][2]/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(s/CASES[1][2]/'stock23/run.py').read_text().replace('3758688','3829832')==(s/CASES[2][2]/'cfw/run.py').read_text())
 for turns in [0,6,16]:check('host-wait-'+str(turns),wait_case(turns)==turns)
 before=(s/'sampling-wait-verification-01/before.py').read_text()
 try:wait_case(6,before)
 except NameError as e:check('host-wait-old-import-failure',"json" in str(e))
 else:raise ValueError('Old progress loop failure not reproduced')
 reg=s/'mspi1-sampling-regressions-01';r=json.loads((reg/'report.json').read_text());check('regression93',r['passed'] and sum(x['count'] for x in r['cases'])==93)
 for x,tag in zip(r['cases'],['BLACKWALL_MSPI1_RDID_UNIT','BLACKWALL_MSPI1_XIP_MIXED_UNIT']):
  d=reg/x['name'];v=marker((d/'renode.log').read_text(),tag);check(x['name']+'-regression',v['passed'] and v['count']==x['count']);check(x['name']+'-source',(d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==x['source_sha256']);check(x['name']+'-fixtures',all(digest(d/n)==h for n,h in x['fixtures'].items()))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,main_locations={n:str(Path(folder)/n) for n,k,folder,i,w in CASES},scope='explicit ideal digital model and source scan execution; no physical timing margin, full boot/display or stock restoration proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
