"""Connect bounded serial-SDR TX transport to native original MSPI0 calls."""
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
    p.add_argument('--stuck', action='store_true')
    a = p.parse_args()
    s = a.simulator
    root = Path(__file__).resolve().parents[1]
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root) or a.stuck and a.guest_stop_control:
        raise ValueError('Preserve distinct private capture plans outside Git')
    manifest = json.loads((s / 'mspi0-first-pio-verification-01/manifest.json').read_text())
    source = s / 'mspi0-first-pio-source-05/report.json'
    if not manifest['passed'] or sha(source) != manifest['files'][str(source.relative_to(s))]:
        raise ValueError('Changed original PIO contract')
    cap = s / 'cpu-sleep-main-02' / a.case
    plan = json.loads((cap / 'plan.json').read_text())
    base = s / 'mspi0-tx-peer-research-01/base-config.cs'
    if sha(base) != manifest['model_hashes']['renode-mspi1-config.cs']:
        raise ValueError('Changed baseline configuration')
    plan.update(id='mspi0-tx-v1', source_root='cpu-sleep-main-02')
    plan['components'] = [dict(name='mspi0-tx', baseline=str(base.relative_to(s)), candidate='tools/renode-mspi1-config.cs',
                               before_sha256=sha(base), after_sha256=sha(root / 'tools/renode-mspi1-config.cs'))]
    config = 'mspi0_config: Miscellaneous.BlackwallMspi0RetentionConfig @ none\n'
    irq = 'mspi0_interrupts: Miscellaneous.BlackwallMspi1Interrupts @ none\n    profile: "source-reset"\n'
    board = (cap / 'board.repl').read_text()
    if board.count(config) != 1 or board.count(irq) != 1:
        raise ValueError('Different MSPI0 owner anchors')
    plan['board_edits'] = [dict(before=config, after=config + '    pio: mspi0_tx\n'),
                           dict(before=irq, after=irq + '    allowAllClear: true\n')]
    plan['board_append'] = '\nmspi0_tx: Miscellaneous.BlackwallMspi0Tx @ none\n    profile: "tx-capture"\n    power: mspi0_power\n    clock: mspi1_clock\n    interrupts: mspi0_interrupts\n    completeTransactions: ' + str(not a.stuck).lower() + '\n'
    plan['runtime_edits'] = []
    q = "m['sysbus.guard'].Mspi0Config.Pio"
    fields = ',mspi0_tx_selected=(' + q + ' is not None),mspi0_tx_slave_effects=False'
    for name in ['Starts', 'Completions', 'Aborted', 'FifoWrites', 'BytesShifted']:
        fields += ',mspi0_tx_' + name.lower() + '=int(' + q + '.' + name + ') if ' + q + ' is not None else 0'
    fields += ',mspi0_tx_frames=[dict(control=int(f.Control),instruction=int(f.Instruction),address=int(f.Address),configuration=int(f.Configuration),payload_hex=str(f.PayloadHex)) for f in ' + q + '.Frames] if ' + q + ' is not None else []'
    plan['diagnostics'] = plan['diagnostics'][:-1] + fields + ')'
    plan['reviewed_sources'] = {}
    for case in plan['cases']:
        audit = s / 'cpu-sleep-saved-audit-01' / case / 'report.json'
        plan['reviewed_sources'][case] = dict(path=str(audit.relative_to(s)), sha256=sha(audit))
        prior = json.loads((s / 'cpu-sleep-main-02' / case / 'report.json').read_text())
        g = next(x for x in prior['observed']['guards'] if x['accesses'])
        boundary = dict(kind='strict-mmio', pc=prior['observed']['pc'], **{k: g[k] for k in ['address', 'operation', 'width', 'value']})
        common = [dict(path=['diagnostics', k], eq=v) for k, v in [('accepted_commands', 59), ('replies', 60)]]
        checks = common + [dict(path=['diagnostics', 'mspi0_tx_selected'], eq=True), dict(path=['diagnostics', 'mspi0_tx_slave_effects'], eq=False)]
        plan['semantics'][case] = dict(
            candidate=dict(boundary=dict(kind='bounded-capture'), comparison=dict(policy='prefix', path=['selected_observation', 'events']), checks=checks,
                           allowed_differences=['Explicit timed serial-SDR TX transport/FIFO/capture and all-clear IRQ profile only.'],
                           unresolved_differences=['Provisional frontier; slave effects, RX, other modes, boot/display unverified.']),
            control=dict(boundary=boundary, comparison=dict(policy='exact', path=['observed']),
                         checks=common + [dict(path=['selected_observation'], eq_source=['selected_observation']), dict(path=['diagnostics', 'mspi0_tx_selected'], eq=False)],
                         allowed_differences=['Default CPU/events preserved.'], unresolved_differences=['INTCLR all remains unsupported.']))
        if a.stuck:
            c = plan['semantics'][case]['candidate']
            c['comparison'] = dict(policy='bounded-invariants', paths=[['observed', 'memory_policy', 'violations'], ['observed', 'system_control', 'violations']])
            c['checks'] += [dict(path=['diagnostics', k], eq=v) for k, v in [('mspi0_tx_completions', 0), ('mspi0_tx_bytesshifted', 0), ('mspi0_tx_frames', [])]]
    plan.update(host_capture_seconds=120, memory_export_policy='paused-after-observation')
    plan.pop('execution_mode', None)
    if a.guest_stop_control:
        plan.pop('host_capture_seconds')
        plan.pop('memory_export_policy')
        plan['execution_mode'] = 'until-guest-stop'
    plan['mspi0_first_pio_source_sha256'] = sha(source)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan, indent=2) + '\n')
    print('Prepared private MSPI0 TX candidate', a.case, 'stuck' if a.stuck else 'timed')


if __name__ == '__main__':
    main()
