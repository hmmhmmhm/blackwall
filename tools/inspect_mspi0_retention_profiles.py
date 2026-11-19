"""Verify saved natural MSPI0 retention success/fault and default CPU control."""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from analyze_adc_metadata import SVD_SHA
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from native_replay import MAIN_LAYOUT
from prepare_vendor_startup_candidate import sha
from run_native_candidate import memory_exports, validate_memory_exports, memory_export_policy, read_memory_snapshot


def inspect(s, case, mode):
    source = {'active': 'mspi0-retention-main-02', 'stuck': 'mspi0-retention-stuck-01', 'control': 'mspi0-retention-control-01'}[mode]
    f = s / source / case
    ap = s / 'mspi0-retention-saved-audit-01' / (case if mode == 'active' else mode) / 'report.json'
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
    if (d['accepted_commands'], d['replies']) != (59, 60):
        raise ValueError('Changed preceding BLE startup')
    if mode == 'control':
        old = json.loads((s / 'mspi0-queue-main-01' / case / 'report.json').read_text())
        if not v['control'] or d['mspi0_retention_selected'] or o != old['observed'] or v['selected_observation'] != old['selected_observation']:
            raise ValueError('Default CPU/events changed')
    else:
        expected = dict(mspi0_retention_selected=True, mspi0_off_requests=1,
                        mspi0_cqflagreads=1, mspi0_last_flags=128,
                        mspi0_config_reads=32, mspi0_config_writes=20,
                        mspi0_cqreads=8, mspi0_cqwrites=6,
                        mspi0_irq_reads=4, mspi0_irq_writes=3,
                        mspi0_irq_enable=0, mspi0_irq_status=0, mspi0_clock_enabled=False)
        if mode == 'active':
            expected.update(mspi0_phase='powered-off', mspi0_power_cycles=1, mspi0_controller_power_downs=1,
                            mspi0_cqcfg=0, mspi0_cqswflags=0, mspi0_status_word=0)
        else:
            expected.update(mspi0_phase='stuck-on', mspi0_power_cycles=0, mspi0_controller_power_downs=0,
                            mspi0_cqcfg=2, mspi0_cqswflags=128, mspi0_status_word=0x4000)
        if any(d[k] != x for k, x in expected.items()):
            raise ValueError('Different retained-controller history')
        clock = o['mcu_clock_response']
        if clock['profile'] != 'nominal' or clock['mode_word'] != 22 or clock['misc_word'] & 0x20:
            raise ValueError('Original clock release did not clear HFRC2 force')
        guards = [g for g in o['guards'] if g['accesses']]
        if len(guards) != 1:
            raise ValueError('Multiple unsupported boundaries')
        g = guards[0]
        if (g['address'], g['operation'], g['width'], g['value'], g['accesses']) != (0x40021050, 'read', 4, 0, 1):
            raise ValueError('Different CPU power-control boundary')
        if o['pc'] != (0x44e10c if case == 'stock24' else 0x44d81c) or o['register_context']['r0'] != 0x40021050:
            raise ValueError('Different original power-control load')
        raw = (f / 'main.bin').read_bytes()
        i = decode(raw, o['pc'], 2)[0]
        load = decode(raw, o['pc'] - 4, 4)[0]
        if (i.mnemonic, i.op_str) != ('ldr', 'r0, [r0]') or literal(raw, load) != 0x40021050:
            raise ValueError('Different original register dataflow')
    return dict(case=case, mode=mode, capture=str(f.relative_to(s)),
                report_sha256=sha(f / 'report.json'), audit_sha256=sha(ap), pc=o['pc'],
                original_semantic_passed=v['semantic_validation']['passed'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence')
    svd = a.simulator / 'apollo-dfp-research-01/apollo510.svd'
    if sha(svd) != SVD_SHA:
        raise ValueError('Changed public register metadata')
    peripheral = next(x for x in ET.parse(svd).getroot().findall('./peripherals/peripheral') if x.findtext('name') == 'PWRCTRL')
    register = next(x for x in peripheral.findall('./registers/register') if x.findtext('name') == 'CPUPWRCTRL')
    if int(register.findtext('addressOffset'), 0) != 0x50 or int(register.findtext('resetValue'), 0) != 0:
        raise ValueError('Different CPU power register metadata')
    rows = [inspect(a.simulator, case, 'active') for case in ('stock24', 'stock23', 'cfw')]
    rows += [inspect(a.simulator, 'stock24', mode) for mode in ('stuck', 'control')]
    a.output.mkdir(mode=0o700)
    (a.output / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows, native_captures=5,
        safe_fault_fallback_verified=False, complete_wake_verified=False,
        boot_verified=False, display_verified=False, hardware_accessed=False), indent=2) + '\n')
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    print('Verified native3 retained-controller off, stuck-on without reset, default CPU/events exact; wake/boot/display incomplete')


if __name__ == '__main__':
    main()
