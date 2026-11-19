"""Audit declared power-profile changes separately from preserved legacy rejections."""
import argparse
import json
from pathlib import Path

from iom_shared_power_model import compose,board_profile
from probe_iom_shared_reconnect import POST
from run_runtime_connection_m55 import sha
from verify_kv_persistence_cycle import validate_capture
from verify_runtime_reconnect import verify as old_verify,verify_power_boundary


def read(p):return json.loads(p.read_text())


def rejection(call,expected,path):
    try:call()
    except ValueError as error:
        if error.args!=(expected,):raise
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        path.write_text(json.dumps(dict(preserved=True,failed=expected),indent=2)+'\n')
        return True
    raise ValueError('Legacy model contract unexpectedly accepted a changed power model')


def verify(s,root,out):
    on=root/'enabled';off=root/'disabled';ref=s/'runtime-readvertise-native-03/delayed'
    for cap in (on,off,ref):validate_capture(cap)
    parent=read(s/'runtime-readvertise-reconnect-research-01/manifest.json')
    for n in ('capture-files.json','main.bin','strict.cs','board.repl','run.py'):
        pin=parent['files'][str((ref/n).relative_to(s))]
        if sha(ref/n)!=pin['sha256'] or (ref/n).stat().st_size!=pin['bytes']:raise ValueError('Changed power baseline')
    legacy_on=rejection(lambda:old_verify(s,on,out/'legacy-on'),dict(only_declared_controller_change=False,only_explicit_board_option=False,runner_extension_exact=False),out/'legacy-on/rejection.json')
    legacy_off=rejection(lambda:verify_power_boundary(s,off,out/'legacy-off'),dict(exact_controller_change=False),out/'legacy-off/rejection.json')
    a=read(on/'exports/readvertising.json');b=read(on/'exports/reconnect.json');dc=read(on/'exports/disconnect.json')
    pa=read(on/'connection-profile.json');pb=read(off/'connection-profile.json')
    power=read(on/'exports/iom-shared-power.json');off_power=read(off/'exports/iom-shared-power.json')
    by_module={v['module']:v for v in power['powers']};disabled={v['module']:v for v in off_power['powers']}
    logs=[]
    for cap in (on,off):
        rows=[json.loads(l.split('BLACKWALL_IOM_SHARED_POWER ',1)[1]) for l in (cap/'renode.log').read_text().splitlines() if l.startswith('BLACKWALL_IOM_SHARED_POWER ')]
        logs.append(rows==[read(cap/'exports/iom-shared-power.json')])
    checks=dict(
        legacy_rejections_preserved=legacy_on and legacy_off,
        exact_power_model=all((cap/'strict.cs').read_text()==compose((ref/'strict.cs').read_text()) and read(cap/'connection-profile.json')['model_sha256']==sha(cap/'strict.cs') for cap in (on,off)),
        only_selected_board_change=(on/'board.repl').read_text()==board_profile((ref/'board.repl').read_text()) and (off/'board.repl').read_bytes()==(ref/'board.repl').read_bytes(),
        runner_extension_exact=all((cap/'run.py').read_text()==(ref/'run.py').read_text()+POST for cap in (on,off)),
        original_main_and_fill=all((cap/n).read_bytes()==(ref/n).read_bytes() for cap in (on,off) for n in ('main.bin','sram-fill.bin','itcm-fill.bin')),
        option_declared=pa['iom_shared_gate'] is True and pb['iom_shared_gate'] is False,
        enabled_prefix_entire_sram_exact=all((on/'exports'/n).read_bytes()==(ref/'exports'/n).read_bytes() for n in ('connection-sram.bin','disconnect-sram.bin')),
        disabled_entire_sram_exact=all((off/'exports'/n).read_bytes()==(ref/'exports'/n).read_bytes() for n in ('connection-sram.bin','disconnect-sram.bin','readvertising-sram.bin')),
        disabled_reports_exact=all(read(off/'exports'/n)==read(ref/'exports'/n) for n in ('connection.json','disconnect.json','readvertising.json','reconnect.json','frozen-peer-fault.json')),
        report_matches_logs=all(logs),
        selected_power_owners=sorted(by_module)==sorted(disabled)==[2,4,5,6,7] and all(v['selected'] for v in by_module.values()) and not any(v['selected'] for v in disabled.values()),
        active_hcpc_peer=by_module[4]['phase']=='on' and by_module[4]['request']==by_module[4]['status']==0x20,
        actual_local_gate=by_module[6]['phase']=='gated' and by_module[6]['request']==by_module[6]['status']==0 and by_module[6]['requests']>disabled[6]['requests'],
        real_resets_accounted=all(v['power_cycles']==v['device_power_downs'] for v in by_module.values()),
        disabled_original_blocker=disabled[6]['phase']=='off-requested' and disabled[6]['request']==0 and disabled[6]['status']==0x80,
        sensor_fault_not_bypassed=b['gaf']['on_demand']==dc['imu_gaf']['on_demand'] and b['gaf']['on_demand']['pending'] and b['gaf']['on_demand']['requests']==b['gaf']['on_demand']['triggers']==1 and b['gaf']['on_demand']['busy_reads']==926 and b['gaf']['on_demand']['completed_calculations']==0,
        explicit_virtual_delay=dc['delay']['fired'] and dc['delay']['milliseconds']==1000 and dc['delay']['fired_ticks']-dc['delay']['start_ticks']==1000000000,
        no_hardware_claim=all(v['hardware_accessed'] is False and v['physical_retention_verified'] is False for v in (power,off_power)))
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,original_reconnection_verified=True,legacy_on_other_checks_preserved=21,legacy_off_other_checks_preserved=9,
        rearm_virtual_nanoseconds=a['ticks']-a['start_ticks'],reconnect_virtual_nanoseconds=b['ticks']-a['ticks'],power=power,disabled_power=off_power,
        scope='stock24 original delayed1000ms disconnect/readvertise/reconnect with declared sensor frozen fault and shared-IOM profile',
        default_off_preserved=True,physical_retention_verified=False,normal_gaf_verified=False,e14_complete=False,hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('captures',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve previous audit')
    r=verify(a.simulator,a.captures,a.output);print(json.dumps(dict(passed=r['passed'],checks=len(r['checks']),delayed_reconnect=True,e14_complete=False)))


if __name__=='__main__':main()
