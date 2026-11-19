"""Audit non-FF erase timeout, observer contrasts, and fresh-process formatting."""
import argparse
import hashlib
import json
from pathlib import Path

from pinned_main import MAIN_LAYOUT
from inspect_nor_error_propagation import body
from runtime_event_models import integrate_gaf
from runtime_firmware_candidate import PROFILES
from verify_kv_persistence_cycle import validate_capture, log_value


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def verify(s,case='stock24'):
    if case not in ('stock24','stock23','cfw'):raise ValueError('Unknown original profile')
    root=s/'boot-nor-erase-native-01' if case=='stock24' else s/'boot-nor-erase-peers-01'/case
    source=s/'runtime-kv-commit-native-01'/case
    validate_capture(source)
    profile=json.loads((source/'connection-profile.json').read_text())
    hold_pc=profile['getter']
    busy_pc=0x4e8a46 if case=='stock24' else 0x4db672
    format_erases,format_programs={'stock24':(136,270),'stock23':(136,268),'cfw':(135,266)}[case]
    caps={name:root/name for name in ('control-off','control-on','fault','fault-off','restart')}
    for p in caps.values():validate_capture(p)
    reports={name:log_value(p/'renode.log','BLACKWALL_BOOT_ERASE') for name,p in caps.items()}
    native={name:log_value(p/'renode.log','BLACKWALL_REPORT') for name,p in caps.items()}
    meta={name:json.loads((p/'erase-source.json').read_text()) for name,p in caps.items()}
    c=caps['control-on'];f=caps['fault'];off=caps['fault-off'];re=caps['restart'];co=caps['control-off']
    ramp=bytes(range(256))*16+b'\xff'*(0x40000-4096)
    def data(p,phase,window):return (p/('exports/nor-'+phase+'-'+window+'.bin')).read_bytes()
    initial_sram=(c/'sram-fill.bin').read_bytes()
    normal=reports['control-on'];fault=reports['fault'];restart=reports['restart']
    healthy_diff=sum(x!=y for x,y in zip((c/'exports/erase-sram.bin').read_bytes(),(co/'exports/erase-sram.bin').read_bytes()))
    fault_diff=sum(x!=y for x,y in zip((f/'exports/erase-sram.bin').read_bytes(),(off/'exports/erase-sram.bin').read_bytes()))
    failure_guards=[g for g in native['fault']['guards'] if g['accesses']]
    fault_config=log_value(f/'renode.log','BLACKWALL_MSPI1_CONFIG')['registers']
    same_summary=lambda a,b:{k:v for k,v in a.items() if k not in ('rows','observer_completed')}=={k:v for k,v in b.items() if k not in ('rows','observer_completed')}
    normal_pairs=[[0,0],[1,0],[2,4096],[3,4096],[4,0]]
    failure_pairs=[[0,1],[1,4],[2,0],[3,0],[4,0]]
    checks=dict(
        original_main=all(sha(p/'main.bin')==MAIN_LAYOUT[PROFILES[case]][3] for p in caps.values()),
        model_same=all((p/'strict.cs').read_bytes()==(c/'strict.cs').read_bytes() for p in caps.values()),
        board_only_fault_toggle=all((p/'board.repl').read_text().replace('    completeSectorErase: false\n','    completeSectorErase: true\n')==(c/'board.repl').read_text() for p in caps.values()),
        explicit_fault_settings=all(meta[name]['fault']==(name in ('fault','fault-off')) for name in caps)
            and '    completeSectorErase: false\n' in (f/'board.repl').read_text()
            and '    completeSectorErase: true\n' in (re/'board.repl').read_text(),
        explicit_observer_settings=all(meta[name]['observe']==(name in ('control-on','fault','restart')) for name in caps),
        initial_pattern=data(c,'before','kv-nv')==data(f,'before','kv-nv')==ramp,
        non_ff_sector=sum(x!=255 for x in ramp[:4096])==4080,
        before_lfs_erased=all(x==255 for x in data(c,'before','littlefs')),
        pre_cpu_volatile_unchanged=all((p/'exports/fresh-sram-before-cpu.bin').read_bytes()==initial_sram for p in caps.values()),
        cpu_zero_import=all(log_value(p/'renode.log','BLACKWALL_ERASE_IMPORT')==dict(cpu_instructions=0,sram_unchanged=True,retained=(name=='restart')) for name,p in caps.items()),
        summaries_match_logs=all(reports[name]==json.loads((p/'exports/erase.json').read_text()) for name,p in caps.items()),
        primary_report_consistency=all(native[name]['pc']==reports[name]['pc'] and native[name]['memory_policy']['violations']==0 for name in caps),
        metadata_no_old_ram=all(not m['previous_guest_sram_imported'] for m in meta.values()),
        initial_images_match=all(sha(p/name)==expected and data(p,'before',name.removeprefix('initial-').removesuffix('.bin'))==(p/name).read_bytes()
            for label,p in caps.items() for name,expected in meta[label]['initial_images'].items()),
        execution_input_hashes=all((p/name).resolve().is_relative_to(p.resolve()) and sha(p/name)==expected
            for p in caps.values() for name,expected in json.loads((p/'connection-inputs.json').read_text()).items()),
        original_source_lineage=all(m['source_capture_sha256']==sha(source/'capture-files.json') for m in meta.values()),
        erase_source_contract=all(m['erase_contract_sha256']==sha(s/'nor-erase-propagation-01/report.json') for m in meta.values()),
        observed_normal_returns=[x[:3:2] for x in normal['rows']]==normal_pairs and normal['observer_completed'] and not normal['overflow'],
        observed_error_returns=[x[:3:2] for x in fault['rows']]==failure_pairs and fault['observer_completed'] and not fault['overflow'],
        actual_erase_counters=all(row[7:9]==[1,0] for row in fault['rows']) and all(row[7:9]==[1,1] for row in normal['rows']),
        actual_original_return_sites=all(row[1]==meta['fault']['return_sites'][row[0]] and row[6]&0x1ff==0 for row in fault['rows']),
        normal_boot_hold=all(reports[name]['held'] and reports[name]['pc']==hold_pc
            and reports[name]['erase_starts']==reports[name]['erase_completions']==format_erases
            and reports[name]['program_starts']==reports[name]['program_completions']==format_programs
            for name in ('control-off','control-on','restart')),
        fault_no_commit=all(reports[name]['erase_starts']==1 and reports[name]['erase_completions']==0
            and reports[name]['erase_busy'] and reports[name]['last_erase']==0x1fc0000
            and reports[name]['program_starts']==reports[name]['program_completions']==reports[name]['program_bytes']==0
            and not reports[name]['held'] for name in ('fault','fault-off')),
        fault_all_backing_preserved=all(data(p,'before',w)==data(p,'after',w) for p in (f,off) for w in ('kv-nv','littlefs')),
        fault_observer_ram_exact=(f/'exports/erase-sram.bin').read_bytes()==(off/'exports/erase-sram.bin').read_bytes(),
        fault_observer_nor_exact=all(data(f,phase,w)==data(off,phase,w) for phase in ('before','after') for w in ('kv-nv','littlefs')),
        fault_observer_summary_exact=same_summary(reports['fault'],reports['fault-off']),
        normal_observer_nor_exact=all(data(c,phase,w)==data(co,phase,w) for phase in ('before','after') for w in ('kv-nv','littlefs')),
        normal_observer_summary_exact=same_summary(normal,reports['control-off']),
        normal_sram_mismatch_preserved=healthy_diff==(270 if case=='stock24' else 0),
        actual_busy_read_guard=len(failure_guards)==1 and failure_guards[0]['name']=='guard_iom7_tail'
            and failure_guards[0]['operation']=='write' and failure_guards[0]['address']==0x40061000
            and failure_guards[0]['value']==0x100461 and failure_guards[0]['width']==4
            and fault_config['12']==0x6c and fault_config['8']==0x1fc1000 and native['fault']['pc']==busy_pc,
        unobserved_same_guard=[g for g in native['fault-off']['guards'] if g['accesses']]==failure_guards,
        normal_no_unsupported=all(not any(g['accesses'] for g in native[name]['guards']) for name in ('control-off','control-on','restart')),
        fresh_retained_images=all(sha(re/('initial-'+w+'.bin'))==sha(f/('exports/nor-after-'+w+'.bin'))
            and data(re,'before',w)==data(f,'after',w) for w in ('kv-nv','littlefs')),
        retained_lineage=meta['restart']['retained_source_sha256']==sha(f/'capture-files.json'),
        restart_formatted_same_nor=all(data(re,'after',w)==data(c,'after',w) for w in ('kv-nv','littlefs')),
        restart_same_sram=(re/'exports/erase-sram.bin').read_bytes()==(c/'exports/erase-sram.bin').read_bytes(),
        restart_same_first_returns=restart['rows']==normal['rows'],
        actual_data_changed_after_format=data(re,'after','kv-nv')!=ramp and data(re,'after','kv-nv')[4:8]==b'FDB0',
        no_architectural_fault=all(r['cfsr']==r['hfsr']==r['memory_violations']==0 for r in reports.values()))
    if case!='stock24':
        old=s/'kvtime-persistent-research-01/before-renode-mspi1-pio.cs'
        new=s/'runtime-nor-timeout-research-01/after-renode-mspi1-pio.cs'
        for path,manifest in ((old,s/'kvtime-persistent-manifest.json'),(new,s/'runtime-nor-timeout-research-01/manifest.json')):
            pin=json.loads(manifest.read_text())['files'][str(path.relative_to(s))]
            if path.stat().st_size!=pin['bytes'] or sha(path)!=pin['sha256']:raise ValueError('Changed NOR composition source')
        saved=(source/'strict.cs').read_text()
        if saved.count(old.read_text())!=1:raise ValueError('Unknown original NOR composition')
        expected_model,gaf=integrate_gaf(s,saved.replace(old.read_text(),new.read_text()))
        checks['pinned_source_model_composition']=all((p/'strict.cs').read_text()==expected_model for p in caps.values())
        contract=next(c for c in json.loads((s/'nor-erase-propagation-01/report.json').read_text())['cases'] if c['case']==case)
        raw=(source/'main.bin').read_bytes();chain=contract['chain']
        sites=[body(raw,chain[k],n)[-1].address for k,n in [('poll',0x60),('nor',0x110),('adapter',0x150),('part',0x50),('fdb',0x30)]]
        checks['source_decoded_return_sites']=all(m['return_sites']==sites for m in meta.values())
        checks['normal_observer_sram_exact']=checks.pop('normal_sram_mismatch_preserved')
        if case=='cfw':
            # Preserve the failed neutrality contract. A consistent mismatch is
            # evidence classification, never proof that hooks have no effect.
            checks.pop('fault_observer_ram_exact')
            checks['fault_sram_mismatch_preserved']=fault_diff==35
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,native_erase_timeout_returns=True,non_ff_preserved=True,
        fresh_formatter_reached_original_hold=True,observer_fault_sram_exact=fault_diff==0,
        observer_normal_sram_exact=healthy_diff==0,observer_normal_sram_differences=healthy_diff,
        observer_neutrality_unproven=healthy_diff!=0 or fault_diff!=0,native_images=1,e08_complete=False,full_boot_complete=False,
        existing_user_data_recovery_verified=False,physical_partial_erase_verified=False,hardware_accessed=False)
    if case=='cfw':
        report.update(observer_fault_sram_differences=fault_diff,
            unobserved_error_return_chain_verified=False,
            storage_result_observer_independent=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--case',choices=('stock24','stock23','cfw'),default='stock24');p.add_argument('--all-originals',action='store_true');a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    a.output.mkdir(mode=0o700,parents=True)
    if a.all_originals:
        rows=[dict(verify(a.simulator,c),case=c) for c in ('stock24','stock23','cfw')]
        report=dict(passed=True,cases=rows,native_images=3,native_erase_timeout_returns=True,
                    e08_complete=False,full_boot_complete=False,hardware_accessed=False)
    else:report=verify(a.simulator,a.case)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    exact=all(c['observer_normal_sram_exact'] for c in report['cases']) if a.all_originals else report['observer_normal_sram_exact']
    print(json.dumps(dict(passed=True,checks=sum(len(c['checks']) for c in report['cases']) if a.all_originals else len(report['checks']),observer_normal_sram_exact=exact)))


if __name__=='__main__':main()
