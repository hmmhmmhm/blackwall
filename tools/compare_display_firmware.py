"""Compare registered main images in the same API-driven partial display scenario."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

from firmware_candidate import candidate_runtime
from display_firmware_candidate import candidate_semantics, stimulus_entries
from native_replay import FILES


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def byte_changes(before, after):
    if len(before) != len(after):
        raise ValueError('Different byte capture lengths')
    count = 0
    first = []
    for offset, (old, new) in enumerate(zip(before, after)):
        if old != new:
            count += 1
            if len(first) < 64:
                first.append(dict(offset=offset, before=old, after=new))
    return dict(changed_bytes=count, first_changes=first, changes_truncated=count > len(first),
                before_sha256=hashlib.sha256(before).hexdigest(),
                after_sha256=hashlib.sha256(after).hexdigest())


def load_expectation(path):
    expected = json.loads(path.read_text())
    keys = {'schema', 'candidate_passed', 'failed_checks', 'surface_sha256',
            'final_sram_sha256', 'trace_sha256'}
    if (not isinstance(expected, dict) or set(expected) != keys
            or type(expected['schema']) is not int or expected['schema'] != 1
            or type(expected['candidate_passed']) is not bool
            or not isinstance(expected['failed_checks'], list)
            or any(not isinstance(key, str) for key in expected['failed_checks'])
            or len(set(expected['failed_checks'])) != len(expected['failed_checks'])
            or any(not isinstance(expected[key], str) or not re.fullmatch('[0-9a-f]{64}', expected[key])
                   for key in ('surface_sha256', 'final_sram_sha256', 'trace_sha256'))):
        raise ValueError('Unsupported display comparison expectation')
    return expected


def preflight(baseline, candidate, output, expectation=None):
    if (output.exists() or output.resolve().is_relative_to(baseline.resolve())
            or output.resolve().is_relative_to(candidate.resolve())):
        raise ValueError('Comparison needs a new directory outside both captures')
    expected = load_expectation(expectation) if expectation is not None else None
    original = json.loads((baseline / 'profile.json').read_text())
    selected = json.loads((candidate / 'profile.json').read_text())
    if 'firmware_candidate' in original or 'firmware_candidate' not in selected:
        raise ValueError('Need an original baseline and a registered display candidate')
    wanted = copy.deepcopy(original)
    wanted['stimulus_entries'] = stimulus_entries((baseline / 'harness.s').read_text())
    if 'status_semantics' in wanted:
        wanted['status_semantics'] = candidate_semantics(wanted['status_semantics'])
    normalized = {key: value for key, value in selected.items() if key != 'firmware_candidate'}
    if normalized != wanted:
        raise ValueError('Different display scenario/profile; not a firmware-only comparison')
    if not original.get('gpu_ring_components') or not original.get('content_watches'):
        raise ValueError('Display comparison requires a GPU surface capture profile')
    inputs = (FILES - {'main.bin', 'run.py'}) | {'harness.s', 'harness.bin', 'status-source.json'}
    before_cs = {p.name for p in baseline.glob('*.cs')}
    after_cs = {p.name for p in candidate.glob('*.cs')}
    if before_cs != after_cs or any((baseline / name).read_bytes() != (candidate / name).read_bytes()
                                    for name in sorted(inputs | before_cs)):
        raise ValueError('Different display model/board/input/observer bytes')
    runtime = candidate_runtime((baseline / 'run.py').read_text(),
                                (baseline / 'main.bin').stat().st_size,
                                (candidate / 'main.bin').stat().st_size)
    if runtime != (candidate / 'run.py').read_text():
        raise ValueError('Different executable display scenario beyond candidate memory extent')
    return expected, selected


def captured_surface(capture, report):
    surface = report.get('gpu_ring', {}).get('captured_surface')
    if not surface:
        raise ValueError('Display comparison requires a captured L8 surface')
    frame = (capture / 'exports/gpu-last-frame.bin').read_bytes()
    ram = (capture / 'exports/content-after-sram.bin').read_bytes()
    offset = surface['address'] - 0x20000000
    size = surface['stride'] * surface['height']
    if (len(ram) != 0x380000 or len(frame) != size or offset < 0 or offset + size > len(ram)
            or frame != ram[offset:offset + size]
            or hashlib.sha256(frame).hexdigest() != surface['sha256']):
        raise ValueError('Captured display surface differs from guest SRAM')
    return surface, frame, ram


def write_png(path, data, width, height, stride):
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
    rows = b''.join(b'\0' + data[y * stride:y * stride + width] for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def compare(simulator, baseline, candidate, output, expectation=None):
    from run_display_activation_m55 import audit

    expected, selected = preflight(baseline, candidate, output, expectation)
    output.mkdir(mode=0o700, parents=True)
    base_result = audit(simulator, baseline, output / 'baseline-audit')
    candidate_result = audit(simulator, candidate, output / 'candidate-audit')
    base_surface, before, before_ram = captured_surface(baseline, base_result)
    chosen_surface, after, after_ram = captured_surface(candidate, candidate_result)
    layout = ('address', 'width', 'height', 'stride')
    if any(base_surface[key] != chosen_surface[key] for key in layout):
        raise ValueError('Different display surface layout')
    surface_diff = byte_changes(before, after)
    memory_diff = byte_changes(before_ram, after_ram)
    base_trace = canonical_sha256(base_result['observed'])
    chosen_trace = canonical_sha256(candidate_result['observed'])
    if expected is None:
        expected = dict(schema=1, candidate_passed=True, failed_checks=[],
                        surface_sha256=surface_diff['before_sha256'],
                        final_sram_sha256=memory_diff['before_sha256'], trace_sha256=base_trace)
    if any(key not in candidate_result['checks'] for key in expected['failed_checks']):
        raise ValueError('Unknown expected display failed check')
    failed = sorted(key for key, passed in candidate_result['checks'].items() if not passed)
    checks = dict(baseline_passed=base_result['passed'],
        expected_candidate_verdict=candidate_result['passed'] == expected['candidate_passed'],
        expected_failed_checks=failed == sorted(expected['failed_checks']),
        expected_surface=surface_diff['after_sha256'] == expected['surface_sha256'],
        expected_final_sram=memory_diff['after_sha256'] == expected['final_sram_sha256'],
        expected_trace=chosen_trace == expected['trace_sha256'])
    for name in ('sram-full.bin', 'ui-after-sram.bin', 'display-after-sram.bin'):
        initial = (baseline / 'exports' / name).read_bytes()
        chosen = (candidate / 'exports' / name).read_bytes()
        if len(initial) != 0x380000 or len(chosen) != 0x380000:
            raise ValueError('Display comparison requires full SRAM captures')
        checks['same_' + name] = initial == chosen
    for change in surface_diff['first_changes']:
        change.update(x=change['offset'] % base_surface['stride'], y=change['offset'] // base_surface['stride'])
    write_png(output / 'baseline-surface.png', before, base_surface['width'], base_surface['height'], base_surface['stride'])
    write_png(output / 'candidate-surface.png', after, chosen_surface['width'], chosen_surface['height'], chosen_surface['stride'])
    result = dict(passed=all(checks.values()), checks=checks,
        candidate_execution_contract_passed=candidate_result['passed'],
        candidate=selected['firmware_candidate'], failed_checks=failed,
        surface=dict(layout={key: base_surface[key] for key in layout}, **surface_diff),
        final_sram=dict(base_address=0x20000000, **memory_diff),
        trace=dict(before_sha256=base_trace, after_sha256=chosen_trace), expectation=expected,
        native_rerun=False, full_ui_verified=False, natural_main_complete=False,
        scope='same-model API-driven partial display surface; not full boot/UI compatibility')
    (output / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('simulator', 'baseline', 'candidate', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--expectation', type=Path)
    args = parser.parse_args()
    if any(not path.resolve().is_relative_to(args.simulator.resolve())
           for path in (args.baseline, args.candidate, args.output)):
        parser.error('Display comparison assets must remain in the private simulator')
    result = compare(args.simulator, args.baseline, args.candidate, args.output, args.expectation)
    print(json.dumps(dict(passed=result['passed'], changed_surface_bytes=result['surface']['changed_bytes'])))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
