"""Reject reboot inputs that are not the declared writer output."""
import hashlib
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_restored_boot import validate_lineage
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
BASELINE=PRIVATE/'simulator/recovery-m55-writer-12/success/mram.bin'
MAIN=PRIVATE/'simulator/sustained-render-guard-native-01/stock24/main.bin'

@unittest.skipUnless(BASELINE.is_file() and MAIN.is_file(),'Private pinned images required')
class RebootInputTests(unittest.TestCase):
    def fixture(self):
        data=bytearray(BASELINE.read_bytes());data[0x38000:0x38000+3700068]=MAIN.read_bytes()
        report=dict(passed=True,full_main_restore=True,destination=0x438000,final_mram_sha256=hashlib.sha256(data).hexdigest(),checks={'whole_mram_expected':True},rom_programming_modeled=True,hardware_accessed=False)
        return data,report
    def test_complete_main_and_writer_hash_are_required(self):
        data,report=self.fixture();validate_lineage(report,bytes(data),'restored')
        data[0x38020]^=1
        with self.assertRaises(ValueError):validate_lineage(report,bytes(data),'restored')
        report['final_mram_sha256']=hashlib.sha256(data).hexdigest()
        with self.assertRaises(ValueError):validate_lineage(report,bytes(data),'restored')
    def test_failed_writer_or_nonzero_unmodeled_metadata_are_rejected(self):
        data,report=self.fixture();report['passed']=False
        with self.assertRaises(ValueError):validate_lineage(report,bytes(data),'restored')
        report['passed']=True;data[0x3ff000]=1;report['final_mram_sha256']=hashlib.sha256(data).hexdigest()
        with self.assertRaises(ValueError):validate_lineage(report,bytes(data),'restored')
    def test_clear_marker_is_preserved_but_other_nonzero_marker_is_unsupported(self):
        data,report=self.fixture();data[0x3fe000:0x3fe004]=b'\xff'*4
        report['final_mram_sha256']=hashlib.sha256(data).hexdigest();validate_lineage(report,bytes(data),'restored')
        data[0x3fe000:0x3fe004]=b'\x55'*4;report['final_mram_sha256']=hashlib.sha256(data).hexdigest()
        with self.assertRaises(ValueError):validate_lineage(report,bytes(data),'restored')

    def test_incomplete_requires_uncommitted_vectors(self):
        data,report=self.fixture()
        with self.assertRaises(ValueError):validate_lineage(report,bytes(data),'incomplete')
        data[0x38000:0x38010]=bytes(16);report['destination']=0x438010;report['final_mram_sha256']=hashlib.sha256(data).hexdigest()
        validate_lineage(report,bytes(data),'incomplete')

class RebootPathTests(unittest.TestCase):
    def test_early_reject_label_does_not_prove_sp_rejection(self):
        from run_restored_boot import reboot_path_matches
        points={'stock-handoff':0,'main-reset':0}
        events=[{'label':x} for x in ['sp-rejected-target','sp-predicate']]
        self.assertFalse(reboot_path_matches(points,events,'incomplete'))
        events.append({'label':'sp-rejected-target'})
        self.assertTrue(reboot_path_matches(points,events,'incomplete'))
    def test_valid_vector_handoff_order_is_required(self):
        from run_restored_boot import reboot_path_matches
        points={'stock-handoff':1,'main-reset':1}
        events=[{'label':x} for x in ['sp-rejected-target','sp-predicate','sp-accepted','stock-handoff','main-reset']]
        self.assertTrue(reboot_path_matches(points,events,'interrupted-valid-vectors'))
        self.assertFalse(reboot_path_matches(points,events[:-1],'interrupted-valid-vectors'))


@unittest.skipUnless(BASELINE.is_file() and MAIN.is_file() and (PRIVATE/'recovery/boot-2-4-analysis/boot-2.4.0.24.bin').is_file(),'Private pinned images required')
class BootPrefixRebootInputTests(unittest.TestCase):
    fixture=RebootInputTests.fixture
    def test_explicit_stock_prefix_preserves_failed_writer_outcome(self):
        data,report=self.fixture();stock=(PRIVATE/'recovery/boot-2-4-analysis/boot-2.4.0.24.bin').read_bytes()
        data[0x10000:0x10000+149776]=stock+bytes(3)
        report.update(passed=False,full_main_restore=False,boot_restore=True,destination=0x410000,checks={})
        report['final_mram_sha256']=hashlib.sha256(data).hexdigest()
        validate_lineage(report,bytes(data),'restored',boot_state='stock-prefix')
        self.assertFalse(report['passed'])
        with self.assertRaises(ValueError):validate_lineage(report,bytes(data),'restored')
        data[0x11000]^=1;report['final_mram_sha256']=hashlib.sha256(data).hexdigest()
        with self.assertRaises(ValueError):validate_lineage(report,bytes(data),'restored',boot_state='stock-prefix')

if __name__=='__main__':unittest.main()
