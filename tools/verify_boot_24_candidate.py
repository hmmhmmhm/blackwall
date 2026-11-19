"""Independent structural check of the experimental 2.4 candidate, not installation approval."""
import argparse
import hashlib
import json
from pathlib import Path
from blackwall_package import branch_target
from prepare_boot_24_candidate import BOOT_SHA

BASE, APP, APPEND, STOCK_LENGTH = 0x410000, 0x438000, 0x434910, 149773
HOOKS = ((0x42e666, 'boot_task_then_flag'), (0x42e3e4, 'boot_handoff'), (0x42e450, 'boot_handoff'))


def verify(stock, image, blob, symbols):
    assert len(stock) == STOCK_LENGTH and hashlib.sha256(stock).hexdigest() == BOOT_SHA
    assert len(image) % 4096 == 0 and BASE + len(image) <= APP
    assert symbols['base'] == APPEND and symbols['bytes'] == len(blob)
    assert symbols['sha256'] == hashlib.sha256(blob).hexdigest()
    prefix = bytearray(image[:STOCK_LENGTH])
    targets = {}
    for address, name in HOOKS:
        offset = address-BASE
        target = branch_target(address, image[offset:offset+4])
        expected = APPEND + symbols['functions'][name]['offset']
        assert target == expected and APPEND <= target < APPEND+len(blob)
        prefix[offset:offset+4] = stock[offset:offset+4]
        targets[hex(address)] = hex(target)
    assert prefix == stock, 'Original bytes changed outside the three hooks'
    assert image[STOCK_LENGTH:APPEND-BASE] == b'\xff'*3
    assert image[APPEND-BASE:APPEND-BASE+len(blob)] == blob
    raw_end = APPEND-BASE+len(blob)
    assert image[raw_end:] == b'\xff'*(len(image)-raw_end)
    return {'installable': False, 'hardware_validated': False,
            'bytes': len(image), 'sha256': hashlib.sha256(image).hexdigest(),
            'original_prefix_preserved_except_hooks': True, 'alignment_gap_bytes': 3,
            'appended_code_bytes': len(blob), 'hook_targets': targets,
            'partition_end_exclusive': hex(BASE+len(image))}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    a = p.parse_args()
    build = a.directory/'source/build'
    stock = (a.directory/'stock-boot-2.4.0.24.bin').read_bytes()
    image = (build/'bootloader.bin').read_bytes()
    blob = (build/'patch.bin').read_bytes()
    symbols = json.loads((build/'patch.json').read_text())
    result = verify(stock, image, blob, symbols)
    for name, offset in [('prefix', 100), ('alignment-gap', STOCK_LENGTH),
                         ('appended-code', APPEND-BASE+120), ('page-padding', len(image)-1)]:
        bad = bytearray(image)
        bad[offset] ^= 1
        try:
            verify(stock, bad, blob, symbols)
        except AssertionError:
            continue
        raise AssertionError('Mutation not rejected: '+name)
    result['corruption_controls_rejected'] = 4
    out = a.directory/'structural-verification.json'
    with out.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result, indent=2))
