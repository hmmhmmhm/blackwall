"""Audit reset-config fixtures and actual original indirect RDCR/4BYTE verification."""
import argparse,json,struct
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from verify_mspi1_address_mode import board as unit_board,phases
from probe_mspi1_address_mode_main import PLANS,board,instrument

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[];cases=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 current=models(s);red=s/'mspi1-address-mode-unit-01';green=s/'mspi1-address-mode-unit-02';log=(red/'renode.log').read_text();check('red-configuration-API-missing',"'configurationByte' with value '[NumericalValue: 0]'" in log and 'Constructor rejected' in log and 'BLACKWALL_ADDRESS_UNIT ' not in log)
 for f in ['board.repl','setup.py','probe.resc','spin.bin','result.py']+[f'{kind}-{n}.py' for n in range(len(phases(0))) for kind in ['phase','advance']]:check('red-green-same-'+f,(red/f).read_bytes()==(green/f).read_bytes())
 for name,seed,complete,count in [('mspi1-address-mode-unit-02',0,True,42),('mspi1-address-mode-tb-unit-01',8,True,42),('mspi1-address-mode-unknown-unit-01',None,True,5),('mspi1-address-mode-stuck-unit-01',0,False,14)]:
  d=s/name;r=json.loads((d/'report.json').read_text());check(name+'-raw-result',r==marker((d/'renode.log').read_text(),'BLACKWALL_ADDRESS_UNIT') and r['passed'] and r['count']==count);check(name+'-source',(d/'strict.cs').read_bytes()==current);check(name+'-board',(d/'board.repl').read_text()==unit_board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),seed,complete))
  if seed is not None and complete:
   for n,(us,code) in enumerate(phases(seed)):check(name+'-phase-'+str(n),(d/f'phase-{n}.py').read_text()==code and 'FromMicroseconds('+str(us)+')' in (d/f'advance-{n}.py').read_text())
 reg=s/'mspi1-address-mode-regressions-01';r=json.loads((reg/'report.json').read_text());check('regressions84',r['passed'] and [x['count'] for x in r['cases']]==[36,22,26])
 for x,tag in zip(r['cases'],['BLACKWALL_WREN_UNIT','BLACKWALL_STATUS_BYTE','BLACKWALL_MSPI1_PIO_UNIT']):
  d=reg/x['name'];v=marker((d/'renode.log').read_text(),tag);check(x['name']+'-regression',v['passed'] and v['count']==x['count'] and (d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==x['source_sha256'] and all(digest(d/n)==h for n,h in x['fixtures'].items()))
 parent=s/'mspi1-address-mode-main-01';r=json.loads((parent/'report.json').read_text());check('main4',r['passed'] and len(r['cases'])==4)
 for name,key,seed in PLANS:
  d=parent/name;src=s/'mspi1-write-enable-main-01'/key;prior=json.loads((src/'report.json').read_text());r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);check(name+'-raw-report',r['passed'] and r['observed']==v);check(name+'-model',(d/'strict.cs').read_bytes()==current);bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',raw==(d/'main.bin').read_bytes());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-assets',True);check(name+'-board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),seed));runtime,meta=instrument((src/'run.py').read_text(),raw,key);check(name+'-read-only-runtime',(d/'run.py').read_text()==runtime and r['observation']==meta);ob=marker(log,'BLACKWALL_OBSERVATION');address=marker(log,'BLACKWALL_NOR_ADDRESS');q=marker(log,'BLACKWALL_MSPI1_SAMPLING');latch=marker(log,'BLACKWALL_NOR_LATCH');status=marker(log,'BLACKWALL_NOR_STATUS');check(name+'-markers',ob==r['selected_observation'] and address==r['address_mode'] and q==r['sampling'] and latch==r['latch'] and status==r['nor_status']);check(name+'-scope',not r['array_addressing_verified'] and not r['boot_verified'] and not r['hardware_validated'] and not r['installable']);check(name+'-no-event-loss',ob['dropped_events']==0 and len(ob['events'])==ob['sequence']);old=prior['selected_observation'];events=ob['events'];check(name+'-original-prefix',events[:len(old['events'])]==old['events']);points={x['label']:x for x in ob['points']};op={x['label']:x for x in old['points']};check(name+'-scan-snapshots-preserved',all(points[n]['snapshot']==op[n]['snapshot'] for n in ['scan-matrix-0','scan-matrix-1','scan-matrix-2','scan-return']));cfg=marker(log,'BLACKWALL_MSPI1_CONFIG')['registers'];g=[x for x in v['guards'] if x['accesses']];tail=events[len(old['events']):]
  if seed is not None:
   check(name+'-EN4B-and-RDCR-complete',address==dict(seed=0,current=32,four_byte=True,EN4B_completed=1,RDCR_completed=1) and status['reads_completed']==2 and q['starts']==q['completions']==1160 and q['id_frames']==1153 and q['fifo_reads']==1156 and not q['busy'] and q['pending']==0);labels=['EN4B-caller-return','status-byte','status-result','status-poll-return','address-indirect-call','configuration-helper-entry','configuration-byte','configuration-result','address-check-caller'];check(name+'-native-verification-sequence',[x['label'] for x in tail]==labels and [x['r0'] for x in tail]==[0,0x42,0,0,meta['helper']|1,meta['helper']|1,0x20,1,1] and ob['sequence']==345);check(name+'-actual-indirect-target',all(points[n]['hits']==1 for n in meta['points']) and all(x['address']==meta['points'][x['label']] for x in tail if x['label'] in meta['points']));check(name+'-next-WRDI-still-strict',cfg['12']==4 and cfg['132']==0x3010061 and len(g)==1 and g[0]['address']==0x40061000 and g[0]['operation']=='write' and g[0]['value']==0xc1);st=v['stack_context'];b=struct.pack('<32I',*st['words']);off=v['register_context']['r1']-st['base'];check(name+'-next-command-only-descriptor',off==36 and b[off:off+24]==bytes.fromhex('000000000000010000000000010004000000000000000000'))
  else:check(name+'-unknown-preserves-boundary',address==dict(seed=-1,current=-1,four_byte=False,EN4B_completed=0,RDCR_completed=0) and not tail and cfg['12']==0xb7 and boundary_state(v)==boundary_state(prior['observed']))
  cases.append(dict(case=name,address_mode=address,actual_callback_target=hex(meta['helper']|1) if seed is not None else None,original_bit5_result=1 if seed is not None else None,next_command=cfg['12']))
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(parent/'stock23'/f).read_bytes()==(parent/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(parent/'stock23/run.py').read_text().replace('3758688','3829832')==(parent/'cfw/run.py').read_text());check('known-unknown-runtime-identical',(parent/'stock24/run.py').read_bytes()==(parent/'stock24-unknown/run.py').read_bytes())
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='reset config, actual original callback target and bit5 readback only; no 32bit array addressing, physical mode, NV writes, full boot or display proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
