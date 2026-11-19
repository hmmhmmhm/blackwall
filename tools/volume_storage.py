"""Store pinned, explicitly supplied emulator inputs in a Docker named volume."""
import io
import json
import re
import subprocess
import tarfile
from uuid import uuid4
from pathlib import Path

from run_original_boot_screen import checked_asset, checked_path, sha, validate_profile

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649'
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


def volume_name(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value):
        raise ValueError('Invalid Docker volume name')
    return value


def docker(*args, data=None):
    result = subprocess.run(['docker', *args], input=data, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace').strip() or 'Docker command failed')
    return result.stdout


def select_profile(source, name):
    source = Path(source).resolve()
    choices = {
        'imu': source / 'simulator/imu-observation-bw604/profile.json',
        'detailed': source / 'simulator/detailed-boot-observer-bw601/profile.json',
        'timed': source / 'simulator/timed-boot-observer-bw595/profile.json',
        'stock': ROOT / 'docs/data/original-boot-stock24-profile.json',
    }
    if name == 'auto':
        return next((p for p in choices.values() if p.is_file()), None)
    return choices[name] if name in choices and choices[name].is_file() else None


def pinned_inputs(source, profile_file, boot=None, main=None):
    source = Path(source).resolve()
    profile_file = Path(profile_file).resolve()
    profile = json.loads(profile_file.read_text())
    validate_profile(profile)
    entries = {'profile.json': profile_file.read_bytes()}
    for name, spec in profile['assets'].items():
        override = boot if name == 'boot' else main if name == 'main' else None
        path = checked_asset(source, spec, override)
        entries[spec['path']] = path.read_bytes()
    for name, spec in profile['components'].items():
        base = ROOT if spec['origin'] == 'repo' else source
        path = checked_path(base, spec['path'])
        if sha(path) != spec['sha256']:
            raise ValueError('Component hash mismatch: ' + name)
        if spec['origin'] != 'repo':
            entries[spec['path']] = path.read_bytes()
    if sum(map(len, entries.values())) > MAX_ARCHIVE_BYTES:
        raise ValueError('Input set is too large')
    return profile, entries


def archive(entries):
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode='w') as tar:
        for name, data in sorted(entries.items()):
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or not path.parts:
                raise ValueError('Unsafe archive path')
            info = tarfile.TarInfo(path.as_posix())
            info.size = len(data)
            info.mode = 0o600
            tar.addfile(info, io.BytesIO(data))
    return result.getvalue()


def import_volume(name, entries):
    name = volume_name(name)
    existing = subprocess.run(['docker', 'volume', 'inspect', name], capture_output=True)
    if existing.returncode == 0:
        raise ValueError('Volume already exists; choose another name')
    if b'No such volume' not in existing.stderr and b'no such volume' not in existing.stderr.lower():
        raise RuntimeError('Cannot inspect Docker volumes: ' + existing.stderr.decode(errors='replace').strip())
    payload = archive(entries)
    token = uuid4().hex
    docker('volume', 'create', '--label', 'io.blackwall.asset-volume=1', '--label', 'io.blackwall.creation-token=' + token, name)
    labels = json.loads(docker('volume', 'inspect', name).decode())[0].get('Labels') or {}
    if labels.get('io.blackwall.creation-token') != token:
        raise RuntimeError('Volume creation raced with another owner; refusing to modify it')
    try:
        docker('run', '--rm', '-i', '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--mount', f'type=volume,source={name},target=/data', '--entrypoint', 'tar', IMAGE,
               '-xf', '-', '-C', '/data', '--no-same-owner', data=payload)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise RuntimeError('Import failed; the newly created volume may contain partial data: ' + name) from exc


def extract_volume(name, destination):
    name = volume_name(name)
    destination = Path(destination).resolve()
    try:
        info = json.loads(docker('volume', 'inspect', name).decode())
    except RuntimeError as exc:
        if 'no such volume' in str(exc).lower():
            raise ValueError('Docker volume not found; run blackwall setup first') from exc
        raise
    labels = info[0].get('Labels') or {}
    if labels.get('io.blackwall.asset-volume') != '1':
        raise ValueError('Docker volume is not a Blackwall asset volume')
    raw = docker('run', '--rm', '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                 '--mount', f'type=volume,source={name},target=/data,readonly', '--entrypoint', 'tar', IMAGE,
                 '-cf', '-', '-C', '/data', '.')
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise ValueError('Volume export is too large')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:*') as tar:
        members = tar.getmembers()
        total = 0
        for item in members:
            path = Path(item.name)
            if path.is_absolute() or '..' in path.parts or not (item.isfile() or item.isdir()):
                raise ValueError('Unsafe volume archive entry')
            total += item.size
            if total > MAX_ARCHIVE_BYTES:
                raise ValueError('Volume contents are too large')
        for item in members:
            if item.isdir():
                continue
            target = (destination / item.name).resolve()
            if not target.is_relative_to(destination) or target.exists():
                raise ValueError('Unsafe or duplicate volume archive entry')
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(item) as source, target.open('xb') as output:
                while data := source.read(1024 * 1024):
                    output.write(data)
    profile = destination / 'profile.json'
    if not profile.is_file():
        raise ValueError('Volume has no pinned profile')
    pinned_inputs(destination, profile)
    return profile
