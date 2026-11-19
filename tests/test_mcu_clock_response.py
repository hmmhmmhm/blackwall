import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from simulator_mcu_clock import McuClockResponse


class ClockResponseTests(unittest.TestCase):
    def make(self,profile='nominal',mode='lp'):
        report={'models':[],'buck_response':{'phase':'active'}}
        misc={'value':0xfbbfc0}
        return McuClockResponse(report,mode,profile,misc),report,misc

    def test_request_ready_ack_status_and_force_release(self):
        model,report,misc=self.make()
        self.assertEqual(model.read_clock(4),0)
        self.assertEqual(model.read_mode(4),13)
        self.assertTrue(model.write_misc(4,0xfbbfe0))
        self.assertEqual(model.read_clock(4),0x81000000)
        self.assertTrue(model.write_mode(4,14))
        self.assertEqual(model.read_mode(4),22)
        self.assertTrue(model.write_misc(4,0xfbbfc0))
        self.assertEqual(model.read_clock(4),0x81000000)
        self.assertEqual(report['mcu_clock_response']['phase'],'acked')

    def test_unready_and_no_ack_profiles_keep_distinct_failure_states(self):
        model,report,_=self.make('hfrc2-unready')
        self.assertTrue(model.write_misc(4,0xfbbfe0))
        self.assertEqual(model.read_clock(4),0x80000000)
        self.assertFalse(model.write_mode(4,14))
        model,report,_=self.make('no-ack')
        self.assertTrue(model.write_misc(4,0xfbbfe0))
        self.assertTrue(model.write_mode(4,14))
        for _ in range(25):self.assertEqual(model.read_mode(4),10)
        self.assertEqual(report['mcu_clock_response']['phase'],'pending')
        self.assertTrue(model.write_misc(4,0xfbbfc0))
        self.assertEqual(model.read_clock(4),0)

    def test_denied_mode_has_ack_but_preserves_old_status(self):
        model,report,_=self.make('denied')
        self.assertTrue(model.write_misc(4,0xfbbfe0))
        self.assertTrue(model.write_mode(4,14))
        self.assertEqual(model.read_mode(4),14)
        self.assertEqual(report['mcu_clock_response']['phase'],'denied')

    def test_high_performance_initial_state_and_idempotent_request(self):
        model,report,_=self.make(mode='hp')
        self.assertEqual(model.read_mode(4),22)
        self.assertEqual(model.read_clock(4),0x81000000)
        self.assertTrue(model.write_mode(4,22))
        self.assertTrue(model.write_mode(4,22))
        self.assertEqual(report['mcu_clock_response']['transitions'],0)

    def test_width_request_readonly_bits_and_prerequisites_are_checked(self):
        model,report,_=self.make()
        self.assertFalse(model.write_mode(4,14))
        report['buck_response']['phase']='requested'
        self.assertFalse(model.write_misc(4,0xfbbfe0))
        report['buck_response']['phase']='active'
        self.assertFalse(model.write_misc(4,0xfbbfe1))
        self.assertFalse(model.write_misc(1,0x20))
        self.assertTrue(model.write_misc(4,0xfbbfe0))
        for value in (2,30,15,13):self.assertFalse(model.write_mode(4,value))
        self.assertIsNone(model.read_clock(1))
        self.assertIsNone(model.read_mode(2))


if __name__=='__main__':unittest.main()
