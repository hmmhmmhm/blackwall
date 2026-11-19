"""Prepare a private, non-installable 2.4 boot research source tree; no hardware access."""
import argparse
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import tarfile

COMMIT = '6198d70e18293caebf8314d2e40bd3b1d0a5ee16'
BOOT_SHA = 'ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665'


def prepare(upstream, boot_path, output):
    root = Path(__file__).resolve().parents[1]
    if output.resolve().is_relative_to(root) or output.exists():
        raise ValueError('Use a new directory outside Git')
    boot = boot_path.read_bytes()
    if hashlib.sha256(boot).hexdigest() != BOOT_SHA or len(boot) != 149773:
        raise ValueError('Wrong stock boot image')
    for address, expected in ((0x42e666, 'fff789ff'), (0x42e3e4, 'fff700fe'), (0x42e450, 'fff7cafd')):
        assert boot[address-0x410000:address-0x410000+4].hex() == expected
    archive = subprocess.check_output(['git', '-C', str(upstream), 'archive', COMMIT])
    os.umask(0o077)
    output.mkdir(parents=True)
    source = output/'source'
    source.mkdir()
    (output/'source.tar').write_bytes(archive)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(source, filter='data')
    changes = {
        'src/platform.h': [('0x0042e56du', '0x0042e57du'), ('0x0042dfd9u', '0x0042dfe9u'),
                           ('0x00434210u', '0x00434220u'), ('2.3.2.14 only', '2.4.0.24 research candidate only')],
        'src/boot.ld': [('0x0042e656', '0x0042e666'), ('0x0042e3d4', '0x0042e3e4'),
                        ('0x0042e440', '0x0042e450'), ('0x00434900', '0x00434910'),
                        ('2.3.2.14', '2.4.0.24 research candidate')],
        'src/examples/recover.c': [('0x0042e83du', '0x0042e84du'), ('2.3.2.14', '2.4.0.24 research candidate')],
        'Makefile': [('--base 0x434900', '--base 0x434910')],
        'tools/g2patch/artifacts.py': [('if base == 0x434900:', 'if base == 0x434910:')],
        'tools/g2patch/firmware.py': [('STOCK_BYTES = 149760', 'STOCK_BYTES = 149773'),
            ('22a2b98e606b4d296e957a3a8b600a2158497638d79485c817c2025536329ba7', BOOT_SHA),
            ('0x0042E656', '0x0042E666'), ('0x0042E3D4', '0x0042E3E4'), ('0x0042E440', '0x0042E450'),
            ('2.3.2.14', '2.4.0.24 research candidate'),
            ('if not STOCK_BYTES <= target < len(image):', 'if not 0x24910 <= target < len(image):')],
        'tools/patch.py': [('fixed 2.3.2.14 bootloader', 'experimental fixed 2.4.0.24 bootloader'),
            ('    image.extend(blob)', '    image.extend(b"\\xff" * (0x24910 - len(image)))\n    image.extend(blob)')],
    }
    diff = []
    for name, replacements in changes.items():
        file = source/name
        original = file.read_text()
        changed = original
        for before, after in replacements:
            if changed.count(before) != 1:
                raise ValueError(f'Unexpected source text: {name}: {before}')
            changed = changed.replace(before, after)
        file.write_text(changed)
        diff.extend(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                                       fromfile='a/'+name, tofile='b/'+name))
    (output/'research-source.patch').write_text(''.join(diff))
    (output/'stock-boot-2.4.0.24.bin').write_bytes(boot)
    (output/'recovery.key').write_text(secrets.token_hex(32))
    manifest = {'kind': 'experimental-2.4-boot-source', 'installable': False,
                'hardware_validated': False, 'upstream_commit': COMMIT,
                'archive_sha256': hashlib.sha256(archive).hexdigest(), 'stock_boot_sha256': BOOT_SHA,
                'append_address': '0x434910', 'changed_files': list(changes),
                'unverified': ['full scheduler and watchdog behavior', 'hardware revision and ROM',
                               'physical recovery', 'Faceclaw mixed-version combination']}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('upstream', type=Path)
    p.add_argument('stock_boot', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    prepare(a.upstream, a.stock_boot, a.output)
