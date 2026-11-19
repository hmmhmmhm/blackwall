"""Audit the nominal clock engine, compiled public layout, and saved original ARM runs."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from stimer_engine_source import load_engine,SHA
from probe_stimer_clock_main import PLANS,MARKER,board_for
from verify_stimer_clock_counter import SETUP,PHASES
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output
 if o.exists():raise ValueError('Fresh output required')
 checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,name):
  found=[json.loads(x.split(name+' ',1)[1]) for x in log.splitlines() if x.startswith(name+' ')]
  check(name+'-unique-'+str(len(checks)),len(found)==1);return found[0]
 engine=load_engine(s).encode();addon=(ROOT/'tools/renode-stimer-clock-probe.cs').read_bytes();b=s/'stimer-clock-main-01';base=s/'stimer-interrupt-main-03';unit=s/'stimer-clock-unit-04'
 check('engine-current',(b/'engine.cs').read_bytes()==engine);check('addon-current',(b/'addon.cs').read_bytes()==addon);check('loader-current',(b/'loader.py').read_bytes()==(ROOT/'tools/stimer_engine_source.py').read_bytes());check('runner-current',(b/'runner.py').read_bytes()==(ROOT/'tools/probe_stimer_clock_main.py').read_bytes())
 pin=json.loads((s/'stimer-engine-research-01/source.json').read_text());data=(s/'stimer-engine-research-01/AmbiqApollo4_SystemTimer.cs').read_bytes();tree=json.loads((s/'rtc-module-research-01/renode-infrastructure-tree.json').read_text());check('engine-upstream-pin',hashlib.sha256(data).hexdigest()==pin['sha256']==SHA and pin['commit']==tree['sha'] and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==pin['git_blob']==next(x['sha'] for x in tree['tree'] if x['path']==pin['path']))
 license_pin=json.loads((s/'stimer-engine-research-01/license.json').read_text());license_bytes=(s/'stimer-engine-research-01/MIT.txt').read_bytes();check('mit-license-pin',hashlib.sha256(license_bytes).hexdigest()==license_pin['sha256'] and hashlib.sha1(b'blob '+str(len(license_bytes)).encode()+b'\0'+license_bytes).hexdigest()==license_pin['git_blob']==next(x['sha'] for x in tree['tree'] if x['path']=='licenses/MIT.txt'));check('license-preserved',(b/'MIT.txt').read_bytes()==(unit/'MIT.txt').read_bytes()==license_bytes)
 check('no-register-write-time-increment',b'systemTimer.Increment(' not in engine);check('full-32bit-period',engine.count(b'0x100000000UL,')==2)
 source=json.loads((s/'timer-source-research-01/sources.json').read_text())
 for f in source['files']:check(f['path']+'-public-sha',hashlib.sha256((s/'timer-source-research-01'/Path(f['path']).name).read_bytes()).hexdigest()==f['sha256'])
 header=(s/'timer-source-research-01/apollo510.h').read_text();end=header.index('} STIMER_Type;');start=header.rfind('typedef struct {',0,end);c='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+header[start:end]+'} STIMER_Type;\n'
 for reg,offset in [('STCFG',0),('STTMR',4),('SCMPR0',0x20),('SCMPR7',0x3c),('STMINTEN',0x100)]:c+='_Static_assert(offsetof(STIMER_Type,'+reg+')=='+str(offset)+',"'+reg+'");\n'
 for enum,value in [('NOCLK',0),('HFRC_6MHZ',1),('HFRC_375KHZ',2),('XTAL_32KHZ',3),('XTAL_16KHZ',4),('XTAL_1KHZ',5),('LFRC_NOMINAL',6)]:check(enum+'-clock-select',bool(re.search(r'STIMER_STCFG_CLKSEL_'+enum+r'\s*= '+str(value)+',',header)))
 o.mkdir(mode=0o700);(o/'layout.c').write_text(c);compiled=subprocess.run(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(o/'layout.c'),'-o',str(o/'layout.o')],capture_output=True,text=True,timeout=30);(o/'compiler.log').write_text(compiled.stdout+compiled.stderr);check('compiled-clock-counter-compare-offsets',compiled.returncode==0)
 r=json.loads((unit/'report.json').read_text());log=(unit/'renode.log').read_text();check('unit33-raw',r==marker(log,'BLACKWALL_STIMER_CLOCK_UNIT') and r['passed'] and r['count']==33 and 'Renode is quitting' in log);check('unit-current-setup',(unit/'setup.py').read_text()==SETUP)
 for n,(_,script) in enumerate(PHASES):check('unit-current-phase-'+str(n),(unit/f'phase-{n}.py').read_text()==script)
 check('unit-same-model',(unit/'strict.cs').read_bytes()==(b/'stock24/strict.cs').read_bytes())
 for name,key,enabled in PLANS:
  d=b/name;src=base/key;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-pinned-original',raw==(src/'main.bin').read_bytes()==(d/'main.bin').read_bytes());check(name+'-raw-report',r['observed']==v and r['image_id']==IMAGE and 'Renode is quitting' in log)
  check(name+'-only-engine-addon',(d/'strict.cs').read_bytes()==(src/'strict.cs').read_bytes()+b'\n'+engine+b'\n'+addon);check(name+'-board',(d/'board.repl').read_text()==board_for((src/'board.repl').read_text(),enabled));check(name+'-observation-only-runtime',(d/'run.py').read_text()==(src/'run.py').read_text().replace('except Exception as error:\n',MARKER+'except Exception as error:\n'))
  for file in ['result.py','probe.resc','sram-fill.bin','itcm-fill.bin']:check(name+'-unchanged-'+file,(d/file).read_bytes()==(src/file).read_bytes())
  check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable'] and not r['additional_hypotheses'][-1]['physical_clock']);clock=r['clock'];check(name+'-clock-marker',clock==marker(log,'BLACKWALL_STIMER_CLOCK'));guards=[g for g in v['guards'] if g['accesses']]
  if enabled:
   expected_counter=26 if key=='stock24' else 31;expected_pending=key!='stock24'
   check(name+'-nominal-prefix',clock==dict(enabled=True,config=0x103,counter=expected_counter,frequency=32768,enable=1,status=int(expected_pending),pending=expected_pending,reads=15,writes=4,irq=[expected_pending]+[False]*8))
   check(name+'-next-power-write',len(guards)==1 and guards[0]['operation']=='write' and guards[0]['address']==0x40021004 and guards[0]['value']==0x8400 and guards[0]['width']==4)
  else:check(name+'-old-storage-control',clock==dict(enabled=False) and boundary_state(v)==boundary_state(parse_log((src/'renode.log').read_text())))
 for file in FILES:
  if file!='board.repl':check('control-only-board-'+file,(b/'stock24'/file).read_bytes()==(b/'stock24-no-clock'/file).read_bytes())
 for file in ['board.repl','strict.cs','result.py','probe.resc']:check('stock23-cfw-'+file,(b/'stock23'/file).read_bytes()==(b/'cfw'/file).read_bytes())
 check('stock23-cfw-runtime',(b/'stock23/run.py').read_text().replace('3758688','3829832')==(b/'cfw/run.py').read_text())
 check('prior-core-unchanged',(base/'core.cs').read_bytes()==(ROOT/'tools/renode-strict-mmio.cs').read_bytes());check('prior-storage-unchanged',(base/'addon.cs').read_bytes()==(ROOT/'tools/renode-stimer-interrupt-probe.cs').read_bytes())
 (o/'verifier.py').write_bytes(Path(__file__).read_bytes());(o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,source_engine=pin,scope='saved nominal timer engine/unit33/original ARM4 and public offsets; no physical timing/all comparators/capture/main ISR/full boot proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
