"""Verify saved timed TX frames, noncompletion fault and unchanged default CPU."""
import argparse
import json
from pathlib import Path
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from native_replay import MAIN_LAYOUT
from prepare_vendor_startup_candidate import sha
from run_native_candidate import memory_exports, validate_memory_exports, memory_export_policy, read_memory_snapshot


def inspect(s, case, mode):
    folder = {'active': 'mspi0-tx-main-01', 'stuck': 'mspi0-tx-stuck-01', 'control': 'mspi0-tx-control-01'}[mode]
    f = s / folder / case
    ap = s / 'mspi0-tx-saved-audit-01' / (case if mode == 'active' else mode) / 'report.json'
    v = json.loads((f / 'report.json').read_text())
    p = json.loads((f / 'plan.json').read_text())
    a = json.loads(ap.read_text())
    if not a['passed'] or not v['execution_passed'] or v['hardware_accessed']:
        raise ValueError('Unverified saved capture')
    for n, pin in a['capture_hashes'].items():
        if sha(f / n) != pin:
            raise ValueError('Changed capture ' + n)
    if sha(f / 'main.bin') != MAIN_LAYOUT[p['cases'][case]][3]:
        raise ValueError('Changed original main')
    validate_memory_exports(f, memory_exports(p), v['memory_exports'])
    if read_memory_snapshot((f / 'renode.log').read_text(), memory_export_policy(p), v['observed']) != v.get('memory_snapshot'):
        raise ValueError('Changed paused snapshot')
    o, d = v['observed'], v['diagnostics']
    if (d['accepted_commands'], d['replies']) != (59, 60) or d['mspi0_tx_slave_effects']:
        raise ValueError('Changed earlier startup/slave-effect scope')
    if mode == 'control':
        old = json.loads((s / 'cpu-sleep-main-02' / case / 'report.json').read_text())
        if not v['control'] or d['mspi0_tx_selected'] or o != old['observed'] or v['selected_observation'] != old['selected_observation']:
            raise ValueError('Default CPU/events changed')
    else:
        if not d['mspi0_tx_selected']:
            raise ValueError('Missing TX profile')
        expected = dict(mspi0_tx_starts=4, mspi0_tx_completions=4, mspi0_tx_aborted=0,
                        mspi0_tx_fifowrites=1, mspi0_tx_bytesshifted=1) if mode == 'active' else dict(
                        mspi0_tx_starts=1, mspi0_tx_completions=0, mspi0_tx_aborted=0,
                        mspi0_tx_fifowrites=0, mspi0_tx_bytesshifted=0)
        if any(d[k] != x for k, x in expected.items()):
            raise ValueError('Different TX history')
        frames = d['mspi0_tx_frames']
        if mode == 'active':
            if [(f['instruction'], f['control'], f['address'], f['payload_hex']) for f in frames] != [(0x66, 0xc1, 0, ''), (0x99, 0xc1, 0, ''), (6, 0xc1, 0, ''), (1, 0x100c1, 0, '10')]:
                raise ValueError('Different original outbound frames')
            if any(f['configuration'] & 31 != 1 or f['configuration'] & 0x80 for f in frames):
                raise ValueError('Different serial/8-bit instruction configuration')
        elif frames:
            raise ValueError('Fault fabricated completed frame')
        guards = [g for g in o['guards'] if g['accesses']]
        if len(guards) != 1:
            raise ValueError('Multiple unsupported boundaries')
        g = guards[0]
        raw = (f / 'main.bin').read_bytes()
        if mode == 'active':
            if (g['address'], g['operation'], g['width'], g['value'], g['accesses']) != (0x400602a0, 'write', 4, 3, 1) or o['pc'] != (0x572c2a if case == 'stock24' else 0x555cd6):
                raise ValueError('Different command queue enable boundary')
            i = decode(raw, o['pc'], 2)[0]
            if (i.mnemonic, i.op_str) != ('str', 'r0, [r2]') or (o['register_context']['r0'], o['register_context']['r2']) != (3, 0x400602a0):
                raise ValueError('Different original CQ enable store')
            if d['mspi0_cqcfg'] != 2:
                raise ValueError('Rejected queue enable mutated stored configuration')
        else:
            if (g['address'], g['operation'], g['width'], g['value'], g['accesses']) != (0x40010410, 'read', 4, 0, 1) or o['pc'] != 0x501676:
                raise ValueError('Different fault GPIO117 boundary')
            i = decode(raw, o['pc'], 2)[0]
            if (i.mnemonic, i.op_str) != ('ldr', 'r0, [r0]') or literal(raw, decode(raw, o['pc'] - 4, 4)[0]) != 0x40010410:
                raise ValueError('Different GPIO source dataflow')
    return dict(case=case, mode=mode, capture=str(f.relative_to(s)), pc=o['pc'],
                report_sha256=sha(f / 'report.json'), audit_sha256=sha(ap),
                original_semantic_passed=v['semantic_validation']['passed'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence')
    rows = [inspect(a.simulator, c, 'active') for c in ('stock24', 'stock23', 'cfw')]
    rows += [inspect(a.simulator, 'stock24', mode) for mode in ('stuck', 'control')]
    a.output.mkdir(mode=0o700)
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, native_captures=5,
        slave_effects_verified=False, fifo_fault_recovery_verified=False, hardware_accessed=False,
        boot_verified=False, display_verified=False), indent=2) + '\n')
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    print('Verified native3 four TX frames, fault no completion, default CPU/events exact; CQ/slave/display remain unverified')


if __name__ == '__main__':
    main()
