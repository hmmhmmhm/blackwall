"""Find static direct-call candidates to pinned codec check entries; no device I/O."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from blackwall_package import parse_bundle
from audit_assets import PINS
from emulate_codec_flow import PROFILES, BASE
from emulate_codec_query import PROFILES as QUERY_PROFILES


def candidates(raw, target):
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    found = []
    for offset in range(0, len(raw)-3, 2):
        first, second = struct.unpack_from('<HH', raw, offset)
        if first & 0xf800 != 0xf000 or second & 0xd000 != 0xd000:
            continue
        instruction = next(decoder.disasm(raw[offset:offset+4], BASE+offset), None)
        if instruction is None or instruction.mnemonic != 'bl' or instruction.op_str != f'#{target:#x}':
            continue
        context_start = max(0, offset-24)
        context = [dict(address=hex(i.address), bytes=i.bytes.hex(), instruction=i.mnemonic+' '+i.op_str)
                   for i in decoder.disasm(raw[context_start:offset+12], BASE+context_start)]
        found.append(dict(address=hex(BASE+offset), bytes=raw[offset:offset+4].hex(), context=context))
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    results = {}
    for key, profile in PROFILES.items():
        data = (args.inputs/QUERY_PROFILES[key]['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != PINS[key]:
            raise ValueError('Bundle hash mismatch: '+key)
        raw = next(c for c in parse_bundle(data) if c.type_id == 0).payload[32:]
        results[key] = candidates(raw, profile['entry'])
    report = dict(scope='halfword BL candidates; no code reachability proof', results=results,
                  bundle_sha256={key:PINS[key] for key in PROFILES}, hardware_validated=False,
                  caveats=['Data can decode as instructions', 'Indirect calls and callbacks are not enumerated',
                           'Context starts at a fixed preceding halfword, not a proven function boundary'])
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps({key:[item['address'] for item in items] for key,items in results.items()}))


if __name__ == '__main__':
    main()
