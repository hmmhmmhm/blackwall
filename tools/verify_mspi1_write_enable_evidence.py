"""Audit opt-in WEL transitions, default regressions and original command-only continuation."""
import argparse,json,struct
from pathlib import Path
from native_replay import FILES,parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from verify_mspi1_write_enable import board as unit_board,phases
from probe_mspi1_write_enable_main import PLANS,board,instrument

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[];cases=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 current=models(s);red=s/'mspi1-write-enable-unit-01';log=(red/'renode.log').read_text();check('red-latch-API-not-supported',"'emulateWriteEnableLatch' with value '[BoolValue: True]'" in log and 'Constructor rejected' in log and 'BLACKWALL_WREN_UNIT ' not in log);bad=s/'mspi1-write-enable-unit-02';check('unit02-dynamic-import-failure-preserved','Cannot import name BlackwallMspi1PioReset' in (bad/'renode.log').read_text())
 for name,seed,enabled,complete,count in [('mspi1-write-enable-unit-03',64,True,True,36),('mspi1-write-enable-nv-unit-01',252,True,True,36),('mspi1-write-enable-disabled-unit-01',64,False,True,4),('mspi1-write-enable-stuck-unit-01',64,True,False,14)]:
  d=s/name;r=json.loads((d/'report.json').read_text());check(name+'-raw-result',r==marker((d/'renode.log').read_text(),'BLACKWALL_WREN_UNIT') and r['passed'] and r['count']==count);check(name+'-model',(d/'strict.cs').read_bytes()==current);check(name+'-board',(d/'board.repl').read_text()==unit_board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),seed,enabled,complete))
  if enabled and complete:
   for n,(us,code) in enumerate(phases(seed)):check(name+'-phase-'+str(n),(d/f'phase-{n}.py').read_text()==code and 'FromMicroseconds('+str(us)+')' in (d/f'advance-{n}.py').read_text())
 green=s/'mspi1-write-enable-unit-03'
 for f in ['board.repl','probe.resc','spin.bin','result.py']+[f'{kind}-{n}.py' for n in range(len(phases(64))) for kind in ['phase','advance']]:check('red-green-same-'+f,(red/f).read_bytes()==(green/f).read_bytes())
 check('red-green-harness-import-fix-only',(red/'setup.py').read_text().replace('from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMspi1PioReset\n','Ctor=type(q)\n').replace("try:BlackwallMspi1PioReset(m,'idle-nor-reset'","try:Ctor(m,'idle-nor-reset'")==(green/'setup.py').read_text())
 reg=s/'mspi1-write-enable-regressions-01';r=json.loads((reg/'report.json').read_text());check('regressions70',r['passed'] and [x['count'] for x in r['cases']]==[22,22,26])
 for x,tag in zip(r['cases'],['BLACKWALL_STATUS_BYTE','BLACKWALL_STATUS_BYTE','BLACKWALL_MSPI1_PIO_UNIT']):
  d=reg/x['name'];v=marker((d/'renode.log').read_text(),tag);check(x['name']+'-regression',v['passed'] and v['count']==x['count'] and (d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==x['source_sha256'] and all(digest(d/n)==h for n,h in x['fixtures'].items()))
 parent=s/'mspi1-write-enable-main-01';pr=json.loads((parent/'report.json').read_text());check('main-batch4',pr['passed'] and len(pr['cases'])==4)
 for name,key,enabled in PLANS:
  d=parent/name;src=s/'mspi1-status-main-01'/(key+'-idle');prior=json.loads((src/'report.json').read_text());r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);check(name+'-raw-report',r['passed'] and v==r['observed']);check(name+'-model',(d/'strict.cs').read_bytes()==current);bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',raw==(d/'main.bin').read_bytes());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-assets',True);check(name+'-board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),enabled));runtime,meta=instrument((src/'run.py').read_text(),raw,key);check(name+'-read-only-runtime',(d/'run.py').read_text()==runtime and meta==r['observation']);ob=marker(log,'BLACKWALL_OBSERVATION');latch=marker(log,'BLACKWALL_NOR_LATCH');q=marker(log,'BLACKWALL_MSPI1_SAMPLING');status=marker(log,'BLACKWALL_NOR_STATUS');check(name+'-markers',ob==r['selected_observation'] and latch==r['latch'] and q==r['sampling'] and status==r['nor_status']);check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'] and not r['WEL_read_after_WREN_observed']);check(name+'-event-stream',ob['dropped_events']==0 and len(ob['events'])==ob['sequence']);events=ob['events'];old=prior['selected_observation'];check(name+'-original-idle-prefix',events[:len(old['events'])]==old['events']);points={x['label']:x for x in ob['points']};old_points={x['label']:x for x in old['points']};check(name+'-original-scan-output',all(points[label]['snapshot']==old_points[label]['snapshot'] for label in ['scan-matrix-0','scan-matrix-1','scan-matrix-2','scan-return']));g=[x for x in v['guards'] if x['accesses']];cfg=marker(log,'BLACKWALL_MSPI1_CONFIG')['registers'];wr=[x for x in events if x['label']=='wren-wrapper-return'];cr=[x for x in events if x['label']=='wren-caller-return']
  if enabled:
   check(name+'-completed-WREN-and-model-latch',latch==dict(enabled=True,seed=64,current=66,wel=True,WREN_completed=1) and status['reads_completed']==1 and q['starts']==q['completions']==1157 and q['id_frames']==1153 and q['fifo_reads']==1154 and q['pending']==0 and not q['busy']);check(name+'-original-transfer-and-caller-return',len(wr)==len(cr)==1 and wr[0]['r0']==cr[0]['r0']==0 and wr[0]['address']==meta['return_point'] and cr[0]['address']==meta['caller_return'] and wr[0]['sequence']<cr[0]['sequence'] and ob['sequence']==336);check(name+'-next-B7-still-strict',len(g)==1 and g[0]['operation']=='write' and g[0]['address']==0x40061000 and g[0]['value']==0xc1 and cfg['12']==0xb7 and cfg['132']==0x3010061);st=v['stack_context'];b=struct.pack('<32I',*st['words']);off=v['register_context']['r1']-st['base'];check(name+'-B7-command-only-descriptor',off==36 and b[off:off+24]==bytes.fromhex('0000000000000100000000000100b7000000000000000000'))
  else:check(name+'-default-boundary-preserved',latch==dict(enabled=False,seed=64,current=64,wel=False,WREN_completed=0) and not wr and not cr and cfg['12']==6 and boundary_state(v)==boundary_state(prior['observed']))
  cases.append(dict(case=name,latch=latch,next_instruction=cfg['12'],observed_original_WEL_readback=False))
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(parent/'stock23'/f).read_bytes()==(parent/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(parent/'stock23/run.py').read_text().replace('3758688','3829832')==(parent/'cfw/run.py').read_text());check('enabled-disabled-runtime-identical',(parent/'stock24/run.py').read_bytes()==(parent/'stock24-disabled/run.py').read_bytes())
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='optional idle WEL model and original WREN completion/B7 request; no original WEL readback, program/erase, NV state, full boot or display proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
