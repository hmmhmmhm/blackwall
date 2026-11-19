"""Audit retained synthetic guest records, preserving the baseline engine defect."""
import argparse
import json
from pathlib import Path
from probe_m55_reset_contract import ASM

def verify(capture,out,aware=False):
    rows=[]
    for method in ('machine-reset','guest-aircr'):
        for mode in (0,0x50,1):rows.append(json.loads((capture/(method+'-'+str(mode)+'-true')/'report.json').read_text()))
    rows.append(json.loads((capture/'machine-reset-0-false/report.json').read_text()))
    if any(len(r[state]['words'])!=9 for r in rows for state in ('first','masked','reboot','after')):raise ValueError('Incomplete guest snapshots')
    logs=[]
    for r in rows:
        case=capture/(r['method']+'-'+str(r['mode'])+'-'+str(r['init_vector']).lower())
        values=[json.loads(line.split('BLACKWALL_M55_RESET ',1)[1]) for line in (case/'renode.log').read_text().splitlines() if line.startswith('BLACKWALL_M55_RESET ')]
        logs.append(values==[r] and (case/'guest.elf').read_bytes()==(capture/'guest.elf').read_bytes())
    checks=dict(first_boots=all(r['first']['words'][0]==1 for r in rows),mapped_ram_retained=all(r['after']['words'][8]==0xcafebabe for r in rows),initialized_vectors_reboot=all(r['after']['words'][0]==2 and r['after']['vtor']==0x438000 for r in rows if r['init_vector']),missing_init_vector_rejected=all(r['after']['words'][0]==1 and r['after']['vtor']==0 for r in rows if not r['init_vector']),mask_zero_control=all(r['after']['words'][1]>r['masked']['words'][1]>0 and r['after']['cached_basepri']==0 for r in rows if r['mode']==0 and r['init_vector']),primask_reset_control=all(r['masked']['words'][1]==0 and r['after']['words'][1]>0 and r['after']['words'][3]==0 for r in rows if r['mode']==1),basepri_guest_masked_first=all(r['masked']['words'][1]==0 and r['masked']['words'][2]==r['masked']['cached_basepri']==0x50 for r in rows if r['mode']==0x50),no_original_firmware_or_hardware=all(not r['original_firmware_executed'] and not r['hardware_accessed'] for r in rows))
    if aware:
        checks['reset_cache_and_irq_fixed']=all(r['after']['words'][2]==r['after']['cached_basepri']==0 and r['after']['words'][1]>0 and r['after'].get('reset_completions',0)>=1 for r in rows if r['mode']==0x50)
        checks['model_used']=all(r['after'].get('implementation','').endswith('.BlackwallResetAwareNVIC') for r in rows)
    else:checks['baseline_bug_reproduced']=all(r['after']['words'][2]==0 and r['after']['cached_basepri']==0x50 and r['after']['words'][1]==0 for r in rows if r['mode']==0x50)
    checks['exact_guest_fixture']=(capture/'guest.s').read_text()==ASM
    checks['reports_match_logs_and_elf']=all(logs)
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,cases=rows,reset_aware_model=aware,baseline_engine_defect_reproduced=not aware,declared_synthetic_reset_contract_verified=aware,original_firmware_executed=False,g2_application_restart_verified=False,e06_complete=False,hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);p.add_argument('--reset-aware',action='store_true');a=p.parse_args();r=verify(a.capture,a.output,a.reset_aware);print(json.dumps(dict(passed=True,checks=len(r['checks']),reset_aware=a.reset_aware,e06_complete=False)))

if __name__=='__main__':main()
