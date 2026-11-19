"""Audit the unchanged original delayed path and its IOM6 shared-domain blocker."""
import argparse
import json
from pathlib import Path

from probe_reconnect_power import POST
from run_runtime_connection_m55 import sha
from verify_kv_persistence_cycle import validate_capture
from pinned_main import MAIN_LAYOUT
from runtime_firmware_candidate import PROFILES


def read(p):return json.loads(p.read_text())


def verify(s,cap,research,out):
    ref=s/'runtime-readvertise-native-03/delayed';validate_capture(cap);validate_capture(ref)
    parent=read(s/'runtime-readvertise-reconnect-research-01/manifest.json')
    for n in ('capture-files.json','main.bin','strict.cs'):
        pin=parent['files'][str((ref/n).relative_to(s))]
        if sha(ref/n)!=pin['sha256'] or (ref/n).stat().st_size!=pin['bytes']:raise ValueError('Changed predecessor')
    a=read(cap/'exports/reconnect-power.json');stage=read(cap/'exports/readvertising.json')
    lines=[json.loads(l.split('BLACKWALL_RECONNECT_POWER ',1)[1]) for l in (cap/'renode.log').read_text().splitlines() if l.startswith('BLACKWALL_RECONNECT_POWER ')]
    iom={v['module']:v for v in a['ioms']};powers=a['uarts']+a['ioms']+[v for v in a['extras'].values() if v is not None]
    request=a['gpu_request']|a['adc_request']
    for v in powers:request|=v['request']
    changed=[v for v in powers if a['proposed']&v['mask']!=v['request']]
    source=s/'mspi1-source-research-01';pins=read(source/'sources.json')
    for name in ('am_hal_pwrctrl.c','am_hal_pwrctrl.h','apollo510.h'):
        if sha(source/name)!=next(v['sha256'] for v in pins['files'] if v['path'].endswith('/'+name)):raise ValueError('Changed power source')
    helper=read(research/'source-report.json');expected=[]
    for case in ('stock24','stock23','cfw'):
        raw=s/'runtime-att-acceptance-native-01'/case/'main.bin'
        if sha(raw)!=MAIN_LAYOUT[PROFILES[case]][3]:raise ValueError('Not the original helper binary')
        for module in range(8):
            own=1<<(module+1);group=0x1e if module<4 else 0x1e0;peer=1<<((module//4*4+(module+1)%4)+1);other=0x20 if module<4 else 2
            for enabled in (0,own,peer,own|peer,other,0x200):expected.append((case,module,module+3,enabled,group,0 if enabled&group and not enabled&own else 1))
    actual=[(v['case'],v['module'],v['native_enum'],v['enabled'],v['group'],v['return_value']) for v in helper['rows']]
    checks=dict(
        model_and_inputs_unchanged=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('strict.cs','main.bin','board.repl','sram-fill.bin','itcm-fill.bin')),
        observation_only_after_stop=(cap/'run.py').read_text()==(ref/'run.py').read_text()+POST,
        original_entire_sram_exact=all((cap/'exports'/n).read_bytes()==(ref/'exports'/n).read_bytes() for n in ('connection-sram.bin','disconnect-sram.bin','readvertising-sram.bin')),
        original_report_values_exact=all(read(cap/'exports'/n)==read(ref/'exports'/n) for n in ('connection.json','disconnect.json','readvertising.json','reconnect.json','frozen-peer-fault.json')),
        report_matches_log=lines==[a],
        same_stopped_cpu=a['paused'] and a['pc']==stage['pc']==0x494d78 and a['registers']==stage['registers'],
        exact_request_delta=request==a['request_before']==0xe20 and a['proposed']==0xea0 and a['changed_mask']==request^a['proposed']==0x80,
        only_iom6_changes=len(changed)==1 and changed[0]==iom[6],
        iom6_pending_disable=iom[6]['mask']==0x80 and iom[6]['phase']=='off-requested' and iom[6]['request']==0 and iom[6]['status']==0x80 and iom[6]['off_profile']==0,
        iom4_holds_hcpc=iom[4]['mask']==0x20 and iom[4]['phase']=='on' and iom[4]['request']==iom[4]['status']==0x20 and a['buck_phase']=='active',
        uart_not_the_changed_domain=all(a['proposed']&v['mask']==v['request'] for v in a['uarts']),
        helper_matrix_original_144=helper['passed'] and helper['original_helper_runs']==len(actual)==144 and actual==expected and all(v['reads'] and set(v['reads'])=={0x40021004} for v in helper['rows']),
        fixed_source=helper['source_commit']==pins['commit']=='61b293a49db34030c545f99101f7ebf6a3050314',
        no_reconnect_claim=not read(cap/'exports/reconnect.json')['executed'] and stage['peer']['readvertising_commands']==0,
        no_hardware_access=a['hardware_accessed'] is False)
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,request_before=hex(request),request_after=hex(a['proposed']),changed_module='IOM6',shared_domain='HCPC (IOM4..7)',
        original_helper_executions=144,model_modified=False,scenario_passed=False,reconnection_executed=False,physical_retention_verified=False,
        scope='source-supported missing shared-domain lifecycle; no power behavior changed or delayed reconnect success',e14_complete=False,hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('research',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    r=verify(a.simulator,a.capture,a.research,a.output);print(json.dumps(dict(passed=r['passed'],checks=len(r['checks']),changed_module=r['changed_module'],scenario_passed=False)))


if __name__=='__main__':main()
