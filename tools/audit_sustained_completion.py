"""Audit saved sustained matrix, original UI queue state and measured execution cost."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import struct
import subprocess
import sys
import re

S = Path.home() / 'Library/Application Support/Blackwall/simulator'
CASES = ['stock24', 'stock23', 'cfw']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p):
    return json.loads(p.read_text())


def profile_summary(plan):
    declared = {}
    for key, field, expected in [('status_profile', 'hex', '5a01'),
                                 ('rtc_profile', 'name', 'independent-weekday'),
                                 ('controller_version_profile', 'name', 'startup-mock'),
                                 ('uart_capture_profile', 'name', 'bounded-prefix')]:
        if key not in plan:
            continue
        value = plan[key]
        if value[field] != expected:
            raise ValueError('Unknown declared profile ' + key)
        declared[key] = value
    if 'controller_version_profile' in declared:
        value = declared['controller_version_profile']
        if value['identity'] != '0d34120d5a007856' or value['physical_identity_verified'] is not False or value['limit'] != 32:
            raise ValueError('Undeclared controller identity or physical claim')
        if value.get('startup_command_profile') is not None and (value['startup_command_profile'] not in ['version-and-advertising-stop', 'version-and-advertising-reconfigure'] or value['advertising_disable_limit'] != 1):
            raise ValueError('Unknown startup command selector contract')
        if value.get('startup_command_profile') == 'version-and-advertising-reconfigure' and value['advertising_parameters_hex'] != '0106200f400640060001000000000000000700':
            raise ValueError('Unknown advertising parameters')
    if 'uart_capture_profile' in declared:
        value = declared['uart_capture_profile']
        if value['module'] != 0 or value['prefix_capacity'] != 4096:
            raise ValueError('Unknown bounded UART capture contract')
    return dict(declared=declared, full_integration=len(declared) == 4)


def uart_stream_witness(transfers, completion_count, observed):
    """Recompute the native UART0 stream from original exporter DMA source bytes."""
    stream = bytearray()
    for row in transfers:
        data = bytes.fromhex(row['data'])
        if not 0 < len(data) <= 4095 or not 0x20000000 <= row['target'] < row['target'] + len(data) <= 0x20380000:
            raise ValueError('UART DMA source outside the declared SRAM contract')
        stream.extend(data)
    dma = observed['dma']
    if (completion_count != len(transfers) or dma['starts'] != dma['completions']
            or dma['completions'] != completion_count
            or dma['transferred_bytes'] != len(stream) or observed['tx_total'] != len(stream)):
        raise ValueError('Incomplete UART0 DMA stream or unaccounted PIO bytes')
    digest = 14695981039346656037
    for value in stream:
        digest = ((digest ^ value) * 1099511628211) & ((1 << 64) - 1)
    if (observed['tx_hash'] != digest or observed['tx_bytes'] != min(4096, len(stream))
            or observed['tx_dropped'] != max(0, len(stream) - 4096)
            or observed['tx_truncated'] != (len(stream) > 4096)):
        raise ValueError('UART byte/hash/prefix telemetry does not match source stream')
    return dict(passed=True, transfers=len(transfers), total_bytes=len(stream), fnv1a64=digest,
                captured_prefix_bytes=observed['tx_bytes'], dropped_history_bytes=observed['tx_dropped'],
                scope='Recomputed from original runtime DMA exporter; UART0 all-DMA profile only.')


def resource_summary(rows, container):
    samples = [item for row in rows if row.get('exit_code', 0) == 0
               for item in row['stats'] if item['Name'] == container]
    memory = []
    for item in samples:
        match = re.fullmatch(r'([0-9.]+)(KiB|MiB|GiB|B)', item['MemUsage'].split(' / ')[0])
        if match is None:
            raise ValueError('Unknown Docker memory unit')
        memory.append(float(match[1]) * {'B': 1 / 1048576, 'KiB': 1 / 1024, 'MiB': 1, 'GiB': 1024}[match[2]])
    return dict(samples=len(samples),
        max_sampled_memory_mib=max(memory) if memory else None,
        max_sampled_cpu_percent=max(float(item['CPUPerc'].removesuffix('%')) for item in samples) if samples else None,
        scope='Highest observed samples of the owned Docker lifecycle, including compile/cold boot when sampled; not a process peak or hotspot profile.')


def ui_wait_list(memory, queue):
    def word(address):
        offset = address - 0x20000000
        if address % 4 or offset < 0 or offset + 4 > len(memory):
            raise ValueError('Queue pointer outside saved SRAM')
        return struct.unpack_from('<I', memory, offset)[0]
    if word(queue + 0x38) != 0 or word(queue + 0x3c) != 96 or word(queue + 0x40) != 12:
        raise ValueError('Not the empty original UI queue')
    container = queue + 0x24
    if word(container) != 1 or word(container + 8) != 0xffffffff:
        raise ValueError('One original UI receiver required')
    sentinel = container + 8
    node = word(container + 12)
    owner = word(node + 12)
    if (word(container + 16) != node or word(node + 4) != sentinel or word(node + 8) != sentinel
            or node != owner + 24 or word(node + 16) != container
            or word(owner + 16) != owner or word(owner + 36) != owner):
        raise ValueError('Broken original UI receiver links')
    offset = owner - 0x20000000
    if memory[offset + 52:offset + 84].split(b'\0')[0] != b'ui_task':
        raise ValueError('Unexpected receiver owner')
    return dict(passed=True, queue=queue, owner=owner, messages=0, item_bytes=12, capacity=96)


def final_ui_state(capture, case, observed):
    raw = (capture / 'main.bin').read_bytes()
    memory = (capture / 'exports/sustained-after-sram.bin').read_bytes()
    if len(memory) != 0x380000:
        raise ValueError('Whole final SRAM required')
    pc = 0x445f1c if case == 'stock24' else 0x445ec0
    opcode = struct.unpack_from('<H', raw, pc - 0x438000)[0]
    if opcode != (0x484b if case == 'stock24' else 0x484a):
        raise ValueError('Changed original UI queue literal load')
    literal = ((pc + 4) & ~3) + (opcode & 255) * 4
    slot = struct.unpack_from('<I', raw, literal - 0x438000)[0]
    queue = struct.unpack_from('<I', memory, slot - 0x20000000)[0]
    witness = ui_wait_list(memory, queue)
    tcb = observed['after']['tcb']
    offset = tcb - 0x20000000
    if offset < 0 or offset + 84 > len(memory):
        raise ValueError('Current task outside captured SRAM')
    name = memory[offset + 52:offset + 84].split(b'\0')[0].decode('ascii')
    if not name or struct.unpack_from('<I', memory, offset + 16)[0] != tcb:
        raise ValueError('Invalid current task identity')
    witness.update(queue_slot=slot, load_pc=pc, current_task=name, current_tcb=tcb,
                   final_frame_sha256=sha(capture / 'exports' / observed['samples'][-1]['file']))
    return witness


def audit(matrix, out):
    if out.exists() or not out.is_relative_to(S):
        raise ValueError('New private audit output required')
    state = load(matrix / 'state.json')
    out.mkdir(mode=0o700, parents=True)
    snapshot = out / 'matrix-state.json'
    snapshot.write_text(json.dumps(state, indent=2) + '\n')
    pins = {str(snapshot): sha(snapshot), str(matrix / 'worker.py'): sha(matrix / 'worker.py'),
            str(matrix / 'frozen-tools.json'): sha(matrix / 'frozen-tools.json')}
    for name, digest in load(matrix / 'frozen-tools.json').items():
        p = (matrix / name).resolve()
        if not p.is_relative_to(matrix) or sha(p) != digest:
            raise ValueError('Changed frozen matrix source')
        pins[str(p)] = digest
    rows = []
    seen = set()
    owned = []
    for run in state['completed']:
        key = run['case'], run['ms'], run['repeat']
        if key in seen or key[0] not in CASES or key[1] not in [6000, 60000] or key[2] not in [1, 2]:
            raise ValueError('Duplicate or unknown matrix execution')
        seen.add(key)
        capture = Path(run['capture']).resolve()
        if not capture.is_relative_to(S):
            raise ValueError('Capture outside private simulator')
        dest = out / ('%s-%s-r%s' % key)
        command = [sys.executable, str(matrix / 'source/tools/run_sustained_screen.py'), str(capture),
                   '--audit-existing', '--audit-output', str(dest)]
        checked = subprocess.run(command, capture_output=True, text=True)
        (out / ('%s-%s-r%s.log' % key)).write_text(checked.stdout + checked.stderr)
        if checked.returncode:
            raise ValueError('Saved native semantics rejected ' + str(key))
        result = load(dest / 'report.json')
        obs = result['observed']
        if not result['passed'] or obs['target_ms'] != run['ms']:
            raise ValueError('Wrong target or failed semantics')
        ui = final_ui_state(capture, run['case'], obs)
        wall = obs['wall_seconds']
        virtual = obs['elapsed_ticks'] / 1e9
        host = load(capture / 'host-measurement.json')
        plan = load(capture / 'plan.json')
        profiles = profile_summary(plan)
        uart_witness = None
        if 'uart_capture_profile' in plan:
            original = load(capture / 'exports/touch.json')['uart_dma']
            uart_witness = uart_stream_witness(original['transfers'], original['completions'], obs['uarts'][0])
        owned.append(load(capture / 'renode.process.json')['container'])
        if not plan.get('runtime_insertion') or plan['status_profile']['hex'] != '5a01':
            raise ValueError('Missing preserved runtime or explicit reviewed display profile')
        row = dict(case=key[0], ms=key[1], repeat=key[2], passed=True, capture=str(capture), profiles=profiles, uart_stream=uart_witness, startup_host_guard=plan.get('startup_host_guard'),
            report_sha256=sha(dest / 'report.json'), ui_witness=ui, virtual_seconds=virtual,
            post_screen_wall_seconds=wall, whole_docker_wall_seconds=host['docker_wall_seconds'],
            wall_per_virtual_second=wall / virtual,
            instructions=obs['after']['instructions'] - obs['before']['instructions'],
            frame_delta=obs['after']['frames'] - obs['before']['frames'],
            signal_events=obs['signals']['total'], startup_trace_truncated=result['startup_trace_truncated'],
            signal_sample_truncated=obs['signals']['truncated'],
            config={name: sha(capture / name) for name in ['main.bin', 'strict.cs', 'board.repl', 'run.py', 'activation.cs', 'probe.resc', 'sram-fill.bin', 'itcm-fill.bin', 'sustained-budget.json']})
        resources = matrix / ('%s-%ss-r%s-resources.jsonl' % (key[0], key[1] // 1000, key[2]))
        if not resources.exists():
            resources = capture / 'resource-samples.jsonl'
        if resources.exists():
            row['host_resource_samples'] = resource_summary([json.loads(line) for line in resources.read_text().splitlines()], owned[-1])
            pins[str(resources)] = sha(resources)
        else:
            row['host_resource_samples'] = dict(samples=0, scope='No valid resource sample available')
        rows.append(row)
        pins[str(dest / 'report.json')] = sha(dest / 'report.json')
        for relative, digest in result['capture_hashes'].items():
            pins[str(capture / relative)] = digest
    pairs = {}
    costs = {}
    for ms in [6000, 60000]:
        for case in CASES:
            selected = [r for r in rows if r['case'] == case and r['ms'] == ms]
            valid = (len(selected) == 2 and {r['repeat'] for r in selected} == {1, 2}
                     and selected[0]['config'] == selected[1]['config']
                     and selected[0]['ui_witness']['final_frame_sha256'] == selected[1]['ui_witness']['final_frame_sha256'])
            name = '%s-%s' % (case, ms)
            pairs[name] = dict(passed=valid, runs=len(selected))
            if selected:
                vals = [r['wall_per_virtual_second'] for r in selected]
                costs[name] = dict(runs=len(vals), median=statistics.median(vals), minimum=min(vals), maximum=max(vals))
    gaps = S / 'sustained-required-gaps-01/report.json'
    pins[str(gaps)] = sha(gaps)
    evidence = load(gaps)
    if not evidence['passed'] or not all(v['passed'] for v in evidence['criteria'].values()):
        raise ValueError('Required material gaps not established')
    for name, item in evidence['reviewed_assets'].items():
        p = Path(name)
        if sha(p) != item['sha256'] or p.stat().st_size != item['bytes']:
            raise ValueError('Changed gap evidence')
        pins[name] = item['sha256']
    integrated = {}
    for case in CASES:
        selected = [row for row in rows if row['case'] == case]
        same = len(selected) == 4 and all(row['profiles']['full_integration'] for row in selected)
        same = same and all(len({row['config'][key] for row in selected}) == 1
                            for key in ['main.bin', 'strict.cs', 'board.repl', 'run.py', 'activation.cs'])
        integrated[case] = dict(passed=same, runs=len(selected), scope='Same model/board/runtime at both durations; budgets differ explicitly.')
    complete = (state['status'] == 'completed' and len(rows) == 12 and all(v['passed'] for v in pairs.values())
                and all(v['passed'] for v in integrated.values()))
    containers = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Names}}'],
                                capture_output=True, text=True, check=True).stdout.splitlines()
    if set(owned) & set(containers):
        raise ValueError('A completed capture still owns a container')
    report = dict(schema=2, passed=complete, partial=not complete, matrix_status=state['status'],
        pairs=pairs, integration=integrated, rows=rows, measured_costs=costs, required_material_gaps_verified=True,
        full_goal_verified=complete, hardware_accessed=False, new_arm_executions=0, files=pins,
        completed_owned_containers_absent=owned,
        measurement_scope='Two cold repetitions per family and duration in the declared idle-screen virtual profile; not FPS or physical performance.',
        limitations=['Original ARM main and guest control flow are preserved. Declared component/board substitutions and optional host-only render deadline edits are reconstructed per capture and listed per row.',
                     'Controller identity and RTC weekday behavior are explicit virtual fixtures, not physical identity/timing validation.',
                     'UART history is a bounded prefix. Full-stream count/hash is recomputed from exported DMA source bytes in the UART0 all-DMA profile.',
                     'The original UI receiver is checked in final whole SRAM. Not a proof of every task or every UI interaction.',
                     'All IRQ signal counts are accumulated, but signal and startup PC history are truncated samples; not a full trace.',
                     'Cost includes the configured one-core Docker/observer workload. No hotspot profile or arbitrary workload extrapolation.',
                     'ROM/GPU/GAF missing material is identified, not implemented or physically validated.'])
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'auditor-source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(passed=complete, verified_runs=len(rows), verified_pairs=sum(x['passed'] for x in pairs.values()), partial=not complete)))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('matrix', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--allow-partial', action='store_true')
    a = p.parse_args()
    r = audit(a.matrix.resolve(), a.output.resolve())
    raise SystemExit(0 if r['passed'] or a.allow_partial else 1)
