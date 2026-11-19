import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from simulator_trim_fixture import TrimResetFixture
from simulator_coreldo import CoreLdoReduction


class CoreLdoTests(unittest.TestCase):
    def setup_policy(self,stage=2,cache=True):
        report={'models':[],'buck_start_storage':{'steps_completed':stage}}
        fixture=TrimResetFixture(report)
        if cache:
            for address in fixture.registers:fixture.read(address,4)
        return CoreLdoReduction(report,fixture),fixture,report

    def test_expected_field_reduction_keeps_other_bits(self):
        policy,fixture,report=self.setup_policy()
        self.assertTrue(policy.write(0x40020080,4,0x6d3cd))
        self.assertEqual(fixture.read(0x40020080,4),0x6d3cd)
        self.assertTrue(report['coreldo_reduction_storage']['applied'])

    def test_cache_and_exact_stage_are_required(self):
        for stage,cache in ((0,True),(1,True),(3,True),(2,False)):
            policy,fixture,_=self.setup_policy(stage,cache)
            self.assertFalse(policy.write(0x40020080,4,0x6d3cd))
            self.assertEqual(fixture.read(0x40020080,4),0x6d3d4)

    def test_wrong_fields_width_and_repeat_are_rejected(self):
        for address,size,value in ((0x40020080,4,0x6d3cc),(0x40020080,4,0x6c3cd),
                                   (0x40020080,2,0x6d3cd),(0x40020088,4,0x6d3cd)):
            policy,fixture,_=self.setup_policy()
            self.assertFalse(policy.write(address,size,value))
            self.assertEqual(fixture.read(0x40020080,4),0x6d3d4)
        policy,fixture,_=self.setup_policy()
        self.assertTrue(policy.write(0x40020080,4,0x6d3cd))
        self.assertFalse(policy.write(0x40020080,4,0x6d3cd))
        self.assertEqual(fixture.registers[0x40020080]['writes'],1)
