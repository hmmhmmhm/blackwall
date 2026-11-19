"""Audit explicit status fixtures, preserved controls and original ARM idle/busy observations."""
import argparse,json,struct
from pathlib import Path
from native_replay import FILES,parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from verify_mspi1_status_byte import board as unit_board,phases
from probe_mspi1_status_main import PLANS,board,instrument
UNIT_CASES=[('mspi1-status-unit-02',64,False,False,22),('mspi1-status-busy-unit-01',65,False,False,22),('mspi1-status-zero-unit-01',0,False,False,22),('mspi1-status-ff-unit-01',255,False,False,22),('mspi1-status-unknown-unit-01',None,False,False,4),('mspi1-status-none-unit-01',64,True,False,4),('mspi1-status-stuck-unit-01',64,False,True,10)]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[];summaries=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 current=models(s);red=s/'mspi1-status-unit-01';green=s/'mspi1-status-unit-02';log=(red/'renode.log').read_text();check('red-missing-status-API',"'statusByte' with value '[NumericalValue: 64]'" in log and 'Constructor rejected' in log and 'BLACKWALL_STATUS_BYTE ' not in log)
 for f in ['board.repl','setup.py','probe.resc','spin.bin','result.py']+[f'{kind}-{n}.py' for n in range(len(phases(64))) for kind in ['phase','advance']]:check('red-green-same-'+f,(red/f).read_bytes()==(green/f).read_bytes())
 for name,status,none,stuck,count in UNIT_CASES:
  d=s/name;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();check(name+'-raw-result',r==marker(log,'BLACKWALL_STATUS_BYTE') and r['passed'] and r['count']==count);check(name+'-current-model',(d/'strict.cs').read_bytes()==current);b=unit_board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),status,not none)
  if stuck:b=b.replace('    completeTransactions: true\n','    completeTransactions: false\n')
  check(name+'-board',(d/'board.repl').read_text()==b)
  if status is not None and not none and not stuck:
   for n,(us,code) in enumerate(phases(status)):check(name+'-phase-'+str(n),(d/f'phase-{n}.py').read_text()==code and 'FromMicroseconds('+str(us)+')' in (d/f'advance-{n}.py').read_text())
 regressions=[('mspi1-status-regressions-01','mspi1-rdid-unit-02','BLACKWALL_MSPI1_RDID_UNIT',30),('mspi1-status-regressions-01','mspi1-zero-unit-02','BLACKWALL_ZERO_RDID',36),('mspi1-status-regressions-02','mspi1-pio-unit-05','BLACKWALL_MSPI1_PIO_UNIT',26)]
 for folder,name,tag,count in regressions:
  d=s/folder/name;r=json.loads((d/'report.json').read_text());v=marker((d/'renode.log').read_text(),tag);check(name+'-regression',r['passed'] and v['passed'] and r['count']==v['count']==count and (d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==r['source_sha256'] and all(digest(d/n)==h for n,h in r['fixtures'].items()))
 parent=s/'mspi1-status-main-01';remaining=s/'mspi1-status-main-02';parent_report=json.loads((remaining/'report.json').read_text());check('remaining-main-batch',parent_report['passed'] and len(parent_report['cases'])==2)
 for name,key,status in PLANS:
  d=(remaining if status!=64 else parent)/name;src=s/'mspi1-zero-main-01'/key;prior=json.loads((src/'report.json').read_text());r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);check(name+'-raw-report',r['passed'] and r['observed']==v);check(name+'-model',(d/'strict.cs').read_bytes()==current);bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',raw==(d/'main.bin').read_bytes());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-assets',True);check(name+'-board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),status));runtime,meta=instrument((src/'run.py').read_text(),raw,prior,key,status==65);check(name+'-read-only-observation-runtime',(d/'run.py').read_text()==runtime and r['observation']==meta);ob=marker(log,'BLACKWALL_OBSERVATION');st=marker(log,'BLACKWALL_NOR_STATUS');q=marker(log,'BLACKWALL_MSPI1_SAMPLING');check(name+'-raw-markers',ob==r['selected_observation'] and st==r['nor_status'] and q==r['sampling']);check(name+'-event-stream',ob['dropped_events']==0 and ob['sequence']==len(ob['events']) and ob['capacity']==4096);check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable']);points={x['label']:x for x in ob['points']};events=ob['events'];snapshots=[points['scan-matrix-'+str(n)]['snapshot'] for n in range(3)];check(name+'-source-scan-matrix',all(x['address']==prior['capture']['matrix']+64*n and len(x['words'])==[16,16,4][n] for n,x in enumerate(snapshots)) and [w for x in snapshots for w in x['words']]==prior['pass_masks']==[0xffffffff]*36);scan=[x for x in events if x['label']=='scan-return'];check(name+'-source-scan-return',len(scan)==1 and scan[0]['r0']==0 and q['id_frames']==1153);incoming=[x for x in events if x['label']=='status-byte'];results=[x for x in events if x['label']=='status-result'];poll=[x for x in events if x['label']=='status-poll-return'];n=st['reads_completed'];g=[x for x in v['guards'] if x['accesses']]
  if status is None:check(name+'-default-unknown',st['status_byte']==-1 and n==0 and not incoming and not results and not poll and boundary_state(v)==boundary_state(prior['observed']))
  else:
   check(name+'-explicit-status-byte',st['status_byte']==status and len(results)>0 and all(y['r0']==(status&1) for y in results) and (not incoming if status==65 else n==len(incoming)==len(results) and all(x['r0']==status and x['sequence']<y['sequence'] for x,y in zip(incoming,results))));snapshot=points['status-result' if status==65 else 'status-byte']['snapshot'];check(name+'-first-status-RAM-byte',snapshot['address']==meta['first_buffer'] and len(snapshot['words'])==1 and snapshot['words'][0]&255==status);check(name+'-frame-counters',q['starts']==q['completions']==1155+n and q['fifo_reads']==1153+n and not q['busy'] and q['pending']==0)
   if status&1:
    check(name+'-busy-not-success',n==2401 and len(results)==2400 and len(poll)==2 and all(x['r0']==1 for x in poll))
    check('busy-two-bounded-poll-intervals',[sum(lo<x['sequence']<hi and x['label']=='status-result' for x in events) for lo,hi in [(scan[0]['sequence'],poll[0]['sequence']),(poll[0]['sequence'],poll[1]['sequence'])]]==[1200,1200])
    old_log=(parent/name/'renode.log').read_text();old_ob=marker(old_log,'BLACKWALL_OBSERVATION');check('busy-old-overflow-preserved',old_ob['sequence']==5133 and old_ob['dropped_events']==1037 and ob['sequence']==2733);check('busy-model-and-boundary-unchanged',(parent/name/'strict.cs').read_bytes()==current and (parent/name/'board.repl').read_bytes()==(d/'board.repl').read_bytes() and boundary_state(parse_log(old_log))==boundary_state(v) and marker(old_log,'BLACKWALL_NOR_STATUS')==st and marker(old_log,'BLACKWALL_MSPI1_SAMPLING')==q)
    old_runtime,old_meta=instrument((src/'run.py').read_text(),raw,prior,key,False);check('busy-old-read-only-runtime',(parent/name/'run.py').read_text()==old_runtime)
   else:check(name+'-idle-original-success',n==1 and len(poll)==1 and poll[0]['r0']==0 and scan[0]['sequence']<incoming[0]['sequence']<results[0]['sequence']<poll[0]['sequence'] and len(g)==1 and g[0]['address']==0x40061000 and g[0]['value']==0xc1 and marker(log,'BLACKWALL_MSPI1_CONFIG')['registers']['12']==6)
  summaries.append(dict(case=name,status_byte=st['status_byte'],status_reads=n,poll_returns=[x['r0'] for x in poll],events=ob['sequence'],guard=g))
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(parent/'stock23-idle'/f).read_bytes()==(parent/'cfw-idle'/f).read_bytes())
 check('stock23-CFW-runtime',(parent/'stock23-idle/run.py').read_text().replace('3758688','3829832')==(parent/'cfw-idle/run.py').read_text());check('idle-busy-board-only-status-byte',(parent/'stock24-idle/board.repl').read_text().replace('    statusByte: 64\n','    statusByte: 65\n')==(remaining/'stock24-busy/board.repl').read_text())
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=summaries,scope='explicit immutable status fixtures and original ARM polling observations; no physical NOR status, dynamic WIP/WEL, NV writes, full boot or display proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
