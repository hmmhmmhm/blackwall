"""Verify native VBUS status consumption, state bytes and strict power frontier."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha
from native_replay import MAIN_LAYOUT
from run_native_candidate import memory_exports,validate_memory_exports,memory_export_policy,read_memory_snapshot
from inspect_ambiq_target import decode


def inspect(s,case,folder_name,audit_name,expected):
    folder=s/folder_name/case;audit=s/'vbus-status-saved-audit-01'/audit_name/'report.json'
    reviewed=json.loads(audit.read_text());v=json.loads((folder/'report.json').read_text());p=json.loads((folder/'plan.json').read_text())
    if reviewed.get('passed') is not True or not v['execution_passed'] or v['hardware_accessed']:
        raise ValueError('Unverified saved capture')
    for name,h in reviewed['capture_hashes'].items():
        if sha(folder/name)!=h:raise ValueError('Changed capture: '+name)
    if sha(folder/'main.bin')!=MAIN_LAYOUT[p['cases'][case]][3]:raise ValueError('Changed original main')
    validate_memory_exports(folder,memory_exports(p),v['memory_exports'])
    if read_memory_snapshot((folder/'renode.log').read_text(),memory_export_policy(p),v['observed'])!=v.get('memory_snapshot'):
        raise ValueError('Changed snapshot metadata')
    d=v['diagnostics']
    if tuple(d[k] for k in ['accepted_commands','replies','advertising_commands_accepted','advertising_replies_consumed'])!=(59,60,5,5):
        raise ValueError('Earlier advertising history differs')
    if expected is None:
        old=json.loads((s/'advertising-peer-main-01'/case/'report.json').read_text())
        if not v['control'] or v['observed']!=old['observed'] or v['selected_observation']!=old['selected_observation']:
            raise ValueError('Default unknown CPU/events changed')
        if d['vbus_status_profile'] is not None or d['vbus_status_value']!=-1 or d['vbus_status_reads']!=0:
            raise ValueError('Default unknown status was supplied')
        evidence=dict(source_cpu_events_exact=True)
    else:
        profile='test-vbus-present' if expected else 'test-vbus-absent'
        if v['control'] or (d['vbus_status_profile'],d['vbus_status_value'],d['vbus_status_reads'])!=(profile,expected,1):
            raise ValueError('Different status read history')
        contract=s/'vbus-status-source-01/report.json';manifest=json.loads((s/'vbus-status-verification-01/manifest.json').read_text())
        if sha(contract)!=manifest['source_sha256']:raise ValueError('Changed original consumer contract')
        row=next(c for c in json.loads(contract.read_text())['cases'] if c['case']==case)
        ram=(folder/'exports/sram-full.bin').read_bytes();slot=row['state_byte']
        if ram[slot-0x20000000]!=expected:raise ValueError('Original consumer state differs from status')
        observed=v['observed'];pc=0x494d78 if case=='stock24' else 0x488e90
        guards=[g for g in observed['guards'] if g['accesses']]
        if observed['pc']!=pc or len(guards)!=1:raise ValueError('Different natural frontier')
        g=guards[0]
        if (g['name'],g['accesses'],g['address'],g['operation'],g['width'],g['value'])!=('guard',1,0x40021004,'write',4,0x4e00):
            raise ValueError('Different power request')
        instruction=decode((folder/'main.bin').read_bytes(),pc,2)[0];regs=observed['register_context']
        if (instruction.mnemonic,instruction.op_str)!=('str','r1, [r0]') or (regs['r0'],regs['r1'])!=(0x40021004,0x4e00):
            raise ValueError('Original store arguments differ')
        evidence=dict(state_byte_address=slot,state_byte=expected,pc=pc,next_address=0x40021004,next_value=0x4e00,
                      original_store_verified=True)
    return dict(case=case,capture=str(folder.relative_to(s)),report_sha256=sha(folder/'report.json'),
                audit_sha256=sha(audit),sram_sha256=sha(folder/'exports/sram-full.bin'),evidence=evidence)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Preserve private evidence')
    rows=[inspect(a.simulator,c,'vbus-status-main-01',c,0) for c in ['stock24','stock23','cfw']]
    rows+=[inspect(a.simulator,'stock24','vbus-status-present-01','present',1),inspect(a.simulator,'stock24','vbus-status-control-01','control',None)]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_captures=5,hardware_accessed=False,
        physical_vbus_verified=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('Verified native5: status read and original state 0/1, default unknown CPU/events exact')


if __name__=='__main__':main()
