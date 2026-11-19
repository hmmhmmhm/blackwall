"""Check original repeated-status progress without treating logical pins as hardware proof."""
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
    units = [('mspi1-continuous-status-unit-03', 44), ('mspi1-continuous-status-busy-unit-03', 44),
             ('mspi1-continuous-status-disabled-unit-01', 4), ('mspi1-continuous-status-stuck-unit-01', 4),
             ('mspi1-continuous-status-wrdi-regression-01', 23), ('mspi1-continuous-status-xip-regression-01', 39)]
    for folder, count in units:
        d = s / folder
        tag = ('BLACKWALL_WRDI_UNIT' if 'wrdi' in folder else
               'BLACKWALL_MSPI_POWER_UNIT' if 'xip' in folder else 'BLACKWALL_CONTINUOUS_STATUS_UNIT')
        r = json.loads((d / 'report.json').read_text())
        check(folder + '-log-report', marker((d / 'renode.log').read_text(), tag) == r)
        check(folder + '-count', r['passed'] and r['count'] == len(r['checks']) == count)
        check(folder + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
    for name in ['stock24', 'stock23', 'cfw', 'stock24-default', 'stock24-stuck-on']:
        key = 'stock24' if name.startswith('stock24') else name
        d = s / 'mspi1-continuous-status-main-01' / name
        r = json.loads((d / 'report.json').read_text())
        log = (d / 'renode.log').read_text()
        v = parse_log(log)
        check(name + '-native-replay', v == r['observed'])
        validate_assets(d, json.loads((d / 'derived-inputs.json').read_text())['derived'])
        check(name + '-current-model', (d / 'strict.cs').read_bytes() == models(s))
        bundle = {'stock24': 'stock-2.4.0.24.bin', 'stock23': 'stock-2.3.0.24.bin', 'cfw': 'faceclaw-38-research-only.bin'}[key]
        _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
        check(name + '-original-main', raw == (d / 'main.bin').read_bytes())
        prior_key = 'stock24-stuck-on' if name.endswith('stuck-on') else key
        prior = json.loads((s / 'mspi1-xip-restore-main-02' / prior_key / 'report.json').read_text())
        obs = marker(log, 'BLACKWALL_OBSERVATION')
        prefix = prior['selected_observation']['events']
        check(name + '-same-original-prefix', obs['events'][:len(prefix)] == prefix)
        check(name + '-no-event-loss', not obs['dropped_events'] and obs['sequence'] == len(obs['events']))
        status = marker(log, 'BLACKWALL_CONTINUOUS_STATUS')
        if name.endswith('default') or name.endswith('stuck-on'):
            check(name + '-old-boundary-preserved', boundary_state(v) == boundary_state(prior['observed']))
            check(name + '-no-repeated-status-completion', status['completed'] == status['discarded_bytes'] == 0)
        else:
            check(name + '-one-repeated-byte-skipped', status['selected'] and status['completed'] == status['discarded_bytes'] == 1 and status['total_status'] == 5)
            extra = obs['events'][len(prefix):]
            check(name + '-original-byte-and-poll-results', [e['label'] for e in extra] == ['status-byte', 'status-result', 'status-poll-return']
                  and [e['r0'] for e in extra] == [64, 0, 0])
            guards = [g for g in v['guards'] if g['accesses']]
            cfg = marker(log, 'BLACKWALL_MSPI1_CONFIG')['registers']
            check(name + '-array-read-stays-guarded', len(guards) == 1 and guards[0]['address'] == 0x40061000
                  and guards[0]['operation'] == 'write' and guards[0]['value'] == 0x100461
                  and cfg['12'] == 0x6c and cfg['8'] == 0x1fc0000)
            pio = marker(log, 'BLACKWALL_MSPI1_RDID')
            check(name + '-no-array-start-or-data', pio['starts'] == pio['completions'] == 1164
                  and not pio['busy'] and pio['rx_entries'] == 0 and pio['fifo_reads'] == 1159)
        check(name + '-pin-compatibility-not-claimed', status['physical_pins_verified'] is False)
        wel = marker(log, 'BLACKWALL_NOR_LATCH')
        address = marker(log, 'BLACKWALL_NOR_ADDRESS')
        check(name + '-NOR-state-unchanged', wel['current'] == 64 and not wel['wel'] and address['four_byte'] and address['current'] == 32)
        rows.append(dict(case=name, pc=hex(v['pc']), status=status, events=obs['sequence']))
    for f in ['strict.cs', 'board.repl', 'result.py', 'probe.resc']:
        check('stock23-CFW-same-' + f, (s / 'mspi1-continuous-status-main-01/stock23' / f).read_bytes()
              == (s / 'mspi1-continuous-status-main-01/cfw' / f).read_bytes())
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=rows,
        scope='Repeated status protocol under explicit logical transport; physical pin routing, array data and full boot/display unverified'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
