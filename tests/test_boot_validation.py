import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class BootValidationTests(unittest.TestCase):
    def setUp(self):
        path=ROOT/'tools/run_boot_validation.py'
        self.assertTrue(path.is_file(), 'Boot-specific scenario runner is required')
        spec=importlib.util.spec_from_file_location('boot_validation',path)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def test_classification_does_not_call_guard_vendor_rejection(self):
        self.assertEqual(self.m.classify({'guards':[{'accesses':1}],'policy':0,'cfsr':0,'hfsr':0,'handoff':0,'main':0,'limit':False}), 'unsupported-model')

    def test_cpu_fault_and_timeout_are_not_success(self):
        base=dict(guards=[],policy=0,cfsr=0,hfsr=0,handoff=0,main=0,limit=False)
        self.assertEqual(self.m.classify(dict(base,cfsr=1)),'cpu-fault')
        self.assertEqual(self.m.classify(dict(base,limit=True)),'timeout')
        self.assertEqual(self.m.classify(dict(base,handoff=1)),'handoff-only')
        self.assertEqual(self.m.classify(dict(base,handoff=1,main=1)),'main-entered')

    def test_main_entry_never_means_recovery_worker_ran(self):
        d=self.m.recovery_facts({'points':[{'label':'main-reset','hits':1},{'label':'patched-manager','hits':1},{'label':'patched-worker','hits':0}]})
        self.assertTrue(d['patched_manager_entered']);self.assertFalse(d['worker_entered'])
        self.assertFalse(d['recovery_verified'])

    def test_observer_failure_cannot_be_boot_success(self):
        d=dict(guards=[],policy=0,cfsr=0,hfsr=0,handoff=1,main=1,limit=False,events_dropped=1)
        self.assertEqual(self.m.classify(d),'observation-incomplete')

    def test_missing_rom_fetch_is_not_a_guest_fault_or_success(self):
        d=dict(guards=[],policy=0,cfsr=0,hfsr=0,handoff=0,main=0,limit=False,pc=0x0200ff20,unsupported_rom_fetch=True)
        self.assertEqual(self.m.classify(d),'unsupported-rom')

    def test_out_of_range_sp_can_preserve_original_predicate_bit(self):
        import struct
        data=self.m.mutate_main(bytes(16),'sp-bit29-outside')
        self.assertEqual(struct.unpack_from('<I',data)[0],0xa007fb00)
        self.assertEqual(data[4:],bytes(12))

    def test_all_mutations_are_explicit_and_bounded(self):
        self.assertEqual(self.m.mutate_main(bytes(16),'pending-marker'),bytes(16))
        with self.assertRaises(ValueError):self.m.mutate_main(bytes(16),'arbitrary')
        self.assertEqual(self.m.mutate_main(bytes(16),'invalid-sp')[4:],bytes(12))
        self.assertEqual(self.m.mutate_main(bytes(16),'invalid-reset')[:4],bytes(4))

    def test_generated_runtime_cannot_force_execution(self):
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from run_original_boot_screen import validate_runtime
        validate_runtime(self.m.runtime(149773))
        self.assertNotIn('SetRegister',self.m.runtime(159744))

    def test_original_retention_binding_preserved(self):
        self.assertIn("Mspi1Config.AttachRetentionPower",self.m.runtime(149773))

    def test_rom_contract_capture_is_read_only_and_opt_in(self):
        from run_original_boot_screen import validate_runtime
        captured=self.m.runtime(149773,capture_rom_request=True)
        validate_runtime(captured)
        self.assertIn('rom-request.json',captured)
        self.assertNotIn('rom-request.json',self.m.runtime(149773))
        self.assertNotIn('SetRegister',captured)

    def test_unknown_asset_and_scenario_rejected(self):
        with self.assertRaises(ValueError):self.m.require_case('arbitrary')
        with self.assertRaises(ValueError):self.m.check_image(b'unknown','boot')

if __name__=='__main__':unittest.main()
