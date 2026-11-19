"""Offline main-function probe configurations reject accidental wider operations."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_stock_main_mram_probe import validate_case, validate_delay_bytes

class ProbeConfigTests(unittest.TestCase):
    def test_reviewed_entries_and_faults(self):
        for entry in ('adapter','buffer','callback'):
            for fault in ('success','rom-error','readback-corrupt','rom-unready','misaligned'):
                validate_case(entry,fault)
    def test_unknown_variants_rejected(self):
        for entry,fault in [('other','success'),('adapter','erase'),(None,'success'),('adapter',True)]:
            with self.assertRaises(ValueError):validate_case(entry,fault)
    def test_original_delay_bytes_are_required(self):
        self.assertEqual(validate_delay_bytes(bytes.fromhex('0138fdd17047')+bytes(26),bytes.fromhex('0138fdd17047')),bytes.fromhex('0138fdd17047'))
        for observed,literal in [(bytes(32),bytes(6)),(bytes.fromhex('0138fdd17047'),bytes(6)),(bytes(5),bytes(6))]:
            with self.assertRaises(ValueError):validate_delay_bytes(observed,literal)
    def test_ota_verifier_is_an_explicit_callback_diagnostic(self):
        validate_case('callback','success','ota')
        for entry,verification in [('adapter','ota'),('callback','skip')]:
            with self.assertRaises(ValueError):validate_case(entry,'success',verification)
    def test_full_boot_scope_cannot_be_selected_by_other_entries(self):
        validate_case('callback','success','ota',boot_restore=True)
        for entry,fault,verify in [('buffer','success','ota'),('callback','misaligned','ota'),('callback','success','memcmp')]:
            with self.assertRaises(ValueError):validate_case(entry,fault,verify,boot_restore=True)
if __name__=='__main__':unittest.main()
