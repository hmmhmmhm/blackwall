"""Audit RAM-backed sector erase and the original main's success/timeout paths."""
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
    units = [('mspi1-erase-unit-02', 26), ('mspi1-erase-stuck-unit-01', 20),
             ('mspi1-erase-disabled-unit-01', 8), ('mspi1-erase-readonly-unit-01', 8),
             ('mspi1-erase-protected-unit-01', 8), ('mspi1-erase-reset-unit-02', 20),
             ('mspi1-erase-abort-unit-01', 12), ('mspi1-erase-address-mode-unit-01', 7),
             ('mspi1-erase-array-regression-01', 46), ('mspi1-erase-status-regression-01', 44),
             ('mspi1-erase-xip-regression-01', 39)]
    for folder, count in units:
        d = s / folder
        r = json.loads((d / 'report.json').read_text())
        tag = ('BLACKWALL_ARRAY_UNIT' if 'array-regression' in folder else
               'BLACKWALL_CONTINUOUS_STATUS_UNIT' if 'status-regression' in folder else
               'BLACKWALL_MSPI_POWER_UNIT' if 'xip-regression' in folder else 'BLACKWALL_ERASE_UNIT')
        check(folder + '-log-report', marker((d / 'renode.log').read_text(), tag) == r)
        check(folder + '-count', r['passed'] and r['count'] == len(r['checks']) == count)
        check(folder + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
    for name in ['stock24', 'stock23', 'cfw', 'stock24-default', 'stock24-readonly', 'stock24-stuck-compact']:
        key = 'stock24' if name.startswith('stock24') else name
        d = s / 'mspi1-erase-main-01' / name
        r = json.loads((d / 'report.json').read_text())
        log = (d / 'renode.log').read_text()
        v = parse_log(log)
        validate_assets(d, json.loads((d / 'derived-inputs.json').read_text())['derived'])
        check(name + '-native-report', v == r['observed'])
        check(name + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
        bundle = {'stock24': 'stock-2.4.0.24.bin', 'stock23': 'stock-2.3.0.24.bin', 'cfw': 'faceclaw-38-research-only.bin'}[key]
        _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
        check(name + '-original-main', raw == (d / 'main.bin').read_bytes())
        prior = json.loads((s / 'mspi1-array-main-02' / key / 'report.json').read_text())
        obs = marker(log, 'BLACKWALL_OBSERVATION')
        prefix = prior['selected_observation']['events']
        stuck = name.endswith('stuck-compact')
        if stuck:
            prefix = [dict(e, sequence=i + 1) for i, e in enumerate(e for e in prefix if e['label'] != 'status-byte')]
        check(name + '-same-prefix-or-explicit-projection', obs['events'][:len(prefix)] == prefix)
        check(name + '-no-event-loss', obs['capacity'] == 4096 and not obs['dropped_events'] and obs['sequence'] == len(obs['events']))
        erase = marker(log, 'BLACKWALL_NOR_ERASE')
        cfg = marker(log, 'BLACKWALL_MSPI1_CONFIG')['registers']
        guards = [g for g in v['guards'] if g['accesses']]
        extra = obs['events'][len(prefix):]
        if name.endswith('default') or name.endswith('readonly'):
            check(name + '-old-boundary-preserved', boundary_state(v) == boundary_state(prior['observed']))
            check(name + '-no-erase-start-or-commit', erase['starts'] == erase['completions'] == 0 and not erase['busy'])
        elif stuck:
            check(name + '-device-stays-busy', not erase['can_complete'] and erase['starts'] == 1 and erase['completions'] == 0
                  and erase['busy'] and erase['status'] == 0x43 and erase['wel'])
            polls = [e['r0'] for e in extra if e['label'] == 'status-poll-return']
            results = [e['r0'] for e in extra if e['label'] == 'status-result']
            check(name + '-original-bounded-poll-times-out', polls == [1, 1, 1] and results == [1] * 3600)
            check(name + '-busy-array-read-remains-guarded', len(guards) == 1 and guards[0]['address'] == 0x40061000
                  and guards[0]['value'] == 0x100461 and cfg['12'] == 0x6c and cfg['8'] == 0x1fc1000)
            check(name + '-compact-scope-declared', r['compact_status_results_only'] is True and not any(e['label'] == 'status-byte' for e in obs['events']))
        else:
            check(name + '-one-erase-committed', erase['allowed'] and erase['duration_us'] == 1000 and erase['starts'] == erase['completions'] == 1
                  and not erase['busy'] and erase['last_address'] == 0x1fc0000)
            statuses = [e['r0'] for e in extra if e['label'] == 'status-byte']
            check(name + '-guest-observes-busy-then-idle', 0x43 in statuses and 0x40 in statuses and statuses.index(0x43) < statuses.index(0x40))
            check(name + '-program-request-not-accepted', len(guards) == 1 and guards[0]['address'] == 0x40061000
                  and guards[0]['value'] == 0x1000e1 and cfg['12'] == 2 and cfg['8'] == 0x1fc0000)
            wel = marker(log, 'BLACKWALL_NOR_LATCH')
            check(name + '-next-program-WREN-separate', wel['WREN_completed'] == 3 and wel['wel'] and wel['current'] == 0x42)
        check(name + '-not-physical-latency-evidence', erase['physical_latency_verified'] is False)
        array = marker(log, 'BLACKWALL_NOR_ARRAY')
        check(name + '-only-blank-KV-window', array['start'] == 0x1fc0000 and array['length'] == 0x38000 and not array['physical_contents_known'])
        rows.append(dict(case=name, pc=hex(v['pc']), erase=erase, events=obs['sequence'], compact=stuck))
    for f in ['strict.cs', 'board.repl', 'result.py', 'probe.resc']:
        check('stock23-CFW-same-' + f, (s / 'mspi1-erase-main-01/stock23' / f).read_bytes()
              == (s / 'mspi1-erase-main-01/cfw' / f).read_bytes())
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=rows,
        scope='RAM-backed bounded erase with explicit latency and scenario-reset assumptions; no program/DB init/full boot/hardware proof'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
