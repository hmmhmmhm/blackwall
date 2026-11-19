"""Audit captured original readvertising and second connection, without rerunning it."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import struct

from probe_runtime_reconnect import POST
from run_runtime_connection_m55 import inspect,sha
from runtime_reconnect_model import compose
from verify_kv_persistence_cycle import validate_capture
from inspect_ambiq_target import decode


def read(p):return json.loads(p.read_text())
def logged(cap,prefix):
    rows=[json.loads(l.split(prefix+' ',1)[1]) for l in (cap/'renode.log').read_text().splitlines() if l.startswith(prefix+' ')]
    if len(rows)!=1:raise ValueError('Missing or duplicated '+prefix)
    return rows[0]


def verify(s,cap,out):
    validate_capture(cap)
    p=read(cap/'connection-profile.json');delayed=p['disconnect_delay_ms']==1000
    ref=s/'frozen-peer-disconnect-native-01'/('delayed13' if delayed else 'immediate');validate_capture(ref)
    manifest=read(s/'frozen-peer-disconnect-research-01/manifest.json')
    for n in ('capture-files.json','strict.cs','main.bin','run.py','board.repl'):
        pin=manifest['files'][str((ref/n).relative_to(s))]
        if sha(ref/n)!=pin['sha256'] or (ref/n).stat().st_size!=pin['bytes']:raise ValueError('Changed predecessor')
    nominal=inspect(cap,out/'nominal-contract')
    failed=[k for k,v in nominal['checks'].items() if not v]
    expected=['disconnect_rtc_preserved','pinned_gaf_profile'] if delayed else ['pinned_gaf_profile']
    a=read(cap/'exports/readvertising.json');b=read(cap/'exports/reconnect.json')
    if not b.get('executed'):raise ValueError('No second connection execution')
    ram=(cap/'exports/reconnect-sram.bin').read_bytes();ar=(cap/'exports/readvertising-sram.bin').read_bytes()
    active=[p['dm_global']+48*k for k in range(3) if ram[p['dm_global']+48*k+22-0x20000000]]
    de=b['entry'];dx=b['exit'];ptr=de[1] if len(de)==6 else 0
    message=ram[ptr-0x20000000:ptr-0x20000000+36] if 0x20000000<=ptr<0x20380000-36 else b''
    old=read(cap/'exports/connection.json');dc=read(cap/'exports/disconnect.json')
    rtc_delta=datetime.fromisoformat(b['rtc']['date'])-datetime.fromisoformat(dc['rtc']['date'])
    rtc_ns=(rtc_delta.days*86400+rtc_delta.seconds)*1000000000+rtc_delta.microseconds*1000
    elapsed=b['ticks']-dc['virtual_time']['end_ticks']
    expected_commands='0106200fa000a0000001000000000000000700;010a200101'
    checks=dict(
        nominal_rejections_preserved=not nominal['passed'] and failed==expected,
        only_declared_controller_change=(cap/'strict.cs').read_text()==compose((ref/'strict.cs').read_text()) and p['model_sha256']==sha(cap/'strict.cs'),
        original_main_and_inputs=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('main.bin','sram-fill.bin','itcm-fill.bin')),
        only_explicit_board_option=(cap/'board.repl').read_text()==(ref/'board.repl').read_text().replace('    runtimeDisconnectEventHex:','    runtimeReadvertise: true\n    runtimeDisconnectEventHex:'),
        runner_extension_exact=(cap/'run.py').read_text()==(ref/'run.py').read_text()+POST,
        profile_explicit=p['runtime_readvertise'] is True and p['disconnect_reason']==19 and p['disconnect_delay_ms'] in (0,1000),
        earlier_entire_sram_exact=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('exports/connection-sram.bin','exports/disconnect-sram.bin')),
        earlier_report_values_exact=all(read(cap/n)==read(ref/n) for n in ('exports/connection.json','exports/disconnect.json','exports/frozen-peer-fault.json')),
        reports_match_logs=logged(cap,'BLACKWALL_READVERTISING')==a and logged(cap,'BLACKWALL_RECONNECT')==b,
        exact_two_original_commands=all(v['peer']['accepted']==expected_commands and v['peer']['readvertising_commands']==v['peer']['readvertising_replies']==2 for v in (a,b)),
        startup_counts_preserved=all(v['peer']['commands']==59 and v['peer']['replies']==60 for v in (a,b)),
        advertising_completed_once=len(a['completed'])==1 and a['start_ticks']<a['completed'][0]<=a['ticks'] and a['peer']['runtime_events']==4 and not a['peer']['pending'] and a['peer']['state']=='Complete',
        rearm_keeps_ccb_released=all(ar[p['dm_global']+48*k+21-0x20000000]==ar[p['dm_global']+48*k+22-0x20000000]==0 for k in range(3)),
        bounded_phases=a['start_ticks']==dc['virtual_time']['end_ticks'] and 0<a['ticks']-a['start_ticks']<=2000000000 and 0<b['ticks']-a['ticks']<=2000000000,
        reconnect_device_input=b['input']['accepted'] and b['input']['irq'] and b['input']['pending'] and b['input']['pc']==a['pc'],
        original_open_return=b['stopped'] and b['pc']==p['finished'] and b['calls']==1,
        original_wsf_task=len(de)==6 and len(dx)==3 and de[4]==dx[1]==old['entry'][4] and de[5]&511==dx[2]&511==0,
        original_stack=len(de)==6 and len(dx)==3 and de[2]==dx[0]+16,
        decoded_connection_event=len(message)==36 and message[4]==0 and struct.unpack_from('<H',message,6)[0]==64 and message[8:16]==bytes.fromhex('0100112233445566'),
        ccb_reallocated=len(active)==1 and ram[active[0]+21-0x20000000]==3 and struct.unpack_from('<H',ram,active[0]+12-0x20000000)[0]==64 and ram[active[0]+0x10-0x20000000]==1 and ram[active[0]+0x19-0x20000000]==1,
        event_consumed_and_irq_clear=b['peer']['runtime_events']==5 and not b['peer']['pending'] and b['irq_entries']==1 and b['gpio']==dict(irq=False,pending=False,edges=11),
        no_cpu_or_guard_fault=all(not any(g['accesses'] for g in v['guards']) and v['cfsr']==v['hfsr']==v['memory_violations']==0 for v in (a,b)),
        rtc_elapsed_and_no_new_write=all(v['rtc']['commits']==1 and not v['rtc']['pending'] and v['rtc']['error']=='none' for v in (a,b)) and rtc_ns>=0 and abs(rtc_ns-elapsed)<10000000,
        no_sensor_calculation=all(v['gaf']['on_demand']['calculation_supported'] is False and v['gaf']['on_demand']['completed_calculations']==0 for v in (a,b)))
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,nominal_contract_passed=False,nominal_failed_checks=failed,prior_peer_checks_passed=len(nominal['checks'])-len(failed),
        accepted_commands=expected_commands,rearm_virtual_nanoseconds=a['ticks']-a['start_ticks'],reconnect_virtual_nanoseconds=b['ticks']-a['ticks'],completion_callback_clock_lag_nanoseconds=a['ticks']-a['completed'][0],
        second_ccb=active[0],original_task=de[4],sensor=a['gaf']['on_demand'],scope='declared controller replay and second original DM connection; no physical BLE or second ATT transaction',
        normal_initialization_verified=False,e14_complete=False,hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def verify_power_boundary(s,cap,out):
    validate_capture(cap);p=read(cap/'connection-profile.json')
    ref=s/'frozen-peer-disconnect-native-01/delayed13';validate_capture(ref)
    predecessor=read(s/'frozen-peer-disconnect-research-01/manifest.json')
    for n in ('capture-files.json','strict.cs','main.bin'):
        pin=predecessor['files'][str((ref/n).relative_to(s))]
        if sha(ref/n)!=pin['sha256'] or (ref/n).stat().st_size!=pin['bytes']:raise ValueError('Changed delayed predecessor')
    normal=inspect(cap,out/'nominal-contract');a=read(cap/'exports/readvertising.json');b=read(cap/'exports/reconnect.json')
    code=decode((cap/'main.bin').read_bytes(),a['pc'],2)
    failed=[k for k,v in normal['checks'].items() if not v]
    checks=dict(
        earlier_peer_checks_preserved=failed==['disconnect_rtc_preserved','pinned_gaf_profile'] and not normal['passed'],
        exact_controller_change=(cap/'strict.cs').read_text()==compose((ref/'strict.cs').read_text()),
        original_and_close_sram=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('main.bin','exports/connection-sram.bin','exports/disconnect-sram.bin')),
        reports_match_logs=a==logged(cap,'BLACKWALL_READVERTISING') and b==logged(cap,'BLACKWALL_RECONNECT'),
        exact_power_write=a['pc']==0x494d78 and a['registers'][0]==0x40021004 and a['registers'][1]==0xea0 and len(code)==1 and code[0].mnemonic=='str' and code[0].op_str=='r1, [r0]',
        one_strict_boundary=[g for g in a['guards'] if g['accesses']]==[dict(name='guard',accesses=1,address=0x40021004)] and a['cfsr']==a['hfsr']==a['memory_violations']==0,
        no_rearm_or_reconnect=not b['executed'] and not a['completed'] and a['peer']['readvertising_commands']==a['peer']['readvertising_replies']==0 and a['peer']['runtime_events']==4,
        sensor_still_pending=a['gaf']['on_demand']['pending'] and a['gaf']['on_demand']['requests']==a['gaf']['on_demand']['triggers']==1 and a['gaf']['on_demand']['busy_reads']==926 and a['gaf']['on_demand']['completed_calculations']==0,
        correct_delay=p['disconnect_delay_ms']==1000 and p['runtime_readvertise'] is True,
        bounded_execution=0<a['ticks']-a['start_ticks']<=2000000000)
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,scenario_passed=False,checks=checks,elapsed_virtual_nanoseconds=a['ticks']-a['start_ticks'],scope='verified simulator power-write boundary, not firmware failure or reconnect success',reconnection_executed=False,physical_access=False,e14_complete=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);p.add_argument('--expect-power-boundary',action='store_true');a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve saved audits')
    r=(verify_power_boundary if a.expect_power_boundary else verify)(a.simulator,a.capture,a.output);print(json.dumps(dict(passed=r['passed'],checks=len(r['checks']),scenario_passed=r.get('scenario_passed',True),e14_complete=False)))


if __name__=='__main__':main()
