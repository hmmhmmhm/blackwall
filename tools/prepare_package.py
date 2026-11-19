"""Prepare private review artifacts, without device access or installation permission."""
import argparse
import json
import os
from pathlib import Path
from blackwall_package import parse_bundle, sha256
from audit_assets import PINS
from check_recovery_set import check, load

ROOT = Path(__file__).resolve().parents[1]
BOOT_COMPONENT_SHA = '08cdf7373de1fb60b2c2efa0afd5bec9702c0fa85ec63026b1fc1d19561b8368'

def validate_tool_manifest(name, binary, metadata):
    if not isinstance(metadata, dict) or metadata.get('bytes') != len(binary) or metadata.get('sha256') != sha256(binary):
        raise ValueError('Recovery tool metadata does not match binary: ' + name)
    if metadata.get('base') != (0x20010000 if name == 'case.bin' else 0):
        raise ValueError('Recovery tool has wrong link base: ' + name)
    if name != 'case.bin' and metadata.get('functions', {}).get('entry', {}).get('offset') != 0:
        raise ValueError('RAM recovery tool entry must be zero: ' + name)

def prepare(inputs, destination, *, recovery_candidate=None):
    destination = destination.resolve()
    if destination.is_relative_to(ROOT):
        raise ValueError('Firmware output must be outside the repository')
    if destination.exists():
        raise ValueError('Output already exists; never overwrite recovery assets')
    files, provenance = {}, {}
    for label, pin, target in [('cfw', PINS['cfw'], 'main-cfw.bin'), ('stock', PINS['stock_current'], 'main-stock.bin')]:
        data = inputs[label].read_bytes()
        if sha256(data) != pin:
            raise ValueError(f'{label}: input SHA256 mismatch')
        parts = parse_bundle(data)
        main = next(c for c in parts if c.type_id == 0)
        files['components/' + target] = main.ota_bytes()
        provenance[label] = pin
    boot = inputs['boot_component'].read_bytes()
    recovery = None
    expected_boot = BOOT_COMPONENT_SHA
    boot_name = 'boot.bin'
    if recovery_candidate is not None:
        assets, key = load(recovery_candidate)
        recovery = check(assets, key)
        if recovery['boot_base_version'] != '2.4.0.24':
            raise ValueError('This package requires the 2.4 recovery set')
        expected_boot = 'b95254ec99b140e7b2cf41a66ed86ebd5375bb7f80a1d97faaf5fdbad4e04b96'
        boot_name = 'boot-24.bin'
        if boot[128:] != assets['bootloader.bin']:
            raise ValueError('Boot component and recovery candidate differ')
        for name in ('case.bin', 'dump.bin', 'checksum.bin', 'recover.bin'):
            files['recovery-kit/'+name] = assets[name]
            metadata = (recovery_candidate/'source/build'/name.replace('.bin', '.json')).read_bytes()
            validate_tool_manifest(name, assets[name], json.loads(metadata))
            files['recovery-kit/'+name.replace('.bin', '.json')] = metadata
        files['recovery-kit/verification.json'] = (json.dumps(recovery, indent=2)+'\n').encode()
    if sha256(boot) != expected_boot:
        raise ValueError('boot: input SHA256 mismatch')
    files['components/' + boot_name] = boot
    provenance['boot_component'] = expected_boot
    for source in sorted((ROOT / 'web').iterdir()):
        if source.is_file() and source.suffix in ('.html', '.css', '.mjs'):
            files['web/' + source.name] = source.read_bytes()
    path_map = json.loads((ROOT / 'docs/data/document-path-map.json').read_text())['paths']
    for name in ['recovery-manual.md', 'private-recovery-candidate.md', 'web-preparation-ui.md', 'web-protocol-verification.md', 'package-preparation.md', 'bootloader-2-4-candidate.md', 'combined-handoff-verification.md']:
        old_path = 'docs/' + name
        files[old_path] = (ROOT / path_map.get(old_path, old_path)).read_bytes()
    files['NOTICE.md'] = (ROOT / 'NOTICE.md').read_bytes()
    for source in (ROOT / 'licenses').iterdir():
        if source.is_file():
            files['licenses/' + source.name] = source.read_bytes()
    manifest = {
        'schema': 'blackwall-private-preparation/1',
        'installable': False,
        'hardwareValidation': 'none',
        'recoveryPairing': recovery,
        'bootOperation': 'boot-24' if recovery else 'boot',
        'sourceInputs': provenance,
        'files': {name: {'bytes': len(data), 'sha256': sha256(data)} for name, data in files.items()},
        'limitations': ['Device compatibility unknown', 'No full-stock recovery proof',
                        'Web UI is inspection-only', 'Recovery key and host remain in separately preserved recovery directory'],
    }
    # A manifest is written last; an interrupted output without it is incomplete.
    old_mask = os.umask(0o077)
    try:
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
        for name, data in files.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as output:
                output.write(data)
        for name, info in manifest['files'].items():
            if sha256((destination / name).read_bytes()) != info['sha256']:
                raise ValueError(f'Output verification failed: {name}')
        with (destination / 'manifest.json').open('x') as output:
            output.write(json.dumps(manifest, indent=2) + '\n')
    finally:
        os.umask(old_mask)
    return manifest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['cfw', 'stock', 'boot-component', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--recovery-candidate', type=Path)
    args = vars(parser.parse_args())
    recovery_candidate = args.pop('recovery_candidate')
    destination = args.pop('output')
    try:
        manifest = prepare(args, destination, recovery_candidate=recovery_candidate)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Preparation rejected: {error}\n')
    print(json.dumps({'filesVerified': len(manifest['files']), 'installable': False}))

if __name__ == '__main__':
    main()
