import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from probe_memldo_setup import probe

BASE = 0x438000
LLVM = Path('/opt/homebrew/opt/llvm@21/bin')


def assemble(directory, *, destination=0x400201b0, field='0, #6', value=1):
    source = directory / 'helper.s'
    source.write_text(f'''.syntax unified
.thumb
.text
ldr r0, .Lmem
movs r1, #{value}
ldr r2, [r0]
bfi r2, r1, #{field}
str r2, [r0]
ldr r0, .Lref
movs r1, #2
ldr r2, [r0]
bfi r2, r1, #15, #2
str r2, [r0]
movs r0, #0
bx lr
.balign 4
.Lmem: .word 0x40020088
.Lref: .word {destination}
''')
    subprocess.run([str(LLVM / 'clang'), '--target=arm-none-eabi', '-mcpu=cortex-m4',
                    '-mthumb', '-c', str(source), '-o', str(directory / 'helper.o')],
                   check=True, capture_output=True)
    subprocess.run([str(LLVM / 'llvm-objcopy'), '-O', 'binary', '--only-section=.text',
                    str(directory / 'helper.o'), str(directory / 'helper.bin')],
                   check=True, capture_output=True)
    return (directory / 'helper.bin').read_bytes()


class MemLdoProbeTests(unittest.TestCase):
    def test_real_thumb_execution_covers_fields_and_surrounding_bits(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = probe(assemble(Path(temporary)), BASE)
        self.assertEqual(result.get('cases'), 1136)
        self.assertTrue(result['passed'])
        self.assertEqual(result['registers'], ['0x40020088', '0x400201b0'])

    def test_wrong_destination_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = assemble(Path(temporary), destination=0x40021108)
        with self.assertRaisesRegex(ValueError, 'ABI'):
            probe(raw, BASE)

    def test_changed_bitfield_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = assemble(Path(temporary), field='1, #6')
        with self.assertRaisesRegex(ValueError, 'ABI'):
            probe(raw, BASE)

    def test_changed_trim_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = assemble(Path(temporary), value=3)
        with self.assertRaisesRegex(ValueError, 'ABI'):
            probe(raw, BASE)
