"""Audit E08's fixed virtual NOR scenarios; never execute firmware or hardware.

Local sub-audit completion flags predate this aggregate decision. They remain
unchanged. Recovery here means only the explicitly classified storage result.
"""
import argparse
import hashlib
import json
from pathlib import Path

from inspect_kvtime_reload_policy import schema_contract
from kvtime_layout import discover
from verify_boot_nor_erase import verify as verify_erase
from verify_kvtime_corrupt_restart import inspect_capture
from verify_nor_program_cut import verify_pair
from verify_runtime_nor_timeout import verify as verify_program


ACCEPTANCE = 'Assess the extent of corruption and restart outcomes in pinned write/erase failure, interruption, and data/version mismatch scenarios. Do not mask failures as success; distinguish recoverable cases from explicit failure.'
ORIGINALS = ('stock24', 'stock23', 'cfw')
MANIFESTS = (
    'peer-runtime-nor-timeout-research-01/manifest.json',
    'peer-boot-nor-erase-research-01/manifest.json',
    'nor-program-pair-research-01/manifest.json',
    'kvtime-corruption-research-01/manifest.json',
    'kvtime-schema-research-01/manifest.json',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_pins(s):
    pins = {}
    manifests = {}
    for name in MANIFESTS:
        data = (s / name).read_bytes()
        manifest = json.loads(data)
        if not manifest['passed'] or manifest['hardware_accessed']:
            raise ValueError('Invalid research manifest: ' + name)
        manifests[name] = sha(data)
        for relative, expected in manifest['files'].items():
            if relative in pins and pins[relative] != expected:
                raise ValueError('Conflicting evidence: ' + relative)
            pins[relative] = expected
    for relative, expected in pins.items():
        path = s / relative
        if not path.resolve().is_relative_to(s.resolve()):
            raise ValueError('Evidence outside private simulator')
        data = path.read_bytes()
        if len(data) != expected['bytes'] or sha(data) != expected['sha256']:
            raise ValueError('Changed research evidence: ' + relative)
    return dict(manifests=manifests,unique_files=len(pins))


def changed_bytes(before, after):
    if len(before) != len(after):
        raise ValueError('Changed backing window length')
    differences = [[i, x, y] for i, (x, y) in enumerate(zip(before, after)) if x != y]
    return dict(count=len(differences),first=differences[0][0] if differences else None,
                last=differences[-1][0] if differences else None,
                differences_sha256=sha(json.dumps(differences,separators=(',', ':')).encode()))


def mismatch_bounds(s, capture, case):
    result = {}
    baseline = s / 'runtime-kv-retained-restart-02' / case
    for window in ('kv-nv', 'littlefs'):
        before = (capture / ('retained-' + window + '.bin')).read_bytes()
        after = (capture / ('exports/restart-nor-' + window + '.bin')).read_bytes()
        normal = (baseline / ('exports/restart-nor-' + window + '.bin')).read_bytes()
        result[window] = dict(input_sha256=sha(before),output_sha256=sha(after),
                             changes=changed_bytes(before,after),
                             versus_normal_restart=changed_bytes(normal,after))
        if window == 'kv-nv' and before[0x38000:] != after[0x38000:]:
            raise ValueError('NV neighbor changed during mismatch scenario')
    return result


def validate_coverage(rows):
    expected = {(kind,case) for kind in ('write-failure','erase-failure','future-version') for case in ORIGINALS}
    expected |= {('interrupt-before-commit','stock24'),('interrupt-after-commit','stock24'),
                 ('bad-container-crc','stock24'),('bad-record-crc','stock24')}
    actual = [(row['scenario'],row['case']) for row in rows]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('Missing, duplicate, or unexpected fixed storage scenario')
    if any(row['full_app_recovery_verified'] or not row['damage_and_restart_classified'] for row in rows):
        raise ValueError('Unsupported recovery claim or unclassified scenario')


def verify(s, output, scope_path):
    scope = json.loads(scope_path.read_text())
    criterion = next(c for c in scope['criteria'] if c['id'] == 'E08')
    if scope['version'] != 3 or len(scope['criteria']) != 16 or criterion['acceptance'] != ACCEPTANCE:
        raise ValueError('Changed scope requires a new acceptance review')
    pins = verify_pins(s)
    rows = []
    details = dict(program={},erase={},mismatch=[])
    for case in ORIGINALS:
        details['program'][case] = verify_program(s,output/'program'/case,case)
        details['erase'][case] = verify_erase(s,case)
        for kind, outcome in (('write-failure','uncommitted; previous record reread; later unsupported guard'),
                              ('erase-failure','backing unchanged; fresh formatter matches normal; no user-data recovery claim')):
            rows.append(dict(scenario=kind,case=case,outcome=outcome,
                             damage_and_restart_classified=True,full_app_recovery_verified=False))
    details['interruption'] = verify_pair(s,output/'interruption')
    for kind,outcome in (('interrupt-before-commit','old record selected'),
                         ('interrupt-after-commit','new record selected; old retirement pending')):
        rows.append(dict(scenario=kind,case='stock24',outcome=outcome,
                         damage_and_restart_classified=True,full_app_recovery_verified=False))
    fixtures = [('stock24','bad-container-crc','kvtime-corrupt-native-01/stock24-bad-container-crc'),
                ('stock24','bad-record-crc','kvtime-corrupt-native-01/stock24-bad-record-crc'),
                ('stock24','future-version','kvtime-corrupt-native-01/stock24-future-record-type'),
                ('stock23','future-version','kvtime-schema-native-01/stock23'),
                ('cfw','future-version','kvtime-schema-native-01/cfw')]
    for case,kind,relative in fixtures:
        capture = s / relative
        report = inspect_capture(s,capture)
        expected = 'initial_record_rewritten_type3' if kind == 'bad-container-crc' else 'damaged_record_loaded'
        if report['outcome'] != expected or report['full_boot_complete']:
            raise ValueError('Changed mismatch behavior')
        report['backing_bounds'] = mismatch_bounds(s,capture,case)
        if kind == 'future-version':
            source = s / 'runtime-kv-commit-native-01' / case
            raw = (source/'main.bin').read_bytes()
            profile = json.loads((source/'connection-profile.json').read_text())
            report['source_schema'] = schema_contract(raw,discover(raw,profile))
        details['mismatch'].append(report)
        rows.append(dict(scenario=kind,case=case,outcome=expected,
                         integrity_or_version_rejection_verified=kind=='bad-container-crc',
                         damage_and_restart_classified=True,full_app_recovery_verified=False))
    validate_coverage(rows)
    return dict(passed=True,criterion='E08',acceptance=ACCEPTANCE,scope_version=3,
                fixed_scenarios=rows,details=details,evidence_pins=pins,
                fixed_scenario_acceptance_met=True,new_firmware_executions=0,
                full_boot_complete=False,full_app_recovery_verified=False,
                existing_user_data_recovery_verified=False,physical_power_cut_verified=False,
                observer_neutrality_unproven_cases=['stock24 healthy erase','cfw failed erase'],
                interruption_native_profiles=['stock24'],hardware_accessed=False,subagents_used=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--scope',type=Path,default=Path(__file__).resolve().parents[1]/'docs/data/project-scope.json')
    a = p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior acceptance evidence')
    a.output.mkdir(mode=0o700,parents=True)
    report = verify(a.simulator,a.output,a.scope)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,fixed_scenarios=len(report['fixed_scenarios']),
                          fixed_scenario_acceptance_met=True,new_firmware_executions=0)))


if __name__ == '__main__':main()
