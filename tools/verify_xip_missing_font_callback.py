"""Execute original glyph callbacks with a missing descriptor, in isolated Unicorn only."""
import argparse
import json
import struct
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_MEM_INVALID, UC_ERR_READ_UNMAPPED
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from pinned_main import load_pinned_main


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    a.output.mkdir(mode=0o700)
    cases = []
    for key, filename in [('stock24', 'stock-2.4.0.24.bin'), ('stock23', 'stock-2.3.0.24.bin'), ('cfw', 'faceclaw-38-research-only.bin')]:
        _, raw = load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes())
        replay = json.loads((a.simulator/'xip-font-config-main-01'/key/'report.json').read_text())
        if not replay['passed'] or replay['instruction_accounting_delta'] != 1:
            raise ValueError('Missing native font config evidence')
        for bank in [0, 1]:
            font = replay['snapshots']['font-object-'+str(bank)]
            if len(font) != 9 or font[6] != 0:
                raise ValueError('Expected original descriptor-null font object')
            for character in [0, 65, 0xAC00]:
                u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
                u.mem_map(0x438000, (len(raw)+4095) & ~4095)
                u.mem_write(0x438000, raw)
                u.mem_map(0x20000000, 0x10000)
                u.mem_write(0x20001000, struct.pack('<9I', *font))
                for register, value in [(UC_ARM_REG_R0, 0x20001000), (UC_ARM_REG_R1, 0x20002000),
                                        (UC_ARM_REG_R2, character), (UC_ARM_REG_R3, 0),
                                        (UC_ARM_REG_SP, 0x2000f000), (UC_ARM_REG_LR, 0x438001)]:
                    u.reg_write(register, value)
                faults = []
                def invalid(cpu, access, address, size, value, _):
                    faults.append(dict(pc=hex(cpu.reg_read(UC_ARM_REG_PC)), address=address, size=size, access=access))
                    return False
                u.hook_add(UC_HOOK_MEM_INVALID, invalid)
                error = None
                try:
                    u.emu_start(font[0], 0x438000, count=1000)
                except UcError as e:
                    error = e.errno
                returned = u.reg_read(UC_ARM_REG_PC) == 0x438000
                if character == 0:
                    if error is not None or faults or not returned or u.reg_read(UC_ARM_REG_R0) != 0:
                        raise ValueError('NUL glyph control did not return false')
                elif error != UC_ERR_READ_UNMAPPED or len(faults) != 1 or faults[0]['address'] != 0x12 or faults[0]['size'] != 2:
                    raise ValueError('Missing descriptor fault differs')
                cases.append(dict(case=key, bank=bank, callback=hex(font[0]), character=character,
                                  returned=returned, error=error, faults=faults))
    report = dict(passed=True, cases=cases, count=len(cases), original_code=True,
                  isolated_function_entry=True, synthetic_arguments=True,
                  forced_internal_branches=False, full_main_executed=False, hardware_accessed=False,
                  scope='Original callbacks with native-observed font objects copied into synthetic SRAM; NUL returns false, nonzero codepoints fault with null descriptor. Does not prove main reaches callback or all fonts fail.')
    (a.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, count=len(cases), null_character_controls=6, nonzero_descriptor_faults=12)))


if __name__ == '__main__':
    main()
