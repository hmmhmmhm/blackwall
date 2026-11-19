import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from nema_pixel_reference import render_white_a4_reference


def word_float(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def commands(stride=64):
    pairs = [(0, 0x2100a000), (4, (9 << 24) | stride), (8, (32 << 16) | 64),
             (0x110, 0), (0x114, (32 << 16) | 64), (0x1d0, 0x504), (0x118, 0),
             (0x11c, 0x141f801f), (0x1c, 0xffffffff), (0x10, 0x615bf0),
             (0x14, (0x34 << 24) | 3), (0x18, (4 << 16) | 6),
             (0x174, word_float(-16)), (0x168, word_float(-10)),
             (0x160, word_float(1)), (0x164, 0), (0x16c, 0), (0x170, word_float(1)),
             (0x104, (16 << 16) | 10), (0x108, (20 << 16) | 14), (0xff000100, 2)]
    return [value for pair in pairs for value in pair]


def change(words, register, value):
    result = list(words)
    result[result[::2].index(register) * 2 + 1] = value
    return result


class PixelReferenceTests(unittest.TestCase):
    def setUp(self):
        self.reads = []
        self.packed = bytes.fromhex('0123ab4567ab89ababcd ef ab'.replace(' ', ''))

    def read(self, address, size):
        self.reads.append((address, size))
        self.assertEqual((address, size), (0x615bf0, 12))
        return self.packed

    def test_all_alpha_levels_and_unused_row_padding(self):
        frame, info = render_white_a4_reference(commands(), bytes(64 * 32), self.read)
        actual = bytes(frame[y * 64 + x] for y in range(16, 20) for x in range(10, 14))
        self.assertEqual(actual, bytes(n * 17 for n in range(16)))
        self.assertEqual(sum(bool(p) for p in frame), 15)
        self.assertFalse(info['hardware_validated'])
        self.assertEqual(info['draw'], [10, 16, 14, 20])

    def test_clip_uses_source_coordinates_before_clipping(self):
        words = change(commands(), 0x110, (17 << 16) | 11)
        words = change(words, 0x114, (19 << 16) | 13)
        frame, _ = render_white_a4_reference(words, bytes(2048), self.read)
        self.assertEqual([frame[y * 64 + x] for y in (17, 18) for x in (11, 12)],
                         [85, 102, 153, 170])
        self.assertEqual(sum(bool(p) for p in frame), 4)

    def test_padded_output_stride(self):
        frame, _ = render_white_a4_reference(commands(80), bytes(80 * 32), self.read)
        self.assertEqual(frame[19 * 80 + 13], 255)
        self.assertTrue(all(frame[y * 80 + 64:y * 80 + 80] == bytes(16) for y in range(32)))

    def test_unsupported_modes_fail_before_memory_read(self):
        for reg, value in [(0x1d0, 0x501), (0x11c, 0x141e8000), (0x1c, 0x80ffffff),
                           (0x14, (8 << 24) | 3), (0x164, word_float(1)),
                           (0xff000100, 3), (4, (9 << 24) | 65), (0x114, (33 << 16) | 64)]:
            with self.subTest(register=reg):
                with self.assertRaises(ValueError):
                    render_white_a4_reference(change(commands(), reg, value), bytes(2048), self.read)
                self.assertEqual(self.reads, [])

    def test_nonzero_destination_is_not_silently_overwritten(self):
        with self.assertRaises(ValueError):
            render_white_a4_reference(commands(), b'\1' + bytes(2047), self.read)
        self.assertEqual(self.reads, [])

    def test_unknown_or_truncated_stream_is_rejected(self):
        for words in (commands()[:-1], commands() + [0, 0], [0x99] + commands()[1:]):
            with self.assertRaises(ValueError):
                render_white_a4_reference(words, bytes(2048), self.read)
        self.assertEqual(self.reads, [])

    def test_short_source_is_rejected(self):
        with self.assertRaises(ValueError):
            render_white_a4_reference(commands(), bytes(2048), lambda address, size: bytes(size - 1))


if __name__ == '__main__':
    unittest.main()
