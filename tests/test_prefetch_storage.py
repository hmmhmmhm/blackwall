import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from simulator_prefetch import PrefetchStorage


class PrefetchTests(unittest.TestCase):
    def make(self):
        report={'models':[]}
        return PrefetchStorage(report),report

    def test_all_defined_field_words_roundtrip_after_write(self):
        model,report=self.make()
        self.assertIsNone(model.read(0xe001e004,4))
        for word in range(1024):
            self.assertTrue(model.write(0xe001e004,4,word))
            self.assertEqual(model.read(0xe001e004,4),word)
        self.assertEqual(report['prefetch_storage']['writes'],1024)
        self.assertEqual(report['prefetch_storage']['reads'],1024)

    def test_hal_default_is_decoded_without_claiming_physical_effects(self):
        model,report=self.make()
        self.assertTrue(model.write(0xe001e004,4,0x369))
        self.assertEqual(report['prefetch_storage']['fields'],dict(enable=True,max_outstanding=6,max_lookahead=6,min_lookahead=4))
        self.assertFalse(report['prefetch_storage']['hardware_verified'])

    def test_other_bits_widths_addresses_and_prewrite_reads_are_rejected(self):
        model,report=self.make()
        self.assertIsNone(model.read(0xe001e004,4))
        for address,size,value in [(0xe001e004,4,0x400),(0xe001e004,2,0x369),(0xe001e000,4,0x369)]:
            self.assertFalse(model.write(address,size,value))
        self.assertTrue(model.write(0xe001e004,4,0x369))
        self.assertIsNone(model.read(0xe001e004,2))
        self.assertIsNone(model.read(0xe001e000,4))
        self.assertEqual(model.read(0xe001e004,4),0x369)
