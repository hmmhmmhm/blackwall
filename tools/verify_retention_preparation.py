"""Audit original power preparation boundaries without equating WFI completion with sleep."""
import argparse,hashlib,json,struct
from pathlib import Path
from verify_original_system_reset import verify as verify_staging,clean
from retention_preparation_models import compose_timer_controls,compose_inactive_audio,compose_retention_flush

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def logged(cap,label):return [json.loads(x[len(label)+1:]) for x in (cap/'renode.log').read_text().splitlines() if x.startswith(label+' ')]
def verify(s,cap,out):
    if out.exists():raise ValueError('Use a fresh audit output')
    base=verify_staging(cap,out/'staging',True)
    r=read(cap/'exports/retention-preparation.json');source=read(cap/'preparation-source.json');ref=s/'cpu-retention-staging-native-02';board=(cap/'board.repl').read_text()
    flags=[('idleChannelControls','idle'),('inactiveAudioStatus','audio'),('retentionFlush','flush')];selected={k:('    '+n+': true\n') in board for n,k in flags}
    manifest=s/'cpu-retention-staging-research-01/manifest.json'
    if sha(manifest)!='e963eba901edde5f8dcedb6a78495c26d3f44d9436ed95971e7bacf34abaa547':raise ValueError('Changed parent acceptance manifest')
    pins=read(manifest)['files']
    for n in ('strict.cs','board.repl','run.py'):
        if sha(ref/n)!=pins[str((ref/n).relative_to(s))]['sha256']:raise ValueError('Changed pinned reference '+n)
    expected=(ref/'strict.cs').read_text()
    if selected['idle']:expected=compose_timer_controls(expected)
    if selected['audio']:expected=compose_inactive_audio(expected)
    if selected['flush']:expected=compose_retention_flush(expected)
    stripped=board
    for n,k in flags:stripped=stripped.replace('    '+n+': true\n','')
    checks=dict(original_staging=base['passed'],exact_model=(cap/'strict.cs').read_text()==expected,exact_board_without_profiles=stripped==(ref/'board.repl').read_text(),original_main=sha(cap/'main.bin')==sha(ref/'main.bin'),pinned_runtime_prefix=(cap/'run.py').read_text().startswith((ref/'run.py').read_text()),snapshot_hash=sha(cap/'exports/retention-preparation-sram.bin')==r['sram_sha256'],snapshot_size=(cap/'exports/retention-preparation-sram.bin').stat().st_size==0x380000,log_exact=logged(cap,'BLACKWALL_RETENTION_PREPARATION')==[r],no_seed_or_hardware=r['host_pc_or_register_seed'] is False and r['hardware_accessed'] is False,architectural_fault_free=r['cfsr']==r['hfsr']==r['memory']['violations']==r['system_control']['violations']==0,configured_retention=r['cpd_value']==0x22 and r['retention_stages']==1,resume_progress=r['ticks']>r['start_ticks'])
    guards=[v for v in r['guard_detail'] if v['accesses']]
    if not selected['idle']:pc,address,name=0x5c1d02,0x40008220,'guard'
    elif not selected['audio']:pc,address,name=0x44dfc8,0x40021010,'guard'
    elif not selected['flush']:pc,address,name=0x44e16e,0x47ff0000,'guard_iom7_tail'
    else:pc,address,name=0x44e176,None,None
    if address is not None:checks['bounded_frontier']=r['pc']==pc and guards==[dict(name=name,accesses=1,address=address,width=4,value=0,operation='read')]
    else:
        raw=(cap/'main.bin').read_bytes()
        checks['original_wfi_completion']=r['pc']==pc and not guards and r['wfi_return_seen'] and r['retention_flushes']==1 and r['scr']&4!=0 and raw[0x44e174-0x438000:0x44e176-0x438000]==bytes.fromhex('30bf') and not r['sleep_overflow']
    if selected['idle']:
        expected_reads=[0 if n in (0,7,14) else 1 for n in range(16)]
        checks['all_idle_channels_read']=r['idle_control_reads']==expected_reads
        checks['selected_channels_preserved']=r['selected_timer_controls']==[0x120,0x42,0xa10]
    if 'audio_status_reads' in r:checks['inactive_audio_read']=selected['audio'] and r['audio_status_reads']==1
    later=None
    if (cap/'exports/original-sleep-return.json').exists():
        later=read(cap/'exports/original-sleep-return.json');checks['sleep_caller_return']=later['return_seen'] and later['pc']==0x4765e2 and later['cpd_value']==0 and clean(later) and logged(cap,'BLACKWALL_ORIGINAL_SLEEP_RETURN')==[later] and sha(cap/'exports/original-sleep-return-sram.bin')==later['sram_sha256']
    restarted=None
    if (cap/'exports/restart-service.json').exists():
        restarted=read(cap/'exports/restart-service.json');checks['restart_service_capture']=logged(cap,'BLACKWALL_RESTART_SERVICE')==[restarted] and sha(cap/'exports/restart-service-sram.bin')==restarted['sram_sha256']
    app=None
    if (cap/'exports/restart-app.json').exists():
        app=read(cap/'exports/restart-app.json');p=read(cap/'connection-profile.json');conn=read(cap/'exports/restart-connection.json')
        checks['restarted_services']=restarted['held'] and restarted['pc']==p['getter'] and clean(restarted) and restarted['peer']['commands']==59
        checks['new_connection']=conn['accepted'] and conn['stopped'] and clean(conn) and conn['pc']==p['finished'] and logged(cap,'BLACKWALL_RESTART_CONNECTION')==[conn]
        checks['new_app_action']=app['stopped'] and clean(app) and app['pc']==p['service']['consumer_return'] and len(app['inputs'])==len(app['consumers'])==len(app['applied'])==len(app['returns'])==1 and app['applied'][0][0]==0 and app['rtc']['commits']==1 and app['rtc']['date'].startswith('2023-11-14T22:13:20.') and app['peer']['events']==3 and logged(cap,'BLACKWALL_RESTART_APP')==[app] and sha(cap/'exports/restart-app-sram.bin')==app['sram_sha256']
    events=(restarted or later or r).get('sleep_events',[])
    cycle=None
    for i,event in enumerate(events):
        if event[0:2]==[0,1]:
            ended=next((v for v in events[i+1:] if v[0:2]==[0,0]),None)
            if ended is not None and ended[2]>event[2]:
                timer=next((v for v in events[i+1:] if v[0]==3 and v[2]>=ended[2]),None)
                cycle=dict(entered=event,exited=ended,duration_ns=ended[2]-event[2],next_timer_isr=timer)
            break
    if app is not None:
        raw=(cap/'main.bin').read_bytes();timer_pc=struct.unpack_from('<I',raw,0xc0)[0]&~1
        checks['renode_sleep_and_timer_prefix']=cycle is not None and cycle['entered'][3]==cycle['exited'][3]==0x44e176 and cycle['next_timer_isr'] is not None and cycle['next_timer_isr'][3]==timer_pc and cycle['next_timer_isr'][4]&511==48
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    result=dict(passed=True,checks=checks,profiles=selected,stage_checks=len(base['checks']),observed=r,sleep_caller_return=later,restart_service=restarted,restart_app=app,wfi_completed=selected['flush'],renode_sleep_prefix=cycle,event_history_complete=not bool((restarted or later or r).get('sleep_overflow',False)),renode_blocked_wfi_verified=cycle is not None,physical_sleep_verified=False,wake_source_verified=False,whole_g2_boot_complete=False,e06_complete=False,hardware_accessed=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();v=verify(a.simulator,a.capture,a.output);print(json.dumps(dict(passed=True,checks=len(v['checks']),staging_checks=v['stage_checks'],wfi=v['wfi_completed'],restarted_app=v['restart_app'] is not None,e06_complete=False)))
if __name__=='__main__':main()
