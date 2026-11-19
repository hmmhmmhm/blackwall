import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from export_mspi0_frame import matched_payload


class Mspi0FrameExportTests(unittest.TestCase):
    def fixture(self):
        data = bytes(range(256)) * 600 + b'\xa5\x5a'
        frame = dict(source=0x20094400, length=153602, sha256=hashlib.sha256(data).hexdigest(),
                     configuration=0x40161, xip_configuration=0x45ec, pio_mixed=5,
                     instruction_configuration=0x630062)
        return frame, data, bytes(0x94400) + data + bytes(16)

    def test_export_requires_bytes_equal_to_the_consumed_dma_hash(self):
        frame, data, snapshot = self.fixture()
        self.assertEqual(matched_payload(frame, snapshot), data)
        altered = bytearray(snapshot)
        altered[0x94400 + 123] ^= 1
        with self.assertRaisesRegex(ValueError, 'changed'):
            matched_payload(frame, bytes(altered))

    def test_unknown_layout_and_truncated_source_are_rejected(self):
        frame, data, snapshot = self.fixture()
        for key, value in [('length', 153600), ('source', 0x40010000), ('pio_mixed', 0), ('configuration', 0)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                matched_payload(dict(frame, **{key: value}), snapshot)
        with self.assertRaisesRegex(ValueError, 'range'):
            matched_payload(frame, snapshot[:0x94400 + 50])


if __name__ == '__main__':
    unittest.main()
