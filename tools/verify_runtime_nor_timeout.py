"""Audit real runtime NOR timeout returns, unchanged backing and a fresh reset.

The preserved GAF/CPU guards are not successful application recovery.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from inspect_nor_error_propagation import discover_chain
from pinned_main import MAIN_LAYOUT
from probe_runtime_nor_timeout import timeout_return_chain
from runtime_event_models import integrate_gaf
from runtime_firmware_candidate import PROFILES
from run_runtime_connection_m55 import inspect
from verify_kv_persistence_cycle import validate_capture, log_value


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def verify(s,audit,case='stock24'):
    if case not in ('stock24','stock23','cfw'):raise ValueError('Unknown original profile')
    source=s/'runtime-kv-commit-native-01'/case
    family=s/'runtime-nor-timeout-gaf-native-01' if case=='stock24' else s/'runtime-nor-timeout-gaf-peers-02'/case
    control=family/'control';fault=family/'fault'
    restart=s/('runtime-nor-timeout-gaf-restart-01' if case=='stock24' else 'runtime-nor-timeout-gaf-peer-restart-01')/case
    gaf_pc=0x58236c if case=='stock24' else 0x57b014
    reset_pc=0x4956e2 if case=='stock24' else 0x4897fa
    for cap in (source,control,fault,restart):validate_capture(cap)
    p=json.loads((control/'connection-profile.json').read_text())
    c,bodies=discover_chain((source/'main.bin').read_bytes(),(source/'exports/sram-full.bin').read_bytes(),p)
    fdb,part,adapter,nor,poll=bodies;sites=[x[-1].address for x in (poll,nor,adapter,part,fdb)]
    e=log_value(fault/'renode.log','BLACKWALL_RUNTIME_NOR_ERROR')
    off=log_value(control/'renode.log','BLACKWALL_RUNTIME_NOR_ERROR')
    n=log_value(fault/'renode.log','BLACKWALL_RUNTIME_NOR_COMMIT')
    r=log_value(fault/'renode.log','BLACKWALL_RUNTIME_CONNECTION')
    cr=json.loads((control/'exports/connection.json').read_text())
    original_report=json.loads((source/'exports/connection.json').read_text())
    cr_without_gaf={k:v for k,v in cr.items() if k!='imu_gaf'}
    old_component=(s/'kvtime-persistent-research-01/before-renode-mspi1-pio.cs').read_text()
    new_component=(s/'runtime-nor-timeout-research-01/after-renode-mspi1-pio.cs').read_text()
    model=(source/'strict.cs').read_text()
    if model.count(old_component)!=1:raise ValueError('Unknown source NOR composition')
    model,profile=integrate_gaf(s,model.replace(old_component,new_component))
    fault_runtime=(control/'run.py').read_text().replace('if False:g.Mspi1Config.Pio.HoldNextProgramCompletion()',
        'if True:g.Mspi1Config.Pio.HoldNextProgramCompletion()').replace('fault_requested=False','fault_requested=True')
    fn=log_value(restart/'renode.log','BLACKWALL_RUNTIME_KV_RESTART')
    imp=log_value(restart/'renode.log','BLACKWALL_RETAINED_IMPORT')
    meta=json.loads((restart/'restart-source.json').read_text())
    before=(fault/'exports/nor-before-kv-nv.bin').read_bytes()
    after=(fault/'exports/nor-after-kv-nv.bin').read_bytes()
    offset=c['layout']['record']-0x20000000
    old_record=(source/'exports/sram-full.bin').read_bytes()[offset:offset+12]
    new_record=(control/'exports/connection-sram.bin').read_bytes()[offset:offset+12]
    fault_record=(fault/'exports/connection-sram.bin').read_bytes()[offset:offset+12]
    live_rows=[row for row in e['rows'] if row[9]==1]
    gaf=r.get('imu_gaf',{})
    checks=dict(
        original_arm=sha(fault/'main.bin')==MAIN_LAYOUT[PROFILES[case]][3],
        normal_native_contract=inspect(control,audit/'control')['passed'],
        model_composition=model==(control/'strict.cs').read_text()==(fault/'strict.cs').read_text(),
        pinned_gaf=profile==p['gaf_profile']==json.loads((control/'gaf-profile.json').read_text()),
        runtime_diff_only_explicit_fault=fault_runtime==(fault/'run.py').read_text(),
        control_old_report_fields_exact=cr_without_gaf==original_report,
        control_sram_nor_exact=all((control/'exports'/name).read_bytes()==(source/'exports'/name).read_bytes()
            for name in ('sram-full.bin','connected-sram.bin','connection-sram.bin','nor-before-kv-nv.bin',
                         'nor-after-kv-nv.bin','nor-before-littlefs.bin','nor-after-littlefs.bin')),
        fault_initial_state_exact=all((control/'exports'/name).read_bytes()==(fault/'exports'/name).read_bytes()
            for name in ('sram-full.bin','connected-sram.bin','nor-before-kv-nv.bin','nor-before-littlefs.bin')),
        observer_same=(control/'activation.cs').read_bytes()==(fault/'activation.cs').read_bytes(),
        off_has_no_injection=not off['fault_requested'] and off['held_programs']==0 and not off['armed']
            and not off['program_busy'] and not off['overflow'] and off['app_returned'],
        one_real_held_program=e['fault_requested'] and e['held_programs']==1 and not e['armed']
            and e['program_busy'] and not e['overflow'],
        native_return_chain=timeout_return_chain(e) and [x[:3:2] for x in live_rows]==[
            [0,1],[1,4],[2,0],[3,0],[4,0]],
        actual_sites_and_thread=all(len(row)==10 and row[1]==sites[row[0]] and row[5]==p['service']['tcb']
            and row[6]&0x1ff==0 and row[7]==n['before']['program_starts']+1
            and row[8]==n['before']['program_completions'] for row in live_rows),
        real_wip_not_commit=n['after']['program_busy'] and n['after']['program_starts']-n['before']['program_starts']==1
            and n['after']['program_completions']==n['before']['program_completions']
            and n['after']['program_bytes']==n['before']['program_bytes'],
        nor_unchanged=before==after and (fault/'exports/nor-before-littlefs.bin').read_bytes()==(fault/'exports/nor-after-littlefs.bin').read_bytes(),
        no_erase=not n['after']['erase_busy'] and n['after']['erase_starts']==n['before']['erase_starts']
            and n['after']['erase_completions']==n['before']['erase_completions'],
        ram_is_not_durability=fault_record==new_record and new_record!=old_record and new_record not in after and old_record in after,
        no_app_return=not e['app_returned'] and not r['att']['stopped'] and not r['att']['returns'],
        actual_gaf_progress=gaf.get('fields')==41 and gaf.get('read_bytes')==153 and gaf.get('written_bytes')==225
            and gaf.get('clock_reads')==1,
        later_gaf_guard_preserved=r['pc']==gaf_pc and [(g['name'],g['accesses'],g['address']) for g in r['guards'] if g['accesses']]
            ==[('iom4',1,0x40054120)] and struct.pack('<I',r['att']['registers'][1]).hex()=='7c000402',
        no_architectural_fault=r['cfsr']==r['hfsr']==r['memory_violations']==0,
        reports_match_logs=e==json.loads((fault/'exports/nor-error.json').read_text())
            and n==json.loads((fault/'exports/nor-commit.json').read_text())
            and r==json.loads((fault/'exports/connection.json').read_text()),
        retained_exact=sha(restart/'retained-kv-nv.bin')==sha(fault/'exports/nor-after-kv-nv.bin')
            and sha(restart/'retained-littlefs.bin')==sha(fault/'exports/nor-after-littlefs.bin')
            and meta['source_capture_sha256']==sha(fault/'capture-files.json'),
        fresh_cpu_sram=imp==dict(cpu_instructions=0,sram_unchanged=True,windows=2)
            and not meta['previous_guest_sram_imported']
            and (restart/'exports/fresh-sram-before-cpu.bin').read_bytes()==(source/'sram-fill.bin').read_bytes(),
        fresh_model_no_runtime_fault=(restart/'strict.cs').read_bytes()==(fault/'strict.cs').read_bytes()
            and 'HoldNextProgramCompletion()' not in (restart/'run.py').read_text(),
        previous_record_read=bytes(fn['record'])==old_record
            and (restart/'exports/restart-sram.bin').read_bytes()[offset:offset+12]==old_record,
        reset_later_guard_preserved=not fn['held'] and fn['pc']==reset_pc
            and fn['cfsr']==fn['hfsr']==fn['memory_violations']==0,
        reset_report_matches_log=fn==json.loads((restart/'exports/restart.json').read_text()))
    if case!='stock24':
        reference=s/'runtime-kv-commit-native-01/stock24';validate_capture(reference)
        saved=(reference/'run.py').read_text();begin=saved.index('    def gaf_snapshot():\n')
        block=saved[begin:saved.index('    started_ticks=',begin)]
        controls=[json.loads((cap/'nor-error-source.json').read_text()) for cap in (control,fault)]
        checks['peer_diagnostic_source_pinned']=all(m.get('gaf_diagnostic_source_sha256')==sha(reference/'capture-files.json') for m in controls)
        checks['peer_diagnostic_code_exact']=all((cap/'run.py').read_text().count(block)==1
            and (cap/'run.py').read_text().count("    if p.get('gaf_profile'):result['imu_gaf']=gaf_snapshot()\n")==1 for cap in (control,fault))
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    return dict(passed=True,checks=checks,native_timeout_propagation_verified=True,
        layer_returns=[x[:3:2] for x in live_rows],backing_changed=False,
        attempted_ram_record=fault_record.hex(),retained_record=old_record.hex(),
        native_images=1,full_app_recovery_verified=False,full_boot_complete=False,
        e08_complete=False,hardware_accessed=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--case',choices=('stock24','stock23','cfw'),default='stock24');p.add_argument('--all-originals',action='store_true');a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    a.output.mkdir(mode=0o700,parents=True)
    if a.all_originals:
        rows=[dict(verify(a.simulator,a.output/c,c),case=c) for c in ('stock24','stock23','cfw')]
        report=dict(passed=True,cases=rows,native_images=3,native_timeout_propagation_verified=True,
                    full_app_recovery_verified=False,e08_complete=False,hardware_accessed=False)
    else:report=verify(a.simulator,a.output,a.case)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=sum(len(c['checks']) for c in report['cases']) if a.all_originals else len(report['checks']),native_timeout_propagation_verified=True)))


if __name__=='__main__':main()
