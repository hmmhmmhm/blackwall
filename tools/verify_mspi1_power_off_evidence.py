"""Recheck native power-off observations against pinned original inputs and logs."""
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
    checks = []
    def check(name, condition):
        if not condition:
            raise ValueError(name)
        checks.append(name)
    def marker(log, tag):
        rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines() if line.startswith(tag + ' ')]
        check(tag + '-unique', len(rows) == 1)
        return rows[0]
    for folder, count in [('mspi1-power-off-unit-03', 26), ('mspi1-power-off-stuck-unit-02', 14),
                          ('mspi1-power-off-unknown-unit-02', 4), ('mspi1-power-off-owner-unit-01', 6),
                          ('mspi1-power-off-cqflags-regression-02', 33), ('mspi1-power-off-wrdi-regression-02', 23)]:
        d = s / folder
        r = json.loads((d / 'report.json').read_text())
        tag = ('BLACKWALL_CQFLAGS_UNIT' if 'cqflags' in folder else
               'BLACKWALL_WRDI_UNIT' if 'wrdi' in folder else 'BLACKWALL_MSPI_POWER_UNIT')
        check(folder + '-log-report', marker((d / 'renode.log').read_text(), tag) == r)
        check(folder + '-checks', r['passed'] and r['count'] == len(r['checks']) == count)
        check(folder + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
    rows = []
    for name in ['stock24', 'stock23', 'cfw', 'stock24-stuck-on', 'stock24-unknown']:
        key = 'stock24' if name.startswith('stock24') else name
        d = s / 'mspi1-power-off-main-02' / name
        r = json.loads((d / 'report.json').read_text())
        log = (d / 'renode.log').read_text()
        v = parse_log(log)
        check(name + '-native-log-report', v == r['observed'])
        validate_assets(d, json.loads((d / 'derived-inputs.json').read_text())['derived'])
        check(name + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
        bundle = {'stock24': 'stock-2.4.0.24.bin', 'stock23': 'stock-2.3.0.24.bin', 'cfw': 'faceclaw-38-research-only.bin'}[key]
        _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
        check(name + '-original-bytes', raw == (d / 'main.bin').read_bytes())
        off = marker(log, 'BLACKWALL_MSPI_CONTROLLER_OFF')
        obs = marker(log, 'BLACKWALL_OBSERVATION')
        prior = json.loads((s / 'mspi1-cqflags-main-02' / key / 'report.json').read_text())
        prefix = prior['selected_observation']['events']
        check(name + '-prefix-and-no-loss', len(prefix) == 352 and obs['events'][:352] == prefix
              and not obs['dropped_events'] and len(obs['events']) == obs['sequence'])
        ret = [e['r0'] for e in obs['events'] if e['label'] == 'MSPI-power-off-return']
        guards = [g for g in v['guards'] if g['accesses']]
        if name.endswith('unknown'):
            check(name + '-same-boundary', boundary_state(v) == boundary_state(prior['observed']))
            check(name + '-no-opt-in-no-powerdown', ret == [] and off['count'] == off['power_cycles'] == 0
                  and not off['shutdown_gate'] and off['external_supply'] == 'unspecified')
        elif name.endswith('stuck-on'):
            check(name + '-original-timeout-return', ret == [4])
            check(name + '-no-reset-on-stuck-response', off['count'] == off['power_cycles'] == 0
                  and off['phase'] == 'stuck-on' and off['status'] == 0x8000)
            check(name + '-guarded-reenable', len(guards) == 1 and guards[0]['address'] == 0x40021004
                  and guards[0]['value'] == 0x8400 and guards[0]['operation'] == 'write')
        else:
            check(name + '-original-success-and-restart', ret == [0] and off['count'] == off['power_cycles'] == 1
                  and off['phase'] == 'on' and off['status'] == off['request'] == 0x8000)
            check(name + '-next-original-restore-boundary', v['pc'] == (0x4e9054 if key == 'stock24' else 0x4dbc80)
                  and len(guards) == 1 and guards[0]['address'] == 0x40061090
                  and guards[0]['value'] == 0xed and guards[0]['operation'] == 'write')
        nor = marker(log, 'BLACKWALL_NOR_ADDRESS')
        wel = marker(log, 'BLACKWALL_NOR_LATCH')
        check(name + '-external-state-retained', nor['four_byte'] and nor['current'] == 32 and not wel['wel'] and wel['current'] == 64)
        rows.append(dict(case=name, pc=hex(v['pc']), power_return=ret, off=off))
    for f in ['strict.cs', 'board.repl', 'result.py', 'probe.resc']:
        check('stock23-cfw-same-' + f, (s / 'mspi1-power-off-main-02/stock23' / f).read_bytes()
              == (s / 'mspi1-power-off-main-02/cfw' / f).read_bytes())
    report = dict(passed=True, count=len(checks), checks=checks, native=rows,
                  scope='Explicit digital off response and retained-NOR hypothesis, not physical recovery or full boot/display')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
