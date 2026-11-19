"""Audit frozen B0 power models and the original reset-to-worker/main witness."""
import argparse,ast,hashlib,json,shutil,struct
from pathlib import Path
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(out):
 out=Path(out).resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private audit required')
 sim=PRIVATE/'simulator';old=sim/'upstream23-b0-pcm07-native-bw575-01';checks={}
 helper=Path(__file__).parent/'model-binding-source.py'
 if not helper.exists():helper=Path(__file__).parent/'verify_b0_ton_profile.py'
 helper_text=helper.read_text();tree=ast.parse(helper_text);functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name.startswith('bind_b0_')];ns={};exec(compile(ast.Module(body=functions,type_ignores=[]),'frozen-binding','exec'),ns)
 prior=(old/'strict.cs').read_text();expected=ns['bind_b0_ton'](prior)
 checks['binder_idempotent']=ns['bind_b0_ton'](expected)==expected
 native=[]
 for n,pc in ((1,0x41c7e8),(2,0x42f74a),(3,None)):
  d=sim/f'upstream23-b0-ton-native-bw576-0{n}';m=read(d/'manifest.json');r=read(d/'report.json');native.append(r)
  checks[f'native{n}_pins']=m['boot_sha256']=='7010d103d02a49333362ec185fb04c9657626f97cec5240063375d1c52e55a7e' and m['main_sha256']=='69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c' and r['images_unchanged']
  checks[f'native{n}_components']=all(sha(d/name)==h for name,h in m['components'].items())
  checks[f'native{n}_synthetic_only']=m['synthetic_chip_revision']==0x21 and m['synthetic_trim']==1 and m['b0_ton_configuration'] and not m['hardware_accessed'] and not m['physical_chip_revision_observed'] and not m['physical_trim_observed']
  checks[f'native{n}_no_fault']=r['cfsr']==r['hfsr']==r['policy']==r['system_control_violations']==r['events_dropped']==0
  checks[f'native{n}_removed']=read(d/'native.process.json')['status']=='removed' and len(r['cleanup'])==4 and all(not (d/row['path']).exists() for row in r['cleanup'])
  checks[f'native{n}_board_delta']=(d/'board.repl').read_text()==(old/'board.repl').read_text().replace('    halStorage: true\n','    halStorage: true\n    b0TonConfiguration: true\n')
  rows={x['address']:x for x in r['b0_ton_registers']}
  checks[f'native{n}_ton_writes']={a:x['writes'] for a,x in rows.items()}=={0x40020340:1,0x40020344:2,0x4002034c:2,0x40020354:1,0x40020358:1} and rows[0x40020340]['value']==0x80400000 and all(x['value']==0 for a,x in rows.items() if a!=0x40020340)
  if pc is not None:checks[f'native{n}_bounded_frontier']=r['pc']==pc and not r['scope']['worker_entered']
  if n==3:
   checks['final_bound_model_exact']=(d/'strict.cs').read_text()==expected
   runtime=(d/'run.py').read_text();clean='\n'.join(line for line in runtime.split('\n') if not line.startswith("result['b0_ton_registers']=") and not line.startswith("result['b0_power_state']="));checks['runtime_only_post_stop_exports']=clean==(old/'run.py').read_text()
 r=native[-1];points={p['label']:p for p in r['points']};order=['boot-reset','boot-manager','storage-wrapper','patched-manager','power-slots-before-manager','patched-worker','marker-load','stock-handoff','main-reset']
 checks['original_order']=all(points[x]['hits']==1 for x in order) and [points[x]['first'] for x in order]==list(range(1,10))
 checks['natural_callback_slots_zero']=next(x['words'] for x in r['snapshots'] if x['label']=='power-slots-before-manager')==[0,0]
 checks['complete_power_init']=r['b0_power_state']==dict(override_steps=10,mem_steps=2,override_complete=True,core_reduced=974,buck_steps=3,core_applied=True)
 checks['worker_main_without_auth']=r['scope']==dict(worker_entered=True,main_entered=True,authentication_verified=False,recovery_verified=False,hardware_accessed=False) and r['classification']=='main-entered' and not any(x['accesses'] for x in r['guards'])
 frame=bytes(r['uart2_tx']);body=bytes((0,1,3,12))+b'HELO'+struct.pack('<II',2,0x32524c45);checks['hello_wire_format']=frame==b'\x5a\xa5\xff'+bytes([len(body)])+body+bytes([(len(body)-2+sum(body))&255])
 tree=read(sim/'gaf-delay-clock-research-01/upstream-tree.json');blobs={x['path']:x['sha'] for x in tree['tree']};public={}
 for name,path in [('am_hal_pwrctrl.c',sim/'upstream/hal-ambiq-61b293a/am_hal_pwrctrl.c'),('am_hal_spotmgr_pcm0_7.h',sim/'recovery-info1-research-bw575-01/am_hal_spotmgr_pcm0_7.h'),('am_hal_spotmgr_pcm0_7.c',sim/'recovery-info1-research-bw575-01/am_hal_spotmgr_pcm0_7.c')]:
  b=path.read_bytes();checks[name+'_blob']=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==blobs['mcu/apollo510/hal/'+name];public[name]=dict(path=str(path),sha256=sha(path))
 checks['pcm07_reduce6_source']='#define CORELDOACTIVETRIM_REDUCE_IN_SIMOBUCK_INIT          6' in Path(public['am_hal_spotmgr_pcm0_7.h']['path']).read_text()
 for name,marker,passed in [('b0-ton-unit-red-bw576-01',None,False),('b0-override-unit-red-bw576-01',None,False),('b0-ldo-unit-red-bw576-01',None,False),('b0-ldo-unit-green-bw576-01','BLACKWALL_B0_TON 109',True)]:
  d=sim/name;q=read(d/'report.json');checks[name]=q['passed']==passed and (marker is None or q['marker']==[marker]) and read(d/'native.process.json')['status']=='removed'
 result=dict(passed=all(checks.values()),checks=checks,public_sources=public,helper_sha256=sha(helper),native_reports=[sha(sim/f'upstream23-b0-ton-native-bw576-0{n}/report.json') for n in (1,2,3)],progress='10/12 unchanged; BV05/06 not authenticated or recovered',physical_compatibility=False,scope='Original reset -> worker/HELLO -> stock main on synthetic B0/trim1 with explicit digital power contracts; no physical or analog validation')
 out.mkdir(parents=True,mode=0o700);shutil.copy2(__file__,out/'audit-source.py');shutil.copy2(helper,out/'model-binding-source.py');(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('B0 power recovery audit failed')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);audit(p.parse_args().output)
