"""Audit version-specific original reset/restart using fixed source inputs and device effects."""
import argparse,hashlib,json,struct
from pathlib import Path
from reset_restart_inputs import fixed_inputs
from verify_original_system_reset import clean

def read(p):return json.loads(p.read_text())
def sha(data):return hashlib.sha256(data).hexdigest()
def logged(cap,label):return [json.loads(x[len(label)+1:]) for x in (cap/'renode.log').read_text().splitlines() if x.startswith(label+' ')]

def verify(s,cap,out,memory_policy=None,system_control=None):
    if out.exists():raise ValueError('Fresh audit output required')
    cp=read(cap/'connection-profile.json');case=cp['case'];inputs,p=fixed_inputs(s,case)
    if memory_policy is not None:
        from reset_memory_policy_candidate import with_memory_policy
        inputs,p=with_memory_policy(s,inputs,p,memory_policy)
    if system_control is not None:
        from reset_memory_policy_candidate import with_system_control
        inputs,p=with_system_control(s,inputs,p,system_control)
    r=read(cap/'exports/system-reset-entry.json');before=r['before'];entry=r['entry'];after=read(cap/'exports/system-reset-after.json');stage=read(cap/'exports/system-reset-later.json');prep=read(cap/'exports/retention-preparation.json');returned=read(cap/'exports/original-sleep-return.json');service=read(cap/'exports/restart-service.json');connection=read(cap/'exports/restart-connection.json');app=read(cap/'exports/restart-app.json')
    main=inputs['main.bin'];sp,vector=struct.unpack_from('<II',main);vector&=~1
    hashes={n:sha(data) for n,data in inputs.items()};actual_hashes=read(cap/'connection-inputs.json')
    phases=[before,entry,after,stage,prep,returned,service,connection,app]
    checks=dict(fixed_execution_inputs=all((cap/n).read_bytes()==data for n,data in inputs.items()),input_manifest=actual_hashes==hashes,original_main=sha(main)==p['main_sha256'],first_app_return=before['pc']==cp['service']['consumer_return'] and before['rtc']['commits']==1 and before['peer']['events']==3,device_reset_request=r['request']==dict(address=0xe000ed0c,value=0x05fa0004,origin='external virtual NVIC device input'),no_pc_seed=r['host_pc_or_register_seed'] is False and r['original_firmware_executed'] is True and r['hardware_accessed'] is False,original_reset_vector=r['entry_seen'] and entry['pc']==r['expected_entry']==vector and entry['sp']==r['expected_sp']==sp and entry['vtor']==0x438000,one_system_reset=before['nvic_reset_count']==0 and all(v['nvic_reset_count']==1 for v in phases[1:]),clean_all_phases=all(clean(v) for v in phases),basepri_reset=entry['basepri']==after['basepri']==0,rtc_reset_domain=entry['rtc']['date']=='2000-01-01T00:00:00.00' and entry['rtc']['commits']==after['rtc']['commits']==service['rtc']['commits']==0,controller_reset_domain=entry['peer']==dict(state='Unreleased',commands=0,events=0),kv_nor_reset_preserves_bytes=len({v['nor_kv_sha256'] for v in (before,entry,after)})==1,pio_idle_reset=all(not v[k] for v in (before,entry,after) for k in ('pio_busy','pio_program_busy','pio_erase_busy')),itcm_backing_retained=len({v['itcm_sha256'] for v in (before,entry,after)})==1,itcm_provenance_retained=len({v['memory']['written'] for v in (before,entry,after)})==1 and before['memory']['written']>0,original_initializer_executes=after['ticks']-entry['ticks']>=20000000 and after['pc']!=vector,qualified_retention_store=stage['retention_return_seen'] and stage['pc']==p['retention_return'] and stage['retention_stages']==1 and stage['cpd_value']==0x22,all_idle_controls=prep['idle_control_reads']==[0 if n in (0,7,14) else 1 for n in range(16)],selected_controls=prep['selected_timer_controls']==[0x120,0x42,0xa10],inactive_audio_domain=prep['audio_status_reads']==1,original_wfi_completed=prep['wfi_return_seen'] and prep['pc']==p['wfi_return'] and prep['scr']&4!=0 and prep['retention_flushes']==1 and not prep['sleep_overflow'],original_sleep_caller_return=returned['return_seen'] and returned['pc']==p['sleep_return'] and returned['cpd_value']==0,services_reinitialized=service['held'] and service['pc']==cp['getter'] and service['peer']['commands']==59 and service['peer']['events']==0 and service['peer']['state']=='Complete',new_connection=connection['accepted'] and connection['stopped'] and connection['pc']==cp['finished'] and connection['peer']['events']==1,new_app_action=app['stopped'] and app['pc']==cp['service']['consumer_return'] and len(app['inputs'])==len(app['consumers'])==len(app['applied'])==len(app['returns'])==1 and app['applied'][0][0]==0 and app['rtc']['commits']==1 and app['rtc']['date'].startswith('2023-11-14T22:13:20.') and app['peer']['events']==3)
    pairs=[('system-reset-after','BLACKWALL_ORIGINAL_RESET_AFTER',after),('system-reset-later','BLACKWALL_ORIGINAL_RESET_LATER',stage),('retention-preparation','BLACKWALL_RETENTION_PREPARATION',prep),('original-sleep-return','BLACKWALL_ORIGINAL_SLEEP_RETURN',returned),('restart-service','BLACKWALL_RESTART_SERVICE',service),('restart-connection','BLACKWALL_RESTART_CONNECTION',connection),('restart-app','BLACKWALL_RESTART_APP',app)]
    checks['all_phase_logs_match']=all(logged(cap,label)==[v] for _,label,v in pairs) and logged(cap,'BLACKWALL_ORIGINAL_RESET_ENTRY')==[dict(seen=True,pc=entry['pc'],resets=1)]
    snapshots=[('system-reset-before-sram.bin',before),('system-reset-entry-sram.bin',entry),('system-reset-after-sram.bin',after),('system-reset-later-sram.bin',stage),('retention-preparation-sram.bin',prep),('original-sleep-return-sram.bin',returned),('restart-service-sram.bin',service),('restart-app-sram.bin',app)]
    checks['all_memory_captures_match']=all((cap/'exports'/name).stat().st_size==0x380000 and sha((cap/'exports'/name).read_bytes())==v['sram_sha256'] for name,v in snapshots)
    events=service['sleep_events'];cycle=None
    checks['event_prefix_shape']=all(len(v)==6 and v[0] in (0,1,2,3) and v[1] in (0,1) for v in events) and [v[2] for v in events]==sorted(v[2] for v in events)
    for n,v in enumerate(events):
        if v[0:2]==[0,1]:
            end=next((x for x in events[n+1:] if x[0:2]==[0,0]),None)
            if end and end[2]>v[2]:
                timer=next((x for x in events[n+1:] if x[0]==3 and x[2]>=end[2]),None)
                cycle=dict(entered=v,exited=end,duration_ns=end[2]-v[2],timer_isr=timer)
            break
    checks['renode_sleep_and_irq32']=cycle is not None and cycle['entered'][3]==cycle['exited'][3]==p['wfi_return'] and cycle['timer_isr'] is not None and cycle['timer_isr'][3]==p['timer32_isr'] and cycle['timer_isr'][4]&511==48
    if system_control is not None:
        checks['instruction_cache_reset_and_reinitialized']=before['system_control']['icache'] is True and entry['system_control']['icache'] is False and service['system_control']['icache'] is True and app['system_control']['icache'] is True
    if (cap/'reset-restart-profile.json').exists():checks['version_profile_exact']=read(cap/'reset-restart-profile.json')==p
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    a=(cap/'exports/system-reset-before-sram.bin').read_bytes();b=(cap/'exports/system-reset-entry-sram.bin').read_bytes();changed=[n for n,(x,y) in enumerate(zip(a,b)) if x!=y]
    result=dict(passed=True,case=case,checks=checks,profile=p,case_original_app_restart_verified=True,renode_sleep_prefix=cycle,event_history_complete=not service['sleep_overflow'],sram_request_to_entry=dict(changed_bytes=len(changed),elapsed_ns=entry['ticks']-before['ticks'],pure_reset_retention_proven=False),rtc_after=app['rtc'],observer_neutrality_verified=False,full_g2_boot_verified=False,physical_sleep_verified=False,physical_hardware_access=False,e06_complete=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);p.add_argument('--memory-policy',type=Path);p.add_argument('--system-control',type=Path);a=p.parse_args();r=verify(a.simulator,a.capture,a.output,a.memory_policy,a.system_control);print(json.dumps(dict(passed=True,case=r['case'],checks=len(r['checks']),sleep_ms=r['renode_sleep_prefix']['duration_ns']/1e6,e06_complete=False)))
if __name__=='__main__':main()
