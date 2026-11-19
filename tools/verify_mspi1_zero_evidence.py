"""Audit zero-turnaround red/green units and unmodified ARM main continuation from saved logs."""
import argparse,json,struct
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state,digest,FILES
from verify_mspi1_pio_reset import models
from verify_mspi1_zero_turnaround import SETUP,phases
from verify_mspi1_sampling_profile import board
from probe_mspi1_sampling_main import observation
from pinned_main import load_pinned_main

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 def marker(log,tag):
  rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(rows)!=1:raise ValueError(tag)
  return rows[0]
 current=models(s);red=s/'mspi1-zero-unit-01';green=s/'mspi1-zero-unit-02';old=b'            bool captureSupported=configuration==0x3010861 || (SamplingProfile=="ideal-sdr" && (configuration&~0x1c00000u)==0x2010861u);';new=b'            uint normalizedCapture=configuration&~0x1c00000u;\n            bool captureSupported=configuration==0x3010861 || (SamplingProfile=="ideal-sdr" && (normalizedCapture==0x2010861u || normalizedCapture==0x2010061u));';frozen=(red/'strict.cs').read_bytes();check('model-delta-only-zero-turnaround',frozen.count(old)==1 and frozen.replace(old,new)==current);log=(red/'renode.log').read_text();check('red-original-unsupported-start',"include @/work/setup.py" in log and 'BLACKWALL unsupported write at 0x40061000, width 4' in log and 'BLACKWALL_ZERO_RDID ' not in log)
 for f in ['board.repl','setup.py','probe.resc','spin.bin','result.py']+[f'{kind}-{n}.py' for n in range(len(phases())) for kind in ['phase','advance']]:check('red-green-same-'+f,(red/f).read_bytes()==(green/f).read_bytes())
 positive="start()\ncheck('zero-start-pending',q.Busy and q.RxEntries==0)\nblocked('zero-read-before-complete',lambda:b.ReadDoubleWord(0x40061014))\n"
 for name,count,fixed,none in [('mspi1-zero-unit-02',36,False,False),('mspi1-zero-fixed-01',4,True,False),('mspi1-zero-none-01',4,False,True)]:
  d=s/name;r=json.loads((d/'report.json').read_text());check(name+'-raw-result',r==marker((d/'renode.log').read_text(),'BLACKWALL_ZERO_RDID') and r['passed'] and r['count']==count);check(name+'-current-model',(d/'strict.cs').read_bytes()==current);b=board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),not fixed)
  if none:b=b.replace('    identityProfile: "mx25u25643g"\n','    identityProfile: "none"\n')
  check(name+'-board',(d/'board.repl').read_text()==b);check(name+'-setup',(d/'setup.py').read_text()==SETUP+("blocked('zero-without-profile-or-identity',start)\n" if fixed or none else positive))
  if not fixed and not none:
   for n,(us,code) in enumerate(phases()):check('zero-phase-fixture-'+str(n),(d/f'phase-{n}.py').read_text()==code and 'FromMicroseconds('+str(us)+')' in (d/f'advance-{n}.py').read_text())
 reg=s/'mspi1-zero-regressions-01';r=json.loads((reg/'report.json').read_text());check('regressions114',r['passed'] and [x['count'] for x in r['cases']]==[51,33,30])
 for x,tag in zip(r['cases'],['BLACKWALL_MSPI1_SAMPLING_UNIT','BLACKWALL_MSPI1_SAMPLING_UNIT','BLACKWALL_MSPI1_RDID_UNIT']):
  d=reg/x['name'];v=marker((d/'renode.log').read_text(),tag);check(x['name']+'-regression',v['passed'] and v['count']==x['count'] and (d/'strict.cs').read_bytes()==current and digest(d/'strict.cs')==x['source_sha256'] and all(digest(d/n)==h for n,h in x['fixtures'].items()))
 parent=s/'mspi1-zero-main-01';cases=[]
 for name,key,bundle,ideal in [('stock24','stock24','stock-2.4.0.24.bin',True),('stock23','stock23','stock-2.3.0.24.bin',True),('cfw','cfw','faceclaw-38-research-only.bin',True),('stock24-fixed','stock24','stock-2.4.0.24.bin',False)]:
  d=parent/name;src=s/'mspi1-sampling-context-01'/key;base=json.loads((src/'report.json').read_text());r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);check(name+'-raw-report',r['passed'] and v==r['observed']);check(name+'-current-model',(d/'strict.cs').read_bytes()==current);_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',raw==(d/'main.bin').read_bytes());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-assets',True);check(name+'-board',(d/'board.repl').read_text()==board((src/'board.repl').read_text(),ideal));run,capture=observation((src/'run.py').read_text(),raw,base['metadata'],base['selected_observation']);check(name+'-read-only-runtime',(d/'run.py').read_text()==run and r['capture']==capture);q=marker(log,'BLACKWALL_MSPI1_SAMPLING');ob=marker(log,'BLACKWALL_OBSERVATION');check(name+'-markers',q==r['sampling'] and ob==r['selected_observation']);check(name+'-no-loss',ob['dropped_events']==0 and len(ob['events'])==ob['sequence']);check(name+'-scope',not r['boot_verified'] and not r['hardware_validated'] and not r['installable']);points={x['label']:x for x in ob['points']}
  if ideal:
   check(name+'-1153-RDID-complete',q['profile']=='ideal-sdr' and q['id_frames']==q['fifo_reads']==1153 and q['starts']==q['completions']==1155 and not q['busy'] and q['pending']==0 and q['completed_mask']==0xf0)
   snapshots=[points['scan-matrix-'+str(n)]['snapshot'] for n in range(3)];check(name+'-original-scan-matrix',all(x['address']==capture['matrix']+64*n and len(x['words'])==[16,16,4][n] for n,x in enumerate(snapshots)) and [w for x in snapshots for w in x['words']]==r['pass_masks']==[0xffffffff]*36)
   ret=points['scan-return'];check(name+'-original-selection',ret['hits']==1 and ret['snapshot']['address']==capture['output'] and struct.pack('<2I',*ret['snapshot']['words'])[:6].hex()==r['selection']=='010000010e20');events=ob['events'];scan=[x for x in events if x['label']=='scan-return'];post=[x for x in events if x['sequence']>scan[0]['sequence']];check(name+'-post-scan-native-ID',scan[0]['r0']==0 and ob['sequence']==3790 and [x['label'] for x in post]==['rdid-fifo-return','classifier-input','classifier-result'] and post[0]['r0']==0 and post[1]['r0']==0xc22539 and post[2]['r0']==0)
   cfg=marker(log,'BLACKWALL_MSPI1_CONFIG')['registers'];g=[x for x in v['guards'] if x['accesses']];check(name+'-next-status-read-strict',cfg['132']==0x3010061 and cfg['12']==5 and len(g)==1 and g[0]['address']==0x40061000 and g[0]['value']==0x10441 and g[0]['operation']=='write');st=v['stack_context'];b=struct.pack('<32I',*st['words']);off=v['register_context']['r1']-st['base'];check(name+'-status-descriptor',off==36 and struct.unpack_from('<I',b,off)[0]==1 and b[off+6]==0 and b[off+12]==1 and struct.unpack_from('<H',b,off+14)[0]==5 and b[off+16]==1);cases.append(dict(case=name,id_frames=q['id_frames'],next_command=5,next_bytes=1))
  else:check(name+'-fixed-boundary-unchanged',boundary_state(v)==boundary_state(base['observed']) and q['id_frames']==288 and q['profile']=='fixed-capture' and points['scan-return']['hits']==0)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:check('stock23-CFW-'+f,(parent/'stock23'/f).read_bytes()==(parent/'cfw'/f).read_bytes())
 check('stock23-CFW-runtime',(parent/'stock23/run.py').read_text().replace('3758688','3829832')==(parent/'cfw/run.py').read_text())
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='original post-scan RDID continuation in explicit digital model; no full boot, display, physical identity or recovery proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
