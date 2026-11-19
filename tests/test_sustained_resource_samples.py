import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sustained_resource_samples import sample_resources


class ResourceSamplesTests(unittest.TestCase):
    @patch('sustained_resource_samples.subprocess.run')
    def test_timeout_is_recorded_without_raising_or_retrying(self, run):
        run.side_effect = subprocess.TimeoutExpired(['docker', 'stats'], 15)
        row = sample_resources('owned-container')
        self.assertEqual(row['exit_code'], 124)
        self.assertEqual(row['stats'], [])
        self.assertEqual(row['error'], 'resource-sample-timeout')
        run.assert_called_once()

    @patch('sustained_resource_samples.subprocess.run')
    def test_success_preserves_actual_stats(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '{"Name":"owned-container","CPUPerc":"99%"}\n', '')
        row = sample_resources('owned-container')
        self.assertEqual(row['exit_code'], 0)
        self.assertEqual(row['stats'][0]['Name'], 'owned-container')
        self.assertNotIn('error', row)

    @patch('sustained_resource_samples.subprocess.run')
    def test_failed_or_malformed_sampling_is_not_a_valid_sample(self, run):
        for code, output in [(1, ''), (0, 'invalid-json')]:
            with self.subTest(code=code):
                run.return_value = subprocess.CompletedProcess([], code, output, 'error')
                row = sample_resources('owned-container')
                self.assertNotEqual(row['exit_code'], 0)
                self.assertEqual(row['stats'], [])


if __name__ == '__main__':
    unittest.main()
