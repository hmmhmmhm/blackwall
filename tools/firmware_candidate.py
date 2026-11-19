"""Register raw G2 main images for offline emulation; never accept installable OTAs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from native_replay import IMAGE, digest, validate_assets
from pinned_main import MAIN_LAYOUT

BASE, MAIN_CAPACITY = 0x438000, 0x3c0000
DECLARATION_KEYS = {'schema', 'id', 'format', 'target', 'cpu', 'profile', 'load_address',
                    'main_bytes', 'main_sha256', 'initial_sp', 'reset_vector'}


def validate_main(raw, declaration):
    if not isinstance(declaration, dict) or set(declaration) != DECLARATION_KEYS:
        raise ValueError('Invalid candidate declaration fields')
    if (type(declaration['schema']) is not int or declaration['schema'] != 1
            or declaration['format'] != 'raw-main' or declaration['target'] != 'g2-temple-main'
            or declaration['cpu'] != 'cortex-m55' or not isinstance(declaration['profile'], str) or declaration['profile'] not in MAIN_LAYOUT):
        raise ValueError('Unsupported candidate format/target/profile')
    if not isinstance(declaration['id'], str) or not re.fullmatch('[a-z][a-z0-9-]{0,63}', declaration['id']):
        raise ValueError('Invalid candidate identifier')
    for key in ['load_address', 'main_bytes', 'initial_sp', 'reset_vector']:
        if type(declaration[key]) is not int:
            raise ValueError('Integer candidate layout fields required')
    if declaration['load_address'] != BASE or not 8 <= len(raw) <= MAIN_CAPACITY or declaration['main_bytes'] != len(raw):
        raise ValueError('Candidate main extent differs or exceeds mapped memory')
    if hashlib.sha256(raw).hexdigest() != declaration['main_sha256']:
        raise ValueError('Candidate main hash differs')
    sp, pc = struct.unpack_from('<2I', raw)
    if sp != declaration['initial_sp'] or pc != declaration['reset_vector']:
        raise ValueError('Candidate vectors differ from declaration')
    if sp % 8 or not 0x20000000 < sp <= 0x20380000:
        raise ValueError('Candidate stack outside mapped SRAM or unaligned')
    if not pc & 1 or not BASE + 8 <= (pc & ~1) < BASE + len(raw):
        raise ValueError('Candidate reset must be a Thumb address inside main')


def compatibility_anchors(raw, points):
    addresses = {struct.unpack_from('<I', raw, 4)[0] & ~1}
    addresses.update(point['address'] for point in points)
    return [dict(address=address, bytes_hex=raw[address - BASE:address - BASE + 16].hex())
            for address in sorted(addresses) if BASE <= address < BASE + len(raw)]


def check_anchors(raw, anchors):
    for anchor in anchors:
        offset = anchor['address'] - BASE
        expected = bytes.fromhex(anchor['bytes_hex'])
        if offset < 0 or not expected or raw[offset:offset + len(expected)] != expected:
            raise ValueError('Observer/reset code profile unsupported at ' + hex(anchor['address']))


def baseline_contract(folder, profile):
    if profile not in MAIN_LAYOUT:
        raise ValueError('Unknown baseline profile')
    manifest_path = folder / 'derived-inputs.json'
    derived = json.loads(manifest_path.read_text())['derived']
    validate_assets(folder, derived)
    raw = (folder / 'main.bin').read_bytes()
    if len(raw) != MAIN_LAYOUT[profile][1] or hashlib.sha256(raw).hexdigest() != MAIN_LAYOUT[profile][3]:
        raise ValueError('Baseline is not the pinned main for declared profile')
    report = json.loads((folder / 'report.json').read_text())
    if report.get('execution_passed') is not True:
        raise ValueError('Baseline requires a completed capture')
    return digest(manifest_path), compatibility_anchors(raw, report['selected_observation']['points'])


def register_candidate(raw_path, declaration, baseline, output):
    raw = raw_path.read_bytes()
    validate_main(raw, declaration)
    baseline_hash, anchors = baseline_contract(baseline, declaration['profile'])
    check_anchors(raw, anchors)
    record = dict(schema=1, declaration=declaration, baseline_inputs_sha256=baseline_hash,
                  anchors=anchors, main_file='main.bin')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / 'main.bin').write_bytes(raw)
    (output / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def load_candidate(manifest_path, baseline, profile):
    record = json.loads(manifest_path.read_text())
    if (not isinstance(record, dict) or set(record) != {'schema', 'declaration', 'baseline_inputs_sha256', 'anchors', 'main_file'}
            or type(record['schema']) is not int or record['schema'] != 1):
        raise ValueError('Invalid registered candidate record')
    artifact = manifest_path.parent / 'main.bin'
    if record['main_file'] != 'main.bin' or artifact.resolve().parent != manifest_path.parent.resolve():
        raise ValueError('Invalid registered candidate artifact path')
    if not isinstance(record['declaration'], dict) or record['declaration'].get('profile') != profile:
        raise ValueError('Candidate profile differs from execution plan')
    baseline_hash, anchors = baseline_contract(baseline, profile)
    if record['baseline_inputs_sha256'] != baseline_hash or record['anchors'] != anchors:
        raise ValueError('Candidate baseline/observer contract differs')
    raw = artifact.read_bytes()
    validate_main(raw, record['declaration'])
    check_anchors(raw, anchors)
    return raw, record


def candidate_runtime(runtime, old_length, new_length):
    before="memory_policy=BlackwallMemoryPolicy(m,m['sysbus.cpu'],m['sysbus.main'],m['sysbus.itcm'],"+str(old_length)+")"
    after="memory_policy=BlackwallMemoryPolicy(m,m['sysbus.cpu'],m['sysbus.main'],m['sysbus.itcm'],"+str(new_length)+")"
    if runtime.count(before)!=1:
        raise ValueError('Unknown candidate memory-policy length anchor')
    return runtime.replace(before,after)


def metadata(record, registration_hash):
    declared = record['declaration']
    return dict(id=declared['id'], profile=declared['profile'], main_sha256=declared['main_sha256'],
                main_bytes=declared['main_bytes'], registration_sha256=registration_hash,
                image_id=IMAGE, physical_compatibility_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    register = sub.add_parser('register')
    register.add_argument('main', type=Path)
    register.add_argument('declaration', type=Path)
    register.add_argument('baseline', type=Path)
    register.add_argument('output', type=Path)
    register.add_argument('--private-root', type=Path, default=Path.home() / 'Library/Application Support/Blackwall/simulator')
    check = sub.add_parser('check')
    check.add_argument('manifest', type=Path)
    check.add_argument('baseline', type=Path)
    check.add_argument('--profile', required=True)
    args = parser.parse_args()
    if args.command == 'register':
        if not args.output.resolve().is_relative_to(args.private_root.resolve()):
            parser.error('Candidate output must remain under the private simulator root')
        record = register_candidate(args.main, json.loads(args.declaration.read_text()), args.baseline, args.output)
        print(json.dumps(metadata(record, digest(args.output / 'manifest.json'))))
    else:
        _, record = load_candidate(args.manifest, args.baseline, args.profile)
        print(json.dumps(metadata(record, digest(args.manifest))))


if __name__ == '__main__':
    main()
