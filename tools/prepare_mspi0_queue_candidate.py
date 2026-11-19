"""Connect disabled MSPI0 command queue and isolated IRQ20 to original main."""
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
    manifest = json.loads((s / 'mspi0-queue-verification-01/manifest.json').read_text())
    source = s / 'mspi0-queue-source-03/report.json'
    if not manifest['passed'] or manifest['files'][str(source.relative_to(s))] != sha(source):
        raise ValueError('Changed original queue contract')
    cap = s / 'mspi0-config-main-01' / a.case
    plan = json.loads((cap / 'plan.json').read_text())
    baseline = s / 'mspi0-queue-peer-research-01/base-renode-mspi1-config.cs'
    if sha(baseline) != manifest['model_hashes']['renode-mspi1-config.cs']:
        raise ValueError('Changed baseline model')
    plan.update(id='mspi0-disabled-queue-v1', source_root='mspi0-config-main-01')
    plan['components'] = [dict(name='mspi0-disabled-queue', baseline=str(baseline.relative_to(s)),
                               candidate='tools/renode-mspi1-config.cs', before_sha256=sha(baseline),
                               after_sha256=sha(root / 'tools/renode-mspi1-config.cs'))]
    anchor = 'mspi0_config: Miscellaneous.BlackwallMspi1ConfigStorage @ none\n    profile: "source-reset-config"\n'
    if (cap / 'board.repl').read_text().count(anchor) != 1:
        raise ValueError('Different original MSPI0 board anchor')
    plan['board_edits'] = [dict(before=anchor, after=anchor + '    commandQueueInit: true\n    mspi0Initialization: true\n    interrupts: mspi0_interrupts\n')]
    plan['board_append'] = '\nmspi0_interrupts: Miscellaneous.BlackwallMspi1Interrupts @ none\n    profile: "source-reset"\n    IRQ -> nvic@20\n'
    plan['runtime_edits'] = []
    config = "m['sysbus.guard'].Mspi0Config"
    fields = ',mspi0_queue_selected=bool(' + config + '.Mspi0Initialization)'
    for key in ['CqReads', 'CqWrites', 'CqFlagReads']:
        fields += ',mspi0_' + key.lower() + '=int(' + config + '.' + key + ')'
    for key in ['Enable', 'Status', 'Reads', 'Writes']:
        fields += ',mspi0_irq_' + key.lower() + '=int(' + config + '.Interrupts.' + key + ') if ' + config + '.Interrupts is not None else 0'
    fields += ',mspi0_cqcfg=int(' + config + '.CqValues[0x2a0]),mspi0_cqswflags=int(' + config + '.CqValues[0x2b0])'
    plan['diagnostics'] = plan['diagnostics'][:-1] + fields + ')'
    plan['reviewed_sources'] = {}
    for case in plan['cases']:
        audit = s / 'mspi0-config-saved-audit-01' / case / 'report.json'
        plan['reviewed_sources'][case] = dict(path=str(audit.relative_to(s)), sha256=sha(audit))
        prior = json.loads((s / 'mspi0-config-main-01' / case / 'report.json').read_text())
        g = next(x for x in prior['observed']['guards'] if x['accesses'])
        boundary = dict(kind='strict-mmio', pc=prior['observed']['pc'], **{k: g[k] for k in ['address', 'operation', 'width', 'value']})
        common = [dict(path=['diagnostics', k], eq=v) for k, v in [('accepted_commands', 59), ('replies', 60)]]
        plan['semantics'][case] = dict(
            candidate=dict(boundary=dict(kind='bounded-capture'), comparison=dict(policy='prefix', path=['selected_observation', 'events']),
                           checks=common + [dict(path=['diagnostics', k], eq=v) for k, v in [('mspi0_queue_selected', True), ('mspi0_cqcfg', 2), ('mspi0_cqswflags', 128)]],
                           allowed_differences=['Explicit disabled queue and IRQ20 initialization only.'],
                           unresolved_differences=['Provisional frontier; GPIO, retained power, CQFLAGS, engines and display remain unverified.']),
            control=dict(boundary=boundary, comparison=dict(policy='exact', path=['observed']),
                         checks=common + [dict(path=['selected_observation'], eq_source=['selected_observation']), dict(path=['diagnostics', 'mspi0_queue_selected'], eq=False)],
                         allowed_differences=['Default configuration and events preserved.'], unresolved_differences=['Queue-index write remains unsupported.']))
    plan.update(host_capture_seconds=120, memory_export_policy='paused-after-observation')
    plan.pop('execution_mode', None)
    if a.guest_stop_control:
        plan.pop('host_capture_seconds')
        plan.pop('memory_export_policy')
        plan['execution_mode'] = 'until-guest-stop'
    plan['mspi0_queue_source_sha256'] = sha(source)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan, indent=2) + '\n')
    print('Prepared private MSPI0 disabled queue/IRQ candidate', a.case)


if __name__ == '__main__':
    main()
