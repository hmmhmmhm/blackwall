"""Compare registered firmware in the same captured device-runtime scenario."""
import argparse
import json
from pathlib import Path

from firmware_candidate import candidate_runtime


def preflight(baseline, candidate, output, expectation=None):
    if output.exists() or output.resolve().is_relative_to(baseline.resolve()) or output.resolve().is_relative_to(candidate.resolve()):
        raise ValueError('Comparison needs a new directory outside both captures')
    expected = dict(schema=1, failed_checks=[], sram_changes=[], connection_report_equal=True)
    if expectation is not None:
        expected = json.loads(expectation.read_text())
        if (set(expected) != {'schema', 'failed_checks', 'sram_changes', 'connection_report_equal'}
                or type(expected['schema']) is not int or expected['schema'] != 1
                or not isinstance(expected['failed_checks'], list)
                or not isinstance(expected['sram_changes'], list)
                or expected['connection_report_equal'] is not True):
            raise ValueError('Unsupported runtime comparison expectation')
    original = json.loads((baseline / 'connection-profile.json').read_text())
    selected = json.loads((candidate / 'connection-profile.json').read_text())
    if 'firmware_candidate' in original or 'firmware_candidate' not in selected:
        raise ValueError('Need an original baseline and a registered candidate capture')
    normalized = {key: value for key, value in selected.items() if key != 'firmware_candidate'}
    normalized['main_sha256'] = original['main_sha256']
    if normalized != original:
        raise ValueError('Different runtime scenario/profile; not a firmware-only comparison')
    source_inputs = json.loads((baseline / 'connection-inputs.json').read_text())
    candidate_inputs = json.loads((candidate / 'connection-inputs.json').read_text())
    ignored = {'main.bin', 'run.py', 'connection-profile.json', 'runner-source.py'}
    extras = {'firmware-candidate.json', 'firmware-runtime-anchors.json'}
    if set(candidate_inputs) - set(source_inputs) != extras | {
            key for key in candidate_inputs if key.startswith('firmware-baseline/')}:
        raise ValueError('Unexpected candidate execution inputs')
    if any(candidate_inputs.get(key) != value for key, value in source_inputs.items() if key not in ignored):
        raise ValueError('Different model/board/input/observer bytes')
    expected_runtime = candidate_runtime((baseline / 'run.py').read_text(),
                                         (baseline / 'main.bin').stat().st_size,
                                         (candidate / 'main.bin').stat().st_size)
    if expected_runtime != (candidate / 'run.py').read_text():
        raise ValueError('Different executable scenario beyond candidate memory extent')
    return expected, selected


def compare(baseline, candidate, output, expectation=None):
    from run_runtime_connection_m55 import inspect

    expected, selected = preflight(baseline, candidate, output, expectation)
    output.mkdir(mode=0o700, parents=True)
    base_result = inspect(baseline, output / 'baseline-audit')
    candidate_result = inspect(candidate, output / 'candidate-audit')
    failed = sorted(key for key, passed in candidate_result['checks'].items() if not passed)
    for key in expected['failed_checks']:
        if key not in candidate_result['checks']:
            raise ValueError('Unknown expected failed check')
    before = (baseline / 'exports/connection-sram.bin').read_bytes()
    after = (candidate / 'exports/connection-sram.bin').read_bytes()
    if len(before) != len(after) or len(before) != 0x380000:
        raise ValueError('Expected full SRAM captures')
    differences = []
    difference_count = 0
    for index, (x, y) in enumerate(zip(before, after)):
        if x != y:
            difference_count += 1
            if len(differences) < 64:
                differences.append(dict(address=0x20000000 + index, before=x, after=y))
    before_connection = (baseline / 'exports/connected-sram.bin').read_bytes()
    after_connection = (candidate / 'exports/connected-sram.bin').read_bytes()
    report_equal = base_result['observed'] == candidate_result['observed']
    checks = dict(baseline_passed=base_result['passed'],
                  same_initial_sram=(baseline / 'exports/sram-full.bin').read_bytes() == (candidate / 'exports/sram-full.bin').read_bytes(),
                  same_pre_att_sram=before_connection == after_connection,
                  expected_failed_checks=failed == sorted(expected['failed_checks']),
                  expected_sram_changes=difference_count == len(differences) and differences == expected['sram_changes'],
                  same_connection_report=report_equal)
    result = dict(passed=all(checks.values()), checks=checks,
                  candidate_execution_contract_passed=candidate_result['passed'],
                  candidate=selected['firmware_candidate'], failed_checks=failed,
                  sram_change_count=difference_count, sram_changes=differences,
                  sram_changes_truncated=difference_count > len(differences),
                  expectation=expected, native_rerun=False,
                  scope='same device-runtime scenario; not full boot/UI compatibility')
    (output / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--expectation', type=Path)
    args = parser.parse_args()
    result = compare(args.baseline, args.candidate, args.output, args.expectation)
    print(json.dumps(dict(passed=result['passed'], failed_checks=result['failed_checks'],
                          sram_change_count=result['sram_change_count'])))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
