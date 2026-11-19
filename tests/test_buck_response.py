import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from simulator_buck_start import BuckStartStorage


class BuckResponseTests(unittest.TestCase):
    def make(self, mode='active'):
        report={'models': [], 'buck_override_storage': {'complete': True},
                'memldo_setup_storage': {'steps_completed': 0}}
        return BuckStartStorage(report, response_model=mode), report

    def enable(self, model):
        for address, value in model.SEQUENCE:
            self.assertTrue(model.write(address, 4, value))

    def test_response_requires_enable_and_post_enable_setup_then_stays_stable(self):
        model, report=self.make()
        self.assertIsNone(model.sample_status(0x40021108,4))
        self.enable(model)
        self.assertEqual(report['buck_response']['phase'],'requested')
        self.assertIsNone(model.sample_status(0x40021108,4))
        report['memldo_setup_storage']['steps_completed']=2
        for _ in range(4):self.assertEqual(model.sample_status(0x40021108,4),0x30)
        self.assertEqual(report['buck_response']['phase'],'active')
        self.assertEqual(report['buck_response']['reads'],4)
        self.assertEqual(report['buck_response']['transitions'],2)

    def test_fault_profile_never_reports_active(self):
        model, report=self.make('stuck-off');self.enable(model)
        report['memldo_setup_storage']['steps_completed']=2
        for _ in range(4):self.assertEqual(model.sample_status(0x40021108,4),0)
        self.assertEqual(report['buck_response']['phase'],'stuck-off')

    def test_bad_requests_and_partial_reads_do_not_advance_response(self):
        model, report=self.make()
        self.assertFalse(model.write(0x40021100,4,1))
        self.assertEqual(report['buck_response']['phase'],'off')
        self.enable(model);report['memldo_setup_storage']['steps_completed']=2
        self.assertIsNone(model.sample_status(0x40021108,1))
        self.assertIsNone(model.sample_status(0x4002110c,4))
        self.assertEqual(report['buck_response']['phase'],'requested')

    def test_response_and_single_sample_are_mutually_exclusive(self):
        with self.assertRaises(ValueError):BuckStartStorage({'models':[]},status_fixture='lp',response_model='active')
        with self.assertRaises(ValueError):BuckStartStorage({'models':[]},response_model='lp')


if __name__=='__main__':unittest.main()
