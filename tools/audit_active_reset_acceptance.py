"""Read saved full-board reset evidence for all three original firmware profiles."""
import argparse,hashlib,json,struct
from pathlib import Path
from native_replay import MAIN_LAYOUT
S=Path.home()/'Library/Application Support/Blackwall/simulator'
CASES={'stock24':'stock_current','stock23':'stock_base','cfw':'cfw'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def audit(captures,audits,out):
 if out.exists() or not out.is_relative_to(S):raise ValueError('New private audit required')
 cases={}
 for case,profile in CASES.items():
  folder=captures/case;report=load(audits/case/'report.json');p=load(folder/'plan.json');e=folder/'exports'
  integrity={}
  for name,digest in report['capture_hashes'].items():
   child=(folder/name).resolve()
   if not child.is_relative_to(folder.resolve()):raise ValueError('Invalid capture path')
   integrity[name]=child.is_file() and sha(child)==digest
  valid=report['passed'] and report['execution_passed'] and report['semantic_validation']['passed'] and all(report['diagnostics'].values())
  if not valid:
   cases[case]=dict(passed=False,checks={'native_semantics':False,'capture_integrity':all(integrity.values())});continue
  before=report['before'];entry=report['entry']['state'];after=report['observed'];w=report['warm_task_wait_witness'];raw=(folder/'main.bin').read_bytes();vec_sp,vec_pc=struct.unpack_from('<2I',raw)
  before_ram=(e/'active-reset-before-sram.bin').read_bytes();entry_ram=(e/'active-reset-entry-sram.bin').read_bytes()
  checks=dict(native_semantics=valid,capture_integrity=all(integrity.values()),original_profile=len(raw)==MAIN_LAYOUT[profile][1] and sha(folder/'main.bin')==MAIN_LAYOUT[profile][3],entry_vector=entry['pc']==vec_pc&~1 and entry['sp']==vec_sp and entry['vtor']==0x438000,single_reset=entry['reset_count']==before['reset_count']+1==after['reset_count'],active_before=before['gpu']['frames']>=5 and before['gpu']['bytes']==576*288 and before['imu']['fifo_ready'] and before['peer']['state']=='Complete',volatile_restored=entry['gpu']['frames']==entry['gpu']['bytes']==0 and entry['imu']['phase']=='unselected' and not entry['imu']['fifo_ready'] and entry['peer']['state']=='Unreleased' and entry['peer']['commands']==entry['uart_rx']==entry['touch_frames']==0 and entry['cache_lines']==0,retained_itcm_nor_fs=all(before[k]==entry[k] for k in ['itcm_sha256','kv_sha256','fs_sha256']) and before['written_itcm']==entry['written_itcm'],post_reset_app=after['gpu']['frames']>=5 and after['imu']['fifo_ready'] and after['imu']['phase']=='disabled' and after['peer']['state']=='Complete' and after['peer']['commands']==59 and after['icache'] and after['cache_lines']==2048,post_reset_task=w['passed'] and all(w['checks'].values()),declared_device_input="b.WriteDoubleWord(0xe000ed0c,0x05fa0004)" in (folder/'run.py').read_text() and not any(k in (folder/'run.py').read_text() for k in ['cpu.PC=','cpu.PC =','cpu.SetRegister(','cpu.SeedRegister(']),full_sram_captures=len(before_ram)==len(entry_ram)==0x380000,shared_iom_profile=p['components']['shared-iom']['source_class_sha256']=='5221ccf22756c86c7049c73bc305a2a30c9df380f587373688faeed0a78826da' and p['components']['shared-iom']['board_owners']==5)
  cases[case]=dict(passed=all(checks.values()),checks=checks,before=before,entry=entry,after=after,wait_resume_ms=(w['later_callback_rows'][0][10]-w['wait_ticks'])/1e6,warm_frames=len(report['warm_lifecycle']['frames']),warm_elapsed_ms=report['warm_lifecycle']['elapsed_ticks']/report['warm_lifecycle']['ticks_per_ms'],sram_bytes_changed_during_async_reset=sum(a!=b for a,b in zip(before_ram,entry_ram)),source_report_sha256=sha(audits/case/'report.json'))
 result=dict(schema=1,criterion='E06',scope_version=3,passed=all(v['passed'] for v in cases.values()),original3_active_reset_verified=all(v['passed'] for v in cases.values()),cases=cases,sram_policy='MappedMemory backing retained; original activity between asynchronous request and entry and later original startup writes are allowed. Pre-request/entry SRAM equality is not asserted.',hardware_accessed=False,new_native_runs=False,whole_goal_complete=False)
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');(out/'auditor-source.py').write_bytes(Path(__file__).read_bytes());print(json.dumps({'passed':result['passed'],'cases':{k:{'passed':v['passed'],'failed':[name for name,ok in v['checks'].items() if not ok]} for k,v in cases.items()}}));return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('captures',type=Path);p.add_argument('audits',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=audit(a.captures.resolve(),a.audits.resolve(),a.output.resolve());raise SystemExit(0 if r['passed'] else 1)
