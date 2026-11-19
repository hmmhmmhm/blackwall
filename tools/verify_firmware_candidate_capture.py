"""Audit the E04 appended-data fixture and legacy control without executing firmware."""
import argparse
import json
from pathlib import Path

from native_replay import digest, validate_assets
from firmware_candidate import load_candidate, metadata


def verify(folder):
    source = folder / 'baseline'
    original = (source / 'main.bin').read_bytes()
    raw, record = load_candidate(folder / 'candidate/firmware-candidate.json', source, 'stock_current')
    assert raw == original + b'BLACKWALL-E04-V1'
    assert record['declaration']['main_bytes'] == len(original) + 16
    assert record['declaration']['main_sha256'] != digest(source / 'main.bin')
    reference = json.loads((source / 'report.json').read_text())
    rows = {}
    for name in ['candidate', 'legacy-control']:
        capture = folder / name
        report = json.loads((capture / 'report.json').read_text())
        derived = json.loads((capture / 'derived-inputs.json').read_text())
        validate_assets(capture, derived['derived'])
        assert digest(capture / 'plan.json') == derived['plan_sha256']
        assert digest(capture / 'runner-source.py') == derived['runner_sha256']
        assert report['passed'] and report['execution_passed'] and report['semantic_validation']['passed']
        assert report['observed'] == reference['observed']
        assert report['selected_observation'] == reference['selected_observation']
        for filename in ['board.repl', 'probe.resc', 'itcm-fill.bin', 'sram-fill.bin', 'strict.cs']:
            assert (capture / filename).read_bytes() == (source / filename).read_bytes()
        audit = json.loads((folder / (name + '-audit') / 'report.json').read_text())
        assert audit['passed'] and audit['native_rerun'] is False
        for name_in_capture, expected_hash in audit['capture_hashes'].items():
            artifact = (capture / name_in_capture).resolve()
            assert artifact.is_relative_to(capture.resolve()) and digest(artifact) == expected_hash
        validate_assets(source, audit['source_hashes'])
        rows[name] = report
    candidate = folder / 'candidate'
    info = metadata(record, digest(candidate / 'firmware-candidate.json'))
    assert rows['candidate']['firmware_candidate'] == info
    assert rows['candidate']['diagnostics']['firmware_marker_hex'] == raw[-16:].hex()
    assert 'firmware_candidate' not in rows['legacy-control']
    assert rows['legacy-control']['diagnostics']['firmware_marker_hex'] == '00' * 16
    assert (folder / 'legacy-control/main.bin').read_bytes() == original
    assert (candidate / 'run.py').read_text().replace(',3700084)', ',3700068)') == (folder / 'legacy-control/run.py').read_text()
    isolation = json.loads((folder / 'audit-isolation.json').read_text())
    assert isolation['registry_unavailable_during_audit'] and isolation['registry_restored']
    preflight = json.loads((folder / 'preflight.json').read_text())
    assert preflight['passed'] and len(preflight['rejections']) == 6
    assert all(row['rejected'] for row in preflight['rejections'])
    assert preflight['existing_registration_preserved']
    return dict(passed=True, criteria={'E04': {'passed': True}}, new_main_hash_verified=True,
                new_length_verified=True, guest_appended_bytes_verified=True,
                original_code_vectors_unchanged=True, native_candidate_and_legacy_verified=True,
                cpu_events_equal_to_baseline=True, models_and_initial_memory_unchanged=True,
                saved_audits_passed=True, registration_unavailable_during_audit=True,
                invalid_registration_rejections=6, fixture_is_new_cfw_feature=False,
                E15_functional_comparison_complete=False, full_startup_verified=False,
                display_verified=False, hardware_accessed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output')
    answer = verify(args.folder)
    args.output.write_text(json.dumps(answer, indent=2) + '\n')
    print('E04 candidate input and legacy control verified; E15/startup/display remain incomplete')
