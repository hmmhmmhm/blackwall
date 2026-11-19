"""Audit named RDID model and original CPU three-byte copy, without device claims."""
import argparse,json,struct
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from verify_mspi1_rdid import board,COMMON,ACTIVE,PHASES

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(tag+' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 current=models(s)
 for name,count,identity,complete in [('mspi1-rdid-unit-02',30,'mx25u25643g',True),('mspi1-rdid-none-01',5,'none',True),('mspi1-rdid-stuck-01',19,'mx25u25643g',False)]:
  d=s/name;log=(d/'renode.log').read_text();r=json.loads((d/'report.json').read_text());check(name+'-result',r==marker(log,'BLACKWALL_MSPI1_RDID_UNIT') and r['passed'] and r['count']==count);check(name+'-source',(d/'strict.cs').read_bytes()==current);check(name+'-board',(d/'board.repl').read_text()==board((s/'mspi1-xip-mixed-main-01/stock24/board.repl').read_text(),identity,complete));setup=COMMON+("check('none-profile',q.IdentityProfile=='none')\nblocked('none-does-not-invent-ID',start)\n" if identity=='none' else ACTIVE);check(name+'-setup',(d/'setup.py').read_text()==setup);check(name+'-terminal','Renode is quitting' in log and 'There was an error' not in log)
  phases=[] if identity=='none' else PHASES if complete else [(1000,"check('stuck-no-RX',q.Busy and q.RxEntries==q.ReadIdTransfers==0)\n")]
  for n,(us,phase) in enumerate(phases):check(name+'-phase-'+str(n),(d/f'phase-{n}.py').read_text()==phase and 'FromMicroseconds('+str(us)+')' in (d/f'advance-{n}.py').read_text())
 root=s/'mspi1-rdid-main-01';contract=json.loads((s/'mspi1-rdid-contract-01/report.json').read_text())
 for name,key,pc in [('stock24','stock24',0x4e8a46),('stock23','stock23',0x4db672),('cfw','cfw',0x4db672),('stock24-no-identity','stock24',0x4e8a46)]:
  d=root/name;prior=s/'mspi1-xip-mixed-main-01'/key;log=(d/'renode.log').read_text();v=parse_log(log);r=json.loads((d/'report.json').read_text());identity='none' if name=='stock24-no-identity' else 'mx25u25643g';check(name+'-report',v==r['observed']);check(name+'-source',(d/'strict.cs').read_bytes()==current);check(name+'-board',(d/'board.repl').read_text()==board((prior/'board.repl').read_text(),identity));validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-assets',True)
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-main-bytes',raw==(d/'main.bin').read_bytes());q=marker(log,'BLACKWALL_MSPI1_RDID');check(name+'-marker',q==r['rdid'] and q['identity']==identity);check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable']);check(name+'-pc',v['pc']==pc);capture=next(x for x in contract['cases'] if x['case']==key);ob=marker(log,'BLACKWALL_OBSERVATION');point=next(x for x in ob['points'] if x['label']=='rdid-fifo-return')
  if identity=='none':
   check(name+'-default-boundary',boundary_state(v)==boundary_state(parse_log((prior/'renode.log').read_text())));check(name+'-no-invented-response',not q['selected'] and q['read_id_transfers']==q['fifo_reads']==q['rx_entries']==0 and q['starts']==2 and point['hits']==0 and point['snapshot'] is None)
  else:
   check(name+'-model-transfers',q['selected'] and q['starts']==q['completions']==290 and q['read_id_transfers']==q['fifo_reads']==288 and q['rx_entries']==q['aborted']==0 and q['control']==0x30442 and not q['busy']);snap=point['snapshot'];check(name+'-CPU-three-bytes-preserve-fourth',point['address']==capture['FIFO_return'] and point['hits']==288 and snap['address']==capture['buffer'] and snap['words']==[(capture['before_word']&0xff000000)|0x3925c2] and snap['sequence']==point['first_sequence']);check(name+'-bounded-observer-not-full-trace',ob['capacity']==128 and ob['dropped_events']==447 and ob['sequence']==575)
   cfg=marker(log,'BLACKWALL_MSPI1_CONFIG')['registers'];check(name+'-next-capture-setting',cfg['132']==0x3410861 and cfg['12']==0x9f and (cfg['132']^0x3010861)==(1<<22));g=[x for x in v['guards'] if x['accesses']];check(name+'-next-strict',len(g)==1 and g[0]['address']==0x40061000 and g[0]['value']==0x30441 and g[0]['operation']=='write');x=marker(log,'BLACKWALL_MSPI1_XIP');check(name+'-no-backing',not x['backing_data'] and x['guard_accesses']==0)
  # Observation is the only runtime addition to the frozen original execution.
  runtime=(prior/'run.py').read_text();start='    e.StartAll()\n';runtime=runtime.replace(start,"    observer.AddPoint('rdid-fifo-return',"+str(capture['FIFO_return'])+")\n    observer.CaptureSram(m,'rdid-fifo-return',"+str(capture['buffer'])+",1)\n"+start)
  from probe_mspi1_rdid_main import MARKER
  runtime=runtime.replace('except Exception as error:\n',MARKER+'except Exception as error:\n');check(name+'-observer-only-runtime',(d/'run.py').read_text()==runtime)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(root/'stock23'/f).read_bytes()==(root/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(root/'stock23/run.py').read_text().replace('3758688','3829832')==(root/'cfw/run.py').read_text())
 reg=s/'mspi1-rdid-regressions-01';r=json.loads((reg/'report.json').read_text());check('regression89',r['passed'] and sum(x['count'] for x in r['cases'])==89)
 for x,tag in zip(r['cases'],['BLACKWALL_MSPI1_PIO_UNIT','BLACKWALL_MSPI1_XIP_MIXED_UNIT']):
  d=reg/x['name'];v=marker((d/'renode.log').read_text(),tag);check(x['name']+'-result',v['passed'] and v['count']==x['count']);check(x['name']+'-source',(d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==x['source_sha256']);check(x['name']+'-fixtures',all(digest(d/n)==h for n,h in x['fixtures'].items()))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='explicit model and first CPU copy; trace bounded, actual chip, signal margin, boot/display and flash backing unverified'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
