"""Audit original watchdog configuration at the intentionally unsupported reset boundary."""
import argparse,hashlib,json,re,tempfile
from pathlib import Path
from probe_gaf_natural_timeout import build

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(s,out):
 if out.exists():raise ValueError('Fresh audit output required')
 cap=s/'watchdog-natural-request-native-01';parent=s/'runtime-local-version-pause-native-01';wd=read(cap/'exports/watchdog-state.json');f=read(cap/'exports/frozen-core.json');pause=read(cap/'exports/pause-observer.json');inputs=read(cap/'connection-inputs.json');root=Path(__file__).parent
 source=(root/'renode-watchdog.cs').read_bytes();reset=(root/'renode-reset-controller.cs').read_bytes();model=(cap/'strict.cs').read_bytes();board=(cap/'board.repl').read_text()
 with tempfile.TemporaryDirectory(dir=s,prefix='wdt-audit-') as temporary:
  generated=Path(temporary)/'prepared';build(s,generated,'0d34120d5a007856',32,300000,True,True,True)
  regenerated=all((generated/n).read_bytes()==(cap/n).read_bytes() for n in inputs) and read(generated/'connection-inputs.json')==inputs
 cfg=wd['configuration'];clock=cfg>>24;threshold=(cfg>>8)&255;substeps=[16,2048,256,16,1][clock];nominal_seconds=threshold*16/substeps
 checks=dict(exact_input_recipe=regenerated,input_hashes=all(sha(cap/n)==h for n,h in inputs.items()),compiled_watchdog_exact=model.count(source)==1,compiled_reset_gate_exact=model.count(reset)==1,observed_configuration=cfg==0x020ce005,active_reset_request=(cfg&5)==5 and (cfg&2)==0,nominal_profile=clock==2 and threshold==224 and substeps==256 and nominal_seconds==14,actual_request=wd['reset_due'] is True and wd['gating_evaluated'] is True,gate_enabled=wd['rstgen_configuration']==2 and wd['wdren'] is True and wd['allowed_by_gate'] is True,observed_writes=wd['configuration_reads']==5 and wd['configuration_writes']==3 and wd['restarts']==188 and wd['rstgen_writes']==1,no_irq_stage=wd['interrupt_events']==0 and wd['interrupt_pending'] is False and wd['irq'] is False,reset_not_implemented='unsupported;' in wd['reset_propagation'] and 'no full-system reset' in wd['reset_propagation'],clock_is_hypothesis='1024Hz hypothesis' in wd['source_clock'] and wd['hardware_verified'] is False,pause_cause=pause['seen'] is True and pause['internal_pause'] is False and pause['machine_aborted'] is False and 'BlackwallApollo510Watchdog.' in pause['trace'],no_gaf_completion=f['requests']==f['triggers']==1 and f['busy_reads']==15132 and not f['rows'] and f['completed_calculations']==0 and f['calculation_supported'] is False,no_other_fault=f['cfsr']==f['hfsr']==f['memory_violations']==0 and not any(g['accesses'] for g in f['guards']),final_result_identical=read(parent/'exports/frozen-core.json')==f,entire_sram_identical=all((parent/n).read_bytes()==(cap/n).read_bytes() for n in ('exports/sram-full.bin','exports/connected-sram.bin','exports/connection-sram.bin','exports/frozen-core-sram.bin')),cpu_instruction_rate_declared='    PerformanceInMips: 10\n' in board,existing_reset_profile_not_enabled='InitVectorTableOffset' not in board and 'BlackwallResetAwareNVIC' not in board)
 if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
 result=dict(passed=True,checks=checks,configuration_hex=hex(cfg),nominal_watchdog=dict(lfrc_hypothesis_hz=1024,counter_hz=16,reset_threshold=224,reset_interval_seconds=nominal_seconds,physical_timing_verified=False,elapsed_since_last_restart_directly_observed=False),observed=wd,gate_allows_reset=True,watchdog_reset_executed=False,natural_gaf_timeout_observed=False,cpu_profile=dict(performance_in_mips=10,is_physical_clock_measurement=False),next_prerequisites=['Reuse verified reset vector/NVIC/memory/cache lifecycle profile','Establish virtual reset-domain and reset-cause contract before watchdog propagation','Keep watchdog, firmware loop and clocks unchanged until separately justified'],physical_hardware_access=False)
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.output);print(json.dumps(dict(passed=True,checks=len(r['checks']),configuration=r['configuration_hex'],nominal_reset_seconds=r['nominal_watchdog']['reset_interval_seconds'],actual_reset=False)))
if __name__=='__main__':main()
