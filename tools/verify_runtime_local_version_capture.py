"""Audit the optional version transaction and distinguish watchdog from GAF timeout."""
import argparse,hashlib,json,tempfile
from pathlib import Path
from probe_gaf_natural_timeout import build
from runtime_local_version_model import compose

IDENTITY='0d34120d5a007856'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def logged(cap,label):return [json.loads(l[len(label)+1:]) for l in (cap/'renode.log').read_text().splitlines() if l.startswith(label+' ')]

def verify(s,out):
 if out.exists():raise ValueError('Fresh audit output required')
 original=s/'gaf-natural-timeout-native-03';unit_model=compose((original/'strict.cs').read_text());units=[]
 for name,count,limit,enabled,capacity in [('unit-02',63,2,True,9),('unit-split-01',71,2,True,2),('unit-off-01',26,0,False,9),('unit-max-01',483,32,True,9)]:
  cap=s/('runtime-local-version-'+name);v=read(cap/'report.json');board=(cap/'board.repl').read_text()
  checks=dict(actual_compiled_model=(cap/'strict.cs').read_text()==unit_model,result_matches_log=logged(cap,'BLACKWALL_RUNTIME_ATT_UNIT')==[v],actual_assertions=v['passed'] is True and v['count']==len(v['checks'])==count,no_firmware=v['original_firmware_executed'] is False,selected_profile=('runtimeLocalVersionHex: "'+IDENTITY+'"' in board)==enabled,selected_limit=('runtimeLocalVersionLimit: '+str(limit) in board) if enabled else 'runtimeLocalVersionLimit:' not in board,chunk_capacity='writeCapacity: '+str(capacity)+'\n' in board)
  if not all(checks.values()):raise ValueError(dict(unit=name,failed=[k for k,x in checks.items() if not x]))
  units.append(dict(case=name,count=count,checks=checks))
 rows=[]
 cases=[('runtime-local-version-native-01',2,12000,False,False),('runtime-local-version-native-02',2,12000,True,False),('runtime-local-version-timeout-native-01',32,300000,True,False),('runtime-local-version-pause-native-01',32,300000,True,True)]
 for name,limit,budget,power,observe in cases:
  cap=s/name;f=read(cap/'exports/frozen-core.json');v=read(cap/'exports/local-version.json');n=read(cap/'exports/natural-timeout.json');inputs=read(cap/'connection-inputs.json')
  with tempfile.TemporaryDirectory(dir=s,prefix='version-audit-') as temporary:
   generated=Path(temporary)/'prepared';build(s,generated,IDENTITY,limit,budget,power,observe)
   exact=all((generated/x).read_bytes()==(cap/x).read_bytes() for x in inputs) and read(generated/'connection-inputs.json')==inputs
  checks=dict(exact_execution_recipe=exact,all_inputs_pinned=all(sha(cap/x)==h for x,h in inputs.items()),original_main=sha(cap/'main.bin')=='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a',log_matches=logged(cap,'BLACKWALL_GAF_FROZEN_CORE')==[f],virtual_identity=v['identity']==dict(identity_hex=IDENTITY,limit=limit,physical_identity_verified=False),one_exact_command=v['commands']==1,not_gaf_timeout=n['seen'] is False and not f['rows'] and f['requests']==f['triggers']==1 and f['busy_reads']<200000,not_calculation=f['completed_calculations']==0 and f['calculation_supported'] is False and f['ram_reads']==f['ram_written_bytes']==0,no_cpu_fault=f['cfsr']==f['hfsr']==f['memory_violations']==0,no_seed_or_physical=n['host_pc_register_seed'] is False and n['original_main_executed'] is True and n['hardware_accessed'] is False,prefix_entire_sram_preserved=all((original/x).read_bytes()==(cap/x).read_bytes() for x in ('exports/sram-full.bin','exports/connected-sram.bin','exports/connection-sram.bin')))
  guards=[(g['name'],g['address'],g['accesses']) for g in f['guards'] if g['accesses']]
  if not power:checks['known_power_frontier']=v['replies']==0 and v['pending'] is True and guards==[('guard',0x40021004,1)] and f['pc']==0x494d78
  else:
   checks['full_reply_consumed']=v['replies']==1 and not v['pending'] and not v['gpio_irq'] and not guards
   if budget==12000:checks['bounded_continuation']=n['stop_reason']=='virtual-budget' and f['virtual_ticks']-f['start_ticks']>=12000000000 and f['busy_reads']==13686
   else:checks['watchdog_frontier']=n['stop_reason']=='device-or-guard-pause' and f['busy_reads']==15132 and f['pc']==0x496624
  if observe:
   p=read(cap/'exports/pause-observer.json');checks['actual_watchdog_pause_stack']=p['seen'] is True and p['internal_pause'] is False and p['machine_aborted'] is False and p['state']=='Paused' and 'BlackwallApollo510Watchdog.' in p['trace'] and 'Machine.PauseAndRequestEmulationPause' in p['trace']
   parent=s/'runtime-local-version-timeout-native-01';checks['pause_observation_sram_equal']=all((parent/x).read_bytes()==(cap/x).read_bytes() for x in ('exports/sram-full.bin','exports/connected-sram.bin','exports/connection-sram.bin','exports/frozen-core-sram.bin'));checks['pause_observation_result_equal']=read(parent/'exports/frozen-core.json')==f
  if not all(checks.values()):raise ValueError(dict(case=name,failed=[k for k,x in checks.items() if not x]))
  rows.append(dict(case=name,checks=checks,elapsed_virtual_ns=f['virtual_ticks']-f['start_ticks'],busy_reads=f['busy_reads'],version_commands=v['commands'],version_replies=v['replies']))
 result=dict(passed=True,units=units,unit_assertions=sum(u['count'] for u in units),native=rows,version_transaction_verified_stock24=True,natural_gaf_timeout_observed=False,normal_gaf_supported=False,watchdog_request_observed=True,watchdog_reset_executed=False,physical_hardware_access=False)
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.output);print(json.dumps(dict(passed=True,unit_assertions=r['unit_assertions'],native=len(r['native']),watchdog_request_observed=True,gaf_timeout_observed=False)))
if __name__=='__main__':main()
