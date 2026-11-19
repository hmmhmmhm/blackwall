"""Attach opt-in SRAM CQ/logical DMA engine to the verified TX main candidate."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('case', choices=['stock24', 'stock23', 'cfw'])
    p.add_argument('output', type=Path)
    p.add_argument('--control', action='store_true')
    p.add_argument('--stuck', action='store_true')
    a = p.parse_args()
    s = a.simulator
    root = Path(__file__).resolve().parents[1]
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root) or a.control and a.stuck:
        raise ValueError('Fresh private plans required')
    source = s / 'mspi0-cq-dma-completion-source-03/report.json'
    manifest = json.loads((s / 'mspi0-cq-dma-completion-verification-01/manifest.json').read_text())
    if not manifest['passed'] or sha(source) != manifest['files'][str(source.relative_to(s))]:
        raise ValueError('Changed original IRQ/CQ contract')
    base = s / 'mspi0-dma-peer-research-01/base-config.cs'
    if sha(base) != manifest['model_hashes']['renode-mspi1-config.cs']:
        raise ValueError('Changed configuration baseline')
    cap = s / 'mspi0-tx-main-01' / a.case
    plan = json.loads((cap / 'plan.json').read_text())
    plan.update(id='mspi0-cq-dma-v1', source_root='mspi0-tx-main-01')
    plan['components'] = [dict(name='mspi0-cq-dma', baseline=str(base.relative_to(s)), candidate='tools/renode-mspi1-config.cs',
                               before_sha256=sha(base), after_sha256=sha(root / 'tools/renode-mspi1-config.cs'))]
    anchor = 'mspi0_config: Miscellaneous.BlackwallMspi0RetentionConfig @ none\n'
    if (cap / 'board.repl').read_text().count(anchor) != 1:
        raise ValueError('Different MSPI0 owner')
    plan['board_edits'] = [dict(before=anchor, after=anchor + '    queueDma: true\n    completeDma: ' + str(not a.stuck).lower() + '\n')]
    plan['board_append'] = ''
    plan['runtime_edits'] = []
    q = "m['sysbus.guard'].Mspi0Config.QueueDma"
    fields = ',mspi0_dma_selected=(' + q + ' is not None)'
    for n in ['Enabled', 'Paused', 'DmaActive', 'Starts', 'Completions', 'Aborted', 'Descriptors', 'BytesConsumed', 'DmaStatus']:
        fields += ',mspi0_dma_' + n.lower() + '=int(' + q + '.' + n + ') if ' + q + ' is not None else 0'
    fields += ',mspi0_dma_enable_state=str(' + q + '.EnableState) if ' + q + ' is not None else ""'
    fields += ',mspi0_dma_fault=str(' + q + '.Fault) if ' + q + ' is not None else ""'
    fields += ',mspi0_dma_frames=[dict(source=int(f.Source),device_address=int(f.DeviceAddress),configuration=int(f.Configuration),instruction_configuration=int(f.InstructionConfiguration),xip_configuration=int(f.XipConfiguration),pio_mixed=int(f.PioMixed),length=int(f.Length),sha256=str(f.PayloadSha256)) for f in ' + q + '.Frames] if ' + q + ' is not None else []'
    plan['diagnostics'] = plan['diagnostics'][:-1] + fields + ')'
    plan['reviewed_sources'] = {}
    for case in plan['cases']:
        audit = s / 'mspi0-tx-saved-audit-01' / case / 'report.json'
        plan['reviewed_sources'][case] = dict(path=str(audit.relative_to(s)), sha256=sha(audit))
        prior = json.loads((s / 'mspi0-tx-main-01' / case / 'report.json').read_text())
        g = next(x for x in prior['observed']['guards'] if x['accesses'])
        boundary = dict(kind='strict-mmio', pc=prior['observed']['pc'], **{k: g[k] for k in ['address', 'operation', 'width', 'value']})
        checks = [dict(path=['diagnostics', 'mspi0_dma_selected'], eq=True),
                  dict(path=['diagnostics', 'mspi0_dma_fault'], eq='')]
        if a.stuck:
            checks += [dict(path=['diagnostics', 'mspi0_dma_completions'], eq=0),
                       dict(path=['diagnostics', 'mspi0_dma_frames'], eq=[])]
        plan['semantics'][case] = dict(
            candidate=dict(boundary=dict(kind='bounded-capture'), comparison=dict(policy='bounded-invariants', paths=[['observed', 'memory_policy', 'violations'], ['observed', 'system_control', 'violations']]),
                           checks=checks, allowed_differences=['Explicit SRAM CQ and logical DMA service, 1us/descriptor or 256 payload bytes.'],
                           unresolved_differences=['Provisional boundary; physical timing/wire/panel and unselected pause/error modes unverified.']),
            control=dict(boundary=boundary, comparison=dict(policy='exact', path=['observed']),
                         checks=[dict(path=['selected_observation'], eq_source=['selected_observation']), dict(path=['diagnostics', 'mspi0_dma_selected'], eq=False)],
                         allowed_differences=['Default TX CPU/events unchanged.'], unresolved_differences=['CQEN remains unsupported.']))
    plan.update(host_capture_seconds=120, memory_export_policy='paused-after-observation', mspi0_cq_dma_contract_sha256=sha(source))
    plan.pop('execution_mode', None)
    if a.control:
        plan.pop('host_capture_seconds')
        plan.pop('memory_export_policy')
        plan['execution_mode'] = 'until-guest-stop'
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan, indent=2) + '\n')
    print('Prepared private MSPI0 CQ/DMA plan', a.case, 'stuck' if a.stuck else 'active')


if __name__ == '__main__':
    main()
