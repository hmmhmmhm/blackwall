"""Audit bounded virtual metadata programming, POR requests and fresh boot decisions."""
import argparse,json,hashlib,re,shutil
from pathlib import Path
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
INITIAL=bytes.fromhex('55555555'+'a5'*12)
def read(p):return json.loads(p.read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def namespace(s,name):
 at=s.index('public sealed class '+name);start=s.rfind('namespace Antmicro.',0,at);end=s.find('\nnamespace Antmicro.',at)
 return s[start:] if end<0 else s[start:end]
def remove_method(s,token):
 start=s.index(token);end=s.index('{',start)+1;depth=1
 while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[:start]+s[end:]
def normalized(s):return re.sub(r'\s+',' ',re.sub(r'//[^\n]*','',s)).strip()


def run(experiment,output):
 experiment,output=Path(experiment).resolve(),Path(output).resolve()
 if not experiment.is_relative_to(PRIVATE) or output.exists() or not output.is_relative_to(PRIVATE):raise ValueError('Private experiment and fresh output required')
 expected={
 'success':('software-por-request',4,1,True,b'\xff'*16),
 'success-reboot':('main-entered',0,0,False,b'\xff'*16),
 'rom-error':('software-por-request',0,1,True,INITIAL),
 'rom-error-reboot':('software-por-request',0,1,True,INITIAL),
 'interrupt-0':('interrupted-program',0,0,False,INITIAL),
 'interrupt-0-reboot':('software-por-request',4,1,True,b'\xff'*16),
 'interrupt-1':('interrupted-program',1,0,False,b'\xff'*4+INITIAL[4:]),
 'interrupt-1-reboot':('main-entered',0,0,False,b'\xff'*4+INITIAL[4:]),
 'stuck':('unready-rom-boundary',0,0,False,INITIAL)}
 if {p.parent.name for p in experiment.glob('*/manifest.json')}!=set(expected):raise ValueError('Nine frozen lifecycle runs required')
 checks={};reports={};sources={}
 for name,(classification,words,calls,por,after) in expected.items():
  d=experiment/name;m=read(d/'manifest.json');r=read(d/'report.json');raw=read(d/'exports/result.json');native=read(d/'exports/pending-result.json');initial=(d/'initial-metadata.bin').read_bytes();actual=(d/'exports/metadata-after.bin').read_bytes();sources[name]=(d/'strict.cs').read_text();reports[name]=r
  checks[name+'_sources']=all(sha((d/n).read_bytes())==h for n,h in m['components'].items())
  checks[name+'_raw_records']=all(r[k]==v for k,v in native.items()) and all(r['cpu'][k]==v for k,v in raw.items())
  checks[name+'_metadata']=sha(initial)==m['initial_metadata_sha256'] and actual==after and sha(actual)==r['metadata_after_sha256']
  checks[name+'_input_lineage']=initial==INITIAL if not name.endswith('-reboot') else m['initial_metadata_source']==str(experiment/name[:-7]/'exports/metadata-after.bin') and initial==(experiment/name[:-7]/'exports/metadata-after.bin').read_bytes()
  checks[name+'_classification']=r['classification']==classification and r['programmed_words']==words and r['calls']==calls and r['por_requested']==por and not r['violation']
  checks[name+'_clean_original_execution']=raw['cfsr']==raw['hfsr']==raw['policy']==raw['system_control_violations']==raw['events_dropped']==0 and all(g['accesses']==0 for g in raw['guards']) and r['images_unchanged']
  checks[name+'_source_images']=m['boot']['sha256']=='ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665' and m['main']['fixture_sha256']=='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a'
  checks[name+'_explicit_models']=r['hardware_accessed'] is False and r['physical_por_executed'] is False and r['rom_functional_model'] and m['rom_instruction_is_backend_trap_not_original'] and (d/'rom-trap.bin').read_bytes()==bytes.fromhex('00be') and 'SetRegister' not in (d/'run.py').read_text()
  points={p['label']:p for p in raw['points']}
  if classification=='main-entered':
   checks[name+'_original_handoff']=r['entries']==0 and points['boot-reset']['first']<points['boot-manager']['first']<points['marker-load']['first']<points['stock-handoff']['first']<points['main-reset']['first'] and points['main-reset']['hits']>0
  else:
   checks[name+'_bounded_rom_entry']=r['entries']==1 and r['block_instructions']==0 and [r[k] for k in ('key','operation','source','offset','words','primask')]==[0x12344321,1,0x20022d68,0xff800,4,1] and points['main-reset']['hits']==points['stock-handoff']['hits']==0
  if por:checks[name+'_original_por_write']=r['por_pc']==0x42e87c and r['por_primask']==0 and raw['pc']==0x42e87e and r['control_writes']==3 and r['status']==(7 if name.startswith('rom-error') else 0)
  elif classification=='interrupted-program':checks[name+'_no_return_on_interruption']=r['interrupted'] and not r['unready'] and r['control_writes']==0 and raw['pc']==0x0200ff20
  elif classification=='unready-rom-boundary':checks[name+'_unready_no_effect']=r['unready'] and not r['interrupted'] and r['control_writes']==0 and actual==initial and raw['pc']==0x0200ff20
  checks[name+'_owned_removed']=read(d/'native.process.json')['status']=='removed'
 p=PRIVATE/'simulator';base=(p/'pending-rom-request-bw572-01/ready/strict.cs').read_text()
 policy=namespace(sources['success'],'BlackwallMemoryPolicy')
 policy=remove_method(policy,'public void BindFunctionalRomEntry')
 policy=policy.replace('if(pc==0x0200ff20 && functionalRomGuard!=null)\n            { functionalRomGuard(instructions); return; }','').replace('private Action<uint> functionalRomGuard;','')
 checks['default_code_mmu_guards_unchanged']=normalized(policy)==normalized(namespace(base,'BlackwallMemoryPolicy'))
 checks['same_ready_model']=len({sha(s.encode()) for name,s in sources.items() if name!='stuck'})==1
 checks['stuck_model_delta_only']=sources['stuck']==sources['success'].replace('new BlackwallMemoryStartup(1)','new BlackwallMemoryStartup(0)')
 checks['bounded_two_error_reboots']=({k:v for k,v in reports['rom-error']['cpu'].items() if k!='ticks'}=={k:v for k,v in reports['rom-error-reboot']['cpu'].items() if k!='ticks'})
 old=read(p/'boot-validation-audit-bw554-01/report.json')['cases']['corrupt-marker'];old_path=Path(old['path']);old_report=read(old_path/'report.json')
 checks['original_corrupt_marker_reused']=sha((old_path/'report.json').read_bytes())==old['report_sha256'] and old_report['classification']=='main-entered' and old_report['images_unchanged'] and '0x55555554u' in (old_path/'strict.cs').read_text()
 green=p/'pending-state-green-bw573-01';red=p/'pending-state-red-bw573-01'
 checks['state13_red_green']=read(green/'report.json')['passed'] and not read(red/'report.json')['passed'] and 'BLACKWALL_PENDING_STATE 13' in (green/'native.log').read_text() and 'could not be found' in (red/'native.log').read_text()
 checks['entry_zero_block_diagnostic_preserved']=read(p/'pending-metadata-cycle-bw573-03/entry-diagnostic/report.json')['block_instructions']==0 and read(p/'pending-metadata-cycle-bw573-02/success/report.json')['violation']
 checks['initial_registration_failure_preserved']='Could not find node' in (p/'pending-metadata-cycle-bw573-01/success/native.log').read_text() and not (p/'pending-metadata-cycle-bw573-01/success/exports/result.json').exists()
 result=dict(passed=all(checks.values()),checks=checks,virtual_pending_metadata_cycle_verified=all(checks.values()),error_reboot_ticks=[reports[n]['cpu']['ticks'] for n in ('rom-error','rom-error-reboot')],elapsed_time_exact=False,timing_scope='CPU halt precedes host Machine.Pause; other virtual peripherals can advance after the request. CPU/raw facts except final ticks are exact; no physical POR timing claim.',actual_boot_rom_executed=False,physical_por_propagation_verified=False,valid_full_ota_image_install_verified=False,hardware_accessed=False)
 output.mkdir(parents=True,mode=0o700);shutil.copy2(__file__,output/'audit-source.py');(output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('Pending metadata cycle audit failed')

if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('experiment',type=Path);a.add_argument('output',type=Path);v=a.parse_args();run(v.experiment,v.output)
