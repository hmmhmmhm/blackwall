"""Audit saved original-family touch-scroll and no-input captures; never run ARM."""
import argparse
import hashlib
import json
from pathlib import Path

S = Path.home() / 'Library/Application Support/Blackwall/simulator'
MAIN = {'stock24': 'df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a',
        'stock23': 'fffbf74b3439bf0e4752fb620a7990d0a133898c54f6fb08005ea6b7029655c5',
        'cfw': '4118af85ebb8e634493a61a3ce4a62ae37451e17cea6d0b8b08465f29538dd8f'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def input_witness(value, stack_bytes=128):
    rows = value['rows']
    selected = []
    for tag in [200, 202, 201, 204, 207, 210, 208, 209, 203, 206, 205]:
        candidates = [r for r in rows if r[0] == tag
                      and (not selected or r[10] >= selected[-1][10])
                      and (tag != 203 or r[2] == 3)]
        if not candidates:
            return {'passed': False, 'missing_tag': tag}
        selected.append(candidates[0])
    handler, slider, caller, app, sync, parser, display, queue, ui, consumer, cleanup = selected
    checks = dict(
        source_scroll=slider[2:6] == [1, 4, 10, 167],
        source_caller_return=caller[2] == 0 and caller[6] == handler[6]
        and caller[8] == handler[8],
        app_ack=app[2] == 0 and app[4] == 12,
        ui_parser=parser[3] == 10,
        command_queue=queue[2] == 1 and queue[4] == 6,
        app_input=ui[4] == 6 and ui[3] == consumer[2] and consumer[3] == 6,
        same_ui_task=parser[8] == ui[8] == consumer[8] == cleanup[8],
        callback_cleanup=cleanup[6] == ui[6] - stack_bytes and cleanup[2] == 0,
        callback_after_input=ui[10] > handler[10],
        thread_mode=all((r[9] & 0x1ff) == 0 for r in selected),
    )
    return dict(passed=all(checks.values()), checks=checks, rows=selected)


def evaluate(candidate, control, stack_bytes=128):
    witness = input_witness(candidate, stack_bytes)
    return dict(
        input_consumed=witness['passed'],
        input_state_changed=candidate['after']['input_tick'] != candidate['settled']['input_tick'],
        control_no_input=not control['reload_accepted'] and not control['edge_accepted']
        and control['after']['touch_frames'] == control['settled']['touch_frames']
        and control['after']['input_tick'] == control['settled']['input_tick']
        and not any(r[0] == 203 and r[2] == 3 for r in control['rows']),
        same_initial_frame=candidate['settled']['frame_sha256'] == control['settled']['frame_sha256'],
        control_frame_constant=all(r['frame_sha256'] == control['settled']['frame_sha256']
                                   for r in control['samples'])
        and control['after']['frame_sha256'] == control['settled']['frame_sha256'],
        input_frame_changed=candidate['after']['frame_sha256'] != candidate['settled']['frame_sha256']
        and candidate['after']['frames'] > candidate['settled']['frames'],
        equal_virtual_window=all(x['after']['ticks'] - x['settled']['ticks'] == 200000000
                                 and len(x['samples']) == 40 for x in [candidate, control]),
    )


def audit(candidate, control, out):
    if out.exists() or not out.is_relative_to(S) or any(out.is_relative_to(p) for p in [candidate, control]):
        raise ValueError('New separate private audit output required')
    x, y = [load(p / 'exports/active-input.json') for p in [candidate, control]]
    case = next(iter(load(candidate / 'plan.json')['cases']))
    if case not in MAIN or next(iter(load(control / 'plan.json')['cases'])) != case:
        raise ValueError('Same supported firmware case required')
    stack_bytes = 128 if case == 'stock24' else 120
    checks = evaluate(x, y, stack_bytes)
    profiles = [load(p / 'active-input-profile.json') for p in [candidate, control]]
    checks['explicit_input_only_difference'] = profiles[0]['mode'] == 'scroll' and profiles[1]['mode'] == 'none' and {
        k: v for k, v in profiles[0].items() if k != 'mode'
    } == {k: v for k, v in profiles[1].items() if k != 'mode'}
    checks['same_original_execution_configuration'] = all(
        sha(candidate / name) == sha(control / name)
        for name in ['main.bin', 'strict.cs', 'board.repl', 'activation.cs', 'run.py', 'probe.resc', 'runner-source.py']
    ) and sha(candidate / 'main.bin') == MAIN[case]
    reports = [load(p / 'audit/report.json') for p in [candidate, control]]
    checks['saved_execution_and_clean_runtime'] = all(
        r['passed'] and r['execution_passed'] and r['semantic_validation']['passed']
        and r['diagnostics']['boot_frame'] and r['diagnostics']['clean_runtime']
        for r in reports
    )
    raw = (candidate / 'main.bin').read_bytes()
    checks['original_source_preflight'] = all(
        (case == 'stock24' and 'source_checks' not in profile) or
        (len(profile.get('source_checks', [])) == 6 and all(
            0 <= item['address'] - 0x438000 < len(raw)
            and raw[item['address'] - 0x438000:item['address'] - 0x438000 + len(bytes.fromhex(item['bytes']))].hex() == item['bytes']
            for item in profile['source_checks']))
        for profile in profiles
    )
    checks['pinned_inputs'] = all(
        sha(folder / name) == digest
        for folder in [candidate, control]
        for name, digest in load(folder / 'plan.json')['input_sha256'].items()
    )
    checks['removed_processes'] = all(load(p / 'renode.process.json')['status'] == 'removed'
                                      for p in [candidate, control])
    checks['injection_preserved_cpu_sram'] = all(
        all(v['settled'][k] == v['injected'][k] for k in ['registers', 'ticks', 'instructions'])
        and sha(p / 'exports/active-input-before-sram.bin') == sha(p / 'exports/active-input-injected-sram.bin')
        for p, v in [(candidate, x), (control, y)]
    )
    checks['pulse_contract'] = x['release']['accepted'] and x['release']['fired_at'] - x['release']['started'] == 250000
    checks['frame_bytes_match_observations'] = all(
        (p / 'exports' / name).stat().st_size == 576 * 288 and sha(p / 'exports' / name) == state['frame_sha256']
        for p, value in [(candidate, x), (control, y)]
        for name, state in [('active-settled-frame.bin', value['settled']),
                            ('active-input-after-frame.bin', value['after'])]
        + [('active-frame-%03d.bin' % n, state) for n, state in enumerate(value['samples'])]
    )
    witness = input_witness(x, stack_bytes)
    ui = next(r for r in x['rows'] if r[0] == 203 and r[2] == 3)
    memory = (candidate / 'exports/active-input-after-sram.bin').read_bytes()
    offset = ui[3] - 0x20000000
    checks['retained_command_payload'] = 0 <= offset <= len(memory) - 6 and memory[offset:offset + 6].hex() == '0044a7000a00'
    checks['known_correlated_replies'] = [r['bytes'][9] for r in x['replies']] == [10, 8, 4] and all(
        r['accepted'] and r['before_registers'] == r['after_registers'] and r['before_ticks'] == r['after_ticks']
        for r in x['replies']
    ) and [r['bytes'][1:3] for r in x['replies']] == [r[1:3] for r in x['outgoing'][:3]]
    before = (candidate / 'exports/active-settled-frame.bin').read_bytes()
    after = (candidate / 'exports/active-input-after-frame.bin').read_bytes()
    files = {str(p.relative_to(S)): sha(p) for root in [candidate, control]
             for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    result = dict(schema=1, case=case, criterion='E11', passed=all(checks.values()), checks=checks,
                  touch_scroll_ui_and_frame_verified=all(checks.values()),
                  full_e11_verified=False, witness=witness,
                  pixels_changed=sum(a != b for a, b in zip(before, after)),
                  candidate=str(candidate.relative_to(S)), control=str(control.relative_to(S)),
                  capture_hashes=files, new_native_runs=False, hardware_accessed=False,
                  limitations=['One touch-scroll scenario and firmware case, not all v1 inputs or firmware families.',
                               'Declared virtual peer replies and 250us input waveform; no physical validation.',
                               'Retained command buffer is final-state corroboration, not a history of all writes.'])
    out.mkdir(mode=0o700, parents=True)
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'auditor-source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(passed=result['passed'], checks=checks, pixels_changed=result['pixels_changed'])))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('control', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = audit(args.candidate.resolve(), args.control.resolve(), args.output.resolve())
    raise SystemExit(0 if result['passed'] else 1)
