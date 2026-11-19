import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from emulate_recovery_worker import RecoveryWorker, RamInvocationBoundary

CANDIDATE = Path.home() / 'Library/Application Support/Blackwall/recovery/private-boot-24-candidate-01'

@unittest.skipUnless((CANDIDATE / 'source/build/bootloader.bin').is_file(), 'Private pinned recovery assets required')
class RecoveryWorkerTests(unittest.TestCase):
    def test_authenticated_upload_runs_without_main_and_stops_at_real_ram_call(self):
        worker = RecoveryWorker(CANDIDATE)
        worker.claim()
        writer = (CANDIDATE / 'source/build/recover.bin').read_bytes()
        worker.client.upload(writer, arg0=0x438010, arg1=256)
        with self.assertRaises(RamInvocationBoundary):
            worker.client.execute(source=lambda n: bytes(n))
        report = worker.report()
        self.assertEqual(report['main_instructions'], 0)
        self.assertEqual(report['held'], 1)
        self.assertEqual(report['ram_invocations_reached'], 1)
        self.assertEqual(report['mram_writes'], 0)
        self.assertEqual(report['uploaded_code_sha256'], worker.sha(writer))
        self.assertEqual(report['api_version'], 3)
        self.assertTrue(report['api_callbacks_from_patch'])

    def test_bad_upload_crc_never_reaches_ram_invocation(self):
        worker = RecoveryWorker(CANDIDATE)
        worker.claim()
        original = worker.exchange
        def corrupt(packet):
            if len(packet) == 32 and packet[8] == 2:
                packet = bytearray(packet)
                packet[10] ^= 1
                packet[-1] = (32 + 0x7d + sum(packet[:-1])) & 255
                packet = bytes(packet)
            return original(packet)
        worker.client.exchange = corrupt
        with self.assertRaises(worker.protocol.RemoteError) as error:
            worker.client.upload((CANDIDATE / 'source/build/recover.bin').read_bytes())
        self.assertEqual(error.exception.status, worker.protocol.BAD_CRC)
        self.assertTrue(worker.client.failed)
        frames = worker.frames
        with self.assertRaises(RuntimeError):
            worker.client.execute()
        self.assertEqual(worker.frames, frames)
        report = worker.report()
        self.assertEqual(report['ram_invocations_reached'], 0)
        self.assertEqual(report['mram_writes'], 0)
        self.assertEqual(report['main_instructions'], 0)

    def test_invalid_hold_does_not_claim_worker(self):
        worker = RecoveryWorker(CANDIDATE)
        challenge = worker.handshake.decode_hello(worker.exchange())
        with patch.dict(os.environ, {'G2_BOOT_KEY': (CANDIDATE / 'recovery.key').read_text().strip()}):
            packet = bytearray(worker.handshake.hold(challenge))
        packet[8] ^= 1
        packet[-1] = (len(packet) + 0x7d + sum(packet[:-1])) & 255
        with self.assertRaises(TimeoutError):
            worker.exchange(bytes(packet))
        self.assertEqual(worker.report()['held'], 0)
        self.assertEqual(worker.ram_calls, 0)
        self.assertEqual(worker.main_instructions, 0)

if __name__ == '__main__':
    unittest.main()
