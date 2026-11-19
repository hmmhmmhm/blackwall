from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_package import prepare, validate_tool_manifest
from blackwall_package import sha256
class PackageOutput(unittest.TestCase):
    def test_recovery_metadata_cannot_pair_wrong_binary_or_entry(self):
        data = b'\x01\x02'
        meta = {'bytes': 2, 'sha256': sha256(data), 'base': 0, 'functions': {'entry': {'offset': 0}}}
        validate_tool_manifest('recover.bin', data, meta)
        for bad in [{**meta, 'sha256': '0'*64}, {**meta, 'base': 4}, {**meta, 'functions': {'entry': {'offset': 2}}}]:
            with self.assertRaises(ValueError):
                validate_tool_manifest('recover.bin', data, bad)
    def test_repository_output_is_rejected_before_inputs(self):
        with self.assertRaisesRegex(ValueError,'repository'):
            prepare({},Path(__file__).resolve().parents[1]/'local/package')
    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'exist'):
                prepare({},Path(directory))
    def test_symlink_to_repository_cannot_bypass_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            link=Path(directory)/'link';link.symlink_to(Path(__file__).resolve().parents[1])
            with self.assertRaisesRegex(ValueError,'repository'):
                prepare({},link/'local/package')
