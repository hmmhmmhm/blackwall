"""Audit saved native logical DMA payloads, next original RX frontier and controls."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from inspect_ambiq_target import decode
from native_replay import MAIN_LAYOUT
from prepare_vendor_startup_candidate import sha
from run_native_candidate import memory_exports, validate_memory_exports, memory_export_policy, read_memory_snapshot


def inspect(s, case, mode):
    folder = {'active': 'mspi0-dma-main-04', 'stuck': 'mspi0-dma-stuck-01', 'control': 'mspi0-dma-control-01'}[mode]
    f = s / folder / case
    ap = s / 'mspi0-dma-saved-audit-01' / (case if mode == 'active' else mode) / 'report.json'
    a = json.loads(ap.read_text())
    v = json.loads((f / 'report.json').read_text())
    p = json.loads((f / 'plan.json').read_text())
    if not a['passed'] or not v['execution_passed'] or v['hardware_accessed']:
        raise ValueError('Unverified saved capture')
    for name, expected in a['capture_hashes'].items():
        if sha(f / name) != expected:
            raise ValueError('Changed capture ' + name)
    if sha(f / 'main.bin') != MAIN_LAYOUT[p['cases'][case]][3]:
        raise ValueError('Changed original main')
    validate_memory_exports(f, memory_exports(p), v['memory_exports'])
    if read_memory_snapshot((f / 'renode.log').read_text(), memory_export_policy(p), v['observed']) != v.get('memory_snapshot'):
        raise ValueError('Changed paused snapshot')
    d, o = v['diagnostics'], v['observed']
    if d['mspi0_dma_fault'] or (d['accepted_commands'], d['replies']) != (59, 60):
        raise ValueError('Model rejection or changed earlier BLE mock startup')
    if mode == 'control':
        old = json.loads((s / 'mspi0-tx-main-01' / case / 'report.json').read_text())
        if not v['control'] or d['mspi0_dma_selected'] or o != old['observed'] or v['selected_observation'] != old['selected_observation']:
            raise ValueError('Default CPU/events changed')
    else:
        expected = dict(starts=1, completions=1, descriptors=9, bytesconsumed=153602, aborted=0) if mode == 'active' else dict(
            starts=1, completions=0, descriptors=6, bytesconsumed=0, aborted=0)
        if not d['mspi0_dma_selected'] or any(d['mspi0_dma_' + k] != val for k, val in expected.items()):
            raise ValueError('Different DMA history')
        if mode == 'active':
            prior = json.loads((s / 'mspi0-cq-submit-source-03/report.json').read_text())
            source = next(x for x in prior['cases'] if x['case'] == case)
            frame = dict(source=source['dma_source'], device_address=0, configuration=0x40161,
                         instruction_configuration=0x630062, xip_configuration=0x45ec, pio_mixed=5,
                         length=153602, sha256=hashlib.sha256(bytes(153602)).hexdigest())
            if frame['sha256'] != source['dma_buffer_sha256'] or d['mspi0_dma_frames'] != [frame]:
                raise ValueError('DMA payload differs from original pre-CQ source buffer')
            if (d['mspi0_tx_starts'], d['mspi0_tx_completions'], d['mspi0_tx_bytesshifted']) != (28, 28, 17):
                raise ValueError('Different following PIO history')
            tx = d['mspi0_tx_frames']
            if [(x['instruction'], x['payload_hex']) for x in tx[:4]] != [(0x66, ''), (0x99, ''), (6, ''), (1, '10')]:
                raise ValueError('Earlier PIO prefix changed')
            guards = [x for x in o['guards'] if x['accesses']]
            if len(guards) != 1 or (guards[0]['address'], guards[0]['operation'], guards[0]['width'], guards[0]['value']) != (0x40060000, 'write', 4, 0x40441):
                raise ValueError('Different next RX frontier')
            pc = 0x4e8a46 if case == 'stock24' else 0x4db672
            raw = (f / 'main.bin').read_bytes()
            i = decode(raw, pc, 4)[0]
            if o['pc'] != pc or (i.mnemonic, i.op_str) != ('str.w', 'lr, [r2]'):
                raise ValueError('Different original RX start instruction')
            regs = o['register_context']
            if (regs['r14'], regs['r2']) != (0x40441, 0x40060000):
                raise ValueError('Different RX control dataflow')
            ram = (f / 'exports/sram-full.bin').read_bytes()
            req = ram[regs['r1'] - 0x20000000:regs['r1'] - 0x20000000 + 24]
            if struct.unpack_from('<I', req)[0] != 4 or req[6] != 0 or req[12] != 1 or struct.unpack_from('<H', req, 14)[0] != 0x9f:
                raise ValueError('Different original RX request')
        elif d['mspi0_dma_frames'] or not d['mspi0_dma_dmaactive']:
            raise ValueError('Stuck DMA fabricated completion or lost active request')
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
        physical_wire_verified=False, native_irq_path_directly_instrumented=False, fault_recovery_verified=False,
        hardware_accessed=False, boot_verified=False, display_verified=False), indent=2) + '\n')
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    print('Verified native3 SRAM DMA153602B/hash and next RX, noncompletion, default CPU/events; no panel/full boot')


if __name__ == '__main__':
    main()
