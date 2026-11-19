"""Verify reset metadata against pinned public header/HTML, without device access."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from simulator_trim_fixture import CATALOG, CATALOG_SHA256


def verify(sources):
    raw = CATALOG.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError('Catalog SHA256 mismatch')
    catalog = json.loads(raw)
    texts = {}
    for name, expected in catalog['source_sha256'].items():
        data = (sources/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Public source SHA256 mismatch: '+name)
        texts[name] = data.decode()
    header = texts['apollo510.h']
    for address, item in catalog['registers'].items():
        domain, name = item['name'].split('.')
        doc = texts[domain.lower()+'_regs.html']
        index = doc.index(f'0x{int(address,16):08X}')
        start, end = doc.rfind('<h3 id=', 0, index), doc.find('<h3 id=', index)
        if re.match(r'<h3 id="([A-Z0-9]+)"', doc[start:]).group(1) != name:
            raise ValueError('Address/register name mismatch')
        fields = re.findall(r'colspan="\d+">([A-Z0-9_]+)\s*<br>(0x[0-9a-fA-F]+)', doc[start:end])
        composed, matched, missing = 0, {}, []
        for field, reset in fields:
            if field.startswith('RSVD'):
                if int(reset,16) != 0:
                    raise ValueError('Unexpected nonzero reserved reset bits')
                continue
            prefix = domain+'_'+name+'_'+field
            position = re.search(r'#define '+prefix+r'_Pos\s+\((\d+)UL\)', header)
            mask = re.search(r'#define '+prefix+r'_Msk\s+\((0x[0-9a-fA-F]+)UL\)', header)
            if position is None or mask is None:
                if int(reset,16) != 0:
                    raise ValueError('Missing header field has nonzero reset: '+prefix)
                missing.append(field)
                continue
            shift, bits = int(position.group(1)), int(mask.group(1),16)
            value = int(reset,16)<<shift
            if value & ~bits:
                raise ValueError('Reset value exceeds field mask')
            matched[field] = {'reset': reset, 'position': shift, 'mask': hex(bits)}
            composed |= value
        if not matched or matched != item['fields'] or missing != item['html_only_zero_fields'] or composed != item['reset']:
            raise ValueError('Reset derivation mismatch: '+name)
    return {'scope': 'public reset metadata derivation only', 'catalog_sha256': CATALOG_SHA256,
            'source_sha256': catalog['source_sha256'], 'registers_verified': len(catalog['registers']),
            'valid_device_calibration': False, 'hardware_validated': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.sources)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print('Verified 12 reset words against pinned public sources; not device calibration')


if __name__ == '__main__':
    main()
