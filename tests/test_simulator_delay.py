import sys
import unittest
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn import arm_const as a

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from simulator_delay import CODE, summarize_delay


class DelayTests(unittest.TestCase):
    def machine(self, count, flags):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        cpu.mem_map(0, 0x2000)
        cpu.mem_write(0x40, CODE)
        for index in range(13):
            cpu.reg_write(getattr(a, f'UC_ARM_REG_R{index}'), index+17)
        cpu.reg_write(a.UC_ARM_REG_R0, count)
        cpu.reg_write(a.UC_ARM_REG_SP, 0x1800)
        cpu.reg_write(a.UC_ARM_REG_LR, 0x1001)
        cpu.reg_write(a.UC_ARM_REG_APSR, flags)
        return cpu

    def test_matches_actual_instructions_and_preserves_memory(self):
        for count in (1, 2, 31, 1000):
            for flags in (0, 0xf8000000):
                actual = self.machine(count, flags)
                fast = self.machine(count, flags)
                actual.emu_start(0x41, 0x1000, count=2*count+2)
                self.assertIsNotNone(summarize_delay(fast))
                for reg in [getattr(a, f'UC_ARM_REG_R{i}') for i in range(13)] + [a.UC_ARM_REG_SP, a.UC_ARM_REG_LR, a.UC_ARM_REG_PC, a.UC_ARM_REG_APSR]:
                    self.assertEqual(actual.reg_read(reg), fast.reg_read(reg))
                self.assertEqual(actual.mem_read(0, 0x2000), fast.mem_read(0, 0x2000))

    def test_zero_or_changed_code_is_not_summarized(self):
        self.assertIsNone(summarize_delay(self.machine(0, 0)))
        cpu = self.machine(4, 0)
        cpu.mem_write(0x40, b'\x00\xbf')
        self.assertIsNone(summarize_delay(cpu))
