"""Audit routed mock CQFLAGS, exact original snapshot, counterfactual and unknown control."""
import argparse,json
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from verify_mspi1_cqflags import board as unit_board,PHASES,COMMON,DRIVER,ACTIVE
from probe_mspi1_cqflags_main import PLANS,board,instrument

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[];cases=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 current=models(s);api=s/'mspi1-cqflags-unit-01';log=(api/'renode.log').read_text();check('API-red',"'cqInputLevels' with value '[NumericalValue: 0]'" in log and 'Constructor rejected' in log and 'BLACKWALL_CQFLAGS_UNIT ' not in log);red=s/'mspi1-cqflags-routing-red-01';green=s/'mspi1-cqflags-input3-unit-02';log=(red/'renode.log').read_text();check('routing-functional-red',"include @/work/setup.py" in log and 'disabled-route-always-zero' in log and 'BLACKWALL_CQFLAGS_UNIT ' not in log)
 for f in ['board.repl','setup.py','spin.bin','probe.resc','result.py']+[f'{k}-{n}.py' for n in range(len(PHASES)) for k in ['phase','advance']]:check('routing-red-green-same-'+f,(red/f).read_bytes()==(green/f).read_bytes())
 for name,levels,count in [('mspi1-cqflags-unit-03',0,33),('mspi1-cqflags-input1-unit-02',1,33),('mspi1-cqflags-input2-unit-02',2,33),('mspi1-cqflags-input3-unit-02',3,33),('mspi1-cqflags-unknown-unit-02',None,4)]:
  d=s/name;r=json.loads((d/'report.json').read_text());check(name+'-raw-result',r==marker((d/'renode.log').read_text(),'BLACKWALL_CQFLAGS_UNIT') and r['passed'] and r['count']==count);check(name+'-source',(d/'strict.cs').read_bytes()==current);check(name+'-board',(d/'board.repl').read_text()==unit_board((s/'mspi1-write-disable-main-01/stock24/board.repl').read_text(),levels));setup=COMMON+'INPUT_LEVELS='+str(0 if levels is None else levels)+'\n'+DRIVER+("blocked('unknown-handshake-no-full-read',flags)\n" if levels is None else ACTIVE);check(name+'-setup',(d/'setup.py').read_text()==setup)
  if levels is not None:
   for n,(us,code) in enumerate(PHASES):check(name+'-phase-'+str(n),(d/f'phase-{n}.py').read_text()==code and 'FromMicroseconds('+str(us)+')' in (d/f'advance-{n}.py').read_text())
 reg=s/'mspi1-cqflags-regressions-02';r=json.loads((reg/'report.json').read_text());check('regression56',r['passed'] and [x['count'] for x in r['cases']]==[33,23])
 for x,tag in zip(r['cases'],['BLACKWALL_MSPI1_CQ_INIT_UNIT','BLACKWALL_WRDI_UNIT']):
  d=reg/x['name'];v=marker((d/'renode.log').read_text(),tag);check(x['name']+'-regression',v['passed'] and v['count']==x['count'] and (d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==x['source_sha256'] and all(digest(d/n)==h for n,h in x['fixtures'].items()))
 parent=s/'mspi1-cqflags-main-02';pr=json.loads((parent/'report.json').read_text());check('main5',pr['passed'] and len(pr['cases'])==5);reports={}
 for name,key,levels in PLANS:
  d=parent/name;src=s/'mspi1-write-disable-main-01'/key;prior=json.loads((src/'report.json').read_text());r=json.loads((d/'report.json').read_text());reports[name]=r;log=(d/'renode.log').read_text();v=parse_log(log);check(name+'-raw-report',r['passed'] and v==r['observed']);check(name+'-model',(d/'strict.cs').read_bytes()==current);bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',raw==(d/'main.bin').read_bytes());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-assets',True);check(name+'-board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),levels));runtime,meta=instrument((src/'run.py').read_text(),raw,prior,key);check(name+'-read-only-observation',(d/'run.py').read_text()==runtime and r['observation']==meta);ob=marker(log,'BLACKWALL_OBSERVATION');flags=marker(log,'BLACKWALL_CQ_FLAGS');check(name+'-raw-markers',ob==r['selected_observation'] and flags==r['cq_flags']);check(name+'-scope',not r['CQ_execution_verified'] and not r['array_addressing_verified'] and not r['boot_verified'] and not r['hardware_validated'] and not r['installable']);check(name+'-events-no-loss',ob['sequence']==len(ob['events']) and ob['dropped_events']==0);old=prior['selected_observation'];check(name+'-original-prefix',ob['events'][:len(old['events'])]==old['events']);point=next(x for x in ob['points'] if x['label']=='CQFLAGS-saved');snap=point['snapshot'];g=[x for x in v['guards'] if x['accesses']]
  if levels is None:check(name+'-default-block-preserved',flags==dict(input_levels=-1,full_reads=0,last_value=0) and point['hits']==0 and snap is None and boundary_state(v)==boundary_state(prior['observed']))
  else:
   expected=0x4780 if levels==0 else 0x7480;check(name+'-original-full-word-stored',flags==dict(input_levels=levels,full_reads=1,last_value=expected) and point['hits']==1 and snap==dict(sequence=352,address=meta['snapshot'],words=[expected]) and ob['events'][-1]['label']=='CQFLAGS-saved' and ob['events'][-1]['address']==meta['hook'] and ob['sequence']==352);check(name+'-next-strict-power-write',len(g)==1 and g[0]['address']==0x40021004 and g[0]['operation']=='write' and g[0]['value']==0x400 and g[0]['width']==4)
  prev=s/'mspi1-cqflags-main-01'/name;previous=json.loads((prev/'report.json').read_text());check(name+'-routing-fix-preserved-observed-route7',boundary_state(v)==boundary_state(previous['observed']) and flags==previous['cq_flags'] and point['snapshot']==next(x for x in previous['selected_observation']['points'] if x['label']=='CQFLAGS-saved')['snapshot']);cases.append(dict(case=name,flags=flags,saved=snap,next_guard=g))
 zero=reports['stock24'];three=reports['stock24-input3'];check('counterfactual-diff-only-handshake-word',zero['cq_flags']['last_value']^three['cq_flags']['last_value']==0x3300 and boundary_state(zero['observed'])==boundary_state(three['observed']));check('counterfactual-runtime-identical',(parent/'stock24/run.py').read_bytes()==(parent/'stock24-input3/run.py').read_bytes())
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(parent/'stock23'/f).read_bytes()==(parent/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(parent/'stock23/run.py').read_text().replace('3758688','3829832')==(parent/'cfw/run.py').read_text());check('known-unknown-runtime-identical',(parent/'stock24/run.py').read_bytes()==(parent/'stock24-unknown/run.py').read_bytes())
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='routed mock flags and original retention word save; no live link, actual restore, CQ/DMA execution, full boot or display proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
