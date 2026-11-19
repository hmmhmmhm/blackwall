"""Explicit memory-policy replacement on the immutable reset/restart inputs."""
import hashlib
from pathlib import Path

BASELINE_SHA = '330182ef865a41085daf853a2e5a8678049db8dd4fe2314fb3fe851939880d29'

def with_memory_policy(s, inputs, metadata, source):
    baseline = (s/'reset-memory-protection-research-01/baseline-memory-policy.cs').read_bytes()
    candidate = Path(source).read_bytes()
    if hashlib.sha256(baseline).hexdigest() != BASELINE_SHA:
        raise ValueError('Changed baseline memory policy')
    if inputs['strict.cs'].count(baseline) != 1:
        raise ValueError('Expected exactly one original memory policy')
    if not candidate or candidate == baseline:
        raise ValueError('Explicit distinct memory policy candidate required')
    inputs = dict(inputs)
    inputs['strict.cs'] = inputs['strict.cs'].replace(baseline, candidate, 1)
    metadata = dict(metadata, memory_policy_candidate=dict(
        baseline_sha256=BASELINE_SHA, sha256=hashlib.sha256(candidate).hexdigest()))
    return inputs, metadata

def with_system_control(s, inputs, metadata, source):
    baseline = (s/'reset-domain-acceptance-research-01/baseline-system-control.cs').read_bytes()
    candidate = Path(source).read_bytes()
    baseline_sha = '82067ed1bdc22110330293a607718714e92b074d6835bee55cd761ae9e58d53c'
    if hashlib.sha256(baseline).hexdigest() != baseline_sha:
        raise ValueError('Changed baseline system control')
    if inputs['strict.cs'].count(baseline) != 1:
        raise ValueError('Expected exactly one original system control')
    if not candidate or candidate == baseline:
        raise ValueError('Explicit distinct system control candidate required')
    inputs = dict(inputs)
    inputs['strict.cs'] = inputs['strict.cs'].replace(baseline, candidate, 1)
    metadata = dict(metadata, system_control_candidate=dict(
        baseline_sha256=baseline_sha, sha256=hashlib.sha256(candidate).hexdigest()))
    return inputs, metadata
