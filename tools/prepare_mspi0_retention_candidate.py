"""Connect exact-PC retention flags and explicit MSPI0 off response to original main."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('case', choices=['stock24', 'stock23', 'cfw'])
    p.add_argument('output', type=Path)
    p.add_argument('--guest-stop-control', action='store_true')
    p.add_argument('--stuck-on', action='store_true')
    a = p.parse_args()
    s = a.simulator
    root = Path(__file__).resolve().parents[1]
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root) or a.stuck_on and a.guest_stop_control:
        raise ValueError('Preserve distinct private execution plans outside Git')
    manifest = json.loads((s / 'mspi0-retention-verification-01/manifest.json').read_text())
    source = s / 'mspi0-retention-source-03/report.json'
    if not manifest['passed'] or manifest['files'][str(source.relative_to(s))] != sha(source):
        raise ValueError('Changed original retention contract')
    row = next(x for x in json.loads(source.read_text())['cases'] if x['case'] == a.case)
    cap = s / 'mspi0-queue-main-01' / a.case
    plan = json.loads((cap / 'plan.json').read_text())
    plan.update(id='mspi0-retention-v1', source_root='mspi0-queue-main-01')
    plan['components'] = []
    for name in ['renode-strict-mmio.cs', 'renode-mspi1-config.cs']:
        base = s / 'mspi0-retention-peer-research-01' / ('base-' + name)
        if sha(base) != manifest['model_hashes'][name]:
            raise ValueError('Changed baseline ' + name)
        plan['components'].append(dict(name=name[:-3], baseline=str(base.relative_to(s)), candidate='tools/' + name,
                                       before_sha256=sha(base), after_sha256=sha(root / 'tools' / name)))
    config_anchor = 'mspi0_config: Miscellaneous.BlackwallMspi1ConfigStorage @ none\n    profile: "source-reset-config"\n    commandQueueInit: true\n    mspi0Initialization: true\n    interrupts: mspi0_interrupts\n    baseAddress: 0x40060000\n'
    power_anchor = 'mspi0_power: Miscellaneous.BlackwallPeripheralPower @ none\n    mask: 0x4000\n    profile: 1\n'
    board = (cap / 'board.repl').read_text()
    if board.count(config_anchor) != 1 or board.count(power_anchor) != 1:
        raise ValueError('Different source configuration/power anchors')
    plan['board_edits'] = [dict(before=config_anchor, after='mspi0_config: Miscellaneous.BlackwallMspi0RetentionConfig @ none\n    power: mspi0_power\n    interrupts: mspi0_interrupts\n    readPc: ' + hex(row['save_entry']) + '\n'),
                           dict(before=power_anchor, after=power_anchor + '    offProfile: ' + str(int(a.stuck_on)) + '\n')]
    plan['board_append'] = ''
    plan['runtime_edits'] = []
    config = "m['sysbus.guard'].Mspi0Config"
    power = "m['sysbus.guard'].Mspi0Power"
    fields = ',mspi0_retention_selected=bool(' + config + '.Mspi0RetentionReadPc!=0)'
    fields += ',mspi0_controller_power_downs=int(' + config + '.ControllerPowerDowns)'
    fields += ',mspi0_off_requests=int(' + power + '.OffRequests),mspi0_power_cycles=int(' + power + '.PowerCycles)'
    fields += ',mspi0_last_flags=int(' + config + '.LastCqFlags)'
    plan['diagnostics'] = plan['diagnostics'][:-1] + fields + ')'
    plan['reviewed_sources'] = {}
    for case in plan['cases']:
        audit = s / 'mspi0-queue-saved-audit-01' / case / 'report.json'
        plan['reviewed_sources'][case] = dict(path=str(audit.relative_to(s)), sha256=sha(audit))
        prior = json.loads((s / 'mspi0-queue-main-01' / case / 'report.json').read_text())
        g = next(x for x in prior['observed']['guards'] if x['accesses'])
        boundary = dict(kind='strict-mmio', pc=prior['observed']['pc'], **{k: g[k] for k in ['address', 'operation', 'width', 'value']})
        common = [dict(path=['diagnostics', k], eq=v) for k, v in [('accepted_commands', 59), ('replies', 60)]]
        checks = common + [dict(path=['diagnostics', k], eq=v) for k, v in [('mspi0_retention_selected', True), ('mspi0_off_requests', 1), ('mspi0_cqflagreads', 1), ('mspi0_last_flags', 128)]]
        plan['semantics'][case] = dict(
            candidate=dict(boundary=dict(kind='bounded-capture'), comparison=dict(policy='prefix', path=['selected_observation', 'events']), checks=checks,
                           allowed_differences=['Explicit retention-only flag fixture, disabled-controller off/reset and clock release.'],
                           unresolved_differences=['Provisional frontier; wake, active bus engines, panel state and display unverified.']),
            control=dict(boundary=boundary, comparison=dict(policy='exact', path=['observed']),
                         checks=common + [dict(path=['selected_observation'], eq_source=['selected_observation']), dict(path=['diagnostics', 'mspi0_retention_selected'], eq=False)],
                         allowed_differences=['Default CPU/events preserved.'], unresolved_differences=['CQFLAGS remains unknown.']))
        if a.stuck_on:
            c = plan['semantics'][case]['candidate']
            c['comparison'] = dict(policy='bounded-invariants', paths=[['observed', 'memory_policy', 'violations'], ['observed', 'system_control', 'violations']])
            c['checks'] += [dict(path=['diagnostics', k], eq=v) for k, v in [('mspi0_phase', 'stuck-on'), ('mspi0_power_cycles', 0), ('mspi0_controller_power_downs', 0)]]
    plan.update(host_capture_seconds=120, memory_export_policy='paused-after-observation')
    plan.pop('execution_mode', None)
    if a.guest_stop_control:
        plan.pop('host_capture_seconds')
        plan.pop('memory_export_policy')
        plan['execution_mode'] = 'until-guest-stop'
    plan['mspi0_retention_source_sha256'] = sha(source)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan, indent=2) + '\n')
    print('Prepared private MSPI0 retention candidate', a.case, 'stuck-on' if a.stuck_on else 'off-response')


if __name__ == '__main__':
    main()
