"""Select declared four-byte diagnostic RX input without claiming a physical device identity."""
import argparse
import json
import re
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('case', choices=['stock24', 'stock23', 'cfw'])
    p.add_argument('output', type=Path)
    p.add_argument('--control', action='store_true')
    p.add_argument('--stuck', action='store_true')
    p.add_argument('--rx-hex', default='12345678')
    a = p.parse_args()
    s, root = a.simulator, Path(__file__).resolve().parents[1]
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root) or a.stuck and a.control or not re.fullmatch('[0-9a-fA-F]{8}', a.rx_hex):
        raise ValueError('Fresh private plan and explicit four-byte diagnostic hex required')
    manifest = json.loads((s / 'mspi0-rx-identity-verification-01/manifest.json').read_text())
    source = s / 'mspi0-rx-identity-source-02/report.json'
    base = s / 'mspi0-rx-peer-research-01/base-config.cs'
    if not manifest['passed'] or sha(source) != manifest['files'][str(source.relative_to(s))] or sha(base) != manifest['model_hashes']['renode-mspi1-config.cs']:
        raise ValueError('Changed original RX/pixel contract or baseline')
    cap = s / 'mspi0-dma-main-04' / a.case
    plan = json.loads((cap / 'plan.json').read_text())
    plan.update(id='mspi0-diagnostic-rx-v1', source_root='mspi0-dma-main-04')
    plan['components'] = [dict(name='mspi0-diagnostic-rx', baseline=str(base.relative_to(s)), candidate='tools/renode-mspi1-config.cs',
                               before_sha256=sha(base), after_sha256=sha(root / 'tools/renode-mspi1-config.cs'))]
    anchor = 'mspi0_tx: Miscellaneous.BlackwallMspi0Tx @ none\n'
    if (cap / 'board.repl').read_text().count(anchor) != 1:
        raise ValueError('Different MSPI0 transport owner')
    plan['board_edits'] = [dict(before=anchor, after=anchor + '    diagnosticRxHex: "' + a.rx_hex.lower() + '"\n    completeReceive: ' + str(not a.stuck).lower() + '\n')]
    plan['board_append'], plan['runtime_edits'] = '', []
    q = "m['sysbus.guard'].Mspi0Config.Pio"
    fields = ',mspi0_rx_selected=bool(' + q + '.DiagnosticRxHex),mspi0_rx_fixture=str(' + q + '.DiagnosticRxHex)'
    for n in ['RxStarts', 'RxCompletions', 'RxAborted', 'RxReads', 'RxBytesDelivered']:
        fields += ',mspi0_' + n.lower() + '=int(' + q + '.' + n + ')'
    fields += ',mspi0_rx_frames=[dict(control=int(f.Control),instruction=int(f.Instruction),configuration=int(f.Configuration),payload_hex=str(f.PayloadHex)) for f in ' + q + '.ReceiveFrames]'
    plan['diagnostics'] = plan['diagnostics'][:-1] + fields + ')'
    plan['reviewed_sources'] = {}
    for case in plan['cases']:
        audit = s / 'mspi0-dma-saved-audit-01' / case / 'report.json'
        plan['reviewed_sources'][case] = dict(path=str(audit.relative_to(s)), sha256=sha(audit))
        prior = json.loads((s / 'mspi0-dma-main-04' / case / 'report.json').read_text())
        g = next(x for x in prior['observed']['guards'] if x['accesses'])
        boundary = dict(kind='strict-mmio', pc=prior['observed']['pc'], **{k: g[k] for k in ['address', 'operation', 'width', 'value']})
        checks = [dict(path=['diagnostics', 'mspi0_rx_selected'], eq=True),
                  dict(path=['diagnostics', 'mspi0_rx_fixture'], eq=a.rx_hex.lower()),
                  dict(path=['diagnostics', 'mspi0_dma_fault'], eq='')]
        if a.stuck:
            checks += [dict(path=['diagnostics', 'mspi0_rxcompletions'], eq=0),
                       dict(path=['diagnostics', 'mspi0_rx_frames'], eq=[])]
        plan['semantics'][case] = dict(
            candidate=dict(boundary=dict(kind='bounded-capture'), comparison=dict(policy='bounded-invariants', paths=[['observed', 'memory_policy', 'violations'], ['observed', 'system_control', 'violations']]),
                           checks=checks, allowed_differences=['Explicit diagnostic RX9f/data4 timed FIFO and completion only.'],
                           unresolved_differences=['Provisional frontier; no physical device identity or unknown peer response is verified.']),
            control=dict(boundary=boundary, comparison=dict(policy='exact', path=['observed']),
                         checks=[dict(path=['selected_observation'], eq_source=['selected_observation']), dict(path=['diagnostics', 'mspi0_rx_selected'], eq=False)],
                         allowed_differences=['Default RX-disabled CPU/events unchanged.'], unresolved_differences=['RX9f remains unsupported.']))
    plan.update(host_capture_seconds=120, memory_export_policy='paused-after-observation', mspi0_rx_source_sha256=sha(source))
    plan.pop('execution_mode', None)
    if a.control:
        plan.pop('host_capture_seconds')
        plan.pop('memory_export_policy')
        plan['execution_mode'] = 'until-guest-stop'
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan, indent=2) + '\n')
    print('Prepared private diagnostic RX fixture', a.case, a.rx_hex.lower(), 'stuck' if a.stuck else 'complete')


if __name__ == '__main__':
    main()
