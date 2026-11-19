"""Reuse raw-main registration for device-runtime captures and offline audits."""
import json
import shutil

from firmware_candidate import (load_candidate, metadata, compatibility_anchors,
                                check_anchors, candidate_runtime)
from native_replay import digest
from pinned_main import MAIN_LAYOUT

PROFILES = {'stock24': 'stock_current', 'stock23': 'stock_base', 'cfw': 'cfw'}
SERVICE_CODE = ('consumer', 'service', 'time_handler', 'before_clock_apply',
                'clock_apply', 'tpl_local_callback', 'consumer_return',
                'clock_return', 'ingress')


def observer_points(profile):
    points = [profile[key] for key in ('getter', 'opened', 'finished')]
    points += [profile['gpio'][key] for key in ('isr', 'dispatcher', 'callback', 'set_event')]
    points += [profile['service'][key] for key in SERVICE_CODE if profile.get('att_time')]
    points += [profile[key] for key in ('write_processor', 'write_return', 'closed', 'closed_return')
               if key in profile]
    return [dict(address=address & ~1) for address in sorted(set(points))]


def select(simulator, manifest, baseline, case, original, profile):
    if not manifest.resolve().is_relative_to(simulator.resolve()) or not baseline.resolve().is_relative_to(simulator.resolve()):
        raise ValueError('Firmware registration and baseline must remain private')
    raw, record = load_candidate(manifest, baseline, PROFILES[case])
    if (baseline / 'main.bin').read_bytes() != original:
        raise ValueError('Registration baseline differs from runtime main')
    anchors = compatibility_anchors(original, observer_points(profile))
    check_anchors(raw, anchors)
    return raw, record, anchors


def snapshot(output, manifest, baseline, record, anchors):
    target = output / 'firmware-baseline'
    target.mkdir()
    derived = json.loads((baseline / 'derived-inputs.json').read_text())['derived']
    for name in set(derived) | {'derived-inputs.json', 'report.json'}:
        source = baseline / name
        if not source.resolve().is_relative_to(baseline.resolve()):
            raise ValueError('Invalid baseline asset path')
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    shutil.copyfile(manifest, output / 'firmware-candidate.json')
    (output / 'firmware-runtime-anchors.json').write_text(json.dumps(anchors, indent=2) + '\n')
    return metadata(record, digest(output / 'firmware-candidate.json'))


def inspect(output, profile):
    raw, record = load_candidate(output / 'firmware-candidate.json',
                                 output / 'firmware-baseline', PROFILES[profile['case']])
    original = (output / 'firmware-baseline/main.bin').read_bytes()
    anchors = compatibility_anchors(original, observer_points(profile))
    if json.loads((output / 'firmware-runtime-anchors.json').read_text()) != anchors:
        raise ValueError('Runtime observer contract differs')
    check_anchors(raw, anchors)
    if metadata(record, digest(output / 'firmware-candidate.json')) != profile['firmware_candidate']:
        raise ValueError('Saved candidate identity differs')
    if digest(output / 'main.bin') != profile['firmware_candidate']['main_sha256']:
        raise ValueError('Saved main differs from registered candidate')
    runtime = (output / 'run.py').read_text()
    # The common helper validates the exact memory-policy length anchor.
    candidate_runtime(runtime, len(raw), len(raw))
    return dict(registered_candidate=True, runtime_observer_anchors=True,
                candidate_memory_extent=True)


def check_original(output, profile):
    if ((output / 'firmware-candidate.json').exists()
            or profile['main_sha256'] != MAIN_LAYOUT[PROFILES[profile['case']]][3]):
        raise ValueError('Nonoriginal main requires registered candidate metadata')
