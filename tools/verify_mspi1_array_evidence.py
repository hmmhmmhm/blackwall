"""Audit bounded blank-KVDB reads and original invalid-header execution."""
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
    units = [('mspi1-array-unit-03', 46), ('mspi1-array-erased-unit-03', 46),
             ('mspi1-array-unknown-unit-02', 4), ('mspi1-array-stuck-unit-02', 4),
             ('mspi1-array-noqe-unit-02', 4), ('mspi1-array-busy-unit-02', 4),
             ('mspi1-array-rdid-regression-02', 30), ('mspi1-array-status-regression-02', 44),
             ('mspi1-array-xip-regression-02', 39)]
    for folder, count in units:
        d = s / folder
        r = json.loads((d / 'report.json').read_text())
        tag = ('BLACKWALL_MSPI1_RDID_UNIT' if 'rdid' in folder else
               'BLACKWALL_CONTINUOUS_STATUS_UNIT' if 'status' in folder else
               'BLACKWALL_MSPI_POWER_UNIT' if 'xip' in folder else 'BLACKWALL_ARRAY_UNIT')
        check(folder + '-log-report', marker((d / 'renode.log').read_text(), tag) == r)
        check(folder + '-count', r['passed'] and r['count'] == len(r['checks']) == count)
        check(folder + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
    for name in ['stock24', 'stock23', 'cfw', 'stock24-default', 'stock24-stuck-on']:
        key = 'stock24' if name.startswith('stock24') else name
        d = s / 'mspi1-array-main-02' / name
        r = json.loads((d / 'report.json').read_text())
        log = (d / 'renode.log').read_text()
        v = parse_log(log)
        validate_assets(d, json.loads((d / 'derived-inputs.json').read_text())['derived'])
        check(name + '-native-report', v == r['observed'])
        check(name + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
        bundle = {'stock24': 'stock-2.4.0.24.bin', 'stock23': 'stock-2.3.0.24.bin', 'cfw': 'faceclaw-38-research-only.bin'}[key]
        _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
        check(name + '-original-main', raw == (d / 'main.bin').read_bytes())
        prior_key = 'stock24-stuck-on' if name.endswith('stuck-on') else key
        prior = json.loads((s / 'mspi1-continuous-status-main-01' / prior_key / 'report.json').read_text())
        obs = marker(log, 'BLACKWALL_OBSERVATION')
        prefix = prior['selected_observation']['events']
        check(name + '-original-prefix-preserved', obs['events'][:len(prefix)] == prefix)
        check(name + '-no-event-loss', not obs['dropped_events'] and obs['sequence'] == len(obs['events']))
        array = marker(log, 'BLACKWALL_NOR_ARRAY')
        headers = [e for e in obs['events'] if e['label'] == 'KV-header-read-return']
        invalid = [e for e in obs['events'] if e['label'] == 'KV-header-invalid-return']
        if name.endswith('default') or name.endswith('stuck-on'):
            check(name + '-old-boundary-maintained', boundary_state(v) == boundary_state(prior['observed']))
            check(name + '-no-array-data-or-header-result', array['reads'] == array['bytes'] == 0 and not headers and not invalid)
        else:
            check(name + '-exact-declared-window', array['profile'] == 'erased-range' and array['start'] == 0x1fc0000 and array['length'] == 0x38000)
            check(name + '-exact-array-read', array['reads'] == 1 and array['bytes'] == 16 and array['last_address'] == 0x1fc0000 and array['rx_entries'] == 0)
            check(name + '-original-header-read-success', len(headers) == 1 and headers[0]['r0'] == 0)
            point = next(p for p in obs['points'] if p['label'] == 'KV-header-read-return')
            check(name + '-four-FF-words-in-guest-buffer', point['snapshot']['words'] == [0xffffffff] * 4)
            check(name + '-original-invalid-header-executed', len(invalid) == 1 and invalid[0]['r0'] == 8 and invalid[0]['sequence'] > headers[0]['sequence'])
            cfg = marker(log, 'BLACKWALL_MSPI1_CONFIG')['registers']
            guards = [g for g in v['guards'] if g['accesses']]
            check(name + '-erase-request-remains-guarded', len(guards) == 1 and guards[0]['address'] == 0x40061000 and guards[0]['operation'] == 'write'
                  and guards[0]['value'] == 0xe1 and cfg['12'] == 0x20 and cfg['8'] == 0x1fc0000)
            wel = marker(log, 'BLACKWALL_NOR_LATCH')
            check(name + '-formatter-WREN-completed-not-erase', wel['wel'] and wel['current'] == 0x42 and wel['WREN_completed'] == 2)
            off = marker(log, 'BLACKWALL_MSPI_CONTROLLER_OFF')
            check(name + '-array-history-survives-controller-cycle', off['count'] == off['power_cycles'] == 2 and array['reads'] == 1)
        check(name + '-not-a-device-dump', array['physical_contents_known'] is False)
        rows.append(dict(case=name, pc=hex(v['pc']), array=array, header_read_hits=len(headers), invalid_header_hits=len(invalid), events=obs['sequence']))
    for f in ['strict.cs', 'board.repl', 'result.py', 'probe.resc']:
        check('stock23-CFW-same-' + f, (s / 'mspi1-array-main-02/stock23' / f).read_bytes()
              == (s / 'mspi1-array-main-02/cfw' / f).read_bytes())
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=rows,
        scope='Declared blank KVDB and logical bounded QREAD4B only; no erase/program, full boot/display or hardware recovery proof'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
