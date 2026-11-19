import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from simulator_memldo import MemLdoSetup
from simulator_trim_fixture import TrimResetFixture


class MemLdoSetupTests(unittest.TestCase):
    def setup_policy(self, stage=3, core_applied=True):
        report = {'models': [], 'buck_start_storage': {'steps_completed': stage},
                  'coreldo_reduction_storage': {'applied': core_applied}}
        fixture = TrimResetFixture(report)
        return MemLdoSetup(report, fixture), fixture, report

    def test_ordered_fields_share_readback_and_preserve_other_bits(self):
        policy, fixture, report = self.setup_policy()
        self.assertTrue(policy.write(0x40020088, 4, 0x207c0741))
        self.assertEqual(fixture.read(0x40020088, 4), 0x207c0741)
        self.assertTrue(policy.write(0x400201b0, 4, 0x10000))
        self.assertEqual(fixture.read(0x400201b0, 4), 0x10000)
        self.assertEqual(report['memldo_setup_storage']['steps_completed'], 2)
        self.assertEqual(fixture.registers[0x40020088]['writes'], 1)
        self.assertEqual(fixture.registers[0x400201b0]['writes'], 1)

    def test_wrong_phase_or_missing_core_reduction_rejects_write(self):
        for stage, applied in ((0, True), (2, True), (3, False), (4, True)):
            policy, fixture, _ = self.setup_policy(stage, applied)
            self.assertFalse(policy.write(0x40020088, 4, 0x207c0741))
            self.assertEqual(fixture.read(0x40020088, 4), 0x207c0774)

    def test_order_wrong_values_widths_and_repeats_are_rejected(self):
        for address, width, value in ((0x400201b0, 4, 0x10000), (0x40020088, 2, 0x741),
                                      (0x40020088, 4, 0x207c0742), (0x40020088, 4, 0x207c07c1)):
            policy, fixture, _ = self.setup_policy()
            self.assertFalse(policy.write(address, width, value))
            self.assertEqual(fixture.registers[0x40020088]['writes'], 0)
        policy, fixture, _ = self.setup_policy()
        self.assertTrue(policy.write(0x40020088, 4, 0x207c0741))
        self.assertFalse(policy.write(0x40020088, 4, 0x207c0741))
        self.assertFalse(policy.write(0x400201b0, 4, 0x18000))
        self.assertTrue(policy.write(0x400201b0, 4, 0x10000))
        self.assertFalse(policy.write(0x400201b0, 4, 0x10000))
