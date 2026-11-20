import os
from pathlib import Path
import subprocess
import sys
import unittest


class CliEncodingTests(unittest.TestCase):
    def test_scenarios_command_works_with_ascii_terminal(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'blackwall'), 'scenarios'],
                                capture_output=True, env={**os.environ, 'PYTHONIOENCODING': 'ascii'})
        self.assertEqual(result.returncode, 0, result.stderr.decode('ascii', errors='replace'))
        self.assertIn(b'normal', result.stdout)


if __name__ == '__main__':
    unittest.main()
