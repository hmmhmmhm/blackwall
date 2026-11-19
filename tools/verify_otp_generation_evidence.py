"""Audit generation regressions against saved artifacts and prior original-main runs."""
import argparse
import json
from pathlib import Path

from native_replay import parse_log, validate_assets
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    a.output.mkdir(mode=0o700)
    s, checks = a.simulator, []

    def check(name, ok):
        if not ok:
            raise ValueError(name)
        checks.append(name)

    def marker(log, tag):
        rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines() if line.startswith(tag+' ')]
        check(tag+'-unique', len(rows) == 1)
        return rows[0]

    red = (s/'otp-generation-red-01/renode.log').read_text()
    check('red-stale-HOST-reproduced', 'old-HOST-witness-invalid-after-crypto-reset accepted' in red)
    total = 0
    for suffix, count, tag in [
        ('green-03', 83, 'BLACKWALL_OTP_SERIAL_UNIT'),
        ('last-02', 83, 'BLACKWALL_OTP_SERIAL_UNIT'),
        ('default-02', 6, 'BLACKWALL_OTP_SERIAL_UNIT'),
        ('busy-02', 6, 'BLACKWALL_OTP_SERIAL_UNIT'),
        ('readiness-regression-01', 30, 'BLACKWALL_OTP_READ_READY_UNIT'),
        ('crypto-regression-01', 30, 'BLACKWALL_CRYPTO_POWER_UNIT'),
    ]:
        d = s/('otp-generation-'+suffix)
        report = json.loads((d/'report.json').read_text())
        check(suffix+'-report', report == marker((d/'renode.log').read_text(), tag))
        check(suffix+'-count', report['passed'] and report['count'] == len(report['checks']) == count)
        check(suffix+'-current-model', (d/'strict.cs').read_bytes() == models(s))
        total += count

    for key, filename in [('stock24', 'stock-2.4.0.24.bin'), ('stock23', 'stock-2.3.0.24.bin'), ('cfw', 'faceclaw-38-research-only.bin')]:
        d = s/'otp-generation-main-01'/key
        old = s/'otp-serial-slots-main-01'/key
        log, oldlog = (d/'renode.log').read_text(), (old/'renode.log').read_text()
        report = json.loads((d/'report.json').read_text())
        prior = json.loads((old/'report.json').read_text())
        observed = parse_log(log)
        validate_assets(d, json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(key+'-native-report', observed == report['observed'])
        check(key+'-prior-report', parse_log(oldlog) == prior['observed'])
        check(key+'-boundary-and-CPU-unchanged', observed == prior['observed'])
        check(key+'-current-model', (d/'strict.cs').read_bytes() == models(s))
        _, raw = load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
        check(key+'-original-main', (d/'main.bin').read_bytes() == raw)
        check(key+'-selected-observation-unchanged', report['selected_observation'] == prior['selected_observation'])
        for tag in ['BLACKWALL_OBSERVATION', 'BLACKWALL_OTP_SERIAL_SLOTS', 'BLACKWALL_OTP_READ_READY', 'BLACKWALL_NOR_ARRAY', 'BLACKWALL_NOR_PROGRAM', 'BLACKWALL_NOR_ERASE']:
            check(key+'-'+tag+'-unchanged', marker(log, tag) == marker(oldlog, tag))
        check(key+'-no-boot-display-hardware-claim', not any(report[k] for k in ['boot_verified', 'display_verified', 'hardware_validated']))
    result = dict(passed=True, count=len(checks), checks=checks, unit_checks=total,
                  scope='Power generation local regressions and original-main unchanged prefix/boundary; no off model, boot or physical validation')
    (a.output/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, count=len(checks), unit_checks=total)))


if __name__ == '__main__':
    main()
