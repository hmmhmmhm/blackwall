"""Audit a real guest write paused before FlashDB status commit and fresh restart."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct

from kvtime_layout import discover
from verify_kv_persistence_cycle import validate_capture, log_value
from run_runtime_connection_m55 import inspect


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(s, audit, phase='before-valid-status'):
    if phase not in ('before-valid-status','before-old-retire'):
        raise ValueError('Unknown program boundary')
    stop=6 if phase=='before-valid-status' else 7
    base=s/'runtime-kv-commit-native-01/stock24'
    control=s/'nor-program-cut-native-01/control'
    cut=s/'nor-program-cut-native-01'/phase
    restart=s/('nor-program-cut-restart-01' if stop==6 else 'nor-program-retire-restart-01')/'stock24'
    for p in (base,control,cut,restart):validate_capture(p)
    profile=json.loads((base/'connection-profile.json').read_text())
    raw=(base/'main.bin').read_bytes();layout=discover(raw,profile)
    cp=log_value(control/'renode.log','BLACKWALL_PROGRAM_CUT')
    tp=log_value(cut/'renode.log','BLACKWALL_PROGRAM_CUT')
    n=log_value(cut/'renode.log','BLACKWALL_RUNTIME_NOR_COMMIT')
    r=log_value(restart/'renode.log','BLACKWALL_RUNTIME_KV_RESTART')
    imp=log_value(restart/'renode.log','BLACKWALL_RETAINED_IMPORT')
    normal=(control/'exports/nor-after-kv-nv.bin').read_bytes()
    partial=(cut/'exports/nor-after-kv-nv.bin').read_bytes()
    before=(cut/'exports/nor-before-kv-nv.bin').read_bytes()
    expected=bytearray(normal)
    # These are two observed single-byte FlashDB state transitions, not a
    # hypothetical bit tear of the last program. Both are still uncommitted.
    expected[0x82]=0x1f
    if stop==6:expected[0x245]=0x7f
    offset=layout['record']-0x20000000
    initial=(base/'exports/sram-full.bin').read_bytes()[offset:offset+12]
    record=struct.pack('<IIbB',3,profile['service']['timestamp'],profile['service']['zone'],0)
    record+=struct.pack('<H',binascii.crc_hqx(record,0xffff))
    selected=initial if stop==6 else record
    meta=json.loads((restart/'restart-source.json').read_text())
    checks=dict(
        control_original_contract=inspect(control,audit/'control')['passed'],
        model_main_and_initial_inputs_unchanged=all((p/name).read_bytes()==(base/name).read_bytes()
            for p in (control,cut) for name in ('main.bin','strict.cs','board.repl','sram-fill.bin','itcm-fill.bin')),
        control_reports_exact=all(json.loads((control/'exports'/name).read_text())==json.loads((base/'exports'/name).read_text())
            for name in ('connection.json','nor-commit.json')),
        control_ram_and_nor_exact=all((control/'exports'/name).read_bytes()==(base/'exports'/name).read_bytes()
            for name in ('sram-full.bin','connected-sram.bin','connection-sram.bin','nor-before-kv-nv.bin',
                         'nor-after-kv-nv.bin','nor-before-littlefs.bin','nor-after-littlefs.bin')),
        cut_initial_ram_exact=all((control/'exports'/name).read_bytes()==(cut/'exports'/name).read_bytes()
            for name in ('sram-full.bin','connected-sram.bin','nor-before-kv-nv.bin','nor-before-littlefs.bin')),
        program_prefix_exact=tp['rows']==cp['rows'][:stop] and [x[:3] for x in cp['rows']]==[
            [1,0,0],[2,1,1],[3,2,2],[4,3,22],[5,4,28],[6,5,40],[7,6,41]],
        actual_wip_pause=tp['stopped'] and tp['paused'] and not tp['app_returned'] and tp['stop_program']==stop
            and tp['pc']==tp['rows'][-1][4] and all(row[5]==1 for row in tp['rows']),
        uncommitted_program=n['after']['program_busy'] and n['after']['program_starts']-n['before']['program_starts']==stop
            and n['after']['program_completions']-n['before']['program_completions']==stop-1
            and n['after']['program_bytes']-n['before']['program_bytes']==(40 if stop==6 else 41),
        no_erase_during_selected_write=not n['after']['erase_busy'] and n['after']['erase_starts']==n['before']['erase_starts']
            and n['after']['erase_completions']==n['before']['erase_completions'],
        exact_durable_state=partial==bytes(expected) and normal[0x82]==0x0f and normal[0x245]==0x3f,
        complete_payload=partial[0x263:0x26f]==normal[0x263:0x26f]==record,
        kv_writes_bounded=all(i<0x38000 and x&y==y for i,(x,y) in enumerate(zip(before,partial)) if x!=y),
        nv_neighbor_unchanged=before[0x38000:]==partial[0x38000:],
        littlefs_neighbor_unchanged=(cut/'exports/nor-before-littlefs.bin').read_bytes()==(cut/'exports/nor-after-littlefs.bin').read_bytes(),
        nor_reports_match_log=n==json.loads((cut/'exports/nor-commit.json').read_text()),
        cut_report_matches_log=tp==json.loads((cut/'exports/program-cut.json').read_text()),
        retained_only_committed_bytes=sha(restart/'retained-kv-nv.bin')==sha(cut/'exports/nor-after-kv-nv.bin')
            and sha(restart/'retained-littlefs.bin')==sha(cut/'exports/nor-after-littlefs.bin')
            and meta['source_capture_sha256']==sha(cut/'capture-files.json') and not meta['previous_guest_sram_imported'],
        reset_original_main=(restart/'main.bin').read_bytes()==raw,
        fresh_sram=(restart/'exports/fresh-sram-before-cpu.bin').read_bytes()==(base/'sram-fill.bin').read_bytes(),
        cpu_zero_import=imp==dict(cpu_instructions=0,sram_unchanged=True,windows=2),
        old_value_preexists_in_nor=initial in before and initial in partial,
        selected_record=bytes(r['record'])==selected and initial!=record
            and (restart/'exports/restart-sram.bin').read_bytes()[offset:offset+12]==selected,
        restart_report_matches_log=r==json.loads((restart/'exports/restart.json').read_text()),
        architectural_faults_absent=r['cfsr']==r['hfsr']==r['memory_violations']==0,
        later_failure_preserved=not r['held'] and r['pc']==0x4956e2)
    # Keep the existing pre-commit report stable for saved audits.
    checks={('complete_payload_not_status_committed' if stop==6 else 'complete_payload_status_committed') if k=='complete_payload'
            else ('old_record_selected' if stop==6 else 'new_record_selected') if k=='selected_record' else k:v
            for k,v in checks.items()}
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,old_record=initial.hex(),pending_record=record.hex(),
        cut_program=stop,completed_before_cut=stop-1,bytes_committed_before_cut=40 if stop==6 else 41,
        restart_later_pc=r['pc'],full_boot_complete=False,e08_complete=False,
        physical_power_cut=False,persistence_model='atomic program completion; pending operation discarded in fresh process',
        observer_neutrality='fixed control reports and full SRAM/NOR checkpoints only',hardware_accessed=False)
    if stop==7:
        report['committed_record']=report.pop('pending_record')
        report['selected_record']=selected.hex()
    return report


def verify_pair(s, audit):
    pre=verify(s,audit/'before','before-valid-status')
    post=verify(s,audit/'after','before-old-retire')
    a=s/'nor-program-cut-native-01/before-valid-status'
    b=s/'nor-program-cut-native-01/before-old-retire'
    left=(a/'exports/nor-after-kv-nv.bin').read_bytes()
    right=(b/'exports/nor-after-kv-nv.bin').read_bytes()
    diff=[dict(offset=i,before=x,after=y) for i,(x,y) in enumerate(zip(left,right)) if x!=y]
    checks=dict(single_commit_byte=diff==[dict(offset=0x245,before=0x7f,after=0x3f)],
        only_zero_bit_programmed=left[0x245]&right[0x245]==right[0x245],
        selected_value_changes=pre['old_record']!=post['selected_record'],
        payload_unchanged=pre['pending_record']==post['committed_record'])
    if not all(checks.values()):raise ValueError(checks)
    return dict(passed=True,cases=[pre,post],checks=checks,nor_diff=diff,
        scope='stock24 atomic completion boundary pair; no full application recovery',
        e08_complete=False,hardware_accessed=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--phase',choices=('before-valid-status','before-old-retire','both'),default='before-valid-status');a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    a.output.mkdir(mode=0o700,parents=True)
    report=verify_pair(a.simulator,a.output) if a.phase=='both' else verify(a.simulator,a.output,a.phase)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(report['checks']),
        selected_record=report.get('selected_record',report.get('old_record')),
        cases=len(report.get('cases',[])))))


if __name__=='__main__':main()
