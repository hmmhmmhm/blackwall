"""Verify native module0 configuration, off-domain rejection and legacy control."""
import argparse,json
from pathlib import Path
from native_replay import MAIN_LAYOUT
from prepare_vendor_startup_candidate import sha
from run_native_candidate import memory_exports,validate_memory_exports,memory_export_policy,read_memory_snapshot
from inspect_ambiq_target import decode


def inspect(s,case,folder_name,audit_name,mode):
    f=s/folder_name/case;ap=s/'mspi0-config-saved-audit-01'/audit_name/'report.json';audit=json.loads(ap.read_text());v=json.loads((f/'report.json').read_text());p=json.loads((f/'plan.json').read_text())
    if audit.get('passed') is not True or not v['execution_passed'] or v['hardware_accessed']:raise ValueError('Unverified saved capture')
    for n,h in audit['capture_hashes'].items():
        if sha(f/n)!=h:raise ValueError('Changed capture: '+n)
    if sha(f/'main.bin')!=MAIN_LAYOUT[p['cases'][case]][3]:raise ValueError('Changed original main')
    validate_memory_exports(f,memory_exports(p),v['memory_exports'])
    if read_memory_snapshot((f/'renode.log').read_text(),memory_export_policy(p),v['observed'])!=v.get('memory_snapshot'):raise ValueError('Changed paused snapshot')
    d=v['diagnostics'];o=v['observed']
    if (d['accepted_commands'],d['replies'])!=(59,60):raise ValueError('Changed preceding BLE startup')
    if mode=='control':
        old=json.loads((s/'mspi0-power-main-01'/case/'report.json').read_text())
        if not v['control'] or d['mspi0_config_selected'] or o!=old['observed'] or v['selected_observation']!=old['selected_observation']:raise ValueError('Default CPU/events changed')
        detail=dict(source_cpu_events_exact=True)
    else:
        guards=[g for g in o['guards'] if g['accesses']]
        if len(guards)!=1 or guards[0]['name']!='guard_iom7_tail' or guards[0]['accesses']!=1 or guards[0]['width']!=4:raise ValueError('Different unsupported access')
        g=guards[0]
        if not d['mspi0_config_selected'] or not d['mspi0_clock_enabled']:raise ValueError('Missing selected module0 state')
        if mode=='active':
            pc=0x572bae if case=='stock24' else 0x555c5a
            if o['pc']!=pc or (g['address'],g['operation'],g['value'])!=(0x400602c0,'write',0):raise ValueError('Different queue initialization boundary')
            if (d['mspi0_config_reads'],d['mspi0_config_writes'],d['mspi0_clock_selection'],d['mspi0_phase'])!=(13,20,10,'on'):raise ValueError('Different configuration/clock history')
            i=decode((f/'main.bin').read_bytes(),pc,2)[0]
            if (i.mnemonic,i.op_str)!=('str','r0, [r3]') or (o['register_context']['r0'],o['register_context']['r3'])!=(0,0x400602c0):raise ValueError('Original queue-index store differs')
        else:
            if (g['address'],g['operation'])!=(0x40060090,'read'):raise ValueError('Off-domain access was not stopped')
            if (d['mspi0_config_reads'],d['mspi0_config_writes'],d['mspi0_clock_selection'],d['mspi0_phase'],d['mspi0_status_word'])!=(0,0,8,'stuck-off',0):raise ValueError('Off-domain configuration fabricated')
            i=decode((f/'main.bin').read_bytes(),o['pc'],2)[0]
            if o['pc']!=0x4e7186 or (i.mnemonic,i.op_str)!=('ldr','r5, [r4]') or o['register_context']['r4']!=0x40060090:raise ValueError('Original off-domain load differs')
        detail=dict(mode=mode,pc=o['pc'],address=g['address'],operation=g['operation'],value=g['value'],config_reads=d['mspi0_config_reads'],config_writes=d['mspi0_config_writes'],clock_selection=d['mspi0_clock_selection'])
    return dict(case=case,capture=str(f.relative_to(s)),report_sha256=sha(f/'report.json'),audit_sha256=sha(ap),sram_sha256=sha(f/'exports/sram-full.bin'),detail=detail)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Preserve private evidence')
    rows=[inspect(a.simulator,c,'mspi0-config-main-01',c,'active') for c in ['stock24','stock23','cfw']]
    rows += [inspect(a.simulator,'stock24','mspi0-config-stuck-01','stuck','stuck'),inspect(a.simulator,'stock24','mspi0-config-control-01','control','control')]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_captures=5,hardware_accessed=False,queue_execution_verified=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('Verified native5: module0 config 13 reads/20 writes, off-domain blocked, legacy CPU/events exact')


if __name__=='__main__':main()
