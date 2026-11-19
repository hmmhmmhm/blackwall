"""Verify saved native MSPI0 disabled-queue/IRQ frontier and default control."""
import argparse
import json
from pathlib import Path
from inspect_ambiq_target import decode
from native_replay import MAIN_LAYOUT
from prepare_vendor_startup_candidate import sha
from run_native_candidate import memory_exports, validate_memory_exports, memory_export_policy, read_memory_snapshot


def inspect(s, case, control=False):
    name = 'mspi0-queue-control-01' if control else 'mspi0-queue-main-01'
    f = s / name / case
    ap = s / 'mspi0-queue-saved-audit-01' / ('control' if control else case) / 'report.json'
    audit = json.loads(ap.read_text())
    v = json.loads((f / 'report.json').read_text())
    p = json.loads((f / 'plan.json').read_text())
    if not audit['passed'] or not v['execution_passed'] or v['hardware_accessed']:
        raise ValueError('Unverified saved capture')
    for n, h in audit['capture_hashes'].items():
        if sha(f / n) != h:
            raise ValueError('Changed capture ' + n)
    if sha(f / 'main.bin') != MAIN_LAYOUT[p['cases'][case]][3]:
        raise ValueError('Changed original main')
    validate_memory_exports(f, memory_exports(p), v['memory_exports'])
    if read_memory_snapshot((f / 'renode.log').read_text(), memory_export_policy(p), v['observed']) != v.get('memory_snapshot'):
        raise ValueError('Changed paused memory snapshot')
    o, d = v['observed'], v['diagnostics']
    if (d['accepted_commands'], d['replies']) != (59, 60):
        raise ValueError('Changed preceding BLE startup')
    if control:
        old = json.loads((s / 'mspi0-config-main-01' / case / 'report.json').read_text())
        if not v['control'] or d['mspi0_queue_selected'] or o != old['observed'] or v['selected_observation'] != old['selected_observation']:
            raise ValueError('Default CPU/events changed')
    else:
        expected = dict(mspi0_queue_selected=True, mspi0_cqcfg=2, mspi0_cqswflags=128,
                        mspi0_cqreads=5, mspi0_cqwrites=6, mspi0_cqflagreads=0,
                        mspi0_irq_enable=0x1a80, mspi0_irq_status=0, mspi0_irq_reads=3,
                        mspi0_irq_writes=2, mspi0_phase='on')
        if any(d[k] != x for k, x in expected.items()):
            raise ValueError('Different natural queue/IRQ history')
        guards = [g for g in o['guards'] if g['accesses']]
        if len(guards) != 1:
            raise ValueError('Multiple unsupported boundaries')
        g = guards[0]
        if (g['name'], g['accesses'], g['address'], g['operation'], g['width'], g['value']) != ('guard_iom7_tail', 1, 0x400602b0, 'read', 4, 0):
            raise ValueError('Different CQFLAGS boundary')
        if o['pc'] != (0x4e92dc if case == 'stock24' else 0x4dbf08) or o['register_context']['r1'] != 0x40060000:
            raise ValueError('Different original retained-sleep context')
        i = decode((f / 'main.bin').read_bytes(), o['pc'], 4)[0]
        if (i.mnemonic, i.op_str) != ('ldr.w', 'r1, [r1, #0x2b0]'):
            raise ValueError('Different original CQFLAGS load')
    return dict(case=case, control=control, capture=str(f.relative_to(s)),
                report_sha256=sha(f / 'report.json'), audit_sha256=sha(ap), pc=o['pc'],
                original_semantic_passed=v['semantic_validation']['passed'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence')
    rows = [inspect(a.simulator, c) for c in ('stock24', 'stock23', 'cfw')]
    rows.append(inspect(a.simulator, 'stock24', True))
    a.output.mkdir(mode=0o700)
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows,
        native_captures=4, queue_execution_verified=False, power_off_verified=False,
        boot_verified=False, display_verified=False, hardware_accessed=False), indent=2) + '\n')
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    print('Verified native3 queue/IRQ to unknown CQFLAGS; default control CPU/events exact')


if __name__ == '__main__':
    main()
