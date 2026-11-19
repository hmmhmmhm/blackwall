import sys
import unittest
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from simulator_watchdog import StepWatchdog


class WatchdogTests(unittest.TestCase):
    def model(self):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        report = {'models': [], 'reason': None}
        return StepWatchdog(cpu, report, 1), report

    def test_reset_threshold_and_feed(self):
        w, report = self.model()
        w.write(w.cpu, 0, 4, 0x02000205, None)
        w.advance(127)
        self.assertIsNone(report['reason'])
        w.write(w.cpu, 4, 4, 0xb2, None)
        w.advance(127)
        self.assertIsNone(report['reason'])
        w.advance(1)
        self.assertEqual(report['reason'], 'watchdog-reset-threshold-due')

    def test_disabled_clock_does_not_expire(self):
        w, report = self.model()
        w.advance(100000)
        self.assertIsNone(report['reason'])
        self.assertEqual(w.state['counter_ticks'], 0)

    def test_irq_and_invalid_restart(self):
        w, report = self.model()
        w.write(w.cpu, 0, 4, 0x02010003, None)
        w.advance(64)
        self.assertEqual(report['reason'], 'watchdog-interrupt-due')
        w, report = self.model()
        w.write(w.cpu, 4, 4, 0xb3, None)
        self.assertEqual(report['reason'], 'unsupported-step-watchdog-write')

    def test_other_active_clock_and_reconfiguration_stop(self):
        w, report = self.model()
        w.write(w.cpu, 0, 4, 0x01000001, None)
        self.assertEqual(report['reason'], 'unsupported-step-watchdog-write')
        w, report = self.model()
        w.write(w.cpu, 0, 4, 0x02000205, None)
        w.write(w.cpu, 0, 4, 0x02000305, None)
        self.assertEqual(report['reason'], 'active-watchdog-reconfiguration-unmodeled')
