import importlib.util
from pathlib import Path
import unittest

class UpstreamBootProbeTests(unittest.TestCase):
    def setUp(self):
        p=Path(__file__).resolve().parents[1]/'tools/run_upstream_boot_probe.py'
        self.assertTrue(p.is_file(),'Upstream release probe required')
        s=importlib.util.spec_from_file_location('upstream_probe',p);self.m=importlib.util.module_from_spec(s);s.loader.exec_module(self.m)
    def test_unknown_release_rejected(self):
        with self.assertRaises(ValueError):self.m.check_release(b'unknown','current')
        with self.assertRaises(ValueError):self.m.check_release(b'unknown','anything')
    def test_stock23_runtime_preserves_observation_only_contract(self):
        from run_original_boot_screen import validate_runtime
        source=self.m.runtime23()
        validate_runtime(source)
        self.assertIn('0x432ca2',source);self.assertIn('0x61902a',source)
        self.assertNotIn('0x5fbe3e',source)
        self.assertIn('3922604',source)
    def test_worker_hit_does_not_mean_authentication(self):
        d=self.m.interpret({'patched-worker':1,'main-reset':0})
        self.assertTrue(d['worker_entered']);self.assertFalse(d['authentication_verified'])
    def test_b0_ton_incompatible_inputs_denied_before_files(self):
        for chip,trim in ((0x23,1),(0x21,0),(0x21,-1)):
            with self.assertRaises(ValueError):self.m.derive('current',Path('/tmp/should-not-exist-b0-ton'),trim,chip_revision=chip,b0_ton=True)
    def test_revision_is_explicit_bounded_and_default_preserving(self):
        board='guard:\n    chipRevision: 35\n    info1Metadata: "zero"\n'
        self.assertEqual(self.m.with_chip_revision(board,0x23),board)
        self.assertEqual(self.m.with_chip_revision(board,0x21),board.replace('35','33'))
        for bad in (0x20,0x25,True,None):
            with self.assertRaises(ValueError):self.m.with_chip_revision(board,bad)
        with self.assertRaises(ValueError):self.m.with_chip_revision(board+board,0x21)

if __name__=='__main__':unittest.main()
