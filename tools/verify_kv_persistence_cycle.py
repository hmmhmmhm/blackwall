"""Audit original ARM kvTime write -> retained NOR -> fresh-reset read."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct
from kvtime_layout import discover
from pinned_main import MAIN_LAYOUT
from runtime_firmware_candidate import PROFILES
from run_runtime_connection_m55 import inspect


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log_value(path,prefix):
    values=[json.loads(x.split(' ',1)[1]) for x in path.read_text().splitlines() if x.startswith(prefix+' ')]
    if len(values)!=1:raise ValueError('Missing or duplicated '+prefix)
    return values[0]


def validate_capture(path):
    for name,expected in json.loads((path/'capture-files.json').read_text())['files'].items():
        target=path/name
        if not target.resolve().is_relative_to(path.resolve()) or digest(target)!=expected:
            raise ValueError('Capture pin differs: '+name)


def verify_case(s,case,audit_output):
    writer=s/'runtime-kv-commit-native-01'/case;reader=s/'runtime-kv-retained-restart-02'/case
    validate_capture(writer);validate_capture(reader)
    p=json.loads((writer/'connection-profile.json').read_text())
    raw=(writer/'main.bin').read_bytes();layout=discover(raw,p)
    verdict=inspect(writer,audit_output)
    if digest(writer/'main.bin')!=MAIN_LAYOUT[PROFILES[case]][3]:raise ValueError('Not an original main')
    if (reader/'main.bin').read_bytes()!=raw:raise ValueError('Restart firmware changed')
    n=log_value(writer/'renode.log','BLACKWALL_RUNTIME_NOR_COMMIT')
    if n!=json.loads((writer/'exports/nor-commit.json').read_text()):raise ValueError('NOR report/log differ')
    before=(writer/'exports/nor-before-kv-nv.bin').read_bytes();after=(writer/'exports/nor-after-kv-nv.bin').read_bytes()
    ram=(writer/'exports/connection-sram.bin').read_bytes()
    record=ram[layout['record']-0x20000000:layout['record']-0x20000000+12]
    expected=struct.pack('<IIbB',3,p['service']['timestamp'],p['service']['zone'],0)
    expected+=struct.pack('<H',binascii.crc_hqx(expected,0xffff))
    locations=[i for i in range(len(after)) if after.startswith(expected,i)]
    if len(locations)!=1:raise ValueError('Ambiguous committed payload')
    location=locations[0];header=after[location-30:location-6]
    if len(header)!=24:raise ValueError('Truncated FlashDB header')
    changed=[i for i,(x,y) in enumerate(zip(before,after)) if x!=y]
    imported=log_value(reader/'renode.log','BLACKWALL_RETAINED_IMPORT')
    r=log_value(reader/'renode.log','BLACKWALL_RUNTIME_KV_RESTART')
    if r!=json.loads((reader/'exports/restart.json').read_text()):raise ValueError('Restart report/log differ')
    meta=json.loads((reader/'restart-source.json').read_text())
    reboot_ram=(reader/'exports/restart-sram.bin').read_bytes()
    initial=(reader/'exports/fresh-sram-before-cpu.bin').read_bytes()
    old=(s/'kvtime-persistent-research-01/before-renode-mspi1-pio.cs').read_text()
    new=(s/'kvtime-persistent-research-01/after-renode-mspi1-pio.cs').read_text()
    model=(writer/'strict.cs').read_text()
    checks=dict(
        original_writer_contract=verdict['passed'],writer_record=record==expected,
        completed_programs=n['after']['program_starts']-n['before']['program_starts']==n['after']['program_completions']-n['before']['program_completions']==7,
        committed_bytes=n['after']['program_bytes']-n['before']['program_bytes']==42,
        no_pending_or_erase=not n['after']['program_busy'] and not n['after']['erase_busy'] and n['after']['erase_completions']==n['before']['erase_completions'],
        bounded_bit_transitions=len(before)==len(after)==0x40000 and len(changed)==37 and all(i<0x38000 and before[i]&after[i]==after[i] for i in changed),
        nv_neighbor_preserved=before[0x38000:]==after[0x38000:],
        littlefs_neighbor_preserved=(writer/'exports/nor-before-littlefs.bin').read_bytes()==(writer/'exports/nor-after-littlefs.bin').read_bytes(),
        new_key_and_payload=before.find(expected)<0 and after[location-6:location]==b'kvTime',
        flashdb_header=header[4:8]==b'KV00' and struct.unpack_from('<I',header,8)[0]==42 and header[16]==6 and struct.unpack_from('<I',header,20)[0]==12,
        flashdb_crc32=struct.unpack_from('<I',header,12)[0]==binascii.crc32(header[16:24]+b'kvTime'+expected)&0xffffffff,
        record_crc16=struct.unpack_from('<H',record,10)[0]==binascii.crc_hqx(record[:10],0xffff),
        separate_fresh_cpu=imported==dict(cpu_instructions=0,sram_unchanged=True,windows=2),
        initial_volatile_fill=initial==(reader/'sram-fill.bin').read_bytes() and initial==(writer/'sram-fill.bin').read_bytes(),
        only_committed_images_retained=meta['retained'] and not meta['previous_guest_sram_imported'] and meta['source_capture_sha256']==digest(writer/'capture-files.json'),
        kv_image_exact=digest(reader/'retained-kv-nv.bin')==digest(writer/'exports/nor-after-kv-nv.bin')==meta['retained_inputs']['retained-kv-nv.bin'],
        littlefs_image_exact=digest(reader/'retained-littlefs.bin')==digest(writer/'exports/nor-after-littlefs.bin')==meta['retained_inputs']['retained-littlefs.bin'],
        importer_only_model_change=model.count(old)==1 and model.replace(old,new)==(reader/'strict.cs').read_text(),
        original_reset_read=bytes(r['record'])==expected and reboot_ram[layout['record']-0x20000000:layout['record']-0x20000000+12]==expected and r['array_reads']>0 and r['snapshot_loaded'],
        no_architectural_fault=r['cfsr']==r['hfsr']==r['memory_violations']==0)
    return dict(case=case,passed=all(checks.values()),checks=checks,expected_record=expected.hex(),
                physical_payload_address=0x1fc0000+location,main_sha256=digest(writer/'main.bin'),layout=layout,
                later_boot_reached_hold=r['held'],later_boot_pc=r['pc'],full_boot_complete=False,
                writer_capture_sha256=digest(writer/'capture-files.json'),reader_capture_sha256=digest(reader/'capture-files.json'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--case',action='append',choices=['stock24','stock23','cfw']);a=p.parse_args()
    a.output.mkdir(mode=0o700,parents=True,exist_ok=False);cases=a.case or ['stock24','stock23','cfw']
    rows=[verify_case(a.simulator,c,a.output/(c+'-writer-audit')) for c in cases]
    report=dict(passed=all(r['passed'] for r in rows),cases=rows,all_originals_verified=cases==['stock24','stock23','cfw'],
                scope='kvTime persistence; later boot, runtime reset and interrupted writes remain incomplete',native_rerun=False,hardware_accessed=False)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],cases=len(rows),failed_checks={r['case']:[k for k,v in r['checks'].items() if not v] for r in rows})))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
