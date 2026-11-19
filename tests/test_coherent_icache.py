import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from simulator_icache import CoherentICache


class ICacheTests(unittest.TestCase):
    def make(self):
        report={'models':[]}
        return CoherentICache(report),report

    def test_enable_requires_invalidation_and_supports_disable(self):
        cache,report=self.make()
        self.assertFalse(cache.write(0xd14,4,0x20000))
        self.assertTrue(cache.write(0xf50,4,0))
        self.assertTrue(cache.write(0xd14,4,0x20000))
        self.assertEqual(cache.read(0xd14,4),0x20000)
        self.assertTrue(cache.write(0xd14,4,0))
        self.assertEqual(cache.read(0xd14,4),0)
        self.assertEqual(report['coherent_icache']['invalidations'],1)

    def test_repeated_invalidation_with_enabled_cache_preserves_control(self):
        cache,report=self.make()
        self.assertTrue(cache.write(0xf50,4,0))
        self.assertTrue(cache.write(0xd14,4,0x20000))
        self.assertTrue(cache.write(0xf50,4,0))
        self.assertEqual(cache.read(0xd14,4),0x20000)
        self.assertEqual(report['coherent_icache']['invalidations'],2)

    def test_other_fields_values_and_partial_operations_are_rejected(self):
        cache,_=self.make()
        self.assertTrue(cache.write(0xf50,4,0))
        for offset,size,value in [(0xf50,4,1),(0xf50,1,0),(0xd14,1,0),(0xd14,4,0x10000),(0xd14,4,0x20001),(0xf58,4,0)]:
            self.assertFalse(cache.write(offset,size,value))
        self.assertIsNone(cache.read(0xf50,4))
        self.assertIsNone(cache.read(0xd14,2))
