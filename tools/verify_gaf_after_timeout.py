"""Audit the real request4 path and its watchdog preemption without inventing cleanup."""
import argparse,hashlib,json,tempfile
from pathlib import Path
from probe_gaf_after_timeout import build,OBSERVER,POST

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def semantic(r):
 g=r['gaf'];w=r['watchdog'];p=r['pause']
 return dict(watchdog_outcome=r['outcome']=='watchdog-reset-request' and r['setter_return_seen'] is False,second_request_wait=g['requests']==g['triggers']==2 and g['request_id']==4 and 200000<g['busy_reads']<400000 and g['pending'] is True and g['phase']=='pending',no_cleanup_or_calculation=g['ram_reads']==g['ram_writes']==g['completed_calculations']==0 and g['calculation_supported'] is False and g['last_reject']=='',active_reset_request=w['configuration']==0x020ce005 and w['rstgen_cfg']==2 and w['wdren'] is True and w['reset_due'] is True and w['gating_evaluated'] is True and w['allowed_by_gate'] is True,actual_pause_cause=p['seen'] is True and p['internal'] is False and p['state']=='Paused' and p['aborted'] is False and 'BlackwallApollo510Watchdog' in p['trace'],no_fault=r['cfsr']==r['hfsr']==r['memory_violations']==0 and not any(x['accesses'] for x in r['guards']),declared_profile=r['mode_word']==22 and r['mips']==167 and r['host_pc_register_seed'] is False and r['original_main_executed'] is True and r['hardware_accessed'] is False)

def verify(s,out):
 if out.exists():raise ValueError('Fresh audit output required')
 cap=s/'gaf-after-timeout-native-01';parent=s/'gaf-timeout-cadence-native-01';r=read(cap/'exports/after-timeout.json');first=read(cap/'exports/natural-timeout.json');f=read(cap/'exports/frozen-core.json');prior=read(parent/'exports/natural-timeout.json');checks=semantic(r);inputs=read(cap/'connection-inputs.json')
 checks.update(first_timeout_real=first['seen'] is True and first['pc']==0x55496e and first['r0']==0xfffffffc and first['busy_reads']==200000,first_result_exact_except_host_wall={k:v for k,v in first.items() if k!='wall_seconds'}=={k:v for k,v in prior.items() if k!='wall_seconds'},first_core_json_exact=f==read(parent/'exports/frozen-core.json'),whole_prior_sram_exact=all((cap/'exports'/n).read_bytes()==(parent/'exports'/n).read_bytes() for n in ['sram-full.bin','connected-sram.bin','connection-sram.bin','frozen-core-sram.bin']),prior_rate_boundary_exact=read(cap/'exports/cadence-boundary.json')==read(parent/'exports/cadence-boundary.json'),unchanged_code_board_devices=all((cap/n).read_bytes()==(parent/n).read_bytes() for n in ['main.bin','board.repl','strict.cs']),input_hashes=all(sha(cap/n)==h for n,h in inputs.items()),original_main=sha(cap/'main.bin')=='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a')
 original_guard='if(!fault.Active || fault.Requests!=1 || fault.BusyReads==0)return;';one_shot='if(Seen || !fault.Active || fault.Requests!=1 || fault.BusyReads==0)return;';a=(cap/'activation.cs').read_text();checks['only_owned_one_shot_and_post_observer']=a.endswith('\n'+OBSERVER) and a[:-len('\n'+OBSERVER)].replace(one_shot,original_guard,1)==(parent/'activation.cs').read_text() and a.count(one_shot)==1
 checks['only_post_execution_added']=(cap/'run.py').read_text()==(parent/'run.py').read_text()+POST
 frontier=read(cap/'exports/timeout-frontier.json');row=r['rows']
 checks['actual_request4_call_before_write']=len(row)==1 and row[0][:8]==[1,0x554974,frontier['registers'][5],4,0xfffffffc,first['sp'],first['lr'],first['tcb']] and (row[0][8]&511)==0 and row[0][9:]==[1,200000]
 checks['first_wait_helper_rows_preserved']=r['prior_failure_rows']==f['rows']
 checks['both_trigger_histories']=r['gaf']['history']=='request:2|a272:1f|2a:cb|73:e9|request:4|a272:1f|2a:cb|73:e9'
 checks['no_extra_watchdog_restart']=r['watchdog']['restarts']==read(cap/'exports/watchdog-state.json')['restarts']==188
 legacy=read(s/'watchdog-natural-request-native-01/exports/frozen-core.json');difference=r['ticks']-legacy['virtual_ticks'];checks['watchdog_time_not_rescaled']=0<=difference<1000
 checks['within_post_budget']=0<r['ticks']-r['start_ticks']<15000000000 and r['wall_seconds']<900
 lines=(cap/'renode.log').read_text().splitlines();checks['actual_log_result']=[json.loads(x.split('BLACKWALL_GAF_AFTER_TIMEOUT ',1)[1]) for x in lines if x.startswith('BLACKWALL_GAF_AFTER_TIMEOUT ')]==[r]
 progress=[json.loads(x) for x in (cap/'exports/after-timeout-progress.jsonl').read_text().splitlines() if x.strip()];checks['real_second_wait_progress']=len(progress)>2 and all(x['requests']==2 for x in progress) and all(a['ticks']<b['ticks'] and a['busy_reads']<b['busy_reads'] for a,b in zip(progress,progress[1:]))
 with tempfile.TemporaryDirectory(dir=s,prefix='gaf-after-timeout-audit-') as t:
  p=Path(t)/'prepared';build(s,p);checks['exact_reconstructed_inputs']=all((p/n).read_bytes()==(cap/n).read_bytes() for n in inputs) and read(p/'connection-inputs.json')==inputs
 if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
 negatives=[]
 for name,key,value in [('fake-setter-return','setter_return_seen',True),('missing-second-request','gaf',dict(r['gaf'],requests=1)),('disabled-watchdog','watchdog',dict(r['watchdog'],configuration=0))]:
  bad=dict(r);bad[key]=value
  if all(semantic(bad).values()):raise ValueError('Accepted '+name)
  negatives.append(dict(case=name,rejected=True))
 report=dict(passed=True,checks=checks,negative_rejections=negatives,second_request_polls=r['gaf']['busy_reads']-200000,post_virtual_seconds=(r['ticks']-r['start_ticks'])/1000000000,watchdog_observation_difference_from_10mips_ns=difference,request4_return_observed=False,cleanup_observed=False,setter_return_observed=False,actual_reset_executed=False,full_initialization_complete=False,normal_calculation_supported=False,physical_timing_verified=False,hardware_accessed=False)
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.output);print(json.dumps(dict(passed=True,checks=len(r['checks']),negative_rejections=len(r['negative_rejections']),second_polls=r['second_request_polls'],post_virtual_seconds=r['post_virtual_seconds'])))
