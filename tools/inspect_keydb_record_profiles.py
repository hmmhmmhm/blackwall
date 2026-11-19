"""Saved read-only keydb aperture: normal records, unknown/off, write prelude."""
import argparse,hashlib,json,struct
from pathlib import Path
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from run_native_candidate import memory_exports,validate_memory_exports

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def inspect(s,folder,case,an,kind):
    f=s/folder/case;r=json.loads((f/'report.json').read_text());p=json.loads((f/'plan.json').read_text());ap=s/'keydb-record-saved-audit-01'/an/'report.json';audit=json.loads(ap.read_text())
    if not r['execution_passed'] or not audit['passed'] or r['hardware_accessed']:raise ValueError('Unverified capture')
    for n,h in audit['capture_hashes'].items():
        if sha(f/n)!=h:raise ValueError('Changed saved capture '+n)
    validate_memory_exports(f,memory_exports(p),r['memory_exports']);d=r['diagnostics'];raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();guards=[g for g in r['observed']['guards'] if g['accesses']]
    if len(guards)!=1 or d['accepted_commands']!=2 or d['replies']!=2:raise ValueError('Different boundary/BLE history')
    evidence={}
    if kind=='zero':
        pc=r['observed']['pc'];ins=decode(raw,pc,2)[0];compare=decode(raw,pc+2,4)[0];load=decode(raw,pc-4,4)[0]
        if guards[0]['address']!=0x7fe000 or guards[0]['operation']!='read' or guards[0]['width']!=4 or ins.mnemonic!='ldr' or compare.op_str!='r0, #0x55555555' or literal(raw,load)!=0x7fe000:raise ValueError('Not the original separate OTA-marker load')
        expected=dict(keydb_profile='zero',keydb_backing=True,keydb_reads=2570,keydb_slots=10,keydb_data_reads=3160,keydb_data_bytes=3680,keydb_word_reads=70,keydb_byte_reads=2780,keydb_last_data_address=0x7ff9c3)
        if any(d[k]!=v for k,v in expected.items()):raise ValueError('Different backed-record read sequence')
        prior=s/p['source_root']/case;before=json.loads((prior/'report.json').read_text());base=before['observed']['register_context']['r5']
        if not 0x20000000<=base<=0x20380000-2000 or ram[base-0x20000000:base-0x20000000+2000]!=bytes(2000):raise ValueError('Different declared-empty DB RAM state')
        evidence=dict(marker_load_pc=pc,marker_address=0x7fe000,compared_constant=0x55555555,marker_value_provided=False,ram_database_base=base,ram_database_bytes=2000,ram_database_zero_at_snapshot=True,scope='Final zero RAM is not a complete write history or proof of every keydb operation')
    elif kind=='uninit':
        if not d['keydb_backing'] or d['keydb_reads']!=257 or d['keydb_slots']!=1 or d['keydb_data_reads']!=0 or guards[0]['address']!=0x40021014 or guards[0]['value']!=0x3f:raise ValueError('Uninit write path changed')
        evidence=dict(cache_write_preparation_blocked=True,actual_mram_program_executed=False)
    else:
        prior=json.loads((s/p['source_root']/case/'report.json').read_text())
        if d['keydb_backing'] or d['keydb_data_reads']!=0 or r['observed']!=prior['observed'] or r['selected_observation']!=prior['selected_observation']:raise ValueError('Legacy/default changed CPU or events')
        evidence=dict(source_cpu_events_exact=True)
    return dict(case=case,kind=kind,diagnostics=d,evidence=evidence,original_semantic_passed=r['semantic_validation']['passed'],reviewed_audit_passed=True,report_sha256=sha(f/'report.json'),audit_sha256=sha(ap))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve existing result')
    rows=[inspect(a.simulator,'keydb-record-zero-main-01',c,c,'zero') for c in ['stock24','stock23','cfw']]
    rows +=[inspect(a.simulator,'keydb-record-uninit-main-01','stock24','uninit','uninit'),inspect(a.simulator,'keydb-record-unknown-main-01','stock24','unknown','unknown'),inspect(a.simulator,'keydb-record-control-01','stock24','control','control')]
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_rerun=False,hardware_accessed=False,real_keys_or_ota_flag_known=False,mram_program_executed=False,whole_main_boot_verified=False,display_verified=False),indent=2)+'\n');print('saved keydb record profiles:6/6 passed')
if __name__=='__main__':main()
