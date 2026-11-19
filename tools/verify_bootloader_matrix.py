"""Verify exact offline version pairs, deny unsupported operations, and audit a restore repeat."""
import argparse,itertools,json,hashlib,shutil
from pathlib import Path
import check_bootloader_compatibility as compatibility
import check_recovery_set as recovery
from pinned_main import load_pinned_main
from revalidate_research_assets import PINS
from audit_main_driven_boot_restore import run as audit_restore
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())


def run(experiment,output):
 experiment,output=Path(experiment).resolve(),Path(output).resolve()
 if not experiment.is_relative_to(PRIVATE) or not output.is_relative_to(PRIVATE) or output.exists():raise ValueError('Private experiment and fresh output required')
 source=Path(__file__).resolve().parent
 matrix=source/'matrix.json' if (source/'matrix.json').exists() else source.parent/'docs/data/bootloader-validation-matrix.json'
 profiles=source/'recovery-profiles.json' if (source/'recovery-profiles.json').exists() else source.parent/'docs/data/recovery-artifact-profiles.json'
 compatibility.MATRIX_PATH=matrix;recovery.PROFILE_PATH=profiles
 registry=read(matrix);p=PRIVATE;s=p/'simulator';root=p/'recovery'
 data={
  'stock-boot24':(root/'boot-2-4-analysis/boot-2.4.0.24.bin').read_bytes(),
  'research-patch24':(root/'private-boot-24-candidate-01/source/build/bootloader.bin').read_bytes(),
  'upstream-current23':(root/'upstream-stock23-bw558-01/source/build/bootloader.bin').read_bytes(),
  'research-patch23':(root/'private-boot-candidate-01/source/build/bootloader.bin').read_bytes(),
  'stock-boot23':(root/'boot-2-4-analysis/boot-2.3.2.14.bin').read_bytes(),
  'stock-main24':(s/'sustained-render-guard-native-01/stock24/main.bin').read_bytes(),
  'stock-main23-release':(root/'upstream-stock23-bw558-01/main-2.3.2.14.bin').read_bytes()}
 if any(sha(blob)!=registry['artifacts'][name]['sha256'] for name,blob in data.items()):raise ValueError('Pinned source bytes required before upstream reconstruction')
 previous=bytearray(data['upstream-current23']);previous[0xb89e:0xb8a0]=bytes.fromhex('04f0');previous[0x1e656:0x1e658]=bytes.fromhex('06f0');previous[0x264a8:0x264c8]=b'\xff'*32;data['upstream-previous23']=bytes(previous)
 if sha(data['upstream-previous23'])!=registry['artifacts']['upstream-previous23']['sha256']:raise ValueError('Exact previous release reconstruction required')
 recipe=root/'upstream-stock23-bw558-01/source/tests/test_storage_deferral.py';recipe_text=recipe.read_text()
 if not all(token in recipe_text for token in ('previous[0xB89E:0xB8A0]','previous[0x1E656:0x1E658]','previous[0x264A8:0x264C8]')):raise ValueError('Pinned upstream reconstruction recipe required')
 for alias,name in [('stock_base','stock-main23-legacy'),('cfw','faceclaw38-main')]:data[name]=load_pinned_main((p/PINS[alias][0]).read_bytes())[1]
 checks={'all_artifacts_exact':set(data)==set(registry['artifacts']) and all(sha(v)==registry['artifacts'][k]['sha256'] for k,v in data.items())};rows=[]
 allowed={('stock-boot24','stock-main24','boot-main-screen'),('stock-boot24','stock-main24','pending-metadata-cycle'),('research-patch24','stock-main24','boot-main-screen'),('research-patch24','stock-main24','boot-manager-fallback'),('research-patch24','stock-main24','virtual-main-restore'),('research-patch24','stock-main24','virtual-full-stock-restore'),('upstream-current23','stock-main23-release','boot-manager-fallback'),('upstream-previous23','stock-main23-release','boot-manager-fallback')}
 boots=[k for k,v in registry['artifacts'].items() if v['kind']=='boot'];mains=[k for k,v in registry['artifacts'].items() if v['kind']=='main']
 for b,m,operation in itertools.product(boots,mains,registry['operations']):
  try:
   r=compatibility.check(data[b],data[m],operation);accepted=True;reason=r['profile']
   if r['installable'] or r['hardware_validated'] or r['execution_performed']:raise AssertionError('Virtual planning cannot imply installation')
  except ValueError as error:accepted=False;reason=str(error)
  expected=(b,m,operation) in allowed;rows.append(dict(boot=b,main=m,operation=operation,accepted=accepted,expected=expected,reason=reason))
 checks['operation_cartesian_168']=len(rows)==168 and all(r['accepted']==r['expected'] for r in rows) and sum(r['accepted'] for r in rows)==8
 negatives=[]
 for boot,main,operation,model in [(b'unknown',data['stock-main24'],'boot-main-screen',compatibility.MODEL),(data['stock-boot24'][:-1],data['stock-main24'],'boot-main-screen',compatibility.MODEL),(data['stock-boot24'],data['stock-main24'][:-1],'boot-main-screen',compatibility.MODEL),(data['stock-boot24'],data['stock-main24'],'flash',compatibility.MODEL),(data['stock-boot24'],data['stock-main24'],'boot-main-screen','physical')]:
  try:compatibility.check(boot,main,operation,model=model);negatives.append(False)
  except ValueError:negatives.append(True)
 checks['unknown_truncated_physical_denied']=all(negatives)
 pairs=[recovery.load(root/name) for name in ('private-boot-candidate-01','private-boot-24-candidate-01')];pair_reports=[recovery.check(*pair) for pair in pairs];bad=[]
 for target,other in ((pairs[0],pairs[1]),(pairs[1],pairs[0])):
  for files,key in [({**target[0],'recover.bin':other[0]['recover.bin']},target[1]),(target[0],other[1])]:
   try:recovery.check(files,key);bad.append(False)
   except ValueError:bad.append(True)
 checks['existing_pairing_reused']=all(r['local_artifact_pairing_valid'] and not r['installable'] and not r['hardware_validated'] for r in pair_reports) and all(bad)
 for release,artifact in [('current','upstream-current23'),('previous','upstream-previous23')]:
  d=s/f'upstream23-{release}-native-bw558-01';m=read(d/'manifest.json');r=read(d/'report.json');points={v['label']:v['hits'] for v in r['points']}
  checks[release+'_actual_fallback']=m['boot_sha256']==sha(data[artifact]) and m['main_sha256']==sha(data['stock-main23-release']) and r['classification']=='main-entered' and points['patched-manager']>0 and points['patched-worker']==0 and not r['uart2_tx'] and r['cfsr']==r['hfsr']==r['policy']==0 and r['images_unchanged']
  checks[release+'_source_pins']=all(sha((d/n).read_bytes())==h for n,h in m['components'].items())
 old=s/'main-driven-boot-restore-bw571-01';wm=read(experiment/'writer/manifest.json');wr=read(experiment/'writer/report.json');cr=read(experiment/'cold-boot/report.json');old_wr=read(old/'writer/report.json');old_cr=read(old/'cold-boot/report.json')
 checks['same_writer_executable_inputs']=all((experiment/'writer'/n).read_bytes()==(old/'writer'/n).read_bytes() for n in ('model.cs','caller.S','caller.ld','caller.bin','board.repl','run.py','probe.resc'))
 checks['same_restored_bytes_and_frame']=wr['final_mram_sha256']==old_wr['final_mram_sha256']=='8e0e4761fa99f1c90f8080dc91c998d4379396cb059c2a929681c95083def7f5' and cr['frame_sha256']==old_cr['frame_sha256']=='81200ab102c507de6a5853a33086958d16bcb93168ff631ee76b6c8c391adba2'
 output.mkdir(parents=True,mode=0o700);audit_restore(experiment,output/'restore-audit',regression_source=old)
 checks['repeat_independent_restore_audit']=read(output/'restore-audit/report.json')['passed']
 result=dict(passed=all(checks.values()),checks=checks,operation_results=rows,artifact_pairing=pair_reports,artifact_sha256={k:sha(v) for k,v in data.items()},matrix_sha256=sha(matrix.read_bytes()),recovery_profiles_sha256=sha(profiles.read_bytes()),previous_reconstruction_recipe_sha256=sha(recipe.read_bytes()),new_cadence_sram_sha256=cr['cadence_sram_sha256'],prior_cadence_sram_sha256=old_cr['cadence_sram_sha256'],whole_runtime_sram_exact_claimed=False,hardware_validated=False,installable=False)
 shutil.copy2(__file__,output/'audit-source.py');shutil.copy2(matrix,output/'matrix.json');shutil.copy2(profiles,output/'recovery-profiles.json');result['frozen_support_sha256']={}
 for name in ('check_bootloader_compatibility.py','check_recovery_set.py','pinned_main.py','revalidate_research_assets.py','audit_main_driven_boot_restore.py','audit_stock_main_mram_probe.py','run_original_boot_screen.py','run_renode_m55_probe.py','check_virtual_restore.py'):
  f=source/name;shutil.copy2(f,output/name);result['frozen_support_sha256'][name]=sha(f.read_bytes())
 (output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),accepted=sum(r['accepted'] for r in rows),denied=sum(not r['accepted'] for r in rows),failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('Version matrix verification failed')


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('experiment',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.experiment,a.output)
