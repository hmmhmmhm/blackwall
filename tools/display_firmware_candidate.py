"""Raw-main registration contract for the API-driven display diagnostic."""
import json
import copy
import re

from firmware_candidate import (BASE, MAIN_CAPACITY, load_candidate, metadata,
                                compatibility_anchors, check_anchors, candidate_runtime)
from native_replay import digest
from runtime_firmware_candidate import PROFILES, snapshot


def stimulus_entries(assembly):
    entries = [int(value, 16) & ~1 for value in
               re.findall(r'ldr r12, =0x([0-9a-f]+)\nblx r12', assembly)]
    if len(entries) != 3:
        raise ValueError('Unknown display stimulus caller')
    return entries


def candidate_semantics(original):
    spec = copy.deepcopy(original)
    spec['comparison']['paths'] = [['selected_image_unchanged'], ['original_tasks_resumed']]
    spec['checks'].append(dict(path=['selected_image_unchanged'], eq=True))
    spec['allowed_differences'].append('Explicit registered raw-main candidate; observer/caller entries pinned to original bytes.')
    return spec


def observer_points(profile):
    points = set()
    def collect(value):
        if type(value) is int and BASE <= value < BASE + MAIN_CAPACITY:
            points.add(value & ~1)
        elif isinstance(value, dict):
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    for key in ('getter', 'copy', 'negative_stop', 'contract', 'display',
                'content', 'content_watches', 'stimulus_entries'):
        if key in profile:
            collect(profile[key])
    # These stops are derived from the original functions in the runner.
    collect(profile['contract']['display_on_producer'] + 0x24)
    collect(profile['display']['consumer_return'] + 0x7c)
    return [dict(address=pc) for pc in sorted(points)]


def select(simulator, manifest, baseline, original, profile):
    if any(not p.resolve().is_relative_to(simulator.resolve()) for p in (manifest, baseline)):
        raise ValueError('Firmware registration and baseline must remain private')
    raw, record = load_candidate(manifest, baseline, PROFILES[profile['case']])
    if (baseline / 'main.bin').read_bytes() != original:
        raise ValueError('Registration baseline differs from display main')
    anchors = compatibility_anchors(original, observer_points(profile))
    check_anchors(raw, anchors)
    return raw, record, anchors


def inspect(capture, profile, original):
    if profile['stimulus_entries'] != stimulus_entries((capture / 'harness.s').read_text()):
        raise ValueError('Display stimulus entries differ from captured caller')
    raw, record = load_candidate(capture / 'firmware-candidate.json',
                                 capture / 'firmware-baseline', PROFILES[profile['case']])
    if (capture / 'firmware-baseline/main.bin').read_bytes() != original:
        raise ValueError('Saved registration baseline differs from display main')
    anchors = compatibility_anchors(original, observer_points(profile))
    if json.loads((capture / 'firmware-runtime-anchors.json').read_text()) != anchors:
        raise ValueError('Display observer contract differs')
    check_anchors(raw, anchors)
    if metadata(record, digest(capture / 'firmware-candidate.json')) != profile['firmware_candidate']:
        raise ValueError('Saved display candidate identity differs')
    if (capture / 'main.bin').read_bytes() != raw:
        raise ValueError('Saved display main differs from registered candidate')
    candidate_runtime((capture / 'run.py').read_text(), len(raw), len(raw))
    return dict(registered_candidate=True, display_observer_anchors=True,
                selected_image_unchanged=True, candidate_memory_extent=True)
