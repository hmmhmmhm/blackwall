"""The public ring command validates user choices before touching simulator assets."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / 'tools/run_ring_input_m55.py'

class RingInputCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], capture_output=True,
                              text=True, timeout=15)

    def test_help_without_assets(self):
        result = self.run_cli('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--firmware-manifest', result.stdout)
        self.assertIn('--audit-existing', result.stdout)

    def test_candidate_requires_baseline_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_cli(folder, folder+'/run', '--case', 'stock24',
                                  '--firmware-manifest', folder+'/candidate.json')
            self.assertEqual(result.returncode, 2)
            self.assertIn('Candidate selection requires', result.stderr)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_audit_requires_separate_output(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_cli(folder, folder+'/run', '--case', 'stock24', '--audit-existing')
            self.assertEqual(result.returncode, 2)
            self.assertIn('--audit-output', result.stderr)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_audit_does_not_select_new_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_cli(folder, folder+'/run', '--case', 'stock24', '--audit-existing',
                                  '--audit-output', folder+'/audit',
                                  '--firmware-manifest', folder+'/candidate.json',
                                  '--firmware-baseline', folder+'/base')
            self.assertEqual(result.returncode, 2)
            self.assertIn('Saved audit uses', result.stderr)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_help_does_not_import_arm_packages(self):
        code = """import importlib.abc,runpy,sys
class BlockArm(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in ('unicorn','capstone'):raise RuntimeError('arm-import-during-help')
sys.meta_path.insert(0,BlockArm());sys.path.insert(0,sys.argv[1])
script=sys.argv[2];sys.argv=[script,'--help'];runpy.run_path(script,run_name='__main__')
"""
        result = subprocess.run([sys.executable, '-c', code, str(CLI.parent), str(CLI)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_audit_cannot_write_inside_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_cli(folder, folder+'/capture', '--case', 'stock24',
                                  '--audit-existing', '--audit-output', folder+'/capture/audit')
            self.assertEqual(result.returncode, 2)
            self.assertIn('outside the capture', result.stderr)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_existing_capture_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            capture = Path(folder)/'capture';capture.mkdir();(capture/'keep').write_text('original')
            result = self.run_cli(folder, str(capture), '--case', 'stock24')
            self.assertEqual(result.returncode, 2)
            self.assertIn('new directory', result.stderr)
            self.assertEqual((capture/'keep').read_text(), 'original')

    def test_git_root_is_not_a_private_asset_root(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'.git').mkdir()
            result = self.run_cli(folder, folder+'/capture', '--case', 'stock24')
            self.assertEqual(result.returncode, 2)
            self.assertIn('private simulator root', result.stderr)
            self.assertFalse((Path(folder)/'capture').exists())

class RingObserverAbiTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(CLI.parent))
        from ring_input_scenario import validate_anchors
        self.validate = validate_anchors
        self.profile = {'anchors': [{'address': 0x438008,
            'sha256': '374708fff7719dd5979ec875d56cd2286f6d3cf7ec317a3b25632aab28ec37bb'}]}

    def test_changed_observer_code_is_rejected(self):
        self.validate(bytes(32), self.profile)
        changed = bytearray(32);changed[16] = 1
        with self.assertRaisesRegex(ValueError, 'Unsupported ring observer ABI'):
            self.validate(bytes(changed), self.profile)

    def test_observer_outside_main_is_rejected(self):
        for address in [0x437ffe, 0x438020]:
            profile = {'anchors': [dict(self.profile['anchors'][0], address=address)]}
            with self.assertRaisesRegex(ValueError, 'Unsupported ring observer ABI'):
                self.validate(bytes(32), profile)

if __name__ == '__main__':
    unittest.main()
