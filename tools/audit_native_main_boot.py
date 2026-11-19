"""E05 acceptance from frozen native captures and saved lifecycle audits.
This reads existing artifacts only. It never rebuilds a device model or runs ARM.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from native_replay import MAIN_LAYOUT
S=Path.home()/'Library/Application Support/Blackwall/simulator'
CASES={'stock24':'stock_current','stock23':'stock_base','cfw':'cfw'}
REQUIRED_POINTS={
 'pmic':['pmic-init-entry','pmic-init-return','pmic-init-caller'],
 'nor_nvdb':['address-mode-parent-return','NVdb-initializer-return'],
 'littlefs':['LittleFS-mount-entry','LittleFS-format-return','LittleFS-remount-return','LittleFS-app-init-return'],
 'gpio_timer':['GPIO-role-return','Timer0-setup-return'],
 'font_manager':['font-configure-return','font-manager-return'],
 'uart_power':['UART0-power-client-return'],
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def marker(log,name):
 rows=[json.loads(l[len(name)+1:]) for l in log.splitlines() if l.startswith(name+' ')]
 if len(rows)!=1:raise ValueError('Expected one native marker '+name)
 return rows[0]
def audit(captures,audits,out):
 if out.exists() or not out.is_relative_to(S):raise ValueError('New private output required')
 rows={};all_files={}
 for case,layout in CASES.items():
  folder=captures/case;report_path=audits/case/'report.json';r=load(report_path);plan=load(folder/'plan.json');raw=(folder/'main.bin').read_bytes();log=(folder/'renode.log').read_text()
  checks={};capture_checks={}
  for relative,digest in r['capture_hashes'].items():
   p=(folder/relative).resolve()
   if not p.is_relative_to(folder.resolve()):raise ValueError('Capture path escapes its root')
   capture_checks[relative]=p.is_file() and sha(p)==digest
  checks['saved_audit_matches_capture']=all(capture_checks.values())
  checks['execution_and_semantics']=r['case']==case and r['passed'] and r['execution_passed'] and r['semantic_validation']['passed'] and all(r['execution_checks'].values()) and all(r['diagnostics'].values())
  if not checks['execution_and_semantics']:
   rows[case]=dict(passed=False,checks=checks,failed_capture_checks=[k for k,v in capture_checks.items() if not v],native_report_sha256=sha(report_path));continue
  _,main_size,bundle_size,expected_main_sha256=MAIN_LAYOUT[layout]
  checks['original_main']=len(raw)==main_size and sha(folder/'main.bin')==expected_main_sha256
  initial_sp,reset_vector=struct.unpack_from('<2I',raw)
  resc=(folder/'probe.resc').read_text()
  checks['original_main_vector_recipe']=all(x in resc for x in ['sysbus LoadBinary @/work/main.bin 0x438000','cpu VectorTableOffset 0x438000','include @/work/run.py']) and reset_vector&1==1 and 0x438000<=(reset_vector&~1)<0x438000+main_size and initial_sp%8==0 and 0x20000000<=initial_sp<=0x20380000
  checks['board_model_pinned']=r['execution_checks'].get('input:board.repl') is True and r['diagnostics']['source_model_unchanged'] and r['execution_checks']['no-cpu-control-writes']
  observation=marker(log,'BLACKWALL_OBSERVATION');points={p['label']:p for p in observation['points']}
  services={name:{label:points[label]['hits'] for label in labels} for name,labels in REQUIRED_POINTS.items()}
  checks['required_service_return_paths']=all(hits>0 for group in services.values() for hits in group.values())
  peer=marker(log,'BLACKWALL_CANDIDATE_mspi0-cq-dma-v1')
  checks['controller_startup_peer_complete']=peer['peer_state']=='Complete' and peer['accepted_commands']>0 and peer['frames']>0
  life=r['lifecycle'];touch=load(folder/'exports/touch.json');w=r['task_wait_witness']
  checks['sensor_wrapper_fifo_ready']=life['before']['imu_wrapper_gate']==life['after']['imu_wrapper_gate']==1 and life['after']['fifo_ready']
  checks['native_init_event']=any(row[0]==56 and row[2]==2 and row[8]==w['tcb'] and (row[9]&0x1ff)==0 for row in touch['rows'])
  checks['wait_then_same_task_native_event']=w['passed'] and all(w['checks'].values()) and w['queue_messages']==0 and w['queue_item_bytes']==12 and w['queue_capacity']==96 and bool(w['later_callback_rows']) and all(row in touch['rows'] and row[10]>w['wait_ticks'] and row[8]==w['tcb'] and row[2]==4 and (row[9]&0x1ff)==0 for row in w['later_callback_rows'])
  checks['screen_and_lifecycle']=all(r['diagnostics'][name] for name in ['target_reached','multiple_frames','ordered_without_gaps','content_changed','sleep_wake_pair','first_frame_matches'])
  checks['no_runtime_faults']=r['diagnostics']['fault_free'] and touch['cfsr']==touch['hfsr']==touch['memory_violations']==0 and all(g['accesses']==0 for g in touch['guards'])
  checks['source_trace_matches_export']=marker(log,'BLACKWALL_TOUCH_RUNTIME')==touch and not touch['overflow']
  checks['captured_whole_machine_wait']=sha(folder/'exports/boot-wait-sram.bin')==w['wait_sram_sha256'] and sha(folder/'exports/boot-wait-state.json')==w['wait_state_sha256'] and plan['task_wait_probe_ms']==10
  rows[case]=dict(passed=all(checks.values()),checks=checks,failed_capture_checks=[k for k,v in capture_checks.items() if not v],main_sha256=sha(folder/'main.bin'),initial_sp=initial_sp,reset_vector=reset_vector,bundle_bytes=bundle_size,model_sha256=sha(folder/'strict.cs'),board_sha256=sha(folder/'board.repl'),native_report_sha256=sha(report_path),source_root=str(folder.relative_to(S)),required_service_hits=services,controller_peer=dict(state=peer['peer_state'],accepted_commands=peer['accepted_commands'],frames=peer['frames']),elapsed_ms=life['elapsed_ticks']/life['ticks_per_ms'],frame_count=len(life['frames']),wait_tcb=w['tcb'],wait_queue=w['queue'],wait_ticks=w['wait_ticks'],first_resume_ticks=w['later_callback_rows'][0][10],first_resume_after_wait_ms=(w['later_callback_rows'][0][10]-w['wait_ticks'])/1e6,later_callback_count=len(w['later_callback_rows']),sleep_history_overflow=life['sleep_overflow'])
  for p in [report_path,folder/'plan.json',folder/'probe.resc',folder/'main.bin',folder/'strict.cs',folder/'board.repl',folder/'renode.log']:
   all_files[str(p.relative_to(S))]=sha(p)
 result=dict(schema=1,criterion='E05',scope_version=3,passed=all(x['passed'] for x in rows.values()),cases=rows,source_pins=all_files,original3_main_reset_service_event_wait_resume_verified=all(x['passed'] for x in rows.values()),new_arm_runs=False,hardware_accessed=False,limitations=['Declared virtual peer, blank storage, cold sensor bootstrap and reference GPU profiles; no physical validation.','Gate1 proves wrapper return, not numerical sensor correctness or all subordinate status codes.','100 virtual ms after first screen is the fixed scenario, not an indefinite stability or physical performance claim.','E06 runtime reset, E11 additional input and E12 sample consumption remain separate criteria.'])
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');(out/'auditor-source.py').write_bytes(Path(__file__).read_bytes())
 print(json.dumps({'passed':result['passed'],'cases':{k:{'passed':v['passed'],'failed':[name for name,ok in v['checks'].items() if not ok]} for k,v in rows.items()}}));return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('captures',type=Path);p.add_argument('audits',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=audit(a.captures.resolve(),a.audits.resolve(),a.output.resolve());raise SystemExit(0 if r['passed'] else 1)
