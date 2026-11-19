"""Audit original delay instructions, bounded observations and the declared virtual rate."""
import argparse,hashlib,json,struct,tempfile
from pathlib import Path
from probe_gaf_delay_clock import build

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sample_ok(x):
 return x['requested_us']==5 and x['entry_lr']==0x553615 and x['mode_field']==2 and x['scaled_input']==160 and x['itcm_argument']==392 and x['instructions']>=811 and x['ticks']==x['instructions']*100 and x['exit_sp']==x['entry_sp']-8

def verify(s,out):
 if out.exists():raise ValueError('Fresh audit output required')
 cap=s/'gaf-delay-clock-native-02';base=s/'main-read-routing-pilot-01/01-baseline';r=read(cap/'exports/delay-path.json');raw=(cap/'main.bin').read_bytes();f=read(cap/'exports/frozen-core.json');b=read(cap/'exports/fixed-boundary.json');old=read(base/'exports/fixed-boundary.json');samples=[];active=None
 for row in r['rows']:
  if row[0]==1:active=[row]
  elif active is not None:
   active.append(row)
   if row[0]==2:
    a=active[0];last=row;inner=active[1:-1]
    if a[5]==5:
     if [x[0] for x in inner]!=[3,4]:raise ValueError('Unexpected delay path inside complete sample')
     samples.append(dict(poll=a[1],requested_us=a[5],entry_lr=a[8],entry_sp=a[7],exit_sp=last[7],mode_field=inner[0][6],scaled_input=inner[0][5],itcm_argument=inner[1][5],instructions=last[4]-a[4],ticks=last[3]-a[3]))
    active=None
 inputs=read(cap/'connection-inputs.json')
 with tempfile.TemporaryDirectory(dir=s,prefix='gaf-delay-audit-') as t:
  p=Path(t)/'prepared';build(s,p);regenerated=all((p/n).read_bytes()==(cap/n).read_bytes() for n in inputs) and read(p/'connection-inputs.json')==inputs
 itcm=bytes(r['itcm_bytes']);literal_matches=[i+0x438000 for i in range(len(raw)) if raw.startswith(itcm[:6],i)]
 checks=dict(regenerated_recipe=regenerated,inputs_pinned=all(sha(cap/n)==h for n,h in inputs.items()),original_main=sha(cap/'main.bin')=='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a',same_devices_and_board=all((cap/n).read_bytes()==(base/n).read_bytes() for n in ('strict.cs','board.repl','main.bin','probe.resc')),physical_timing_unverified=read(cap/'delay-clock-profile.json')['physical_timing_verified'] is False,rate_explicit='    PerformanceInMips: 10\n' in (cap/'board.repl').read_text(),fixed_boundary=b['end_ticks']-b['start_ticks']==500000000 and b['requested_ms']==500,architectural_final_exact={k:v for k,v in b.items() if k!='wall_seconds'}=={k:v for k,v in old.items() if k!='wall_seconds'},whole_sram_exact=all((cap/'exports'/n).read_bytes()==(base/'exports'/n).read_bytes() for n in ('sram-full.bin','connected-sram.bin','connection-sram.bin','frozen-core-sram.bin')),whole_existing_result_exact=f==read(base/'exports/frozen-core.json'),clean_execution=f['cfsr']==f['hfsr']==f['memory_violations']==0 and not any(x['accesses'] for x in f['guards']),no_fake_completion=f['busy_reads']==362 and f['completed_calculations']==0 and not f['rows'],bounded_prefix=bool(r['overflow']) and len(r['rows'])==256 and r['polls']==363 and len(samples)==7,no_sync_or_seed=r['sync_time_called'] is False and r['host_pc_register_seed'] is False and r['hardware_accessed'] is False,delay_samples=all(sample_ok(x) for x in samples),minimum_path_observed=sum(x['instructions']==811 for x in samples)==5,clock_literals=struct.unpack_from('<f',raw,0x495ed8-0x438000)[0]==250 and struct.unpack_from('<f',raw,0x495edc-0x438000)[0]==96 and struct.unpack_from('<I',raw,0x495ee0-0x438000)[0]==0x40021000,actual_itcm_loop=itcm[:6].hex()=='0138fdd17047' and literal_matches==[0x7bf54f],integer_conversion=int(5*32*250/96)-24==392)
 research=s/'gaf-delay-clock-research-01';tree=read(research/'upstream-tree.json');records=read(research/'upstream-files.json');utils=(research/'am_hal_utils.c').read_text()
 checks['sdk_git_blobs']=tree.get('truncated') is False and all(hashlib.sha1(b'blob '+str((research/Path(x['path']).name).stat().st_size).encode()+b'\0'+(research/Path(x['path']).name).read_bytes()).hexdigest()==x['git_blob']==next(t['sha'] for t in tree['tree'] if t['path']==x['path']) and sha(research/Path(x['path']).name)==x['sha256'] for x in records)
 checks['sdk_iteration_contract']='Each iteration spends 3 CPU cycles.' in utils and '#define CYCLESPERITER                 ((float)AM_HAL_CLKGEN_FREQ_MAX_MHZ / 3)' in utils and 'AM_HAL_CLKGEN_FREQ_HP250_MHZ / AM_HAL_CLKGEN_FREQ_MAX_MHZ' in utils
 checks['sdk_adjustment_matches']=((13*250//96+40)//3)==24 and '((13 * AM_HAL_CLKGEN_FREQ_HP250_MHZ / AM_HAL_CLKGEN_FREQ_MAX_MHZ) + 40) / 3' in utils
 if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
 negatives=[]
 for key,value in [('itcm_argument',391),('ticks',5000),('entry_lr',0)]:
  bad=dict(samples[0]);bad[key]=value
  if sample_ok(bad):raise ValueError('Accepted '+key)
  negatives.append(dict(field=key,rejected=True))
 result=dict(passed=True,checks=checks,samples=samples,negative_rejections=negatives,observation_prefix_overflow=True,all_delay_calls_captured=False,minimum_path=dict(callback_entry_instructions=2,hal_high_mode_path_instructions=23,itcm_iterations=392,itcm_instructions=785,hal_return_instructions=1,total_instructions=811,virtual_ns_at_10_mips=81100,requested_us=5,ratio=16.22),sleep_instructions_only_for_200000_polls=dict(instructions=162200000,virtual_seconds_at_10_mips=16.22,is_full_timeout_duration=False,is_watchdog_order_proof=False),itcm_literal_match=literal_matches,full_itcm_initialization_stream_decoded=False,physical_timing_verified=False,cpu_rate_changed=False,watchdog_or_timeout_changed=False,normal_gaf_calculation_supported=False,e05_complete=False,hardware_accessed=False)
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.output);print(json.dumps(dict(passed=True,checks=len(r['checks']),samples=len(r['samples']),negative_rejections=len(r['negative_rejections']),minimum_path=r['minimum_path'])))
