"""Operation-specific offline compatibility never implies installation permission."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from check_bootloader_compatibility import check

class CompatibilityTests(unittest.TestCase):
    def test_unknown_bytes_never_select_a_profile(self):
        with self.assertRaisesRegex(ValueError,'Unknown'):check(b'2.4.0.24',b'2.4.0.24','boot-main-screen')
    def test_wrong_model_context_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'virtual model'):check(b'x',b'y','boot-main-screen',model='physical')
    def test_physical_and_arbitrary_operations_are_rejected(self):
        for operation in ('flash','install','uart2-auth',None):
            with self.assertRaises(ValueError):check(b'x',b'y',operation)
if __name__=='__main__':unittest.main()
