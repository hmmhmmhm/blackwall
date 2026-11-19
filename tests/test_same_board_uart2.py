import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_same_board_uart2 import finalize_peer_scope,run

class PeerScopeTests(unittest.TestCase):
    def result(self):
        return dict(classification='main-entered',machine_aborted=False,scope={},virtual_peer=dict(accepted=False,held=None))
    def test_watchdog_options_require_explicit_dependencies(self):
        for options in (dict(dwt=True),dict(watchdog_read_holes=True),dict(watchdog_initial='matching-running'),dict(boot_retention=True,dwt=True,watchdog_read_holes=True,watchdog_initial='auto'),dict(allow_checksum_sram=True),dict(synchronous_iom7_off=True),dict(stock_reference=True)):
            with self.assertRaises(ValueError):run('good-cont',Path('/tmp/invalid-blackwall-peer-output'),**options)
    def test_unmapped_engine_access_prevents_success_classification(self):
        d=self.result();finalize_peer_scope(d,'[WARNING] ReadDoubleWord from non existing peripheral at 0xE0001004')
        self.assertEqual(d['classification'],'unsupported-engine')
    def test_abort_without_guard_is_not_unclassified_success(self):
        d=self.result();d.update(classification='stopped-unclassified',machine_aborted=True);finalize_peer_scope(d,'')
        self.assertEqual(d['classification'],'engine-aborted')
    def test_hello_or_claim_without_verified_okay_is_not_wire_authentication(self):
        d=self.result();d['virtual_peer']['held']={'words':[1,0,1,0]};finalize_peer_scope(d,'')
        self.assertFalse(d['scope']['authentication_verified'])
        d['virtual_peer']['accepted']=True;finalize_peer_scope(d,'');self.assertTrue(d['scope']['authentication_verified'])
        d['virtual_peer']['held']['words']=[0,0,1,0];finalize_peer_scope(d,'');self.assertFalse(d['scope']['authentication_verified'])

if __name__=='__main__':unittest.main()
