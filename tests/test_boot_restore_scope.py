"""Explicit offline boot-write scopes must not expand existing default/main rights."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_recovery_m55_writer import validate_write_scope

class BootRestoreScopeTests(unittest.TestCase):
    def test_boot_scope_requires_its_explicit_option(self):
        for dest,length in ((0x410000,149776),(0x434910,9968),(0x410000,159744)):
            validate_write_scope(dest,length,False,boot_restore=True)
            with self.assertRaises(ValueError):validate_write_scope(dest,length,False)
            with self.assertRaises(ValueError):validate_write_scope(dest,length,True)
    def test_no_option_mixing_or_arbitrary_ranges(self):
        for dest,length in ((0x438000,16),(0x438010,512),(0x7fe000,16),(0x410000,159760),(0x434910,9984),(0x410000,0)):
            with self.assertRaises(ValueError):validate_write_scope(dest,length,False,boot_restore=True)
        with self.assertRaises(ValueError):validate_write_scope(0x410000,159744,True,boot_restore=True)
        with self.assertRaises(ValueError):validate_write_scope(0x410000,159744,False,boot_restore=1)
if __name__=='__main__':unittest.main()
