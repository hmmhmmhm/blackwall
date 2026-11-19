import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from unicorn import Uc

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import emulate_codec_callers as callers


class CallerInitializationTests(unittest.TestCase):
    def test_nine_byte_initialization_preserves_adjacent_poison(self):
        # Synthetic ARM wrapper compiled from fixtures/codec-init-wrapper.s.
        fixture = bytes.fromhex((Path(__file__).parent / 'fixtures/codec-init-wrapper.hex').read_text())
        entry = callers.PROFILES['stock_current']['state']
        # The literal pool aligns the linked .text start to 0x52af6c.
        raw = bytes(entry - callers.BASE) + b'\x00\xbf' + fixture
        instances = []

        def make_cpu(*args):
            cpu = Uc(*args)
            original_map = cpu.mem_map

            def map_memory(address, size, *args):
                original_map(address, size, *args)
                if address == 0x20000000:
                    cpu.mem_write(address, b'\xa5' * size)

            cpu.mem_map = map_memory
            instances.append(cpu)
            return cpu

        with patch.object(callers, 'Uc', make_cpu):
            report = callers.execute(raw, 'stock_current',
                                     dict(name='nine-byte-guard', entry='state', state=2, force=0))
        self.assertEqual(report['result']['force_argument'], 0)
        self.assertEqual(bytes(instances[0].mem_read(0x20001ffc, 17)),
                         b'\xa5' * 4 + bytes(9) + b'\xa5' * 4)


if __name__ == '__main__':
    unittest.main()
