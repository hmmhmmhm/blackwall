"""Select a bounded IMU reset fixture without changing original firmware."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--initial-interface', type=lambda x: int(x, 0), default=0xa5)
    p.add_argument('--initial-drive', type=lambda x: int(x, 0), default=0x5a)
    p.add_argument('--missing-done', action='store_true')
    a = p.parse_args()
    s, root = a.simulator, Path(__file__).resolve().parents[1]
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root) or any(not 0 <= x <= 255 for x in [a.initial_interface, a.initial_drive]):
        raise ValueError('Fresh private plan and byte fixtures required')
    m = json.loads((s / 'imu-reset-verification-01/manifest.json').read_text())
    source = s / 'imu-reset-source-01/report.json'
    if not m['passed'] or sha(source) != m['files'][str(source.relative_to(s))]:
        raise ValueError('Changed reset source contract')
    for n, value in m['model_hashes'].items():
        if sha(root / 'tools' / n) != value:
            raise ValueError('Changed inherited model ' + n)
    baseline = s / 'imu-reset-model-research-01/identity-only.cs'
    if sha(baseline) != m['imu_identity_model_sha256']:
        raise ValueError('Changed identity-only baseline')
    peer = 'tools/renode-imu-identity.cs'
    plan = json.loads((s / 'iom4-imu-main-03/stock23/plan.json').read_text())
    plan.update(id='imu-timed-reset-v1', source_root='iom4-imu-main-03',
                components=[dict(name='imu-timed-reset', baseline=str(baseline.relative_to(s)), candidate=peer, before_sha256=sha(baseline), after_sha256=sha(root / peer))],
                append_components=[], board_append='', runtime_edits=[], imu_reset_contract_sha256=sha(source))
    before = '    profile: "icm45608-whoami-only"\n'
    after = '    profile: "icm45608-reset-lifecycle"\n    initialInterface: ' + str(a.initial_interface) + '\n    initialDrive: ' + str(a.initial_drive) + '\n    completeReset: ' + str(not a.missing_done).lower() + '\n'
    plan['board_edits'] = [dict(before=before, after=after)]
    obj = 'blackwall_imu_identity'
    selected = "str(" + obj + ".Profile)=='icm45608-reset-lifecycle'"
    fields = ',imu_reset_selected=(' + selected + ')'
    properties = [('requests', 'ResetRequests', 'int'), ('completions', 'ResetCompletions', 'int'), ('pending', 'ResetPending', 'bool'), ('elapsed', 'ResetElapsed', 'bool'), ('done', 'ResetDone', 'bool'), ('drive_restores', 'DriveRestores', 'int'), ('interface_restores', 'InterfaceRestores', 'int'), ('status_reads', 'StatusReads', 'int'), ('configuration_reads', 'ConfigurationReads', 'int'), ('drive_value', 'DriveValue', 'int'), ('interface_value', 'InterfaceValue', 'int')]
    for field, prop, typ in properties:
        fields += ',imu_reset_' + field + '=(' + typ + '(' + obj + '.' + prop + ') if ' + selected + ' else None)'
    plan['diagnostics'] = plan['diagnostics'][:-1] + fields + ')'
    plan['reviewed_sources'] = {}
    for case in plan['cases']:
        cap = s / 'iom4-imu-main-03' / case
        audit = s / 'iom4-imu-saved-audit-01' / case / 'report.json'
        plan['reviewed_sources'][case] = dict(path=str(audit.relative_to(s)), sha256=sha(audit))
        prior = json.loads((cap / 'report.json').read_text())
        guard = next(g for g in prior['observed']['guards'] if g['accesses'])
        boundary = dict(kind='strict-mmio', pc=prior['observed']['pc'], **{k: guard[k] for k in ['address', 'operation', 'width', 'value']})
        checks = [dict(path=['diagnostics', 'imu_reset_' + k], eq=v) for k, v in [('selected', True), ('requests', 1), ('completions', 0 if a.missing_done else 1), ('drive_restores', 1), ('interface_restores', 1), ('drive_value', a.initial_drive), ('interface_value', a.initial_interface)]]
        plan['semantics'][case] = dict(
            candidate=dict(boundary=dict(kind='bounded-capture'), comparison=dict(policy='bounded-invariants', paths=[['observed', 'memory_policy', 'violations'], ['observed', 'system_control', 'violations']]),
                           checks=checks, allowed_differences=['Explicit IMU initialization bytes and virtual reset lifecycle only.'],
                           unresolved_differences=['Provisional next frontier; no physical reset timing or full boot proof.']),
            control=dict(boundary=boundary, comparison=dict(policy='exact', path=['observed']),
                         checks=[dict(path=['selected_observation'], eq_source=['selected_observation']), dict(path=['diagnostics', 'imu_reset_selected'], eq=False)],
                         allowed_differences=['Identity-only profile preserves previous CPU/events.'], unresolved_differences=['Reset unsupported.']))
        spec = plan['semantics'][case]['candidate']
        spec['boundary'] = dict(boundary, operation='peer-write', value=3)
        spec['checks'] += [dict(path=['diagnostics', k], eq=v) for k, v in [('imu_last_write', '7ca267'), ('imu_finishes', 11), ('imu_returned_bytes', 4), ('imu_reset_status_reads', 1), ('imu_reset_configuration_reads', 2), ('imu_reset_pending', False), ('imu_reset_elapsed', True), ('imu_reset_done', False)]]
        spec['unresolved_differences'] = ['Next three-byte address-select7ca267 for indirect endianness read is unsupported; reset timing/initial bytes are declared fixtures. Missing RESET_DONE preserves an error but does not stop this next query.']
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan, indent=2) + '\n')
    print('Prepared declared reset fixture', hex(a.initial_interface), hex(a.initial_drive), 'missing-done' if a.missing_done else 'complete')


if __name__ == '__main__':
    main()
