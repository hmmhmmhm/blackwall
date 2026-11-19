import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_native_candidate as runner


class MemoryExportTests(unittest.TestCase):
    def test_only_bounded_sram_and_itcm_are_readable(self):
        exports = [dict(name='sram-full.bin', address=0x20000000, length=0x380000),
                   dict(name='itcm-full.bin', address=0, length=0x40000)]
        self.assertEqual(runner.memory_exports(dict(schema=2, post_stop_memory_exports=exports)), exports)
        for address, length in [(0x40090000, 4), (0x438000, 4), (0x2037fffc, 8),
                                (0x3fffc, 8), (0x20000000, 0), (True, 4)]:
            with self.subTest(address=address, length=length), self.assertRaises(ValueError):
                runner.memory_exports(dict(schema=2, post_stop_memory_exports=[dict(name='dump.bin',address=address,length=length)]))

    def test_unsafe_names_duplicates_and_legacy_plan_are_rejected(self):
        good = dict(name='dump.bin', address=0x20000000, length=4)
        for exports in [[dict(good, name='../main.bin')], [dict(good, name='/tmp/dump.bin')], [good, good]]:
            with self.assertRaises(ValueError):
                runner.memory_exports(dict(schema=2,post_stop_memory_exports=exports))
        with self.assertRaises(ValueError):
            runner.memory_exports(dict(schema=1,post_stop_memory_exports=[good]))
        self.assertEqual(runner.memory_exports(dict(schema=1)), [])

    def test_output_requires_native_hash_and_exact_length(self):
        data = b'\x01\x02\x03\x04'
        export = dict(name='dump.bin', address=0x20000000, length=4)
        metadata = dict(export, sha256=hashlib.sha256(data).hexdigest())
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder/'exports').mkdir()
            path = folder/'exports/dump.bin'
            path.write_bytes(data)
            self.assertEqual(runner.validate_memory_exports(folder,[export],[metadata]),[metadata])
            for content in [data[:-1], b'\x00'*4]:
                path.write_bytes(content)
                with self.assertRaises(ValueError):
                    runner.validate_memory_exports(folder,[export],[metadata])

    def test_export_script_requires_a_guest_stop_and_only_reads_memory(self):
        script = runner.memory_export_runtime([dict(name='dump.bin',address=0x20000000,length=4)])
        self.assertIn('blackwall_paused_before_host', script)
        self.assertIn('m.IsPaused', script)
        self.assertIn('ReadBytes', script)
        self.assertNotIn('WriteDoubleWord', script)
        self.assertNotIn('SetRegister', script)


if __name__ == '__main__':
    unittest.main()
