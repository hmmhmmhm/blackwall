"""Audit WRDI functional red/green, fixture address repair and original continuation."""
import argparse,json,struct,hashlib
from pathlib import Path
from pypdf import PdfReader
from native_replay import parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from verify_mspi1_write_disable import board as unit_board,phases,validate_fixture_addresses
from probe_mspi1_write_disable_main import PLANS,board,instrument

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[];cases=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 current=models(s);pdf=s/'mspi1-pio-research-01/mx25u25643g-v1.1.pdf';pin=json.loads((pdf.parent/'datasheet-source.json').read_text());check('manufacturer-pin',hashlib.sha256(pdf.read_bytes()).hexdigest()==pin['sha256']);text=' '.join(PdfReader(pdf).pages[24].extract_text().split());check('manufacturer-WRDI-completed-clears-WEL','04h' in text and 'WRDI command completion' in text and 'instruction is to reset Write Enable Latch (WEL) bit' in text)
 red=s/'mspi1-write-disable-unit-01';green=s/'mspi1-write-disable-unit-02';log=(red/'renode.log').read_text();check('functional-red-WRDI-refused',"include @/work/phase-1.py" in log and 'BLACKWALL unsupported write at 0x40061000, width 4' in log and 'BLACKWALL_WRDI_UNIT ' not in log)
 for f in ['board.repl','setup.py','probe.resc','spin.bin','result.py']+[f'{kind}-{n}.py' for n in range(len(phases())) for kind in ['phase','advance']]:check('red-green-same-'+f,(red/f).read_bytes()==(green/f).read_bytes())
 for name,seed,enabled,complete,count in [('mspi1-write-disable-unit-02',64,True,True,23),('mspi1-write-disable-nv-unit-02',252,True,True,23),('mspi1-write-disable-disabled-unit-01',64,False,True,4),('mspi1-write-disable-stuck-unit-01',64,True,False,4)]:
  d=s/name;r=json.loads((d/'report.json').read_text());check(name+'-raw-result',r==marker((d/'renode.log').read_text(),'BLACKWALL_WRDI_UNIT') and r['passed'] and r['count']==count);check(name+'-model',(d/'strict.cs').read_bytes()==current);check(name+'-board',(d/'board.repl').read_text()==unit_board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),enabled,complete,seed));steps=[(0,(d/'setup.py').read_text())]
  if enabled and complete:
   for n,(us,code) in enumerate(phases(seed)):check(name+'-phase-'+str(n),(d/f'phase-{n}.py').read_text()==code and 'FromMicroseconds('+str(us)+')' in (d/f'advance-{n}.py').read_text());steps.append((us,code))
  check(name+'-approved-literal-MMIO',validate_fixture_addresses(steps)>0)
 bad=s/'mspi1-write-disable-nv-unit-01';bad_steps=[(0,p.read_text()) for p in sorted(bad.glob('phase-*.py'))]
 try:validate_fixture_addresses(bad_steps)
 except ValueError as e:check('bad-NV-fixture-preflight-rejects',str(e).startswith('Unapproved fixture MMIO address 0xfc0610'))
 else:raise ValueError('Bad NV fixture accepted')
 check('bad-NV-run-preserved','non existing peripheral at 0xFC061014' in (bad/'renode.log').read_text() and not (bad/'report.json').exists());guard=json.loads((s/'mspi1-wrdi-fixture-addresses-02/report.json').read_text());check('positive-and-negative-address-preflight',guard['passed'] and guard['valid_address_counts']=={str(seed):validate_fixture_addresses(phases(seed)) for seed in [64,252]})
 reg=s/'mspi1-write-disable-regressions-01';r=json.loads((reg/'report.json').read_text());check('regressions90',r['passed'] and [x['count'] for x in r['cases']]==[42,22,26])
 for x,tag in zip(r['cases'],['BLACKWALL_ADDRESS_UNIT','BLACKWALL_STATUS_BYTE','BLACKWALL_MSPI1_PIO_UNIT']):
  d=reg/x['name'];v=marker((d/'renode.log').read_text(),tag);check(x['name']+'-regression',v['passed'] and v['count']==x['count'] and (d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==x['source_sha256'] and all(digest(d/n)==h for n,h in x['fixtures'].items()))
 parent=s/'mspi1-write-disable-main-01';r=json.loads((parent/'report.json').read_text());check('main4',r['passed'] and len(r['cases'])==4)
 for name,key,enabled in PLANS:
  d=parent/name;src=s/'mspi1-address-mode-main-01'/key;prior=json.loads((src/'report.json').read_text());r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);check(name+'-raw-report',r['passed'] and r['observed']==v);check(name+'-model',(d/'strict.cs').read_bytes()==current);bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',raw==(d/'main.bin').read_bytes());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-assets',True);check(name+'-board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),enabled));runtime,meta=instrument((src/'run.py').read_text(),raw,key);check(name+'-read-only-runtime',(d/'run.py').read_text()==runtime and r['observation']==meta);ob=marker(log,'BLACKWALL_OBSERVATION');wrdi=marker(log,'BLACKWALL_NOR_WRDI');q=marker(log,'BLACKWALL_MSPI1_SAMPLING');address=marker(log,'BLACKWALL_NOR_ADDRESS');status=marker(log,'BLACKWALL_NOR_STATUS');check(name+'-raw-markers',ob==r['selected_observation'] and wrdi==r['wrdi'] and q==r['sampling'] and address==r['address_mode'] and status==r['nor_status']);check(name+'-scope',not r['wrapper_checks_WEL'] and not r['array_addressing_verified'] and not r['boot_verified'] and not r['hardware_validated'] and not r['installable']);check(name+'-event-stream',ob['dropped_events']==0 and ob['sequence']==len(ob['events']));events=ob['events'];g=[x for x in v['guards'] if x['accesses']]
  if enabled:
   old=prior['selected_observation'];check(name+'-original-prefix',events[:len(old['events'])]==old['events']);tail=events[len(old['events']):];check(name+'-original-wrapper-parent-and-next-read',[x['label'] for x in tail]==['WRDI-wrapper-return','WRDI-caller-return','address-mode-parent-return','status-byte','status-result','status-poll-return'] and [x['r0'] for x in tail]==[0,0,0,0x40,0,0] and ob['sequence']==351);check(name+'-WRDI-and-mode-preservation',wrdi==dict(completed=1,wel=False,current_status=64,current_configuration=32) and address['four_byte'] and address['RDCR_completed']==address['EN4B_completed']==1 and status['reads_completed']==4 and q['starts']==q['completions']==1163 and q['id_frames']==1153 and q['fifo_reads']==1158 and not q['busy'] and q['pending']==0);check(name+'-new-strict-register-read',len(g)==1 and g[0]['operation']=='read' and g[0]['address']==0x400612b0 and g[0]['width']==4)
  else:
   old=json.loads((s/'mspi1-write-enable-main-01/stock24-disabled/report.json').read_text());check(name+'-disabled-latch-default',wrdi['completed']==0 and not wrdi['wel'] and boundary_state(v)==boundary_state(old['observed']) and events==old['selected_observation']['events'])
  cases.append(dict(case=name,wrdi=wrdi,next_guard=g,events=ob['sequence']))
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(parent/'stock23'/f).read_bytes()==(parent/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(parent/'stock23/run.py').read_text().replace('3758688','3829832')==(parent/'cfw/run.py').read_text());check('enabled-disabled-runtime-identical',(parent/'stock24/run.py').read_bytes()==(parent/'stock24-disabled/run.py').read_bytes())
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='opt-in WRDI completion and original continuation; no full boot, array/NV writes or physical state proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
