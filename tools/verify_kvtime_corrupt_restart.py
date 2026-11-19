"""Audit damaged-NOR inputs and classify original main's observed record.

An accepted damaged record is an observation, not a successful recovery claim.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct

from kvtime_layout import discover
from pinned_main import MAIN_LAYOUT
from runtime_firmware_candidate import PROFILES
from verify_kv_persistence_cycle import validate_capture, log_value


def inspect_capture(s, capture):
    validate_capture(capture)
    p=json.loads((capture/'connection-profile.json').read_text())
    case=p['case'];source=s/'runtime-kv-commit-native-01'/case
    baseline=s/'runtime-kv-retained-restart-02'/case
    validate_capture(source);validate_capture(baseline)
    meta=json.loads((capture/'restart-source.json').read_text())
    damage=meta['synthetic_damage_fixture'];mode=damage['mode']
    original=(source/'exports/nor-after-kv-nv.bin').read_bytes()
    damaged=(capture/'retained-kv-nv.bin').read_bytes()
    index=damage['record_offset'];header=index-30
    expected=bytearray(original)
    if mode in ('bad-container-crc','bad-record-crc'):
        expected[index+4]^=1
    elif mode in ('future-record-type','future-record-version'):
        expected[index]=4
        struct.pack_into('<H',expected,index+10,binascii.crc_hqx(expected[index:index+10],0xffff))
    else:
        raise ValueError('Unknown fixture')
    if mode!='bad-container-crc':
        struct.pack_into('<I',expected,header+12,binascii.crc32(expected[header+16:index+12])&0xffffffff)
    r=log_value(capture/'renode.log','BLACKWALL_RUNTIME_KV_RESTART')
    imported=log_value(capture/'renode.log','BLACKWALL_RETAINED_IMPORT')
    raw=(capture/'main.bin').read_bytes();layout=discover(raw,p)
    offset=layout['record']-0x20000000
    fresh=(capture/'exports/fresh-sram-before-cpu.bin').read_bytes()
    ram=(capture/'exports/restart-sram.bin').read_bytes()
    initial=(source/'exports/sram-full.bin').read_bytes()[offset:offset+12]
    fallback=bytearray(initial);fallback[0]=3
    struct.pack_into('<H',fallback,10,binascii.crc_hqx(fallback[:10],0xffff))
    record=bytes(r['record'])
    choices={'damaged_record_loaded':damaged[index:index+12],
             'original_saved_record_loaded':original[index:index+12],
             'initial_record_retained':initial,'initial_record_rewritten_type3':bytes(fallback)}
    outcomes=[name for name,value in choices.items() if value==record]
    baseline_runtime=(baseline/'run.py').read_text()
    for address in (layout['record'],layout['state']):
        baseline_runtime=baseline_runtime.replace('b.ReadBytes('+hex(address)+',',
                                                  'b.ReadBytes('+str(address)+',')
    expected_model=(baseline/'strict.cs').read_text()
    expected_profile=json.loads((baseline/'connection-profile.json').read_text())
    if (capture/'strict.cs').read_text()!=expected_model:
        # Accept only the closed bw389 default-off NOR change, never whatever
        # model happens to be in the current worktree.
        versions=[]
        for manifest_path,relative in [
                (s/'kvtime-persistent-manifest.json','kvtime-persistent-research-01/after-renode-mspi1-pio.cs'),
                (s/'runtime-nor-timeout-research-01/manifest.json','runtime-nor-timeout-research-01/after-renode-mspi1-pio.cs')]:
            pin=json.loads(manifest_path.read_text())['files'][relative];path=s/relative
            if path.stat().st_size!=pin['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=pin['sha256']:
                raise ValueError('Changed declared NOR component')
            versions.append(path.read_text())
        before,after=versions
        if expected_model.count(before)!=1:raise ValueError('Unknown baseline NOR composition')
        expected_model=expected_model.replace(before,after)
        if meta['changed_component_after']!=hashlib.sha256(after.encode()).hexdigest():
            raise ValueError('Undeclared NOR upgrade')
        expected_profile['model_sha256']=hashlib.sha256(expected_model.encode()).hexdigest()
    checks=dict(original_main=hashlib.sha256(raw).hexdigest()==MAIN_LAYOUT[PROFILES[case]][3],
        original_firmware_and_runtime=all((capture/name).read_bytes()==(baseline/name).read_bytes()
            for name in ('main.bin','sram-fill.bin','itcm-fill.bin'))
            and (capture/'run.py').read_text()==baseline_runtime
            and (capture/'strict.cs').read_text()==expected_model and p==expected_profile,
        exact_declared_damage=damaged==bytes(expected),
        change_offsets=damage['changed_offsets']==[i for i,(x,y) in enumerate(zip(original,damaged)) if x!=y],
        base_hash=damage['base_sha256']==hashlib.sha256(original).hexdigest(),
        changed_hash=damage['input_sha256']==meta['retained_inputs']['retained-kv-nv.bin']==hashlib.sha256(damaged).hexdigest(),
        source_capture=meta['source_capture_sha256']==hashlib.sha256((source/'capture-files.json').read_bytes()).hexdigest(),
        other_nor_unchanged=(capture/'retained-littlefs.bin').read_bytes()==(baseline/'retained-littlefs.bin').read_bytes(),
        fresh_sram=fresh==(source/'sram-fill.bin').read_bytes(),
        cpu_zero_import=imported==dict(cpu_instructions=0,sram_unchanged=True,windows=2),
        no_previous_sram=not meta['previous_guest_sram_imported'] and not damage['previous_sram_imported'],
        actual_read=r['snapshot_loaded'] and r['array_reads']>0,
        actual_ram_matches=ram[offset:offset+12]==record,
        report_matches_log=r==json.loads((capture/'exports/restart.json').read_text()),
        no_architectural_fault=r['cfsr']==r['hfsr']==r['memory_violations']==0,
        explicit_classification=len(outcomes)==1)
    if not all(checks.values()):
        raise ValueError({k:v for k,v in checks.items() if not v})
    return dict(case=case,mode=mode,passed=True,checks=checks,outcome=outcomes[0],record=record.hex(),
        saved_record=original[index:index+12].hex(),damaged_record=damaged[index:index+12].hex(),
        container_crc_valid=struct.unpack_from('<I',damaged,header+12)[0]==binascii.crc32(damaged[header+16:index+12])&0xffffffff,
        record_crc_valid=struct.unpack_from('<H',damaged,index+10)[0]==binascii.crc_hqx(damaged[index:index+10],0xffff),
        later_boot_pc=r['pc'],full_boot_complete=bool(r['held']),
        capture_sha256=hashlib.sha256((capture/'capture-files.json').read_bytes()).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path)
    p.add_argument('output',type=Path);p.add_argument('captures',type=Path,nargs='+');a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve previous audit')
    rows=[inspect_capture(a.simulator,c) for c in a.captures]
    a.output.mkdir(mode=0o700,parents=True)
    report=dict(passed=True,cases=rows,hardware_accessed=False,e08_complete=False,
        power_cut_durability_verified=False,write_failure_verified=False)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([dict(mode=r['mode'],outcome=r['outcome'],checks=len(r['checks'])) for r in rows]))


if __name__=='__main__':main()
