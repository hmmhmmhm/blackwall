"""Permissions for the explicitly declared virtual main restoration fixture."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_recovery_m55_writer import validate_write_scope

class FullMainScopeTests(unittest.TestCase):
    def test_default_scope_does_not_expand(self):
        validate_write_scope(0x438010,512,False)
        for dest,length in [(0x438000,16),(0x438010,3700064),(0x410000,16)]:
            with self.assertRaises(ValueError):validate_write_scope(dest,length,False)
    def test_explicit_restore_only_allows_full_body_or_vectors(self):
        validate_write_scope(0x438010,3700064,True)
        validate_write_scope(0x438000,16,True)
        for dest,length in [(0x410000,16),(0x7fe000,16),(0x438010,3700080),(0x438010,512),(0x438000,32)]:
            with self.assertRaises(ValueError):validate_write_scope(dest,length,True)
    def test_types_alignment_empty_are_rejected(self):
        for dest,length,mode in [(True,16,True),(0x438000,True,True),(0x438000,16,1),(0x438010,0,False),(0x438010,17,False),(0x438010,16.0,False)]:
            with self.assertRaises(ValueError):validate_write_scope(dest,length,mode)
if __name__=='__main__':unittest.main()
