import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from simulator_dcache import CoherentDCache


class DCacheTests(unittest.TestCase):
    def make(self):
        report = {'models': []}
        return CoherentDCache(report), report

    def initialize(self, cache, operation=0xf60):
        self.assertTrue(cache.write(0xd84, 4, 0))
        for index in range(2048):
            self.assertTrue(cache.write(operation, 4, ((index % 4) << 30) | ((index // 4) << 5)))

    def test_geometry_requires_selection_and_decodes_to_documented_capacity(self):
        cache, _ = self.make()
        self.assertIsNone(cache.read(0xd80, 4))
        self.assertTrue(cache.write(0xd84, 4, 0))
        value = cache.read(0xd80, 4)
        sets, ways, line = ((value >> 13) & 0x7fff) + 1, ((value >> 3) & 0x3ff) + 1, 1 << ((value & 7) + 4)
        self.assertEqual((sets, ways, line, sets * ways * line), (512, 4, 32, 65536))
        self.assertEqual(value, 0xf03fe019)
        self.assertEqual(cache.read(0xd84, 4), 0)

    def test_enable_requires_every_distinct_set_and_way(self):
        cache, report = self.make()
        self.assertFalse(cache.write(0xd14, 4, 0x10000))
        self.assertTrue(cache.write(0xd84, 4, 0))
        for _ in range(2048):
            self.assertTrue(cache.write(0xf60, 4, 0))
        self.assertFalse(cache.write(0xd14, 4, 0x10000))
        self.initialize(cache)
        self.assertTrue(cache.write(0xd14, 4, 0x10000))
        self.assertEqual(cache.read(0xd14, 4), 0x10000)
        self.assertEqual(report['coherent_dcache']['initialized_lines'], 2048)

    def test_disable_requires_fresh_initialization_before_reenable(self):
        cache, _ = self.make()
        self.initialize(cache)
        self.assertTrue(cache.write(0xd14, 4, 0x10000))
        self.assertTrue(cache.write(0xd14, 4, 0))
        self.assertFalse(cache.write(0xd14, 4, 0x10000))
        self.initialize(cache, 0xf74)
        self.assertTrue(cache.write(0xd14, 4, 0x10000))

    def test_clean_does_not_qualify_as_initialization(self):
        cache, report = self.make()
        self.initialize(cache, 0xf6c)
        self.assertFalse(cache.write(0xd14, 4, 0x10000))
        self.assertEqual(report['coherent_dcache']['clean_set_way'], 2048)
        self.assertEqual(report['coherent_dcache']['initialized_lines'], 0)

    def test_unsupported_selections_reserved_bits_widths_and_commands_reject(self):
        cache, _ = self.make()
        self.assertIsNone(cache.read(0xd84, 4))
        self.assertFalse(cache.write(0xf60, 4, 0))
        for offset, size, value in [(0xd84, 4, 1), (0xd84, 4, 2), (0xd84, 1, 0),
                                    (0xd80, 4, 0), (0xd14, 4, 0x20000)]:
            self.assertFalse(cache.write(offset, size, value))
        self.assertTrue(cache.write(0xd84, 4, 0))
        for offset, size, value in [(0xf60, 4, 1), (0xf60, 4, 1 << 14),
                                    (0xf60, 2, 0), (0xf58, 4, 0), (0xf5c, 4, 0x20000000)]:
            self.assertFalse(cache.write(offset, size, value))
        self.assertIsNone(cache.read(0xf60, 4))
        self.assertIsNone(cache.read(0xd80, 2))


if __name__ == '__main__':
    unittest.main()
