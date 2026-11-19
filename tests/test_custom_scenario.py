import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import blackwall_report as report


class CustomScenarioTest(unittest.TestCase):
    def test_invalid_scenarios_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scenario.json'
            for spec in (
                {'schema': 1, 'name': 'x', 'base': 'normal', 'require_facts': []},
                {'schema': 1, 'name': 'x', 'base': 'unknown', 'require_facts': ['profile_pin']},
                {'schema': 1, 'name': 'x', 'base': 'normal', 'require_facts': ['bad.name']},
            ):
                path.write_text(json.dumps(spec))
                with self.assertRaises(ValueError):
                    report.load_scenario(path)

    def test_missing_fact_fails_report_without_changing_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'capture' / 'exports').mkdir(parents=True)
            (root / 'audit').mkdir()
            audit = {'schema': 2, 'scenario': 'normal', 'passed': True,
                     'boundary_kind': 'bounded-capture', 'observed': {'events': []},
                     'facts': {'profile_pin': True}, 'semantic_validation': {'checks': []}}
            path = root / 'audit' / 'report.json'
            path.write_text(json.dumps(audit))
            custom = {'name': 'Custom', 'base': 'normal', 'require_facts': ['missing_fact']}
            with patch.object(report, 'write_report'):
                model = report.build(root / 'capture', root / 'audit', root / 'report', custom)
            self.assertFalse(model['passed'])
            self.assertEqual(model['checks'], [{'name': 'custom: missing_fact', 'passed': False}])
            self.assertEqual(json.loads(path.read_text()), audit)


if __name__ == '__main__':
    unittest.main()
