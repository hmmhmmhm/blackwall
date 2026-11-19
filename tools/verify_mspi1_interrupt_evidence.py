"""Audit MSPI interrupt source, native original replay, and synthetic IRQ21 service artifacts."""
import argparse,hashlib,json,re
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_interrupts import models,board,DRIVER
from verify_mspi1_interrupt_cpu import SETUP,INJECT,REPORT,guest_bytes
from probe_mspi1_interrupts_main import PLANS,MARKER
from inspect_mspi1_config_contract import collect
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;m=s/'mspi1-interrupts-main-01';checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(d,tag):
  rows=[json.loads(z.split(tag+' ',1)[1]) for z in (d/'renode.log').read_text().splitlines() if z.startswith(tag+' ')]
  check(d.name+' marker-report',rows==[json.loads((d/'report.json').read_text())]);return rows[0]
 contract=json.loads((s/'mspi1-interrupts-contract-01/report.json').read_text());check('source-contract',contract['passed'] and contract['count']==30 and len(contract['cases'])==3)
 header,regs=collect(s);lookup={r['name']:r for r in regs}
 check('current-source-IRQ21',re.search(r'MSPI1_IRQn\s*=\s*21,',header) is not None)
 for name,offset in [('INTEN',0x200),('INTSTAT',0x204),('INTCLR',0x208),('INTSET',0x20c)]:
  r=lookup[name];check(name+' current-source',r['offset']==offset and r['reset']==0 and r['mask']==0x3fff)
 check('current-HAL-source',hashlib.sha256((s/'mspi1-source-research-01/am_hal_mspi.c').read_bytes()).hexdigest()=='5a91ab0c67bda4bd61c7d436b94b5a7c81693b948a331d282ae10e88cc5bf85f')
 unit=s/'mspi1-interrupts-unit-02';r=marker(unit,'BLACKWALL_MSPI1_INTERRUPTS_UNIT');check('unit-count',r['passed'] and r['count']==len(r['checks'])==73);check('unit-models',(unit/'strict.cs').read_bytes()==models(s));check('unit-driver',(unit/'test.py').read_text()==DRIVER)
 cpu=s/'mspi1-interrupts-cpu-01';r=marker(cpu,'BLACKWALL_MSPI1_INTERRUPT_CPU');check('synthetic-CPU-service',r['passed'] and r['count']==7 and r['pc']==0x10200)
 check('synthetic-models',(cpu/'strict.cs').read_bytes()==models(s));check('synthetic-guest',(cpu/'guest.bin').read_bytes()==guest_bytes());check('synthetic-host-code',(cpu/'setup.py').read_text()==SETUP and (cpu/'inject.py').read_text()==INJECT and (cpu/'report.py').read_text()==REPORT);check('synthetic-board',(cpu/'board.repl').read_text()==board((s/'mspi1-xip-guard-main-01/stock24/board.repl').read_text()))
 for name,key,enabled in PLANS:
  d=m/name;src=s/'mspi1-xip-guard-main-01'/key;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());prior=parse_log((src/'renode.log').read_text());check(name+' report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);checks.append(name+' hashes')
  check(name+' current-models',(d/'strict.cs').read_bytes()==models(s));check(name+' board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),enabled));check(name+' observation-only-runtime',(d/'run.py').read_text()==(src/'run.py').read_text().replace('except Exception as error:\n',MARKER+'except Exception as error:\n'))
  bundle='stock-2.4.0.24.bin' if key.startswith('stock24') else {'stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+' original-main',raw==(d/'main.bin').read_bytes())
  for f in ['result.py','probe.resc','sram-fill.bin','itcm-fill.bin']:check(name+' frozen '+f,(d/f).read_bytes()==(src/f).read_bytes())
  irq=r['interrupts'];check(name+' profile',irq['selected']==enabled)
  if not enabled or key=='stock24-stuck-off':
   check(name+' boundary-preserved',boundary_state(v)==boundary_state(prior))
   if enabled:check(name+' no-unpowered-event',irq['enable']==irq['status']==irq['reads']==irq['writes']==0 and not irq['level'])
  else:
   check(name+' original-IRQ-state',irq['enable']==0x1a80 and irq['status']==0 and irq['reads']==irq['writes']==2 and not irq['level'])
   guards=[g for g in v['guards'] if g['accesses']];check(name+' next-timer14-read',len(guards)==1 and guards[0]['address']==0x400083c0 and guards[0]['operation']=='read' and guards[0]['width']==4)
  check(name+' no-completion-claim',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'])
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock-cfw '+f,(m/'stock23'/f).read_bytes()==(m/'cfw'/f).read_bytes())
 check('stock-cfw-runtime',(m/'stock23/run.py').read_text().replace('3758688','3829832')==(m/'cfw/run.py').read_text())
 for dirname,tag,count in [('mspi1-interrupts-config-regression-01','BLACKWALL_MSPI1_CONFIG_UNIT',67),('mspi1-interrupts-cq-regression-01','BLACKWALL_MSPI1_CQ_INIT_UNIT',33),('mspi1-interrupts-xip-regression-01','BLACKWALL_MSPI1_XIP_UNIT',26)]:
  d=s/dirname;r=marker(d,tag);check(dirname+' count',r['passed'] and r['count']==count);check(dirname+' models',(d/'strict.cs').read_bytes()==models(s))
 a.output.mkdir(mode=0o700);(a.output/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='source/native interrupt setup and synthetic software IRQ21/ISR; no original ISR, transfer event, physical, boot or display proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
