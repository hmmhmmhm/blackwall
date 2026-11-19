"""Audit original KVDB program/readback progress with explicitly projected observations."""
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
    def check(name, value):
        if not value:
            raise ValueError(name)
        checks.append(name)
    def marker(log, tag):
        matches = [json.loads(l.split(' ', 1)[1]) for l in log.splitlines() if l.startswith(tag + ' ')]
        check(tag + '-unique', len(matches) == 1)
        return matches[0]
    units = [('mspi1-program-unit-02', 29), ('mspi1-program-streaming-unit-01', 14),
             ('mspi1-program-disabled-unit-01', 9), ('mspi1-program-readonly-unit-01', 9),
             ('mspi1-program-protected-unit-01', 9), ('mspi1-program-stuck-unit-01', 22),
             ('mspi1-program-reset-unit-01', 22), ('mspi1-program-abort-unit-01', 15),
             ('mspi1-program-mode-unit-01', 7), ('mspi1-program-wire-reset-unit-01', 19),
             ('mspi1-program-erase-regression-01', 26), ('mspi1-program-array-regression-01', 46),
             ('mspi1-program-status-regression-01', 44)]
    for folder, count in units:
        d = s / folder
        r = json.loads((d / 'report.json').read_text())
        tag = ('BLACKWALL_ERASE_UNIT' if 'erase-regression' in folder else
               'BLACKWALL_ARRAY_UNIT' if 'array-regression' in folder else
               'BLACKWALL_CONTINUOUS_STATUS_UNIT' if 'status-regression' in folder else 'BLACKWALL_PROGRAM_UNIT')
        check(folder + '-log-report', marker((d / 'renode.log').read_text(), tag) == r)
        check(folder + '-checks', r['passed'] and r['count'] == len(r['checks']) == count)
        check(folder + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
    suppressed = ['status-byte', 'status-result', 'CQFLAGS-saved', 'MSPI-power-off-return', 'XIP-retention-restored', 'MSPI-retention-state-restored']
    for name in ['stock24', 'stock23', 'cfw', 'stock24-default', 'stock24-readonly', 'stock24-stuck']:
        key = 'stock24' if name.startswith('stock24') else name
        d = s / 'mspi1-program-main-02' / name
        r = json.loads((d / 'report.json').read_text())
        log = (d / 'renode.log').read_text()
        v = parse_log(log)
        validate_assets(d, json.loads((d / 'derived-inputs.json').read_text())['derived'])
        check(name + '-native-report', v == r['observed'])
        check(name + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
        bundle = {'stock24': 'stock-2.4.0.24.bin', 'stock23': 'stock-2.3.0.24.bin', 'cfw': 'faceclaw-38-research-only.bin'}[key]
        _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
        check(name + '-original-main', raw == (d / 'main.bin').read_bytes())
        prior = json.loads((s / 'mspi1-erase-main-01' / key / 'report.json').read_text())
        prefix = [dict(e, sequence=i + 1) for i, e in enumerate(e for e in prior['selected_observation']['events'] if e['label'] not in suppressed)]
        obs = marker(log, 'BLACKWALL_OBSERVATION')
        check(name + '-explicit-projection-and-prefix', r['suppressed_observation_points'] == suppressed and obs['events'][:len(prefix)] == prefix)
        check(name + '-no-dropped-selected-events', obs['capacity'] == 4096 and not obs['dropped_events'] and obs['sequence'] == len(obs['events']))
        pg = marker(log, 'BLACKWALL_NOR_PROGRAM')
        cfg = marker(log, 'BLACKWALL_MSPI1_CONFIG')['registers']
        guards = [g for g in v['guards'] if g['accesses']]
        if name.endswith('default') or name.endswith('readonly'):
            check(name + '-prior-program-boundary-maintained', boundary_state(v) == boundary_state(prior['observed']))
            check(name + '-no-program-or-TX', pg['starts'] == pg['completions'] == pg['bytes'] == pg['tx_writes'] == 0 and pg['prefix_words'] == [0xffffffff] * 4)
        elif name.endswith('stuck'):
            check(name + '-program-never-committed', pg['allowed'] and not pg['can_complete'] and pg['busy'] and pg['starts'] == 1 and pg['completions'] == pg['bytes'] == 0
                  and pg['tx_writes'] == 4 and pg['prefix_words'] == [0xffffffff] * 4)
            polls = [e['r0'] for e in obs['events'][len(prefix):] if e['label'] == 'status-poll-return']
            check(name + '-original-program-poll-timeout', polls == [1, 1])
            check(name + '-busy-read-stays-guarded', len(guards) == 1 and guards[0]['address'] == 0x40061000 and guards[0]['value'] == 0x100461 and cfg['12'] == 0x6c and cfg['8'] == 0x1fc1000)
        else:
            expected_bytes = 2337 if key == 'stock24' else 2333
            expected_tx = 613 if key == 'stock24' else 612
            check(name + '-actual-program-commits', pg['allowed'] and pg['duration_us'] == 1000 and pg['starts'] == pg['completions'] == 178
                  and pg['bytes'] == expected_bytes and pg['tx_writes'] == expected_tx and not pg['busy'] and pg['tx_entries'] == 0)
            check(name + '-KV-magic-in-NOR', pg['prefix_words'][1] == 0x30424446 and pg['prefix_words'][0] != 0xffffffff)
            valid = [e for e in obs['events'] if e['label'] == 'KV-header-valid']
            check(name + '-original-valid-header-path', len(valid) == 57 and all(e['r0'] == 1 for e in valid))
            check(name + '-NVdb-still-unknown', len(guards) == 1 and guards[0]['address'] == 0x40061000 and guards[0]['value'] == 0x100461
                  and cfg['12'] == 0x6c and cfg['8'] == 0x1ff8000)
            erase = marker(log, 'BLACKWALL_NOR_ERASE')
            check(name + '-bounded-erase-history', erase['starts'] == erase['completions'] == 112 and not erase['busy'])
            off = marker(log, 'BLACKWALL_MSPI_CONTROLLER_OFF')
            check(name + '-controller-cycle-history', off['count'] == off['power_cycles'] == off['xip_restores'] == 704)
        check(name + '-not-physical-timing-evidence', pg['physical_latency_verified'] is False)
        array = marker(log, 'BLACKWALL_NOR_ARRAY')
        check(name + '-KV-only-declared-range', array['start'] == 0x1fc0000 and array['length'] == 0x38000 and not array['physical_contents_known'])
        rows.append(dict(case=name, pc=hex(v['pc']), program=pg, events=obs['sequence']))
    for f in ['strict.cs', 'board.repl', 'result.py', 'probe.resc']:
        check('stock23-CFW-same-' + f, (s / 'mspi1-program-main-02/stock23' / f).read_bytes() == (s / 'mspi1-program-main-02/cfw' / f).read_bytes())
    check('stock23-CFW-matching-observed-program-summary', rows[1]['program'] == rows[2]['program'])
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=rows,
        scope='RAM-backed page program and original KV header readback; no full DB-init return, physical storage ABI, NVdb data or full boot/display proof'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
