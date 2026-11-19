"""Audit E14's original virtual-peer acceptance against nine fixed original-firmware cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from verify_kv_persistence_cycle import validate_capture
from verify_post_timeout_reconnect import verify as verify_stock24_recovery
from verify_peer_recovery import verify as verify_older_recovery
from run_runtime_connection_m55 import att_packets

ACCEPTANCE = 'Inject virtual peer disconnects, delays, and malformed messages and verify original timeout/error/state and reconnect or explicit failure. Unconditional ready/ack responses are prohibited.'
CASES=('stock24','stock23','cfw')
PARENTS=('runtime-peer-failure-research-01/manifest.json','post-timeout-reconnect-research-01/manifest.json','peer-recovery-version-research-01/manifest.json','post-reset-advertising-research-01/manifest.json')

def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def validate_coverage(rows):
    expected={(kind,case) for kind in ('disconnect','malformed-tpl','delayed-loss-timeout-reconnect') for case in CASES}
    actual=[(x['scenario'],x['case']) for x in rows]
    if len(actual)!=len(set(actual)) or set(actual)!=expected:raise ValueError('Missing, duplicate or unknown E14 scenario')
    if any(not x['verified'] for x in rows):raise ValueError('Unverified peer failure scenario')

def verify(s,out,scope_path):
    scope=read(scope_path);criterion=next(c for c in scope['criteria'] if c['id']=='E14')
    if scope['version']!=3 or len(scope['criteria'])!=16 or criterion['acceptance']!=ACCEPTANCE:raise ValueError('Changed scope requires a new acceptance review')
    out.mkdir(mode=0o700,parents=True,exist_ok=False);pins={};parents={}
    for name in PARENTS:
        path=s/name;m=read(path)
        if not m['passed'] or any(m.get(k,False) for k in ('physical_access','physical_hardware_access','hardware_accessed')):raise ValueError('Invalid source manifest')
        parents[name]=digest(path)
        for relative,value in m['files'].items():
            p=s/relative
            if not p.resolve().is_relative_to(s.resolve()):raise ValueError('Evidence outside simulator')
            metadata=dict(sha256=value,bytes=p.stat().st_size) if isinstance(value,str) else value
            if relative in pins and pins[relative]!=metadata:raise ValueError('Conflicting evidence pin')
            pins[relative]=metadata
    for name,metadata in pins.items():
        p=s/name
        if p.stat().st_size!=metadata['bytes'] or digest(p)!=metadata['sha256']:raise ValueError('Changed evidence: '+name)
    frozen=s/'runtime-peer-failure-research-01/frozen-tools/run_runtime_connection_m55.py';rows=[];details={}
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    for kind,folder in (('disconnect','runtime-disconnect-native-01'),('malformed-tpl','runtime-malformed-crc-native-01')):
        for case in CASES:
            cap=s/folder/case;validate_capture(cap);dest=out/(kind+'-'+case)
            result=subprocess.run([sys.executable,str(frozen),str(s),str(cap),'--case',case,'--audit-existing','--audit-output',str(dest)],capture_output=True,text=True,env=env)
            if result.returncode:raise ValueError('Stored original inspector rejected '+str(cap)+': '+result.stderr[-300:])
            v=read(dest/'verification.json');p=read(cap/'connection-profile.json');r=read(cap/'exports/connection.json')
            if not v['passed'] or not all(v['checks'].values()) or v['api_caller'] or not v['execution_passed']:raise ValueError('Failed native behavior contract')
            if kind=='disconnect':
                dc=read(cap/'exports/disconnect.json');mem=(cap/'exports/disconnect-sram.bin').read_bytes();slots=[p['dm_global']+48*k for k in range(3)]
                required=('disconnect_ccb_deallocated','disconnect_consumed','disconnect_gpio_cleared','disconnect_original_task','disconnect_original_stack','disconnect_app_event','disconnect_no_fault')
                verified=all(v['checks'][k] for k in required) and dc['stopped'] and dc['pc']==p['closed_return'] and dc['runtime_consumed']==4 and not dc['runtime_pending'] and all(mem[x+21-0x20000000]==mem[x+22-0x20000000]==0 for x in slots)
                summary=dict(original_close_return=dc['pc'],app_message=v['disconnect_app_message'],ccb_released=True)
            else:
                required=('att_allowed_tpl_crc_dropped','state_unchanged','rtc_unchanged','mtu_workflow','no_fault','no_unsupported')
                valid=att_packets();bad=p['att_packets'];corrupted=bytes.fromhex(bad[1]);original=bytes.fromhex(valid[1]);a=r['att']
                verified=all(v['checks'][k] for k in required) and p['att_corrupt_crc'] and bad[0]==valid[0] and corrupted[:-1]==original[:-1] and corrupted[-1]==original[-1]^1 and len(a['inputs'])==1 and not a['consumers'] and not a['applied'] and not a['returns'] and a['rtc']['commits']==0
                summary=dict(original_tpl_inputs=1,application_consumers=0,state_preserved=True,rtc_writes=0)
            if not verified:raise ValueError('Unproven direct peer failure state')
            rows.append(dict(scenario=kind,case=case,verified=True,capture=str(cap.relative_to(s)),checks=len(v['checks']),summary=summary));details[kind+'-'+case]=v['checks']
    for case in CASES:
        cap=s/('post-timeout-reconnect-native-01' if case=='stock24' else 'peer-recovery-version-native-01/'+case);dest=out/('recovery-'+case)
        v=(verify_stock24_recovery if case=='stock24' else verify_older_recovery)(s,cap,dest)
        key='single_stock24_timeout_reconnect_scenario_passed' if case=='stock24' else 'single_case_timeout_reconnect_passed'
        if not v['passed'] or not v[key] or not all(v['checks'].values()):raise ValueError('Incomplete original timeout recovery')
        dc=read(cap/'exports/disconnect.json');p=read(cap/'connection-profile.json');elapsed=dc['virtual_time']['end_ticks']-dc['virtual_time']['start_ticks']
        if p['disconnect_delay_ms']!=1000 or not 1000000000<=elapsed<1020000000:raise ValueError('Unproven device input delay')
        rows.append(dict(scenario='delayed-loss-timeout-reconnect',case=case,verified=True,capture=str(cap.relative_to(s)),checks=len(v['checks']),summary=dict(device_delay_ms=1000,original_timeout=True,reset_generation=1,credit_restored=True,ccb_reallocated=True,original_dm_return=True,normal_gaf=False)));details['recovery-'+case]=v['checks']
    unit_checks={}
    for folder in ('post-reset-advertising-unit-01','post-reset-advertising-unit-off-01'):
        v=read(s/folder/'report.json');checks=v['checks']
        if not v['passed'] or v['original_firmware_executed'] or v['count']!=len(checks) or not any(x.startswith('wrong-byte-') for x in checks) or 'no-extra-startup' not in checks or 'missing-generations-denied' not in checks:raise ValueError('Strict response unit coverage missing')
        unit_checks[folder]=v['count']
    validate_coverage(rows)
    report=dict(passed=True,fixed_scenario_acceptance_met=True,e14_complete=True,acceptance=ACCEPTANCE,fixed_scenarios=len(rows),cases=list(CASES),rows=rows,details=details,strict_response_units=unit_checks,parent_manifests=parents,source_files_verified=len(pins),new_firmware_executions=0,post_reset_att_verified=False,full_app_recovery_verified=False,normal_gaf_verified=False,physical_timing_verified=False,all_observer_hooks_off_verified=False,unequal_observer_endpoint_sram_differences_preserved=True,hardware_accessed=False,subagents_used=False)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--scope',type=Path,required=True);a=p.parse_args();r=verify(a.simulator,a.output,a.scope);print(json.dumps(dict(passed=True,fixed_scenarios=r['fixed_scenarios'],e14_complete=True,new_firmware_executions=0)))

if __name__=='__main__':main()
