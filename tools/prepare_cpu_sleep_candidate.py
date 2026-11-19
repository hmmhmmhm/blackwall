"""Connect finite normal-sleep storage and original-PC bus flush to native main."""
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
    a = p.parse_args()
    s = a.simulator
    root = Path(__file__).resolve().parents[1]
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root):
        raise ValueError('Preserve private plans outside Git')
    manifest = json.loads((s / 'cpu-sleep-verification-01/manifest.json').read_text())
    source = s / 'cpu-sleep-source-02/report.json'
    if not manifest['passed'] or sha(source) != manifest['files'][str(source.relative_to(s))]:
        raise ValueError('Changed original sleep contract')
    row = next(x for x in json.loads(source.read_text())['cases'] if x['case'] == a.case)
    cap = s / 'mspi0-retention-main-02' / a.case
    plan = json.loads((cap / 'plan.json').read_text())
    base = s / 'cpu-sleep-peer-research-01/base-core.cs'
    if sha(base) != manifest['model_hashes']['renode-strict-mmio.cs']:
        raise ValueError('Changed source model')
    plan.update(id='cpu-normal-sleep-v1', source_root='mspi0-retention-main-02')
    plan['components'] = [dict(name='cpu-normal-sleep', baseline=str(base.relative_to(s)), candidate='tools/renode-strict-mmio.cs',
                               before_sha256=sha(base), after_sha256=sha(root / 'tools/renode-strict-mmio.cs'))]
    owner = '    mspi0Config: mspi0_config\n'
    ppb = 'ppb_guard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0xe0010000\n    baseAddress: 0xe0010000\n'
    board = (cap / 'board.repl').read_text()
    if board.count(owner) != 1 or board.count(ppb) != 1:
        raise ValueError('Missing unique CPU storage owner anchors')
    tail = 'guard_iom7_tail: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40057400\n    baseAddress: 0x40057400\n    gpuControlOwner: guard\n'
    if board.count(tail) != 1:
        raise ValueError('APB flush requires the existing shared strict-tail owner')
    plan['board_edits'] = [dict(before=owner, after=owner + '    cpuNormalSleep: cpu_normal_sleep\n'),
                           dict(before=ppb, after=ppb + '    gpuControlOwner: guard\n')]
    plan['board_append'] = '\ncpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n    profile: "normal-sleep-storage"\n    flushReadPc: ' + hex(row['wfi_boundary'] - 6) + '\n'
    plan['runtime_edits'] = []
    c = "m['sysbus.guard'].CpuNormalSleep"
    fields = ',cpu_sleep_selected=(' + c + ' is not None)'
    for name in ['PowerControlReads', 'CpdReads', 'CpdWrites', 'FlushReads', 'CpdValue']:
        fields += ',cpu_sleep_' + name.lower() + '=int(' + c + '.' + name + ') if ' + c + ' is not None else 0'
    plan['diagnostics'] = plan['diagnostics'][:-1] + fields + ')'
    plan['reviewed_sources'] = {}
    for case in plan['cases']:
        audit = s / 'mspi0-retention-saved-audit-01' / case / 'report.json'
        plan['reviewed_sources'][case] = dict(path=str(audit.relative_to(s)), sha256=sha(audit))
        prior = json.loads((s / 'mspi0-retention-main-02' / case / 'report.json').read_text())
        g = next(x for x in prior['observed']['guards'] if x['accesses'])
        boundary = dict(kind='strict-mmio', pc=prior['observed']['pc'], **{k: g[k] for k in ['address', 'operation', 'width', 'value']})
        common = [dict(path=['diagnostics', k], eq=v) for k, v in [('accepted_commands', 59), ('replies', 60), ('mspi0_power_cycles', 1)]]
        plan['semantics'][case] = dict(
            candidate=dict(boundary=dict(kind='bounded-capture'), comparison=dict(policy='prefix', path=['selected_observation', 'events']),
                           checks=common + [dict(path=['diagnostics', k], eq=v) for k, v in [('cpu_sleep_selected', True), ('cpu_sleep_cpdvalue', 0x11)]],
                           allowed_differences=['Explicit normal-sleep register state, PPB owner and synchronous bus-flush fixture only.'],
                           unresolved_differences=['Provisional frontier; WFI/wake, physical power, complete boot/display unverified.']),
            control=dict(boundary=boundary, comparison=dict(policy='exact', path=['observed']),
                         checks=common + [dict(path=['selected_observation'], eq_source=['selected_observation']), dict(path=['diagnostics', 'cpu_sleep_selected'], eq=False)],
                         allowed_differences=['Default CPU/events preserved.'], unresolved_differences=['CPUPWRCTRL remains unknown.']))
    plan.update(host_capture_seconds=120, memory_export_policy='paused-after-observation')
    plan.pop('execution_mode', None)
    if a.guest_stop_control:
        plan.pop('host_capture_seconds')
        plan.pop('memory_export_policy')
        plan['execution_mode'] = 'until-guest-stop'
    plan['cpu_sleep_source_sha256'] = sha(source)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan, indent=2) + '\n')
    print('Prepared private normal-sleep candidate', a.case)


if __name__ == '__main__':
    main()
