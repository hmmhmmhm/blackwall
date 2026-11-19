"""Public reset fixtures; selected write exceptions require an explicit controller."""
import hashlib
import json
from pathlib import Path

CATALOG = Path(__file__).with_name('simulator-trim-reset-catalog.json')
CATALOG_SHA256 = '0be186eab9db2c72cdc2fb8b82d72b2498aab90b5817843538d583c231ee9366'
ADDRESSES = frozenset((0x4002036c, 0x40020088, 0x40020044, 0x4002004c,
                       0x40020374, 0x40020080, 0x40021108, 0x400201b0,
                       0x40020344, 0x4002034c, 0x40020358, 0x40020354))


class TrimResetFixture:
    def __init__(self, report):
        raw = CATALOG.read_bytes()
        if hashlib.sha256(raw).hexdigest() != CATALOG_SHA256:
            raise ValueError('Trim reset catalog SHA256 mismatch')
        catalog = json.loads(raw)
        if catalog['schema'] != 'blackwall-trim-reset-catalog/1' or {int(a,16) for a in catalog['registers']} != ADDRESSES:
            raise ValueError('Unexpected trim reset catalog')
        rows = {}
        for address, item in catalog['registers'].items():
            if type(item['reset']) is not int or not 0 <= item['reset'] <= 0xffffffff:
                raise ValueError('Invalid reset word')
            rows[int(address,16)] = {'name': item['name'], 'value': hex(item['reset']), 'reads': 0, 'writes': 0}
        self.registers = rows
        report['models'].append('read-only-public-trim-reset-fixture')
        report['trim_reset_fixture'] = {
            'catalog_sha256': hashlib.sha256(raw).hexdigest(), 'source_sha256': catalog['source_sha256'],
            'upstream_commit': catalog['upstream_commit'],
            'registers': {hex(address): item for address,item in rows.items()},
            'valid_device_calibration': False, 'hardware_verified': False,
            'voltage_and_analog_behavior': 'not-modeled',
            'source_mismatches': {a:r['html_only_zero_fields'] for a,r in catalog['registers'].items() if r['html_only_zero_fields']}}

    def read(self, address, size):
        if address not in self.registers or size != 4:
            return None
        row = self.registers[address]
        row['reads'] += 1
        return int(row['value'],16)
