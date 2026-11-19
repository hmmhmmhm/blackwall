"""Audit frozen native sensor input/control evidence and independently compute samples."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

S = Path.home() / 'Library/Application Support/Blackwall/simulator'
CASES = ['stock24', 'stock23', 'cfw']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def signed(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def expected_ring(before, raw, profile, tick):
    base = profile['output'] - 0x20000000
    word = lambda a: struct.unpack_from('<I', before, a - 0x20000000)[0]
    mode = before[profile['mode_slot'] - 0x20000000]
    period = word(profile['period_table'] + mode * 16 + 4) // 1000
    biases = [struct.unpack_from('<3i', before, profile[name] - 0x20000000)
              for name in ['accel_bias', 'gyro_bias']]
    pc = 0x4c4980 if profile['case'] == 'stock24' else 0x4b92c4
    opcode, operands = struct.unpack_from('<HH', raw, pc - 0x438000)
    if opcode != 0xf8df or operands >> 12 != 7:
        raise ValueError('Changed original matrix literal load')
    matrix_slot = struct.unpack_from('<I', raw, ((pc + 4) & ~3) + (operands & 4095) - 0x438000)[0]
    matrix = struct.unpack_from('<9f', before, matrix_slot - 0x20000000)
    expected = bytearray(before[base:base + 2252])
    struct.pack_into('<III', expected, 0, tick, 10, 10)
    for n in range(10):
        axes = struct.unpack('<6h', bytes(n + k for k in range(12)))
        row = 12 + 112 * n
        struct.pack_into('<I', expected, row, (tick + period * (n - 10)) & 0xffffffff)
        expected[row + 4] |= 3
        struct.pack_into('<6h', expected, row + 6, *axes)
        for offset, values, bias, scale in [(40, axes[:3], biases[0], 8), (52, axes[3:], biases[1], 4000)]:
            vector = [f32(f32(signed(v * scale - b)) / 65536) for v, b in zip(values, bias)]
            rotated = []
            for j in range(3):
                v = f32(vector[0] * matrix[j * 3])
                v = f32(v + f32(vector[1] * matrix[j * 3 + 1]))
                rotated.append(f32(v + f32(vector[2] * matrix[j * 3 + 2])))
            struct.pack_into('<3f', expected, row + offset, *rotated)
    return bytes(expected), matrix_slot


def observation_checks(x, control, memory):
    before, after = x['before'], x['after']
    rows = x['rows']
    callbacks = [r for r in rows if r[0] == 301]
    consumers = [r for r in rows if r[0] == 303]
    parsed = [r for r in rows if r[0] == 304]
    names = [memory[r[8] - 0x20000000 + 52:r[8] - 0x20000000 + 84].split(b'\0')[0] for r in consumers]
    return dict(
        original_initialization=before['gate'] == after['gate'] == 1 and before['ready'] and after['ready']
        and before['frame_bytes'] == 32 and before['watermark'] == 10,
        actual_gpio_irq=len(callbacks) == 1 and (callbacks[0][9] & 511) == 73
        and after['gpio_edges'] == before['gpio_edges'] + 1,
        natural_sensor_task=len(consumers) == len(parsed) == 1 and names == [b'sensor_hub']
        and (consumers[0][9] & 511) == (parsed[0][9] & 511) == 0
        and consumers[0][8] == parsed[0][8] and parsed[0][10] > consumers[0][10]
        and parsed[0][2] == 0,
        actual_sample_transactions=after['consumed'] - before['consumed'] == 10 and after['packets'] == 0
        and after['read_bytes'] - before['read_bytes'] == 324
        and after['completed'] - before['completed'] == 4,
        irq_and_fifo_released=not any(after[k] for k in ['gpio_pending', 'gpio_irq', 'pin_high', 'source_high', 'threshold_pending'])
        and after['threshold_clears'] - before['threshold_clears'] == 1 and after['rejected_transitions'] == 0,
        live_post_input=after['frames'] > before['frames'] and after['ticks'] - before['ticks'] == 100000000,
        control_no_event=not control['rows'] and control['after']['consumed'] == control['before']['consumed']
        and control['after']['sample_header'] == control['before']['sample_header'] == [0, 0, 0],
        no_runtime_faults=all(v['cfsr'] == v['hfsr'] == v['memory_violations'] == v['system_control_violations'] == 0
                              and not v['overflow'] and all(g['accesses'] == 0 for g in v['guards'])
                              and v['after']['gpu_rejections'] == 0 and not v['after']['gpu_fault']
                              for v in [x, control]),
    )


def complete(cases):
    return set(cases) == set(CASES) and all(row['passed'] for row in cases.values())


def audit(root, out):
    if out.exists() or not out.is_relative_to(S):
        raise ValueError('New private output required')
    values = load(root / 'imu-natural-task-values-01/report.json')
    manifest_path = root / 'active-reset-manifest.json'
    if sha(manifest_path) != 'e7c16643e89b9000f9f2d9929b2961cdfb7cee20cdae2c307d2e85a16e83fb68':
        raise ValueError('Changed fixed main/board provenance')
    manifest = load(manifest_path)
    rows, pins = {}, {}
    for case in CASES:
        stem = 'imu-natural-task-native-02' if case == 'stock24' else 'imu-natural-task-family-native-01'
        positive, control = [root / stem / (case + '-' + mode) for mode in ['input', 'control']]
        if out.is_relative_to(positive) or out.is_relative_to(control):
            raise ValueError('Audit output cannot be in its capture')
        x, y = [load(p / 'exports/sensor-input.json') for p in [positive, control]]
        before = (positive / 'exports/sensor-before-sram.bin').read_bytes()
        memory = (positive / 'exports/sensor-after-sram.bin').read_bytes()
        control_before = (control / 'exports/sensor-before-sram.bin').read_bytes()
        control_memory = (control / 'exports/sensor-after-sram.bin').read_bytes()
        value = values['cases'][case]
        profile = value['profile']
        raw = (positive / 'main.bin').read_bytes()
        checks = observation_checks(x, y, memory)
        consumer = next(r for r in x['rows'] if r[0] == 303)
        expected, matrix_slot = expected_ring(before, raw, profile, consumer[2])
        base = profile['output'] - 0x20000000
        checks['full_ring_math'] = memory[base:base + 2252] == expected
        checks['control_ring_preserved'] = control_before[base:base + 2252] == control_memory[base:base + 2252]
        checks['matrix_preserved'] = before[matrix_slot - 0x20000000:matrix_slot - 0x20000000 + 36] == memory[matrix_slot - 0x20000000:matrix_slot - 0x20000000 + 36]
        codec = root / 'imu-natural-task-values-01' / (case + '-expected-codec.bin')
        offset = value['codec_output'] - 0x20000000
        checks['original_codec_cross_engine'] = value['codec_original_arm_isolated_m7'] and value['codec_no_abi_stubs'] and value['codec_sram_preserved'] and value['codec_80_bytes_match_native'] and memory[offset:offset + 80] == codec.read_bytes()
        checks['matching_initial_sensor_state'] = all(x['before'][k] == y['before'][k] for k in ['gate', 'frame_bytes', 'ready', 'watermark', 'int1', 'pad', 'sample_header', 'packets'])
        checks['same_original_model'] = all(sha(positive / name) == sha(control / name) for name in ['main.bin', 'strict.cs', 'activation.cs', 'board.repl', 'run.py', 'probe.resc']) and sha(positive / 'main.bin') == profile['main_sha256']
        checks['device_injection_only'] = all(not re.search(r'cpu\.(?:PC|SP)\s*=|cpu\.(?:SetRegister|SeedRegister)\s*\(|\bb\.Write(?:Byte|Word|DoubleWord|Bytes)\s*\(', (p / 'run.py').read_text()) for p in [positive, control])
        checks['input_preserved_cpu_sram'] = all(x['before'][k] == x['injected'][k] for k in ['registers', 'ticks', 'instructions']) and sha(positive / 'exports/sensor-before-sram.bin') == sha(positive / 'exports/sensor-injected-sram.bin')
        if case != 'stock24':
            checks['all_original_processing_and_return'] = all(sum(r[0] == tag for r in x['rows']) == count for tag, count in [(305, 10), (309, 10), (307, 1), (308, 20), (306, 1)])
            returns = [r for r in x['rows'] if r[0] == 306]
            checks['same_task_caller_return'] = len(returns) == 1 and returns[0][2] == 0 and returns[0][8] == consumer[8] and returns[0][6] == consumer[6] and (returns[0][9] & 511) == 0 and returns[0][10] > consumer[10]
        integrity = []
        for folder in [positive, control]:
            plan = load(folder / 'plan.json')
            integrity.extend(sha(folder / name) == digest for name, digest in plan['input_sha256'].items())
            integrity.append(load(folder / 'renode.process.json')['status'] == 'removed')
            for path in folder.rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    pins[str(path.relative_to(S))] = sha(path)
        checks['ten_device_frames'] = len(x['accepted']) == 10 and all(x['accepted']) and y['accepted'] == []
        checks['original_pulse_configuration'] = (x['before']['int1'] & 7) == 1 and x['before']['pad'] == 0x93
        source = root / load(positive / 'plan.json')['source_root']
        base_model = (source / 'strict.cs').read_text()
        device_prefix = base_model + '\n'
        model = (positive / 'strict.cs').read_text()
        board = (source / 'board.repl').read_text().replace('    runtimePin27: true\n', '    runtimePin27: true\n    runtimePin38: true\n    IRQ38 -> nvic@57\n', 1)
        cut = '\ntry:\n    from System.Security.Cryptography import SHA256\n'
        post = '\ntry:\n    from System import Array,Byte,Func\n'
        checks['only_validated_device_changes'] = sha(source / 'strict.cs') == manifest['files'][str((source / 'strict.cs').relative_to(root))]['sha256'] and model.startswith(device_prefix) and hashlib.sha256(model[len(device_prefix):].encode()).hexdigest() == 'f9567733b8a6b48bfaff49c4140fc4a8961625fc7e92140cdc80fcfbe22dfebf' and (positive / 'board.repl').read_text() == board and sha(positive / 'activation.cs') == sha(source / 'activation.cs')
        checks['original_boot_prefix'] = (positive / 'run.py').read_text().split(post, 1)[0] == (source / 'run.py').read_text().split(cut, 1)[0] and sha(source / 'run.py') == manifest['files'][str((source / 'run.py').relative_to(root))]['sha256']
        checks['pinned_execution'] = all(integrity)
        rows[case] = dict(passed=all(checks.values()), checks=checks, consumer_tick=consumer[2], matrix_slot=matrix_slot,
                          callback_count=len([r for r in x['rows'] if r[0] == 301]),
                          full_caller_return_directly_observed=case != 'stock24')
    partial = dict(rows)
    partial['cfw'] = dict(passed=False)
    negatives = dict(failed_case=not complete(partial), missing_case=not complete({k: v for k, v in rows.items() if k != 'stock23'}))
    passed = complete(rows) and all(negatives.values())
    for path in (root / 'imu-natural-task-values-01').iterdir():
        if path.is_file():
            pins[str(path.relative_to(S))] = sha(path)
    result = dict(schema=1, criterion='E12', scope_version=3, passed=passed, full_e12_verified=passed,
                  original3_natural_task_consumption=complete(rows), cases=rows, partial_case_negatives=negatives,
                  capture_hashes=pins, new_native_runs=False, hardware_accessed=False, whole_goal_complete=False,
                  limitations=['Declared 8us INT1 pulse, cold initialization service and reference GPU profiles.',
                               'Raw sensor transport/ARM decoding and transforms, not numerical EDMP/GAF fusion or physical validation.',
                               'Stock24 preserves its existing trace; old2 additionally observes the whole consumer caller return.'])
    out.mkdir(mode=0o700, parents=True)
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'auditor-source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(passed=passed, cases=rows, partial_case_negatives=negatives)))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator_root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = audit(args.simulator_root.resolve(), args.output.resolve())
    raise SystemExit(0 if result['passed'] else 1)
