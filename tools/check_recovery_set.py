"""Validate a pinned local recovery set. Never imports or executes device tools."""
import argparse
import hashlib
import json
from pathlib import Path


PROFILE_PATH = Path(__file__).resolve().parents[1] / 'docs/data/recovery-artifact-profiles.json'


def check(files, key):
    profiles = json.loads(PROFILE_PATH.read_text())['profiles']
    digests = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    matches = [(version, profile) for version, profile in profiles.items()
               if profile['files']['bootloader.bin'] == digests.get('bootloader.bin')]
    if len(matches) != 1:
        raise ValueError('Unknown boot image: no recovery profile selected')
    version, profile = matches[0]
    for name, expected in profile['files'].items():
        if digests.get(name) != expected:
            raise ValueError(f'{name}: missing or incompatible with selected boot image')
    if hashlib.sha256(key).hexdigest() != profile['key_id']:
        raise ValueError('Recovery key does not match selected boot image')
    return {
        'schema': 'blackwall-recovery-set-check/1',
        'boot_base_version': version,
        'matched_files': digests,
        'key_matches': True,
        'mram_entry': profile['mram_entry'],
        'case_fixture_version': profile['case_base'],
        'local_artifact_pairing_valid': True,
        'installable': False,
        'hardware_validated': False,
        'limitations': [
            'Local boot image is not evidence of the boot installed on either temple',
            'Case fixture version is not the attached case version',
            'Faceclaw and full stock restoration compatibility remain unverified',
            'No hardware access or execution is performed by this checker',
        ],
    }


def load(candidate):
    names = ('bootloader.bin', 'patch.bin', 'recover.bin', 'dump.bin', 'checksum.bin', 'case.bin')
    files = {name: (candidate / 'source/build' / name).read_bytes() for name in names}
    key = (candidate / 'recovery.key').read_text().strip().encode()
    return files, key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = check(*load(args.candidate))
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'boot_base_version': result['boot_base_version'],
                      'local_artifact_pairing_valid': True, 'installable': False}))


if __name__ == '__main__':
    main()
