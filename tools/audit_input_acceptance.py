"""Read frozen touch/ring evidence for E11. Never build models or execute ARM."""
import argparse
import hashlib
import json
import re
from pathlib import Path

S = Path.home() / 'Library/Application Support/Blackwall/simulator'
CASES = ['stock24', 'stock23', 'cfw']
MAINS = {
    'stock24': 'df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a',
    'stock23': 'fffbf74b3439bf0e4752fb620a7990d0a133898c54f6fb08005ea6b7029655c5',
    'cfw': '4118af85ebb8e634493a61a3ce4a62ae37451e17cea6d0b8b08465f29538dd8f',
}
FIRST_FRAME = '5bed2a24ac17aa73a627552376d35af5c27988fd57e60e12faa7c29b55403501'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def verify_files(root, files, pins):
    valid = True
    for name, value in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError('Evidence path escapes its capture root')
        expected = value['sha256'] if isinstance(value, dict) else value
        ok = path.is_file() and sha(path) == expected
        valid = valid and ok
        if ok:
            pins[str(path.relative_to(S))] = expected
    return valid


def complete(touch_ok, cases):
    return touch_ok and set(cases) == set(CASES) and all(v['passed'] for v in cases.values())


def audit(root, out):
    captures = [root / name / case for name in ['ring-hud-functional-native-01', 'ring-hud-no-input-native-01'] for case in CASES]
    if out.exists() or not out.is_relative_to(S) or any(out.is_relative_to(p) for p in captures):
        raise ValueError('New separate private output required')
    pins = {}
    touch_path = root / 'active-hud-touch-family-manifest.json'
    reset_path = root / 'active-reset-manifest.json'
    if sha(touch_path) != 'ae80001af74f5391f6e1a406067c9987141bc5a98efb14851464180e7db371f9':
        raise ValueError('Changed fixed touch evidence manifest')
    if sha(reset_path) != 'e7c16643e89b9000f9f2d9929b2961cdfb7cee20cdae2c307d2e85a16e83fb68':
        raise ValueError('Changed fixed board provenance manifest')
    touch = load(touch_path)
    reset = load(reset_path)
    touch_ok = touch['passed'] and touch['original3_touch_scroll_verified'] and verify_files(root, touch['files'], pins)
    touch_aggregate = load(root / 'active-hud-touch-family-acceptance-01/report.json')
    touch_cases = {}
    for case in CASES:
        info = touch_aggregate['source_reports'][case]
        path = root / info['path']
        report = load(path)
        ok = sha(path) == info['sha256'] and report['passed'] and report['case'] == case and all(report['checks'].values())
        ok = verify_files(root, report['capture_hashes'], pins) and ok
        touch_cases[case] = ok
    touch_ok = touch_ok and touch_aggregate['passed'] and all(touch_cases.values())
    rows = {}
    for case in CASES:
        positive = root / 'ring-hud-functional-native-01' / case
        control = root / 'ring-hud-no-input-native-01' / case
        a_path = root / 'ring-hud-frozen-audit-01' / case / 'report.json'
        b_path = root / 'ring-hud-no-input-frozen-audit-01' / case / 'report.json'
        a, b = load(a_path), load(b_path)
        x = load(positive / 'exports/ring-screen.json')
        ring = load(positive / 'exports/ring.json')
        y = load(control / 'exports/ring-control.json')
        plans = [load(p / 'plan.json') for p in [positive, control]]
        source = root / plans[0]['source_root']
        source_run = source / 'run.py'
        original = reset['files'][str(source_run.relative_to(root))]['sha256']
        anchor = '\ntry:\n    import clr,time,json\n'
        source_prefix = source_run.read_text().split(anchor, 1)[0]
        checks = dict(
            positive_execution_and_semantics=a['passed'] and a['execution_passed'] and a['semantic_validation']['passed'] and all(a['diagnostics'].values()),
            control_execution_and_semantics=b['passed'] and b['execution_passed'] and b['semantic_validation']['passed'] and all(b['diagnostics'].values()),
            original_main=all(sha(p / 'main.bin') == MAINS[case] for p in [positive, control]),
            same_board_model=all(sha(positive / name) == sha(control / name) == reset['files'][str((source / name).relative_to(root))]['sha256'] for name in ['strict.cs', 'board.repl', 'activation.cs', 'probe.resc']),
            preserved_reset_prefix=sha(source_run) == original and all((p / 'run.py').read_text().split(anchor, 1)[0] == source_prefix + '\n' for p in [positive, control]) and all(v['startup_prefix_sha256'] == hashlib.sha256(source_prefix.encode()).hexdigest() for v in plans),
            no_cpu_or_guest_memory_forcing=all(not re.search(r'cpu\.(?:PC|SP)\s*=|cpu\.(?:SetRegister|SeedRegister)\s*\(|\bb\.Write(?:Byte|Word|DoubleWord|Bytes)\s*\(', (p / 'run.py').read_text()) for p in [positive, control]),
            same_initial_cpu_and_time=ring['before']['registers'] == y['before']['registers'] and ring['before']['ticks'] == y['before']['ticks'],
            same_initial_sram=sha(positive / 'exports/before-input-sram.bin') == sha(control / 'exports/ring-control-before-sram.bin'),
            control_covers_positive_window=y['after']['ticks'] - y['before']['ticks'] >= x['final']['ticks'] - ring['before']['ticks'],
            original_report_consumed=bytes(ring['actual_report']).hex() == '00096100020aa7e8030000' and ring['last_tick'] == 1000,
            reference_frame=sha(positive / 'exports/ring-first-frame.bin') == FIRST_FRAME,
            no_input_no_ui=y['before']['frames'] == y['after']['frames'] == 0,
            cfw_hook_fallback=case != 'cfw' or all(any(r[0] == tag and r[1] == pc for r in ring['rows']) for tag, pc in [(60, 0x7d5800), (61, 0x7d5812)]),
        )
        checks['capture_integrity'] = all(verify_files(p, load(p / 'capture-files.json')['files'], pins) for p in [positive, control])
        rows[case] = dict(passed=all(checks.values()), checks=checks,
                          first_frames=x['first']['frames'], final_frames=x['final']['frames'],
                          positive_elapsed_ms=(x['final']['ticks'] - ring['before']['ticks']) / 1e6,
                          control_elapsed_ms=(y['after']['ticks'] - y['before']['ticks']) / 1e6)
        for path in [a_path, b_path, source_run, positive / 'capture-files.json', control / 'capture-files.json']:
            pins[str(path.relative_to(S))] = sha(path)
    for path in [touch_path, reset_path]:
        pins[str(path.relative_to(S))] = sha(path)
    negatives = {}
    partial = dict(rows)
    partial['cfw'] = dict(passed=False)
    negatives['failed_case'] = not complete(touch_ok, partial)
    partial = dict(rows)
    del partial['stock23']
    negatives['missing_case'] = not complete(touch_ok, partial)
    negatives['missing_touch_acceptance'] = not complete(False, rows)
    passed = complete(touch_ok, rows) and all(negatives.values())
    result = dict(schema=1, scope_version=3, criterion='E11', passed=passed, full_e11_verified=passed,
                  touch_cases=touch_cases, ring_cases=rows, partial_case_negatives=negatives,
                  evidence_hashes=pins, new_native_runs=False, hardware_accessed=False, whole_goal_complete=False,
                  supported_inputs=['Touch wake and one additional source1/code4 scroll report.',
                                    'Existing ring-wake relay report/type2, source4/code1, through virtual opposite-temple UART.'],
                  limitations=['No direct R1 BLE or arbitrary gesture support.',
                               'Conditional 10→167 MIPS HP/UI rate input; control without UI stays at startup rate. Not a latency/FPS comparison.',
                               'Declared cold sensor and reference GPU models; no physical validation.'])
    out.mkdir(mode=0o700, parents=True)
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'auditor-source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(passed=passed, touch_cases=touch_cases, ring_cases=rows, partial_case_negatives=negatives)))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator_root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = audit(args.simulator_root.resolve(), args.output.resolve())
    raise SystemExit(0 if result['passed'] else 1)
