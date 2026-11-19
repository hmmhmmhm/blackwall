import json
from pathlib import Path
import platform
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import setup_simulator


class SimulatorSetupSafety(unittest.TestCase):
    @unittest.skipUnless(platform.system() == 'Darwin' and platform.machine() == 'arm64' and sys.version_info[:2] == (3, 14), 'Pinned wheel set targets supported host')
    def test_missing_wheel_is_named_before_environment_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'venv'
            with self.assertRaisesRegex(ValueError,'Missing pinned wheel:'):
                setup_simulator.setup(root,output)
            self.assertFalse(output.exists())
    def test_repository_output_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside the repository'):
            setup_simulator.setup(Path('/missing-wheels'), setup_simulator.ROOT/'local/new-venv')

    def test_existing_environment_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            marker = output/'preserved.txt'
            marker.write_text('existing environment')
            with self.assertRaisesRegex(ValueError, 'Output exists'):
                setup_simulator.setup(Path('/missing-wheels'), output)
            self.assertEqual(marker.read_text(), 'existing environment')
            self.assertEqual(list(output.iterdir()), [marker])

    @unittest.skipUnless(platform.system() == 'Darwin' and platform.machine() == 'arm64' and sys.version_info[:2] == (3, 14), 'Pinned wheel set targets macOS arm64 Python 3.14')
    def test_changed_wheel_is_rejected_before_creating_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = json.loads(setup_simulator.LOCK.read_text())['packages'][0]['wheel']
            (root/wheel).write_bytes(b'corrupt wheel')
            output = root/'new-venv'
            with self.assertRaisesRegex(ValueError, 'Wheel SHA256 mismatch'):
                setup_simulator.setup(root, output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
