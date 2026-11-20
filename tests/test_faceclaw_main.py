import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import faceclaw_main


class FaceclawMainTests(unittest.TestCase):
    def test_cli_rejects_unknown_image_before_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / 'unknown.bin'
            image.write_bytes(b'not a reviewed image')
            output = root / 'output'
            cli = Path(__file__).resolve().parents[1] / 'blackwall'
            result = subprocess.run([sys.executable, str(cli), 'faceclaw38', '--main-image', str(image), '--output', str(output)], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b'Faceclaw 38', result.stderr)
            self.assertFalse(output.exists())

    def test_rejects_unreviewed_firmware_and_checks_vectors(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'main.bin'
            image.write_bytes(struct.pack('<II', 0x2007fb00, 0x601a3f) + b'test')
            with self.assertRaisesRegex(ValueError, 'Faceclaw 38'):
                faceclaw_main.validate_main(image)
            with patch.object(faceclaw_main, 'MAIN_SIZE', image.stat().st_size), \
                 patch.object(faceclaw_main, 'MAIN_SHA256', hashlib.sha256(image.read_bytes()).hexdigest()):
                self.assertEqual(faceclaw_main.validate_main(image), image.read_bytes())
                image.write_bytes(struct.pack('<II', 0x2007fb00, 0x601a41) + b'test')
                with patch.object(faceclaw_main, 'MAIN_SHA256', hashlib.sha256(image.read_bytes()).hexdigest()):
                    with self.assertRaisesRegex(ValueError, 'vectors'):
                        faceclaw_main.validate_main(image)

    def test_result_requires_frame_and_no_virtual_faults(self):
        frame = bytes([0, 13]) * (576 * 288 // 2)
        boot = {'frame': True, 'nonzero': len(frame) // 2, 'gpu_rejections': 0, 'gpu_fault': '', 'instructions': 100}
        touch = {'cfsr': 0, 'hfsr': 0, 'memory_violations': 0, 'guards': [{'accesses': 0}]}
        self.assertTrue(faceclaw_main.valid_result(boot, touch, frame))
        self.assertFalse(faceclaw_main.valid_result(dict(boot, gpu_rejections=1), touch, frame))
        self.assertFalse(faceclaw_main.valid_result(boot, dict(touch, cfsr=1), frame))
        self.assertFalse(faceclaw_main.valid_result(boot, touch, frame[:-1]))

    def test_frame_png_is_a_valid_sized_png(self):
        frame = bytes([0, 13]) * (576 * 288 // 2)
        png = faceclaw_main.frame_png(frame)
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', png[16:24]), (576, 288))


if __name__ == '__main__':
    unittest.main()
