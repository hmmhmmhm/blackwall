"""Summarize only the observed SUBS/BNE/BX delay loop; no wall-clock model."""
from unicorn import arm_const as arm

CODE = bytes.fromhex('0138fdd17047')


def summarize_delay(cpu):
    count = cpu.reg_read(arm.UC_ARM_REG_R0)
    if not count or bytes(cpu.mem_read(0x40, len(CODE))) != CODE:
        return None
    # The last SUBS is 1 - 1: N=0,Z=1,C=1,V=0; BNE/BX preserve these flags.
    flags = cpu.reg_read(arm.UC_ARM_REG_APSR)
    cpu.reg_write(arm.UC_ARM_REG_R0, 0)
    cpu.reg_write(arm.UC_ARM_REG_APSR, (flags & ~0xf0000000) | 0x60000000)
    cpu.reg_write(arm.UC_ARM_REG_PC, cpu.reg_read(arm.UC_ARM_REG_LR))
    return {'input_count': count, 'guest_instructions_summarized': 2*count+1,
            'elapsed_device_time': 'not-modeled'}
