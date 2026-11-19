"""Verify native diagnostic RX consumption, alternate fixture, noncompletion and default CPU."""
import argparse
import hashlib
import json
from pathlib import Path
from inspect_ambiq_target import decode
from native_replay import MAIN_LAYOUT
from prepare_vendor_startup_candidate import sha
from run_native_candidate import memory_exports, validate_memory_exports, memory_export_policy, read_memory_snapshot


def inspect(s, case, mode):
    root = {'active': 'mspi0-rx-main-01', 'alternate': 'mspi0-rx-alternate-01',
            'stuck': 'mspi0-rx-stuck-01', 'control': 'mspi0-rx-control-01'}[mode]
    f = s / root / case
    ap = s / 'mspi0-rx-saved-audit-01' / (case if mode == 'active' else mode) / 'report.json'
    a, v, p = [json.loads(x.read_text()) for x in [ap, f / 'report.json', f / 'plan.json']]
    if not a['passed'] or not v['execution_passed'] or v['hardware_accessed']:
        raise ValueError('Unverified native capture')
    for name, expected in a['capture_hashes'].items():
        if sha(f / name) != expected:
            raise ValueError('Changed capture ' + name)
    if sha(f / 'main.bin') != MAIN_LAYOUT[p['cases'][case]][3]:
        raise ValueError('Changed original main')
    validate_memory_exports(f, memory_exports(p), v['memory_exports'])
    if read_memory_snapshot((f / 'renode.log').read_text(), memory_export_policy(p), v['observed']) != v.get('memory_snapshot'):
        raise ValueError('Changed paused memory snapshot')
    o, d = v['observed'], v['diagnostics']
    if d['mspi0_dma_fault'] or (d['accepted_commands'], d['replies']) != (59, 60):
        raise ValueError('Model fault or changed BLE mock startup')
    if mode == 'control':
        old = json.loads((s / 'mspi0-dma-main-04' / case / 'report.json').read_text())
        if not v['control'] or d['mspi0_rx_selected'] or o != old['observed'] or v['selected_observation'] != old['selected_observation']:
            raise ValueError('RX-disabled CPU/events changed')
    else:
        payload = 'a55ac33c' if mode == 'alternate' else '12345678'
        completed = mode != 'stuck'
        expected = dict(rxstarts=1, rxcompletions=1 if completed else 0, rxreads=1, rxbytesdelivered=4, rxaborted=0)
        if not d['mspi0_rx_selected'] or d['mspi0_rx_fixture'] != payload or any(d['mspi0_' + k] != x for k, x in expected.items()):
            raise ValueError('Different declared RX delivery/history')
        frames = [dict(control=0x40441, instruction=0x9f, configuration=0x2040141, payload_hex=payload)] if completed else []
        if d['mspi0_rx_frames'] != frames:
            raise ValueError('RX completion/frame history differs')
        if completed:
            if (d['mspi0_dma_starts'], d['mspi0_dma_completions'], d['mspi0_dma_descriptors'], d['mspi0_dma_bytesconsumed'],
                d['mspi0_tx_starts'], d['mspi0_tx_completions'], d['mspi0_tx_bytesshifted']) != (2, 2, 18, 307204, 29, 29, 17):
                raise ValueError('Different later DMA/PIO progress')
            frame = dict(source=0x20094400, device_address=0, configuration=0x40161, instruction_configuration=0x630062,
                         xip_configuration=0x45ec, pio_mixed=5, length=153602, sha256=hashlib.sha256(bytes(153602)).hexdigest())
            if d['mspi0_dma_frames'] != [frame, frame]:
                raise ValueError('Different actual DMA frames')
        guards = [g for g in o['guards'] if g['accesses']]
        pc = (0x58236c if case == 'stock24' else 0x57b014) if completed else 0x501676
        boundary = (0x40054120, 'write', 4, 0x101) if completed else (0x40010410, 'read', 4, 0)
        if len(guards) != 1 or (guards[0]['address'], guards[0]['operation'], guards[0]['width'], guards[0]['value']) != boundary or o['pc'] != pc:
            raise ValueError('Different completed/pending frontier')
        i = decode((f / 'main.bin').read_bytes(), pc, 4)[0]
        if completed and ((i.mnemonic, i.op_str) != ('str.w', 'r2, [r0, #0x120]') or (o['register_context']['r0'], o['register_context']['r2']) != (0x40054000, 0x101)):
            raise ValueError('Different original IOM4 store')
        if not completed and ((i.mnemonic, i.op_str) != ('ldr', 'r0, [r0]') or o['register_context']['r0'] != 0x40010410):
            raise ValueError('Different pending GPIO117 read')
    return dict(case=case, mode=mode, capture=str(f.relative_to(s)), pc=o['pc'], report_sha256=sha(f / 'report.json'),
                audit_sha256=sha(ap), original_semantic_passed=v['semantic_validation']['passed'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Fresh private evidence output required')
    rows = [inspect(a.simulator, c, 'active') for c in ('stock24', 'stock23', 'cfw')]
    rows += [inspect(a.simulator, 'stock24', mode) for mode in ('alternate', 'stuck', 'control')]
    a.output.mkdir(mode=0o700)
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, native_captures=6,
        physical_identity_verified=False, fault_recovery_verified=False, hardware_accessed=False,
        boot_verified=False, display_verified=False), indent=2) + '\n')
    print('Verified native3 RX once/DMA2, alternate diagnostic input, noncompletion and default exact; IOM4/boot/UI remain incomplete')


if __name__ == '__main__':
    main()
