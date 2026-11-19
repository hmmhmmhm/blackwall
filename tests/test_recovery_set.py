"""Private-fixture integration tests; firmware and keys remain outside Git."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_recovery_set import check, load


@unittest.skipUnless(os.environ.get('BLACKWALL_RECOVERY_ROOT'), 'Private recovery fixtures required')
class RecoverySetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(os.environ['BLACKWALL_RECOVERY_ROOT'])
        cls.old = load(base / 'private-boot-candidate-01')
        cls.new = load(base / 'private-boot-24-candidate-01')

    def test_verified_pairs_remain_noninstallable(self):
        for pair, version in ((self.old, '2.3.2.14'), (self.new, '2.4.0.24')):
            report = check(*pair)
            self.assertEqual(report['boot_base_version'], version)
            self.assertFalse(report['installable'])
            self.assertFalse(report['hardware_validated'])

    def test_same_size_wrong_version_writer_rejected_both_directions(self):
        for target, other in ((self.old, self.new), (self.new, self.old)):
            files, key = target
            self.assertEqual(len(files['recover.bin']), len(other[0]['recover.bin']))
            with self.assertRaisesRegex(ValueError, 'recover.bin'):
                check({**files, 'recover.bin': other[0]['recover.bin']}, key)

    def test_wrong_private_key_rejected_both_directions(self):
        for target, other in ((self.old, self.new), (self.new, self.old)):
            with self.assertRaisesRegex(ValueError, 'key'):
                check(target[0], other[1])

    def test_every_missing_or_corrupt_file_rejected(self):
        for files, key in (self.old, self.new):
            for name, data in files.items():
                with self.subTest(file=name):
                    missing = dict(files)
                    del missing[name]
                    with self.assertRaises(ValueError):
                        check(missing, key)
                    changed = bytes([data[0] ^ 1]) + data[1:]
                    with self.assertRaises(ValueError):
                        check({**files, name: changed}, key)

    def test_matching_main_version_cannot_select_boot_profile(self):
        files, key = self.new
        with self.assertRaisesRegex(ValueError, 'Unknown boot'):
            check({**files, 'bootloader.bin': b'2.4.0.24'}, key)


if __name__ == '__main__':
    unittest.main()
