"""Audit native original retention restoration and guarded fallback conditions."""
import argparse
import json
from pathlib import Path
from native_replay import parse_log, validate_assets, boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    s, out = a.simulator, a.output
    out.mkdir(mode=0o700)
    checks, rows = [], []
    def check(name, condition):
        if not condition:
            raise ValueError(name)
        checks.append(name)
    def marker(log, tag):
        matches = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines() if line.startswith(tag + ' ')]
        check(tag + '-unique', len(matches) == 1)
        return matches[0]
    for folder, expected in [('mspi1-xip-restore-unit-02', 39), ('mspi1-xip-restore-default-unit-02', 37),
                             ('mspi1-xip-restore-mixed-regression-01', 63), ('mspi1-xip-restore-power-regression-01', 26)]:
        d = s / folder
        r = json.loads((d / 'report.json').read_text())
        tag = 'BLACKWALL_MSPI1_XIP_MIXED_UNIT' if 'mixed' in folder else 'BLACKWALL_MSPI_POWER_UNIT'
        check(folder + '-log-report', marker((d / 'renode.log').read_text(), tag) == r)
        check(folder + '-checks', r['passed'] and r['count'] == len(r['checks']) == expected)
        check(folder + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
    for name in ['stock24', 'stock23', 'cfw', 'stock24-default', 'stock24-stuck-on']:
        key = 'stock24' if name.startswith('stock24') else name
        d = s / 'mspi1-xip-restore-main-02' / name
        r = json.loads((d / 'report.json').read_text())
        log = (d / 'renode.log').read_text()
        v = parse_log(log)
        validate_assets(d, json.loads((d / 'derived-inputs.json').read_text())['derived'])
        check(name + '-native-report', v == r['observed'])
        check(name + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
        bundle = {'stock24': 'stock-2.4.0.24.bin', 'stock23': 'stock-2.3.0.24.bin', 'cfw': 'faceclaw-38-research-only.bin'}[key]
        _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
        check(name + '-original-bytes', raw == (d / 'main.bin').read_bytes())
        obs = marker(log, 'BLACKWALL_OBSERVATION')
        prior = json.loads((s / 'mspi1-power-off-main-02' / ('stock24-stuck-on' if name.endswith('stuck-on') else key) / 'report.json').read_text())
        prefix = prior['selected_observation']['events']
        check(name + '-original-prefix', len(prefix) == 353 and obs['events'][:353] == prefix)
        check(name + '-no-event-loss', not obs['dropped_events'] and obs['sequence'] == len(obs['events']))
        off = marker(log, 'BLACKWALL_MSPI_CONTROLLER_OFF')
        xip = [e for e in obs['events'] if e['label'] == 'XIP-retention-restored']
        restored = [e for e in obs['events'] if e['label'] == 'MSPI-retention-state-restored']
        if name.endswith('default'):
            check(name + '-prior-boundary-unchanged', boundary_state(v) == boundary_state(prior['observed']))
            check(name + '-default-no-exception', not off['xip_restore_selected'] and off['xip_restores'] == 0 and not xip and not restored)
        elif name.endswith('stuck-on'):
            old = json.loads((s / 'mspi1-power-off-main-02/stock24-stuck-on/report.json').read_text())
            check(name + '-stuck-boundary-unchanged', boundary_state(v) == boundary_state(old['observed']))
            check(name + '-no-token-without-off', off['count'] == off['power_cycles'] == off['xip_restores'] == 0 and not xip and not restored)
        else:
            delta = 0 if key == 'stock24' else 0xd3d4
            check(name + '-atomic-XIP-store-reached', len(xip) == 1 and xip[0]['pc'] == 0x4e9058 - delta and xip[0]['r2'] == 0xed)
            check(name + '-full-state-restoration-end-reached', len(restored) == 1 and restored[0]['pc'] == 0x4e9182 - delta
                  and restored[0]['r0'] == 0 and restored[0]['sequence'] > xip[0]['sequence'])
            check(name + '-one-off-one-restore', off['count'] == off['power_cycles'] == off['xip_restores'] == 1 and off['phase'] == 'on')
            guards = [g for g in v['guards'] if g['accesses']]
            check(name + '-next-PIO-guard', len(guards) == 1 and guards[0]['address'] == 0x40061000
                  and guards[0]['value'] == 0x10441 and guards[0]['operation'] == 'write')
            aperture = marker(log, 'BLACKWALL_MSPI1_XIP')
            check(name + '-XIP-still-no-backing', not aperture['backing_data'] and aperture['guard_accesses'] == 0)
        nor = marker(log, 'BLACKWALL_NOR_ADDRESS')
        wel = marker(log, 'BLACKWALL_NOR_LATCH')
        check(name + '-NOR-state-retained', nor['four_byte'] and nor['current'] == 32 and wel['current'] == 64 and not wel['wel'])
        rows.append(dict(case=name, pc=hex(v['pc']), off=off, XIP_restore_hits=len(xip), state_restore_hits=len(restored)))
    for file in ['strict.cs', 'board.repl', 'result.py', 'probe.resc']:
        check('stock23-cfw-same-' + file, (s / 'mspi1-xip-restore-main-02/stock23' / file).read_bytes()
              == (s / 'mspi1-xip-restore-main-02/cfw' / file).read_bytes())
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=rows,
        scope='Guarded digital XIP register restoration only; no memory data, full boot/display or hardware recovery proof'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
