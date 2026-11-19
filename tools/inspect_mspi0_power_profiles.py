"""Verify saved natural MSPI0 power profiles and the next clock-write frontier."""
import argparse
import json
from pathlib import Path
from native_replay import MAIN_LAYOUT
from prepare_vendor_startup_candidate import sha
from run_native_candidate import memory_exports,validate_memory_exports,memory_export_policy,read_memory_snapshot
from inspect_ambiq_target import decode


def inspect(s,case,folder_name,audit_name,profile):
    folder=s/folder_name/case;audit=s/'mspi0-power-saved-audit-01'/audit_name/'report.json'
    a=json.loads(audit.read_text());v=json.loads((folder/'report.json').read_text());plan=json.loads((folder/'plan.json').read_text())
    if a.get('passed') is not True or not v['execution_passed'] or v['hardware_accessed']:raise ValueError('Unverified native capture')
    for name,h in a['capture_hashes'].items():
        if sha(folder/name)!=h:raise ValueError('Changed capture: '+name)
    if sha(folder/'main.bin')!=MAIN_LAYOUT[plan['cases'][case]][3]:raise ValueError('Changed original main')
    validate_memory_exports(folder,memory_exports(plan),v['memory_exports'])
    if read_memory_snapshot((folder/'renode.log').read_text(),memory_export_policy(plan),v['observed'])!=v.get('memory_snapshot'):
        raise ValueError('Changed snapshot metadata')
    d=v['diagnostics']
    if tuple(d[k] for k in ['accepted_commands','replies','vbus_status_reads'])!=(59,60,1):raise ValueError('Earlier startup history changed')
    if profile is None:
        old=json.loads((s/'vbus-status-main-01'/case/'report.json').read_text())
        if not v['control'] or d['mspi0_selected'] or v['observed']!=old['observed'] or v['selected_observation']!=old['selected_observation']:
            raise ValueError('Default missing-owner CPU/events changed')
        evidence=dict(source_cpu_events_exact=True)
    else:
        expected=('on',0x4000) if profile=='active' else ('stuck-off',0)
        if v['control'] or not d['mspi0_selected'] or tuple(d['mspi0_'+k] for k in ['requests','responses','request_word'])!=(1,1,0x4000) or (d['mspi0_phase'],d['mspi0_status_word'])!=expected:
            raise ValueError('Different power response history')
        o=v['observed'];pc=0x4e7040 if case=='stock24' else 0x4d9c6c;guards=[g for g in o['guards'] if g['accesses']]
        if o['pc']!=pc or len(guards)!=1:raise ValueError('Different native clock frontier')
        g=guards[0]
        if (g['name'],g['accesses'],g['address'],g['operation'],g['width'],g['value'])!=('guard',1,0x40004110,'write',4,0xa4210):
            raise ValueError('Different clock write')
        i=decode((folder/'main.bin').read_bytes(),pc,4)[0];regs=o['register_context']
        if (i.mnemonic,i.op_str)!=('str','r5, [r1]') or (regs['r1'],regs['r5'])!=(0x40004110,0xa4210):
            raise ValueError('Different original clock store')
        evidence=dict(profile=profile,status_word=d['mspi0_status_word'],clock_pc=pc,clock_address=0x40004110,clock_value=0xa4210,
                      power_off_or_fault_fallback_verified=False)
    return dict(case=case,capture=str(folder.relative_to(s)),report_sha256=sha(folder/'report.json'),audit_sha256=sha(audit),
                sram_sha256=sha(folder/'exports/sram-full.bin'),evidence=evidence)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Preserve private evidence')
    rows=[inspect(a.simulator,c,'mspi0-power-main-01',c,'active') for c in ['stock24','stock23','cfw']]
    rows += [inspect(a.simulator,'stock24','mspi0-power-stuck-01','stuck','stuck-off'),inspect(a.simulator,'stock24','mspi0-power-control-01','control',None)]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_captures=5,hardware_accessed=False,
        physical_power_verified=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('Verified MSPI0 native5: on/stuck-off continue to strict clock boundary; default CPU/events exact')


if __name__=='__main__':main()
