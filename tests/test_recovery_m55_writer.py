import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from run_recovery_m55_writer import prepare_capture, run_case

CANDIDATE = Path.home() / 'Library/Application Support/Blackwall/recovery/private-boot-24-candidate-01'

@unittest.skipUnless((CANDIDATE / 'source/build/bootloader.bin').is_file(), 'Private pinned recovery assets required')
class RecoveryM55CaptureTests(unittest.TestCase):
    def test_real_uploaded_worker_state_and_memory_are_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'capture'
            manifest = prepare_capture(CANDIDATE, out, bytes(range(256)) * 2)
            self.assertEqual(manifest['registers']['PC'], 0x434910)
            self.assertEqual(manifest['worker']['main_instructions'], 0)
            self.assertEqual(manifest['worker']['mram_writes'], 0)
            self.assertEqual(len((out / 'sram.bin').read_bytes()), 0x80000)
            self.assertEqual((out / 'mram.bin').read_bytes()[0x38000:0x38010], bytes(16))
            self.assertEqual(manifest['payload_bytes'], 512)
            self.assertFalse(manifest['hardware_accessed'])

    def test_explicit_full_restore_preserves_preexisting_vectors(self):
        baseline=Path.home()/'Library/Application Support/Blackwall/simulator/recovery-m55-writer-12/success/mram.bin'
        main=Path.home()/'Library/Application Support/Blackwall/simulator/sustained-render-guard-native-01/stock24/main.bin'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);before=bytearray(baseline.read_bytes());before[0x38000:0x38010]=main.read_bytes()[:16]
            (root/'before.bin').write_bytes(before)
            prepare_capture(CANDIDATE,root/'capture',main.read_bytes()[16:]+bytes(12),full_main_restore=True,mram_before=root/'before.bin')
            self.assertEqual((root/'capture/mram.bin').read_bytes()[0x38000:0x38010],main.read_bytes()[:16])

    def test_unaligned_or_empty_data_is_rejected_before_capture(self):
        for data in [b'', bytes(15), bytes(4097)]:
            with tempfile.TemporaryDirectory() as temp:
                out = Path(temp) / 'invalid'
                with self.assertRaises(ValueError):
                    prepare_capture(CANDIDATE, out, data)
                self.assertFalse(out.exists())

    def test_direct_replay_cannot_write_firmware_inside_repository(self):
        with self.assertRaises(ValueError):
            run_case(Path('/unused'), Path(__file__).resolve().parents[1] / 'forbidden-recovery-output')

    def test_capture_rejects_other_git_worktrees_before_loading_firmware(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.git').write_text('gitdir: /unused')
            with self.assertRaises(ValueError):
                prepare_capture(Path('/unused'), root / 'capture', bytes(16))
            self.assertFalse((root / 'capture').exists())

    def test_incomplete_result_option_cannot_relax_default_writer(self):
        for option in (True,1):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);capture=root/'capture';capture.mkdir()
                (capture/'snapshot.json').write_text(json.dumps(dict(payload_bytes=512,sha256={})))
                with self.assertRaises(ValueError):run_case(capture,root/'output',allow_incomplete=option)
                self.assertFalse((root/'output').exists())

    def test_invalid_interrupt_configuration_rejected_before_capture(self):
        for words in (-2, True, 1.5):
            with self.assertRaises(ValueError):
                run_case(Path('/unused'),Path('/tmp/unused-recovery-fixture'),interrupt_after_words=words)

    def test_invalid_fault_configuration_is_rejected_before_reading_capture(self):
        for status, corrupt in [(-1, False), (256, False), (True, False), (0, 1)]:
            with self.assertRaises(ValueError):
                run_case(Path('/unused'), Path('/tmp/unused-recovery-fixture'), status, corrupt)

if __name__ == '__main__':
    unittest.main()
