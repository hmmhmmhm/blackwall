"""Audit stored original HAL timing calls and the corrected clock-observation protocol."""
import argparse,hashlib,json,math
from pathlib import Path
from hal_loop_time_profile import profile

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def metrics(r,mips):
 q=1000/math.gcd(mips,1000)
 rows=r['delay_rows']
 calibration=all(abs((x[2]-x[1])/mips-x[0])<=max(.3,.01*x[0]) for x in rows)
 quantized=all(abs((x[4]-x[3])-(x[2]-x[1])*1000/mips)<q for x in rows)
 peripherals=r['end_ticks']-r['start_ticks']==200000000 and r['stimer']==dict(config=3,count=6553,frequency=32768) and r['watchdog']==dict(count=3,interrupt_events=1,pending=True,irq=False,reset_due=False) and r['spin_instructions']>1000000
 return dict(calibration=calibration,quantized_clock=quantized,peripherals=peripherals)

def verify(s,out):
 if out.exists():raise ValueError('Fresh audit output required')
 paths=['hal-loop-time-baseline-03','hal-loop-time-derived-lp-01','hal-loop-time-derived-hp-01','hal-loop-time-derived-hp-02'];captures=[s/p for p in paths];reports=[read(p/'report.json') for p in captures];checks={};results=[]
 for p,r in zip(captures,reports):
  pins=read(p/'files.json');checks[p.name+'_pins']=all(sha(p/n)==h for n,h in pins.items());obs=r['observed'];logs=[json.loads(l.split('BLACKWALL_HAL_TIME ',1)[1]) for l in (p/'renode.log').read_text().splitlines() if l.startswith('BLACKWALL_HAL_TIME ')];checks[p.name+'_log']=logs==[obs]
  checks[p.name+'_original_main']=sha(p/'main.bin')=='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a' and (p/'delay-itcm.bin').read_bytes().hex()=='0138fdd17047'
  checks[p.name+'_actual_arm_returns']=obs['mail'][0]==0x600d and obs['mail'][2]==5 and obs['mail'][15]==0 and [x[0] for x in obs['delay_rows']]==[0,1,5,50,1000] and obs['cfsr']==obs['hfsr']==obs['guard_accesses']==obs['wdt_accesses']==0
  checks[p.name+'_limits']=obs['original_hal_executed'] is True and obs['synthetic_caller'] is True and obs['full_main_boot'] is False and obs['hardware_accessed'] is False
  value=metrics(obs,r['profile']['mips']);results.append(dict(capture=p.name,metrics=value))
 checks['identical_synthetic_caller']=len({sha(p/'caller.elf') for p in captures})==len({sha(p/'caller.c') for p in captures})==1
 checks['explicit_profile_derivation']=all(r['profile']==profile(mode) for r,mode in [(reports[1],'lp'),(reports[2],'hp'),(reports[3],'hp')])
 checks['baseline_red']=reports[0]['passed'] is False and reports[0]['checks']['hal_delay_calibration'] is False and results[0]['metrics']['calibration'] is False and all(v for k,v in reports[0]['checks'].items() if k!='hal_delay_calibration')
 checks['historical_hp_failure_preserved']=reports[2]['passed'] is False and reports[2]['delays'][3]['virtual_ns']==49000 and reports[2]['delays'][3]['within_calibration_window'] is False
 checks['corrected_protocol']=reports[3]['measurement_protocol']=='retired-instructions-plus-native-time-quantization-v2' and reports[3]['calibration_window_us']==dict(absolute=.3,relative=.01) and reports[3]['delays'][3]['raw_clock_within_calibration_window'] is False and reports[3]['passed'] is True
 checks['all_derived_contracts']=all(all(x['metrics'].values()) for x in results[1:]) and all(all(r['checks'].values()) for r in (reports[1],reports[3]))
 checks['native_conversion_api']=reports[3]['observed']['quantum_probes']==[[10,1,100,0],[64,8,125,0],[167,167,1000,0]]
 checks['measurement_fix_kept_execution_exact']={k:v for k,v in reports[3]['observed'].items() if k!='quantum_probes'}==reports[2]['observed']
 research=s/'hal-loop-time-research-01';tree=read(research/'renode-tree.json');sources=read(research/'renode-files.json')
 checks['renode_source_git_blobs']=tree['truncated'] is False and all(sha(research/Path(x['path']).name)==x['sha256'] and hashlib.sha1(b'blob '+str((research/Path(x['path']).name).stat().st_size).encode()+b'\0'+(research/Path(x['path']).name).read_bytes()).hexdigest()==x['git_blob']==next(t['sha'] for t in tree['tree'] if t['path']==x['path']) for x in sources)
 ti=(research/'TimeInterval.cs').read_text();checks['source_quantization_contract']='performanceInMips / Misc.GCD(performanceInMips, TicksPerMicrosecond)' in ti and 'cyclesResiduum = cycles % residuumModulus;' in ti and 'cycles -= cyclesResiduum;' in ti
 try:profile('turbo')
 except ValueError:invalid_rejected=True
 else:invalid_rejected=False
 checks['unknown_mode_rejected']=invalid_rejected
 if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
 negatives=[];hp=reports[3]['observed']
 if metrics(hp,10)['calibration']:raise ValueError('Accepted wrong rate')
 negatives.append('wrong-rate')
 bad=dict(hp);bad['stimer']=dict(hp['stimer'],count=6554)
 if metrics(bad,167)['peripherals']:raise ValueError('Accepted wrong timer')
 negatives.append('wrong-timer')
 bad=dict(hp);bad['delay_rows']=[list(x) for x in hp['delay_rows']];bad['delay_rows'][3][4]+=2000
 if metrics(bad,167)['quantized_clock']:raise ValueError('Accepted incoherent clock')
 negatives.append('incoherent-clock')
 report=dict(passed=True,checks=checks,results=results,negative_rejections=negatives,global_default_adopted=False,full_main_boot_verified=False,rtos_timing_verified=False,watchdog_reset_deadline_verified=False,watchdog_counter_interrupt_verified=True,physical_timing_verified=False,hardware_accessed=False)
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.output);print(json.dumps(dict(passed=True,checks=len(r['checks']),negative_rejections=len(r['negative_rejections']))))
