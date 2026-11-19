import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from font_wrapper_contract import discover_wrappers, direct_call_candidates, static_contract

SIM = Path.home() / 'Library/Application Support/Blackwall/simulator'

@unittest.skipUnless((SIM / 'builtin-font-memory-main-01/stock24/main.bin').is_file(), 'Pinned private main required')
class FontWrapperDiscoveryTests(unittest.TestCase):
    def test_original_three_have_unique_wrapper_and_renderer_entries(self):
        for case, expected in [('stock24', 0x508b58), ('stock23', 0x4ea368), ('cfw', 0x4ea368)]:
            raw = (SIM / 'builtin-font-memory-main-01' / case / 'main.bin').read_bytes()
            entries = discover_wrappers(raw)
            self.assertEqual(entries['descriptor'], expected)
            callers = direct_call_candidates(raw, entries['descriptor'])
            self.assertEqual(len(callers), 3)
            self.assertTrue(any(entries['letter'] <= pc < entries['letter'] + 0x200 for pc in callers))
            mapping = static_contract(raw, entries)
            self.assertEqual(len(mapping['ambiq_backend']['bitmap_call_candidates']), 3)
            self.assertLess(int(mapping['ambiq_backend']['registration']['iterator'], 0), entries['letter'])

    def test_absent_or_ambiguous_signatures_are_rejected(self):
        with self.assertRaises(ValueError):
            discover_wrappers(bytes(4096))
        raw = (SIM / 'builtin-font-memory-main-01/stock24/main.bin').read_bytes()
        with self.assertRaises(ValueError):
            discover_wrappers(raw + raw)

if __name__ == '__main__':
    unittest.main()
