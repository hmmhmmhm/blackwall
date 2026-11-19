import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from simulator_buck_start import BuckStartStorage


class BuckStatusTests(unittest.TestCase):
    def setup_fixture(self,name='off',stage=3,memory=2):
        report={'models':[],'memldo_setup_storage':{'steps_completed':memory}}
        model=BuckStartStorage(report,status_fixture=name)
        model.state.update(steps_completed=stage,enable_requested=stage==3)
        return model,report

    def test_only_explicit_documented_statuses_can_be_sampled_once(self):
        for name,word in [('off',0),('lp',0x20),('active',0x30)]:
            model,report=self.setup_fixture(name)
            self.assertEqual(model.sample_status(0x40021108,4),word)
            self.assertIsNone(model.sample_status(0x40021108,4))
            self.assertTrue(model.blocks_readiness(0x40021108))
            self.assertEqual(report['buck_status_fixture']['reads'],1)

    def test_missing_model_phase_or_memory_setup_provides_no_status(self):
        for name,stage,memory in [(None,3,2),('off',2,2),('off',3,1)]:
            model,_=self.setup_fixture(name,stage,memory)
            self.assertIsNone(model.sample_status(0x40021108,4))

    def test_partial_and_wrong_address_do_not_consume_sample(self):
        model,_=self.setup_fixture('active')
        for address,width in [(0x40021108,1),(0x40021108,2),(0x40021100,4)]:
            self.assertIsNone(model.sample_status(address,width))
        self.assertEqual(model.sample_status(0x40021108,4),0x30)

    def test_reserved_or_unknown_status_is_rejected(self):
        for value in ['reserved','1',1,'ACT']:
            with self.assertRaises(ValueError):self.setup_fixture(value)
