"""Audit anchored ARM scan analysis and observation-only replay with no event loss at selected points."""
import argparse,json,hashlib,struct,xml.etree.ElementTree as ET
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state,digest,FILES
from pinned_main import load_pinned_main
from inspect_mspi1_config_contract import collect
from probe_mspi1_sampling_context import metadata,instrument,selection_helper

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 collect(s);check('SVD-header-pins',True);per=next(x for x in ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot().findall('./peripherals/peripheral') if x.findtext('name')=='MSPI0');reg=next(x for x in per.findall('./registers/register') if x.findtext('name')=='DEV0CFG');fields={x.findtext('name'):x for x in reg.findall('./fields/field')}
 for n,pos in [('RXCAP0',22),('RXNEG0',23),('TXNEG0',24)]:check(n+'-bit',fields[n].findtext('bitRange')=='['+str(pos)+':'+str(pos)+']')
 root=s/'mspi1-source-research-01';raw=(root/'am_hal_mspi.c').read_bytes();pin=next(x for x in json.loads((root/'sources.json').read_text())['files'] if x['path'].endswith('/am_hal_mspi.c'));check('HAL-SHA',hashlib.sha256(raw).hexdigest()==pin['sha256']);check('HAL-blob',hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==pin['git_blob']);hal=raw.decode();part=hal[hal.index('case AM_HAL_MSPI_REQ_TIMING_SCAN_SET:'):hal.index('case AM_HAL_MSPI_REQ_TIMING_SCAN_GET:')]
 for n in ['TXNEG0','RXNEG0','RXCAP0','TXDQSDELAY0','RXDQSDELAY0','RXDQS0PDLYEXT0']:check('HAL-scan-'+n,n in part)
 expected_rows=[[1,rxneg,rxcap,coarse,1,32] for rxneg in [0,1] for rxcap in [0,1] for coarse in range(1,10)];table_bytes=bytes(x for row in expected_rows for x in row);table_hash=hashlib.sha256(table_bytes).hexdigest();root=s/'mspi1-sampling-context-01';selection_cases={}
 for key,bundle,delta in [('stock24','stock-2.4.0.24.bin',0),('stock23','stock-2.3.0.24.bin',0x4d18),('cfw','faceclaw-38-research-only.bin',0x4d18)]:
  d=root/key;src=s/'mspi1-rdid-main-01'/key;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-main-pins',raw==(d/'main.bin').read_bytes()==(src/'main.bin').read_bytes());check(key+'-report',r['passed'] and v==r['observed']);prior=parse_log((src/'renode.log').read_text());check(key+'-same-boundary',boundary_state(v)==boundary_state(prior));meta=metadata(raw,delta);check(key+'-anchored-metadata-classifier-units',meta==r['metadata']);selection_cases[key]=selection_helper(raw,delta);check(key+'-longest-run-source-and-units',selection_cases[key]==[dict(mask=0,result=0),dict(mask=0xffffffff,result=32),dict(mask=0x00ff0000,result=8)]);check(key+'-runtime-only-observation',(d/'run.py').read_text()==instrument((src/'run.py').read_text(),meta));check(key+'-other-inputs-identical',all((d/f).read_bytes()==(src/f).read_bytes() for f in FILES if f!='run.py'));validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(key+'-derived-hashes',True)
  ob=marker(log,'BLACKWALL_OBSERVATION');check(key+'-observation-report',ob==r['selected_observation']);check(key+'-selected-events-no-drop',ob['capacity']==4096 and ob['sequence']==len(ob['events'])==1165 and ob['dropped_events']==0);points={x['label']:x for x in ob['points']};words=[]
  for n in range(4):
   p=points['scan-table-'+str(n)];check(key+'-RAM-tile-'+str(n),p['hits']==1 and p['snapshot']['address']==meta['table']+64*n);words+=p['snapshot']['words']
  check(key+'-live-RAM-table',struct.pack('<54I',*words)==(d/'scan-table.bin').read_bytes()==table_bytes and r['table_rows']==expected_rows and r['table_sha256']==table_hash)
  incoming=[e for e in ob['events'] if e['label']=='classifier-input'];result=[e for e in ob['events'] if e['label']=='classifier-result'];fifo=[e for e in ob['events'] if e['label']=='rdid-fifo-return'];rxcap=[e['r2'] for e in ob['events'] if e['label']=='scan-rxcap-byte'];check(key+'-native-ID-order',len(incoming)==len(result)==len(fifo)==288 and all(x['r0']==0xc22539 and y['r0']==0 and z['sequence']<x['sequence']<y['sequence'] for x,y,z in zip(incoming,result,fifo)));check(key+'-coarse-prefix',rxcap==r['rxcap_raw_prefix']==[0]*9+[1]);check(key+'-first-ID-copy',points['rdid-fifo-return']['snapshot']['words']==[0x403925c2]);check(key+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
 # Table addresses differ across firmware revisions; contents and the two 2.3-based variants agree.
 a23=json.loads((root/'stock23/report.json').read_text());cfw=json.loads((root/'cfw/report.json').read_text());check('stock23-CFW-metadata',a23['metadata']==cfw['metadata']);check('all-tables-content-identical',len({json.loads((root/k/'report.json').read_text())['table_sha256'] for k in ['stock24','stock23','cfw']})==1)
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,table_sha256=table_hash,selection_helper_cases=selection_cases,scope='selected-point trace and original classifier, not physical timing window or complete instruction trace'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
