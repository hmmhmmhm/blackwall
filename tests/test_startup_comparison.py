import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from compare_dcache_startup import normalized


class StartupComparisonTests(unittest.TestCase):
    def test_absent_and_null_optional_native_models_are_equivalent(self):
        data = {'unmodeled_engine_messages': [], 'observed': {
            'guards': [{'accesses': 1, 'address': 0x40021108, 'width': 4, 'operation': 'read', 'value': 0}],
            'pc': 0x438008, 'memory_policy': {'violations': 0}, 'system_control': {'violations': 0},
            'coherent_dcache': dict(enabled=True, geometry_reads=2, selector_reads=0, selector_writes=2,
                initialized_lines=2048, invalidate_set_way=2048, clean_set_way=2048,
                clean_invalidate_set_way=0, ccsidr=0xf03fe019)}}
        expected = normalized(data, True)
        nullable = copy.deepcopy(data)
        nullable['observed'].update(mcu_clock_response=None, gfx_power_storage=None, gpu_power_preparation=None, gpu_power_response=None,
                                    buck_response=None, vddf_tempco_storage=None)
        self.assertEqual(normalized(nullable, True), expected)


if __name__ == '__main__':
    unittest.main()
