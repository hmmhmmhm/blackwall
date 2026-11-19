"""Verify native normal-sleep progress, MSPI0 restored state and default control."""
import argparse
import json
import struct
from pathlib import Path
from inspect_ambiq_target import decode
from native_replay import MAIN_LAYOUT
from prepare_vendor_startup_candidate import sha
from run_native_candidate import memory_exports, validate_memory_exports, memory_export_policy, read_memory_snapshot


def inspect(s, case, control=False):
    f = s / ('cpu-sleep-control-01' if control else 'cpu-sleep-main-02') / case
    ap = s / 'cpu-sleep-saved-audit-01' / ('control' if control else case) / 'report.json'
    a = json.loads(ap.read_text())
    v = json.loads((f / 'report.json').read_text())
    p = json.loads((f / 'plan.json').read_text())
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
    if (d['accepted_commands'], d['replies']) != (59, 60):
        raise ValueError('Changed preceding BLE startup')
    shadow = None
    if control:
        old = json.loads((s / 'mspi0-retention-main-02' / case / 'report.json').read_text())
        if not v['control'] or d['cpu_sleep_selected'] or o != old['observed'] or v['selected_observation'] != old['selected_observation']:
            raise ValueError('Default CPU/events changed')
    else:
        counts = (2, 4, 5) if case == 'stock24' else (1, 3, 3)
        expected = dict(cpu_sleep_selected=True, cpu_sleep_powercontrolreads=counts[0],
                        cpu_sleep_flushreads=counts[0], cpu_sleep_cpdreads=counts[1],
                        cpu_sleep_cpdwrites=counts[2], cpu_sleep_cpdvalue=0,
                        mspi0_phase='on', mspi0_requests=2, mspi0_responses=3,
                        mspi0_power_cycles=1, mspi0_controller_power_downs=1,
                        mspi0_clock_enabled=True, mspi0_cqcfg=2, mspi0_cqswflags=128)
        if any(d[k] != x for k, x in expected.items()):
            raise ValueError('Different normal-sleep/retained-controller history')
        guards = [g for g in o['guards'] if g['accesses']]
        if len(guards) != 1:
            raise ValueError('Multiple unsupported boundaries')
        g = guards[0]
        if (g['address'], g['operation'], g['width'], g['value'], g['accesses']) != (0x40060208, 'write', 4, 0xffffffff, 1):
            raise ValueError('Different MSPI0 interrupt clear boundary')
        if o['pc'] != (0x4e8a3e if case == 'stock24' else 0x4db66a):
            raise ValueError('Different original PIO initialization frontier')
        i = decode((f / 'main.bin').read_bytes(), o['pc'], 4)[0]
        if (i.mnemonic, i.op_str) != ('str.w', 'r7, [r2, #0x208]') or (o['register_context']['r2'], o['register_context']['r7']) != (0x40060000, 0xffffffff):
            raise ValueError('Different original interrupt clear store')
        source = s / 'mspi0-retention-source-03/report.json'
        pin = json.loads((s / 'mspi0-retention-verification-01/manifest.json').read_text())
        if sha(source) != pin['files'][str(source.relative_to(s))]:
            raise ValueError('Changed instance provenance')
        instance = next(c['instance'] for c in json.loads(source.read_text())['cases'] if c['case'] == case)
        old = (s / 'mspi0-retention-main-02' / case / 'exports/sram-full.bin').read_bytes()
        ram = (f / 'exports/sram-full.bin').read_bytes()
        offset = instance - 0x20000000
        if old[offset + 0x860] != 1 or ram[offset + 0x860] != 0 or struct.unpack_from('<I', ram, offset)[0] != 0x3bebebe:
            raise ValueError('Original retained-state marker/handle differs')
        shadow = dict(instance=instance, valid_before=1, valid_after=0, enabled_handle=0x3bebebe)
    return dict(case=case, control=control, capture=str(f.relative_to(s)), pc=o['pc'],
                report_sha256=sha(f / 'report.json'), audit_sha256=sha(ap), retained_state=shadow,
                original_semantic_passed=v['semantic_validation']['passed'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence')
    rows = [inspect(a.simulator, case) for case in ('stock24', 'stock23', 'cfw')]
    rows.append(inspect(a.simulator, 'stock24', True))
    a.output.mkdir(mode=0o700)
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, native_captures=4,
        wfi_post_path_progress=True, physical_sleep_verified=False, wake_irq_source_verified=False,
        boot_verified=False, display_verified=False, hardware_accessed=False), indent=2) + '\n')
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    print('Verified native3 normal-sleep post-WFI path/MSPI0 resumed; default CPU/events exact; physical sleep and IRQ source unverified')


if __name__ == '__main__':
    main()
