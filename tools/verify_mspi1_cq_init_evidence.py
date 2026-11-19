"""Audit disabled CQ init metadata, original ARM assets and preserved execution boundaries."""
import argparse,hashlib,json
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from inspect_mspi1_config_contract import collect
from verify_mspi1_cq_init import models,board,DRIVER
from probe_mspi1_cq_init_main import PLANS,MARKER
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;m=s/'mspi1-cq-init-main-01';checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 _,regs=collect(s);lookup={r['name']:r for r in regs}
 for name,offset,mask in [('CQCFG',0x2a0,0x1f),('CQADDR',0x2a8,0xffffffff),('CQSTAT',0x2ac,0xf),('CQFLAGS',0x2b0,0xffff),('CQSETCLEAR',0x2b4,0xffffff),('CQPAUSE',0x2b8,0xffff),('CQCURIDX',0x2c0,0xff),('CQENDIDX',0x2c4,0xff)]:
  r=lookup[name];check(name+' source',r['offset']==offset and r['reset']==0 and r['mask']==mask)
 research=s/'mspi1-cq-research-01';manifest=json.loads((research/'sources.json').read_text());tree=json.loads((s/'timer-source-research-01/tree.json').read_text())['tree']
 check('cmdq-source-commit',manifest['commit']=='61b293a49db34030c545f99101f7ebf6a3050314')
 for f in manifest['files']:
  raw=(research/Path(f['path']).name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();check(f['path']+' pin',hashlib.sha256(raw).hexdigest()==f['sha256'] and blob==f['git_blob']==next(x['sha'] for x in tree if x['path']==f['path']))
 unit=s/'mspi1-cq-init-unit-02';check('unit-current-models',(unit/'strict.cs').read_bytes()==models(s));check('unit-current-driver',(unit/'test.py').read_text()==DRIVER)
 rows=[json.loads(x.split('BLACKWALL_MSPI1_CQ_INIT_UNIT ',1)[1]) for x in (unit/'renode.log').read_text().splitlines() if x.startswith('BLACKWALL_MSPI1_CQ_INIT_UNIT ')]
 check('unit-marker-report',rows==[json.loads((unit/'report.json').read_text())]);check('unit-count',rows[0]['passed'] and rows[0]['count']==len(rows[0]['checks'])==33)
 for name,key,enabled in PLANS:
  d=m/name;src=s/'mspi1-config-main-01'/key;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());prior=parse_log((src/'renode.log').read_text())
  check(name+' report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);checks.append(name+' hashes')
  check(name+' models',(d/'strict.cs').read_bytes()==models(s));check(name+' board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),enabled));check(name+' observation-only-runtime',(d/'run.py').read_text()==(src/'run.py').read_text().replace('except Exception as error:\n',MARKER+'except Exception as error:\n'))
  bundle='stock-2.4.0.24.bin' if key.startswith('stock24') else {'stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+' original-main',raw==(d/'main.bin').read_bytes())
  for f in ['result.py','probe.resc','sram-fill.bin','itcm-fill.bin']:check(name+' frozen '+f,(d/f).read_bytes()==(src/f).read_bytes())
  cq=r['cq'];check(name+' profile',cq['selected']==enabled)
  if not enabled or key=='stock24-stuck-off':check(name+' boundary-preserved',boundary_state(v)==boundary_state(prior) and cq['reads']==cq['writes']==0 and not any(cq['registers'].values()))
  else:
   q=cq['registers'];check(name+' queue-init',cq['reads']==1 and cq['writes']==6 and q['672']==2 and q['696']==0x4000 and q['704']==q['708']==0 and q['688']==0x80 and q['684']==0 and q['680']%4==0 and 0x20000000<=q['680']<0x20380000)
   guards=[g for g in v['guards'] if g['accesses']];check(name+' xip-enable-blocked',len(guards)==1 and guards[0]['address']==0x40061090 and guards[0]['operation']=='write' and guards[0]['value']==0x5ed)
  check(name+' no-completion-claim',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock-cfw '+f,(m/'stock23'/f).read_bytes()==(m/'cfw'/f).read_bytes())
 check('stock-cfw-runtime',(m/'stock23/run.py').read_text().replace('3758688','3829832')==(m/'cfw/run.py').read_text())
 a.output.mkdir(mode=0o700);(a.output/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='disabled queue init source and saved artifacts; no command fetch, XIP, bus, boot or display proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
