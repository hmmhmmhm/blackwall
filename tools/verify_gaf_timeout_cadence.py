"""Audit an explicit post-ATT timing input and the original first timeout continuation."""
import argparse,hashlib,json,tempfile
from pathlib import Path
from probe_gaf_timeout_cadence import build
from hal_loop_time_profile import profile

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def semantic(r,f):
 return dict(original_first_timeout=r['seen'] is True and r['pc']==0x55496e and r['r0']==0xfffffffc and r['busy_reads']==200000,no_seed=r['host_pc_register_seed'] is False and r['original_main_executed'] is True and r['hardware_accessed'] is False,original_stop=r['stop_reason']=='natural-timeout-caller',no_other_fault=f['cfsr']==f['hfsr']==f['memory_violations']==0 and not any(g['accesses'] for g in f['guards']),no_fabricated_calculation=f['completed_calculations']==0 and f['calculation_supported'] is False)

def verify(s,out):
 if out.exists():raise ValueError('Fresh audit output required')
 cap=s/'gaf-timeout-cadence-native-01';r=read(cap/'exports/natural-timeout.json');f=read(cap/'exports/frozen-core.json');boundary=read(cap/'exports/cadence-boundary.json');meta=read(cap/'cadence-profile.json');inputs=read(cap/'connection-inputs.json');checks=semantic(r,f)
 before=boundary['before'];after=boundary['after'];ref=s/'watchdog-natural-request-native-01'
 checks.update(explicit_profile=boundary['profile']==profile('hp') and meta['cadence_profile']==profile('hp'),validated_mode=before['mode_word']==after['mode_word']==22 and before['paused'] is True and after['paused'] is True,rate_input_only=before['mips']==10 and after['mips']==167 and {k:v for k,v in before.items() if k!='mips'}=={k:v for k,v in after.items() if k!='mips'},boundary_sram_exact=(cap/'exports/cadence-before-sram.bin').read_bytes()==(cap/'exports/cadence-after-sram.bin').read_bytes()==(cap/'exports/connection-sram.bin').read_bytes(),prior_prefix_exact=all((cap/'exports'/n).read_bytes()==(ref/'exports'/n).read_bytes() for n in ('sram-full.bin','connected-sram.bin','connection-sram.bin')),model_board_main_unchanged=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('strict.cs','board.repl','main.bin','activation.cs')),input_pins=all(sha(cap/n)==h for n,h in inputs.items()),timeout_contract=meta['original_timeout_poll_limit']==meta['timeout_poll_limit']==200000 and meta['original_delay_us']==meta['delay_us']==5,physical_limits=boundary['physical_timing_verified'] is False and boundary['original_code_changed'] is False and boundary['timeout_or_watchdog_changed'] is False,original_main_sha=sha(cap/'main.bin')=='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a')
 with tempfile.TemporaryDirectory(dir=s,prefix='gaf-timeout-cadence-audit-') as t:
  p=Path(t)/'prepared';build(s,p);checks['regenerated_recipe']=all((p/n).read_bytes()==(cap/n).read_bytes() for n in inputs) and read(p/'connection-inputs.json')==inputs
 source=read(cap/'natural-timeout-source.json');checks['original_call_site']=source['continuation']==0x55496e and source['request_helper']==0x55405c and source['timeout_poll_limit']==200000
 wd=read(cap/'exports/watchdog-state.json');checks['watchdog_still_active']=wd['configuration']==0x020ce005 and wd['rstgen_configuration']==2 and wd['wdren'] is True and wd['reset_due'] is False
 ver=read(cap/'exports/local-version.json');checks['virtual_controller_completed']=ver['commands']==ver['replies'] and ver['pending'] is False and ver['gpio_irq'] is False and ver['identity']['physical_identity_verified'] is False
 frontier=read(cap/'exports/timeout-frontier.json');regs=frontier['registers']
 checks['independent_register_view']=regs[0]==r['r0'] and regs[13]==r['sp'] and regs[14]==r['lr'] and regs[15]==f['pc']==r['pc'] and frontier['tcb']==r['tcb'] and frontier['xpsr']==r['xpsr']
 checks['original_wait_helper_returns']=f['busy_reads']==200000 and f['requests']==f['triggers']==1 and f['pending'] is True and f['rows']==[[tag,pc,r['r0'],r['sp']-stack,r['lr'],r['tcb'],r['xpsr'],200000,1] for tag,pc,stack in [(0,0x5559b2,40),(1,0x55408c,16)]]
 lines=(cap/'renode.log').read_text().splitlines();checks['core_report_matches_log']=[json.loads(line.split('BLACKWALL_GAF_FROZEN_CORE ',1)[1]) for line in lines if line.startswith('BLACKWALL_GAF_FROZEN_CORE ')]==[f]
 checks['verdict_not_full_boot']=read(cap/'verdict.json')==dict(passed=True,natural_request2_timeout_observed=True,normal_calculation_supported=False,full_initialization_complete=False,physical_timing_verified=False,hardware_accessed=False)
 progress=[json.loads(x) for x in (cap/'exports/timeout-progress.jsonl').read_text().splitlines() if x.strip()];checks['actual_forward_progress']=len(progress)>3 and all(a['ticks']<b['ticks'] and a['busy_reads']<b['busy_reads'] for a,b in zip(progress,progress[1:]))
 if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
 negatives=[]
 for name,key,value in [('early-stop','busy_reads',199999),('fake-success-status','r0',0),('forced-register-entry','host_pc_register_seed',True)]:
  bad=dict(r);bad[key]=value
  if all(semantic(bad,f).values()):raise ValueError('Accepted '+name)
  negatives.append(dict(case=name,rejected=True))
 report=dict(passed=True,checks=checks,negative_rejections=negatives,actual_result=r,final_watchdog=wd,virtual_phase_seconds=(f['virtual_ticks']-f['start_ticks'])/1000000000,full_initialization_complete=False,normal_calculation_supported=False,physical_timing_verified=False,hardware_accessed=False)
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.output);print(json.dumps(dict(passed=True,checks=len(r['checks']),negative_rejections=len(r['negative_rejections']),virtual_phase_seconds=r['virtual_phase_seconds'])))
