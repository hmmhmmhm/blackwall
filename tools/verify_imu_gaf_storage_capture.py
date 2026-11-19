"""Verify saved natural-main bias writes; never execute firmware or access hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal


def verify(simulator, root):
    plan = json.loads((simulator / 'imu-gaf-storage-plan-04.json').read_text())
    component = plan['components'][0]
    model = (root / component['candidate']).read_text()
    baseline = (simulator / component['baseline']).read_text()
    assert hashlib.sha256(model.encode()).hexdigest() == component['after_sha256']
    assert hashlib.sha256(baseline.encode()).hexdigest() == component['before_sha256']
    prior_manifest = json.loads((simulator / 'imu-gaf-parameters-verification-01/manifest.json').read_text())
    results = []
    for case in plan['cases']:
        folder = simulator / 'imu-gaf-storage-main-02' / case
        prior = simulator / 'imu-gaf-parameters-main-01' / case
        report = json.loads((folder / 'report.json').read_text())
        assert report['passed'] and report['execution_passed'] and report['semantic_validation']['passed']
        raw = (folder / 'main.bin').read_bytes()
        assert raw == (prior / 'main.bin').read_bytes()
        strict = (folder / 'strict.cs').read_text()
        assert strict.count(model) == 1
        assert strict.replace(model, baseline) == (prior / 'strict.cs').read_text()
        binding = next(x for x in prior_manifest['cases'] if x['case'] == case)
        assert hashlib.sha256(raw).hexdigest() == binding['source_hash']
        returned = binding['calibration_lr'] & ~1
        vector_load = decode(raw, returned - 10, 4)[0]
        assert vector_load.mnemonic.startswith('ldr') and vector_load.op_str.startswith('r1, [pc,')
        vector_address = literal(raw, vector_load)
        ram = (prior / 'exports/sram-full.bin').read_bytes()
        vector = ram[vector_address - 0x20000000:vector_address - 0x20000000 + 12]
        assert len(vector) == 12 and vector == bytes(12)
        prefix = decode(raw, returned, 0x20)
        assert any(i.mnemonic == 'movw' and i.op_str == 'r1, #0xa2a2' for i in prefix)
        assert any(i.mnemonic == 'movs' and i.op_str == 'r2, #1' for i in prefix)
        shifted = struct.pack('<3i', *(v >> 5 for v in struct.unpack('<3i', vector)))
        writes = [(0x774, vector), (0x974, vector), (0x770, bytes(4)),
                  (0x76c, struct.pack('<I', 500000)), (0x780, shifted), (0x78c, shifted)]
        expected = '|'.join(f'{address + index:x}:{value:02x}'
                            for address, data in writes for index, value in enumerate(data))
        diagnostics = report['diagnostics']
        assert diagnostics['imu_gaf_history'] == expected
        assert diagnostics['imu_gaf_written_bytes'] == diagnostics['imu_gaf_write_transactions'] == 56
        assert diagnostics['imu_last_write'] == '7ca2a2'
        assert diagnostics['imu_service_completions'] == 2
        results.append(dict(case=case, written_bytes=56, transactions=56,
                            original_main_unchanged=True, only_imu_component_changed=True,
                            next_packet='7ca2a2', bias_vector_address=vector_address))
    off = json.loads((simulator / 'imu-gaf-storage-off-01/report.json').read_text())
    prior = json.loads((simulator / 'imu-gaf-parameters-main-01/stock24/report.json').read_text())
    assert off['passed'] and off['observed'] == prior['observed']
    assert off['selected_observation'] == prior['selected_observation']
    assert not off['diagnostics']['imu_gaf_enabled']
    assert off['diagnostics']['imu_gaf_written_bytes'] == 0
    return dict(passed=True, cases=results, disabled_cpu_events_exact=True,
                clock_register_value_verified=False, gaf_setter_native_verified=False,
                full_startup_verified=False, hardware_accessed=False)


def verify_clock(simulator, root):
    plan = json.loads((simulator / 'imu-clock-variation-plan-01.json').read_text())
    component = plan['components'][0]
    model = (root / component['candidate']).read_text()
    baseline = (simulator / component['baseline']).read_text()
    assert hashlib.sha256(model.encode()).hexdigest() == component['after_sha256']
    assert hashlib.sha256(baseline.encode()).hexdigest() == component['before_sha256']
    value = plan['clock_variation_byte']
    profile_path = root / 'docs/data/imu-gaf-default-profile.json'
    assert hashlib.sha256(profile_path.read_bytes()).hexdigest() == plan['gaf_profile_sha256']
    fields = json.loads(profile_path.read_text())['fields']
    values = {f['address']: (int({0: 1, 1: value, 4: 20000, 8: 40000}[f['offset']]).to_bytes(f['length'], 'little')
              if f['offset'] in (0, 1, 4, 8) else bytes.fromhex(f['bytes_le'])) for f in fields}
    source = json.loads((simulator / 'imu-parameter-full-setter-01/report.json').read_text())
    bindings = json.loads((simulator / 'imu-gaf-parameters-verification-01/manifest.json').read_text())['cases']
    result = []
    for case in plan['cases']:
        folder = simulator / 'imu-clock-variation-main-01' / case
        prior = simulator / 'imu-gaf-storage-main-02' / case
        report = json.loads((folder / 'report.json').read_text())
        assert report['passed'] and report['execution_passed'] and report['semantic_validation']['passed']
        raw = (folder / 'main.bin').read_bytes()
        binding = next(x for x in bindings if x['case'] == case)
        assert hashlib.sha256(raw).hexdigest() == binding['source_hash']
        assert raw == (prior / 'main.bin').read_bytes()
        strict = (folder / 'strict.cs').read_text()
        assert strict.count(model) == 1 and strict.replace(model, baseline) == (prior / 'strict.cs').read_text()
        original = next(x for x in source['cases'] if x['case'] == case)
        assert original['main_sha256'] == binding['source_hash']
        writes = []
        for request in original['cases'][0]['requests']:
            if request['kind'] == 'write-sram' and request['address'] == 4:
                break
            if request['kind'] == 'write-sram':
                writes.append(request)
        assert len(writes) == 45 and sum(len(bytes.fromhex(w['data'])) for w in writes) == 169
        diagnostics = report['diagnostics']
        odr = bytes.fromhex(diagnostics['imu_odr_values'])
        assert all(6 <= (byte & 15) <= 10 for byte in odr[1:3])
        derived = {0x288: 1250 << ((odr[1] & 15) - 6), 0x290: 20000,
                   0x28c: 1250 << ((odr[2] & 15) - 6), 0x818: 40000}
        supplied = dict(values)
        supplied.update({address: struct.pack('<I', word) for address, word in derived.items()})
        expected = json.loads((prior / 'report.json').read_text())['diagnostics']['imu_gaf_history']
        for write in writes:
            data = supplied[write['address']]
            assert len(data) == len(bytes.fromhex(write['data']))
            expected += '|' + '|'.join(f"{write['address'] + k:x}:{byte:02x}" for k, byte in enumerate(data))
        assert diagnostics['imu_gaf_history'] == expected
        assert diagnostics['imu_gaf_written_bytes'] == diagnostics['imu_gaf_write_transactions'] == 225
        assert diagnostics['imu_gaf_clock_reads'] == diagnostics['imu_gaf_clock_selections'] == 1
        assert diagnostics['imu_gaf_clock_fixture'] == value and diagnostics['imu_service_completions'] == 2
        assert diagnostics['imu_last_write'] == '7c000402'
        ram = (folder / 'exports/sram-full.bin').read_bytes()
        offset = binding['buffer'] - 0x20000000
        for field in fields:
            assert ram[offset + field['offset']:offset + field['offset'] + field['length']] == values[field['address']]
        result.append(dict(case=case, written_bytes=225, original_buffer=binding['buffer'], clock_byte=value,
                           original_main_unchanged=True, only_imu_component_changed=True, next_packet='7c000402'))
    off = json.loads((simulator / 'imu-clock-variation-off-01/report.json').read_text())
    prior = json.loads((simulator / 'imu-gaf-storage-main-02/stock24/report.json').read_text())
    assert off['passed'] and off['observed'] == prior['observed']
    assert off['selected_observation'] == prior['selected_observation']
    assert off['diagnostics']['imu_gaf_clock_fixture'] == -1
    assert off['diagnostics']['imu_gaf_clock_reads'] == 0
    return dict(passed=True, cases=result, disabled_cpu_events_exact=True,
                clock_register_physical_verified=False, gaf_service_executed=False,
                full_startup_verified=False, hardware_accessed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--clock', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh verification output')
    result = (verify_clock if args.clock else verify)(args.simulator, Path(__file__).resolve().parents[1])
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('Verified saved writes in', len(result['cases']), 'original images; disabled control exact')
