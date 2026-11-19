"""Verify the isolated post-enable memory-LDO setup; no hardware access."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

import capstone
import unicorn as u
from unicorn import arm_const as arm

from audit_assets import PINS
from blackwall_package import parse_bundle

BASE = 0x438000
RETURN = 0x20000000
MEM = 0x40020088
REF = 0x400201b0
PROFILES = {
    'stock_base': ('stock-2.3.0.24.bin', 0x5bad3a),
    'stock_current': ('stock-2.4.0.24.bin', 0x5c22e2),
    'cfw': ('faceclaw-38-research-only.bin', 0x5bad3a),
}


def probe(raw, start):
    if start < BASE or start + 28 > BASE + len(raw) or start % 2:
        raise ValueError('Helper ABI is outside the supplied image')
    cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    cs.detail = True
    instructions = list(cs.disasm(raw[start - BASE:start - BASE + 28], start))
    expected = [('ldr', None), ('movs', 'r1, #1'), ('ldr', 'r2, [r0]'),
                ('bfi', 'r2, r1, #0, #6'), ('str', 'r2, [r0]'), ('ldr', None),
                ('movs', 'r1, #2'), ('ldr', 'r2, [r0]'), ('bfi', 'r2, r1, #0xf, #2'),
                ('str', 'r2, [r0]'), ('movs', 'r0, #0'), ('bx', 'lr')]
    if len(instructions) != len(expected):
        raise ValueError('Helper ABI instruction count changed')
    for instruction, (mnemonic, operands) in zip(instructions, expected):
        if instruction.mnemonic != mnemonic or (operands is not None and instruction.op_str != operands):
            raise ValueError('Helper ABI instruction changed')
    for index, target in ((0, MEM), (5, REF)):
        ins = instructions[index]
        if (len(ins.operands) != 2 or ins.operands[0].type != capstone.arm.ARM_OP_REG
                or ins.operands[0].reg != capstone.arm.ARM_REG_R0
                or ins.operands[1].type != capstone.arm.ARM_OP_MEM
                or ins.operands[1].mem.base != capstone.arm.ARM_REG_PC):
            raise ValueError('Helper ABI literal load changed')
        offset = ((ins.address + 4) & ~3) + ins.operands[1].mem.disp - BASE
        if not 0 <= offset <= len(raw) - 4 or struct.unpack_from('<I', raw, offset)[0] != target:
            raise ValueError('Helper ABI peripheral address changed')

    cpu = u.Uc(u.UC_ARCH_ARM, u.UC_MODE_THUMB | u.UC_MODE_MCLASS)
    cpu.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M4)
    extent = (len(raw) + 0xfff) & ~0xfff
    cpu.mem_map(BASE, extent)
    cpu.mem_write(BASE, raw)
    cpu.mem_protect(BASE, extent, u.UC_PROT_READ | u.UC_PROT_EXEC)
    cpu.mem_map(RETURN, 0x1000)
    words, events = {}, []

    def read(uc, offset, size, context):
        address = 0x40020000 + offset
        if address not in words or size != 4:
            raise ValueError('Unexpected peripheral read')
        events.append(('read', address, words[address]))
        return words[address]

    def write(uc, offset, size, value, context):
        address = 0x40020000 + offset
        if address not in words or size != 4:
            raise ValueError('Unexpected peripheral write')
        events.append(('write', address, value))
        words[address] = value

    def code(uc, address, size, context):
        if address not in instruction_sizes or instruction_sizes[address] != size:
            raise ValueError('Execution left isolated helper')

    def ram_write(uc, access, address, size, value, context):
        raise ValueError('Unexpected helper RAM write')

    instruction_sizes = {ins.address: ins.size for ins in instructions}
    cpu.mmio_map(0x40020000, 0x1000, read, None, write, None)
    cpu.hook_add(u.UC_HOOK_CODE, code)
    cpu.hook_add(u.UC_HOOK_MEM_WRITE, ram_write, begin=RETURN, end=RETURN + 0xfff)
    cases = []
    for mem_base, ref_base in ((0, 0), (0xffffffff, 0xffffffff),
                               (0xaaaaaaaa, 0x55555555), (0x55555555, 0xaaaaaaaa)):
        for mem_trim in range(64):
            for reference in range(4):
                cases.append(((mem_base & ~0x3f) | mem_trim,
                              (ref_base & ~0x18000) | (reference << 15)))
    for register, mask in ((MEM, 0x3f), (REF, 0x18000)):
        for bit in range(32):
            if mask & (1 << bit):
                continue
            for current in (1 << bit, 0xffffffff ^ (1 << bit)):
                cases.append((current, 0) if register == MEM else (0, current))
    for before_mem, before_ref in cases:
        words.update({MEM: before_mem, REF: before_ref})
        events.clear()
        cpu.reg_write(arm.UC_ARM_REG_SP, RETURN + 0xf00)
        cpu.reg_write(arm.UC_ARM_REG_LR, RETURN | 1)
        cpu.reg_write(arm.UC_ARM_REG_XPSR, 0x01000000)
        cpu.emu_start(start | 1, RETURN, count=128)
        after_mem = (before_mem & ~0x3f) | 1
        after_ref = (before_ref & ~0x18000) | 0x10000
        expected_events = [('read', MEM, before_mem), ('write', MEM, after_mem),
                           ('read', REF, before_ref), ('write', REF, after_ref)]
        if (events != expected_events or words != {MEM: after_mem, REF: after_ref}
                or cpu.reg_read(arm.UC_ARM_REG_PC) != RETURN or cpu.reg_read(arm.UC_ARM_REG_R0) != 0):
            raise ValueError('Helper result or access sequence differs from expected fields')
    return dict(cases=len(cases), passed=True, registers=[hex(MEM), hex(REF)],
                function_start=hex(start), function_size=28,
                function_sha256=hashlib.sha256(raw[start - BASE:start - BASE + 28]).hexdigest(),
                field_combinations=256, surrounding_pattern_pairs=4,
                single_bit_preservation_cases=112)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700)
    profiles = {}
    for profile, (filename, start) in PROFILES.items():
        data = (args.inputs / filename).read_bytes()
        if hashlib.sha256(data).hexdigest() != PINS[profile]:
            raise ValueError('Input bundle SHA256 mismatch')
        raw = next(component for component in parse_bundle(data) if component.type_id == 0).payload[32:]
        profiles[profile] = dict(probe(raw, start), bundle_sha256=PINS[profile],
                                 raw_main_sha256=hashlib.sha256(raw).hexdigest())
        print(profile, profiles[profile]['cases'], 'passed', flush=True)
    report = dict(scope='isolated real ARM field-setting helper with synthetic register values; no full boot',
                  cpu_model='Unicorn Cortex-M4 approximation', profiles=profiles,
                  cases=sum(profile['cases'] for profile in profiles.values()),
                  hardware_validated=False, boot_verified=False, installable=False,
                  analog_power_and_delay_verified=False)
    path = args.output / 'report.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    path.chmod(0o600)


if __name__ == '__main__':
    main()
