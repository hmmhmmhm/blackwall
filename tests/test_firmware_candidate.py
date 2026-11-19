import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from firmware_candidate import validate_main, compatibility_anchors, check_anchors, load_candidate, candidate_runtime


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.raw = bytearray(512)
        struct.pack_into('<2I', self.raw, 0, 0x2007fb00, 0x438101)
        self.declaration = dict(schema=1, id='new-candidate', format='raw-main', target='g2-temple-main',
                                cpu='cortex-m55', profile='stock_current', load_address=0x438000,
                                main_bytes=512, main_sha256=hashlib.sha256(self.raw).hexdigest(),
                                initial_sp=0x2007fb00, reset_vector=0x438101)

    def test_accepts_new_hash_without_allowlist_addition(self):
        validate_main(bytes(self.raw), self.declaration)

    def test_rejects_mismatch_and_unsupported_declarations(self):
        for field, value in [('schema', True), ('main_bytes', 513), ('main_sha256', '0' * 64),
                             ('load_address', 0), ('profile', 'unknown'), ('cpu', 'cortex-m4'),
                             ('format', 'ota'), ('target', 'case'), ('id', '../escape')]:
            with self.subTest(field=field):
                declaration = dict(self.declaration, **{field: value})
                with self.assertRaises(ValueError):
                    validate_main(bytes(self.raw), declaration)

    def test_vector_values_are_read_from_binary(self):
        for sp, pc in [(0x2007fb04, 0x438101), (0x10000000, 0x438101),
                       (0x20380008, 0x438101), (0x2007fb00, 0x438100),
                       (0x2007fb00, 0x438201), (0x2007fb00, 0x438001)]:
            raw = bytearray(self.raw)
            struct.pack_into('<2I', raw, 0, sp, pc)
            declaration = dict(self.declaration, initial_sp=sp, reset_vector=pc,
                               main_sha256=hashlib.sha256(raw).hexdigest())
            with self.subTest(sp=sp, pc=pc), self.assertRaises(ValueError):
                validate_main(bytes(raw), declaration)

    def test_rejects_truncated_oversize_and_declared_vector_mismatch(self):
        for raw in [b'\0' * 7, b'\0' * (0x3c0000 + 1)]:
            with self.assertRaises(ValueError):
                validate_main(raw, self.declaration)
        with self.assertRaises(ValueError):
            validate_main(bytes(self.raw), dict(self.declaration, reset_vector=0x438103))

    def test_observer_and_reset_anchors_reject_code_changes(self):
        anchors = compatibility_anchors(bytes(self.raw), [dict(address=0x438080)])
        self.assertEqual([x['address'] for x in anchors], [0x438080, 0x438100])
        check_anchors(bytes(self.raw), anchors)
        for offset in [0x80, 0x100]:
            changed = bytearray(self.raw)
            changed[offset] ^= 1
            with self.assertRaises(ValueError):
                check_anchors(bytes(changed), anchors)

    def test_changes_outside_observer_contract_can_be_registered(self):
        anchors = compatibility_anchors(bytes(self.raw), [dict(address=0x438080)])
        changed = bytearray(self.raw)
        changed[0x180] = 42
        check_anchors(bytes(changed), anchors)
        declaration = dict(self.declaration, main_sha256=hashlib.sha256(changed).hexdigest())
        validate_main(bytes(changed), declaration)

    def test_runtime_changes_only_verified_length(self):
        before="    memory_policy=BlackwallMemoryPolicy(m,m['sysbus.cpu'],m['sysbus.main'],m['sysbus.itcm'],512)\n    start()\n"
        self.assertEqual(candidate_runtime(before,512,528), before.replace(',512)',',528)'))
        for wrong in [before.replace(',512)',',513)'), before+before]:
            with self.assertRaises(ValueError):
                candidate_runtime(wrong,512,528)

    def test_malformed_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_main(bytes(self.raw),dict(self.declaration,profile=[]))

    def test_record_cannot_select_external_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = dict(schema=1, declaration=self.declaration, baseline_inputs_sha256='0' * 64,
                          anchors=[], main_file='../outside.bin')
            path = root / 'manifest.json'
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'artifact'):
                load_candidate(path, root / 'missing-baseline', 'stock_current')


if __name__ == '__main__':
    unittest.main()
