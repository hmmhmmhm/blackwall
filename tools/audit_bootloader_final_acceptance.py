"""Reconcile twelve fixed virtual acceptance criteria with preserved primary evidence."""
import argparse,hashlib,json,shutil
from pathlib import Path
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
EVIDENCE={
'BV01':'boot-validation-audit-bw554-01/report.json',
'BV02':'pending-metadata-cycle-audit-bw573-03/report.json',
'BV03':'boot-sp-audit-bw560-01/report.json',
'BV04':'b0-power-recovery-audit-bw576-02/report.json',
'BV05':'dwt-auth-main-audit-bw579-02/report.json',
'BV06':'same-board-mram-audit-bw582-03/report.json',
'BV07':'mram-interruption-bw555-01/audit-and-cleanup.json',
'BV08':'restore-interruption-reset-bw565-01/report.json',
'BV09':'protected-mram-replay-bw563-01/audit-and-cleanup.json',
'BV10':'full-main-restore-audit-bw564-05/report.json',
'BV11':'main-driven-boot-audit-bw571-02/report.json',
'BV12':'bootloader-matrix-audit-bw574-05/report.json'}
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve();here=Path(__file__).resolve().parent;root=here.parent;frozen=here/'sources'
 docs=root/'docs/data' if (root/'docs/data/bootloader-validation-progress.json').exists() else frozen
 index=root/'docs/data/document-path-map.json'
 paths=read(index).get('paths',{}) if docs==root/'docs/data' and index.exists() else {}
 def document(name):
  if docs==frozen:return frozen/Path(name).name
  return root/paths.get(name,name)
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 progress=read(docs/'bootloader-validation-progress.json');sim=PRIVATE/'simulator';checks={};records=[]
 checks['fixed_twelve']=progress['total']==12 and {c['id'] for c in progress['criteria']}==set(EVIDENCE)
 for c in progress['criteria']:
  key=c['id'];p=sim/EVIDENCE[key];r=read(p);sub=r.get('checks',{});checks[key+':primary_passed']=r.get('passed') is True and isinstance(sub,dict) and all(v is True for v in sub.values())
  exists=[]
  for name in c['evidence']:
   x=PRIVATE/name[8:] if name.startswith('private:') else document(name)
   # Frozen acceptance stores all referenced documents for independent existence checks.
   exists.append(x.exists())
  checks[key+':evidence_exists']=all(exists)
  records.append(dict(id=key,description=c['description'],primary='private:simulator/'+EVIDENCE[key],sha256=sha(p),met=checks[key+':primary_passed'],scope='declared virtual acceptance; no physical installation authorization'))
 r=read(sim/EVIDENCE['BV02']);checks['pending_virtual_not_physical']=r['virtual_pending_metadata_cycle_verified'] and not r['actual_boot_rom_executed'] and not r['physical_por_propagation_verified']
 r=read(sim/EVIDENCE['BV05']);checks['auth_separate_from_recovery']=r['bv05_virtual_criteria_met'] and not r['bv06_recovery_command_completed'] and not r['physical_compatibility']
 r=read(sim/EVIDENCE['BV06']);checks['nonzero_repair_not_checksum']=r['bv06_complete'] and len([x for x in r['cases'] if x['nonzero_repair_verified']])==2 and not r['physical_compatibility']
 r=read(sim/EVIDENCE['BV11']);checks['full_stock_declared_components']=r['virtual_full_stock_verified'] and r['restoration']['full_stock_bytes'] and r['restoration']['modified_bytes_covered'] and not r['physical_recovery_verified'] and not r['natural_ota_verified']
 r=read(sim/EVIDENCE['BV12']);checks['matrix_prior_scope_preserved']=r['passed'] and not r['hardware_validated'] and not r['installable']
 matrix=read(docs/'bootloader-validation-matrix.json');checks['matrix_unknown_physical_denied']=not matrix['installable'] and not matrix['hardware_validated'] and matrix['physical_hardware_revision'] is None and matrix['left_boot_version'] is None and matrix['right_boot_version'] is None and matrix['charging_case_version'] is None
 extra=read(docs/'bootloader-additional-profile-evidence.json');checks['additional_profile_separate']=extra['model_sha256']==sha(sim/'recover16-repeat-native-bw582-01/strict.cs') and extra['model']!='synthetic-chip23-trim0' and not extra['checker_auto_enabled'] and not extra['installable'] and not extra['hardware_validated'] and extra['main_sha256']==matrix['artifacts']['stock-main23-release']['sha256'] and extra['boot_sha256']==matrix['artifacts']['upstream-current23']['sha256']
 cleanup=read(sim/'same-board-mram-audit-bw582-02/cleanup-summary.json');checks['recent_jobs_terminal_and_duplicates_removed']=len(cleanup['jobs'])==12 and all(x['status']=='removed' and x['container_absent'] for x in cleanup['jobs']) and cleanup['removed_bytes']==73462296 and all(not (sim/x['directory']/x['path']).exists() for x in cleanup['receipts'])
 checks['failure_history_not_rewritten']=not read(sim/'same-board-mram-audit-bw582-01/report.json')['passed'] and read(sim/'recover16-rom-error-native-bw582-03/report.json')['recovery_command']['failure']['bytes'][14:18]==[7,1,0,8]
 result=dict(passed=all(checks.values()),checks=checks,criteria=records,completed=sum(x['met'] for x in records),total=12,percent=round(100*sum(x['met'] for x in records)/12,1),scope='bootloader-validation-v1, fixed twelve virtual conditions only',actual_boot_rom_executed=False,physical_recovery_verified=False,physical_hardware_accessed=False,installable=False,precision_or_full_chip_emulator_claim=False)
 out.mkdir(parents=True,mode=0o700);dest=out/'sources';dest.mkdir()
 names={'bootloader-validation-progress.json','bootloader-validation-matrix.json','bootloader-additional-profile-evidence.json'}
 names.update(Path(e).name for c in progress['criteria'] for e in c['evidence'] if not e.startswith('private:'))
 for name in names:shutil.copy2(document('docs/'+name),dest/name)
 shutil.copy2(__file__,out/'audit-source.py');(out/'report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),completed=result['completed'],total=12,failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('Final acceptance evidence failed')
if __name__=='__main__':main()
