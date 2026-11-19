import sys
import unittest
from pathlib import Path
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from simulator_scenarios import load_scenario


class ScenarioTests(unittest.TestCase):
    def test_profile_contains_explicit_assumptions_and_hash(self):
        options, receipt = load_scenario('startup-lp-hypothesis')
        self.assertEqual(options['reset_latch'], 2)
        self.assertEqual(options['power_mode'], 'lp')
        self.assertTrue(options['watchdog_step_clock'])
        self.assertNotIn('watchdog_disabled', options)
        self.assertEqual(len(receipt['catalog_sha256']), 64)

    def test_unknown_scenario_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown simulation scenario'):
            load_scenario('hardware-validated')

    def test_cli_rejects_manual_override_before_image_read(self):
        tool = Path(__file__).resolve().parents[1] / 'tools/firmware_runner.py'
        result = subprocess.run([sys.executable, str(tool), '/missing-image.bin',
                                 '--output', '/tmp/blackwall-scenario-test-unused-output.json',
                                 '--scenario', 'startup-lp-hypothesis', '--power-mode', 'hp'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('cannot be mixed', result.stderr)
