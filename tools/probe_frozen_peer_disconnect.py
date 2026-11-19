"""Original BLE disconnect processing with an explicit frozen EDMP fault.

The nominal profile auditor stays unchanged and its rejection is preserved.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from native_replay import IMAGE
from probe_gaf_frozen_core import compose_frozen,scoped_observer_component
from run_renode_m55_probe import execute
from run_runtime_connection_m55 import build as runtime_build,pin_capture,inspect
from runtime_event_models import imu_span
from verify_kv_persistence_cycle import validate_capture


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(s):
    p=s/'observer-suspension-native-02/scoped';validate_capture(p)
    manifest=json.loads((s/'observer-suspension-research-01/manifest.json').read_text())
    for name in ('capture-files.json','strict.cs','main.bin'):
        pin=manifest['files'][str((p/name).relative_to(s))]
        if (p/name).stat().st_size!=pin['bytes'] or sha(p/name)!=pin['sha256']:raise ValueError('Changed fault reference')
    if not manifest['passed']:raise ValueError('Unverified fault reference')
    return p


def build(s,out,delay,reason):
    ref=reference(s)
    profile=runtime_build(s,out,'stock24',att_time=True,disconnect_reason=reason,disconnect_delay_ms=delay,
                          gaf_profile=True,gaf_on_demand_control=True)
    before=(out/'strict.cs').read_text();model=scoped_observer_component(compose_frozen(before))
    if model!=(ref/'strict.cs').read_text() or (out/'main.bin').read_bytes()!=(ref/'main.bin').read_bytes():
        raise ValueError('Combined failure requires the closed stock24 model and original')
    (out/'strict.cs').write_text(model)
    begin,end=imu_span(model);gaf=json.loads((out/'gaf-profile.json').read_text())
    gaf.update(candidate_sha256=hashlib.sha256(model[begin:end].encode()).hexdigest(),
        control_fragment_sha256=sha(Path(__file__).with_name('renode-gaf-frozen-core.cs')),
        on_demand_fault='frozen-core',calculation_supported=False,
        retained_ram_source='prior modeled clear and explicit host writes; no EDMP execution')
    (out/'gaf-profile.json').write_text(json.dumps(gaf,indent=2)+'\n')
    profile.update(gaf_profile=gaf,gaf_profile_sha256=sha(out/'gaf-profile.json'),model_sha256=sha(out/'strict.cs'),
        suspended_startup_observer_labels=['iom7-address','iom7-fifo','iom7-command'],
        combined_fault_scenario='EDMP-frozen-core plus controller-reported disconnect')
    (out/'connection-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    runtime=(out/'run.py').read_text();anchor="    if p.get('disconnect_reason') is not None:\n"
    setup='''    if not app.Stopped or not m.IsPaused or any(v['accesses'] for v in result['guards']) or result['cfsr'] or result['hfsr'] or result['memory_violations']:
        raise ValueError('Combined fault requires completed ATT and a clean whole-machine pause')
    for label in p['suspended_startup_observer_labels']:
        if not observer.SuspendPoint(label):raise ValueError('Already suspended diagnostic point')
'''
    if runtime.count(anchor)!=1:raise ValueError('Unknown disconnect boundary')
    runtime=runtime.replace(anchor,setup+anchor)
    post='''
try:
    from System import Console
    from System.IO import File
    m=monitor.Machine;d=m['sysbus.iom4.imu_identity'].OnDemand
    fault_result=dict(scenario='EDMP-frozen-core plus controller-reported disconnect',phase=str(d.Phase),requests=int(d.Requests),triggers=int(d.Triggers),busy_reads=int(d.BusyReads),calculation_supported=bool(d.CalculationSupported),completed_calculations=int(d.CompletedCalculations),pending=bool(d.Pending),request_ram=int(m['sysbus.iom4.imu_identity'].Service.RamByte(4)),history=str(d.History),last_reject=str(d.LastReject),pc=int(m['sysbus.cpu'].PC.RawValue),suspended_points=[dict(label=str(v.Label),address=int(v.Address),hits=int(v.Hits)) for v in observer.Points if v.Suspended],normal_initialization_verified=False,hardware_accessed=False)
    File.WriteAllText('/work-output/frozen-peer-fault.json',json.dumps(fault_result))
    Console.WriteLine('BLACKWALL_FROZEN_PEER_FAULT '+json.dumps(fault_result))
except Exception as error:Console.WriteLine('BLACKWALL_FROZEN_PEER_FAULT_ERROR '+str(error))
'''
    (out/'run.py').write_text(runtime+post)
    (out/'combined-fault-source.json').write_text(json.dumps(dict(reference_capture_sha256=sha(ref/'capture-files.json'),
        reference_model_sha256=sha(ref/'strict.cs'),normal_model_before_sha256=hashlib.sha256(before.encode()).hexdigest(),
        delay_ms=delay,controller_reported_reason=reason,nominal_profile=False,actual_local_timeout_claimed=False),indent=2)+'\n')
    inputs=json.loads((out/'connection-inputs.json').read_text())
    for name in set(inputs)|{'combined-fault-source.json'}:inputs[name]=sha(out/name)
    (out/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')


def audit(s,cap,out):
    validate_capture(cap);ref=reference(s)
    normal=inspect(cap,out/'nominal-contract')
    p=json.loads((cap/'connection-profile.json').read_text())
    meta=json.loads((cap/'combined-fault-source.json').read_text())
    fault=json.loads((cap/'exports/frozen-peer-fault.json').read_text())
    dc=json.loads((cap/'exports/disconnect.json').read_text())
    failed=[k for k,v in normal['checks'].items() if not v]
    delayed=p['disconnect_delay_ms']!=0
    gaf=dc.get('imu_gaf',{})
    att=json.loads((cap/'exports/connection.json').read_text())
    rtc_before=att['att']['rtc'];rtc_after=dc['rtc']
    rtc_delta=datetime.fromisoformat(rtc_after['date'])-datetime.fromisoformat(rtc_before['date'])
    rtc_ns=(rtc_delta.days*86400+rtc_delta.seconds)*1000000000+rtc_delta.microseconds*1000
    elapsed_ns=dc['virtual_time']['end_ticks']-dc['virtual_time']['start_ticks']
    expected_failures=['disconnect_rtc_preserved','pinned_gaf_profile'] if delayed else ['pinned_gaf_profile']
    checks=dict(
        nominal_rejection_preserved=normal['passed'] is False and failed==expected_failures,
        rtc_tracks_virtual_time=all(r['commits']==1 and r['pending'] is False and r['error']=='none' for r in (rtc_before,rtc_after))
            and 0<=rtc_ns and abs(rtc_ns-elapsed_ns)<10000000,
        closed_fault_model=(cap/'strict.cs').read_bytes()==(ref/'strict.cs').read_bytes() and sha(cap/'strict.cs')==meta['reference_model_sha256'],
        original_main=(cap/'main.bin').read_bytes()==(ref/'main.bin').read_bytes(),
        reference_lineage=sha(ref/'capture-files.json')==meta['reference_capture_sha256'],
        explicit_fault=p.get('combined_fault_scenario')==fault['scenario'] and p['gaf_profile'].get('on_demand_fault')=='frozen-core'
            and p['gaf_profile'].get('calculation_supported') is False and not meta['nominal_profile'] and not meta['actual_local_timeout_claimed'],
        calculation_unavailable=fault['calculation_supported'] is False and fault['completed_calculations']==0 and not fault['normal_initialization_verified'],
        three_owned_points=[v['label'] for v in fault['suspended_points']]==p['suspended_startup_observer_labels']==['iom7-address','iom7-fifo','iom7-command'],
        controller_reason_declared=meta['controller_reported_reason']==p['disconnect_reason'] in (8,19),
        delay_declared=meta['delay_ms']==p['disconnect_delay_ms'] in (0,1000),
        peer_closed_at_original_return=dc['stopped'] and fault['pc']==dc['pc']==p['closed_return'],
        fault_state=(fault['phase']=='pending' and fault['requests']==fault['triggers']==1 and fault['request_ram']==2
                     and fault['busy_reads']>0 and fault['pending'] and gaf['fields']==41 and gaf['read_bytes']==153 and gaf['written_bytes']==225)
                    if delayed else fault['phase']=='unselected' and fault['requests']==fault['triggers']==fault['busy_reads']==0,
        no_hardware_access=fault['hardware_accessed'] is False)
    lines=[json.loads(l.split('BLACKWALL_FROZEN_PEER_FAULT ',1)[1]) for l in (cap/'renode.log').read_text().splitlines() if l.startswith('BLACKWALL_FROZEN_PEER_FAULT ')]
    checks['fault_report_matches_log']=lines==[fault]
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,scope='combined declared sensor hang and controller disconnect; not nominal boot or complete E14',
        checks=checks,nominal_contract_passed=False,nominal_failed_checks=failed,peer_checks_preserved=len(normal['checks'])-len(failed),
        rtc_progression=dict(before=rtc_before,after=rtc_after,elapsed_virtual_nanoseconds=elapsed_ns,elapsed_rtc_nanoseconds=rtc_ns,
            precision_nanoseconds=10000000,replaced_same_second_constraint=delayed),
        fault=fault,disconnect_app_message=normal['disconnect_app_message'],disconnect_virtual_time=dc['virtual_time'],
        actual_local_timeout_verified=False,reconnection_verified=False,normal_gaf_verified=False,full_boot_complete=False,
        e14_complete=False,hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--delay-ms',type=int,choices=(0,1000),default=1000);p.add_argument('--reason',type=lambda x:int(x,0),choices=(8,19),default=19)
    p.add_argument('--audit-existing',action='store_true');p.add_argument('--audit-output',type=Path);a=p.parse_args()
    if a.audit_existing:
        if a.audit_output is None or a.audit_output.exists():raise ValueError('Use a new separate audit output')
        report=audit(a.simulator,a.output,a.audit_output)
    else:
        if a.audit_output is not None:raise ValueError('Audit destination is only for saved audit')
        build(a.simulator,a.output,a.delay_ms,a.reason)
        execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,
            '--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=180)
        pin_capture(a.output);report=audit(a.simulator,a.output,a.output/'combined-verification')
    print(json.dumps(dict(passed=report['passed'],scope=report['scope'],peer_checks=report['peer_checks_preserved'],fault_checks=len(report['checks']),e14_complete=False)))


if __name__=='__main__':main()
