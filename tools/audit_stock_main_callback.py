"""Audit frozen original callback/OTA-verifier evidence and its diagnostic boundaries."""
import argparse
import json
from pathlib import Path
import shutil
from audit_stock_main_mram_probe import PRIVATE, audit_case, read, sha


def run(output, cleanup=False):
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE):
        raise ValueError('Fresh private output required')
    root = PRIVATE / 'simulator'
    groups = {
        'stock-main-callback-bw570-02': {'success', 'rom-error', 'readback-corrupt'},
        'stock-main-ota-verify-bw570-01': {'success', 'rom-error'},
        'stock-main-ota-verify-bw570-02': {'rom-error', 'readback-corrupt'},
    }
    cases = []
    for group, expected in groups.items():
        paths = {p.parent.name: p.parent for p in (root / group).glob('*/manifest.json')}
        if set(paths) != expected:
            raise ValueError('Frozen case inventory differs')
        cases.extend(paths[name] for name in sorted(paths))
    rows = [audit_case(case, cleanup=cleanup) for case in cases]
    initial = root / 'stock-main-callback-bw570-01/success'
    manifest = read(initial / 'manifest.json')
    checks = {
        'initial_registration_failure_preserved': 'registration address has to be aligned to guest page size 0x400' in (initial / 'native.log').read_text() and not (initial / 'exports/result.json').exists(),
        'initial_sources_pinned': all(sha((initial / name).read_bytes()) == h for name, h in manifest['components'].items()),
        'initial_owned_removed': read(initial / 'native.process.json')['status'] == 'removed',
        'four_completed_diagnostics': sum(read(case / 'report.json')['completed'] for case in cases) == 4,
        'three_ota_error_log_boundaries': sum(row['classification'] == 'unsupported-ota-error-log-rtc' for row in rows) == 3,
    }
    passed = all(checks.values()) and all(row['audit_passed'] for row in rows)
    initial_cleanup = initial / 'cleanup.json'
    if cleanup and passed and not initial_cleanup.exists():
        path = initial / 'caller.elf'
        data = path.read_bytes()
        initial_cleanup.write_text(json.dumps(dict(removed=[dict(name='caller.elf', bytes=len(data), sha256=sha(data))], reason='Reproducible ELF from failed platform registration; assembly/link/binary/log retained'), indent=2)+'\n')
        path.unlink()
    output.mkdir(parents=True, mode=0o700)
    shutil.copy2(__file__, output / 'audit-source.py')
    support = Path(__file__).resolve().parent / 'audit_stock_main_mram_probe.py'
    shutil.copy2(support, output / support.name)
    result = dict(passed=passed, checks=checks, cases=rows, support_sha256=sha(support.read_bytes()), hardware_accessed=False, natural_ota_verified=False, full_stock_verified=False)
    (output / 'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=passed, checks=len(checks)+sum(len(row['checks']) for row in rows), failed=[key for key, value in checks.items() if not value]+[row['case'] for row in rows if not row['audit_passed']])))
    if not passed:
        raise ValueError('Frozen callback audit failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    run(args.output, args.cleanup)
