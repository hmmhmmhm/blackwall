"""Static NVdb initializer contract for pinned original main binaries; no device access."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM, ARM_REG_PC
from native_replay import parse_log
from pinned_main import load_pinned_main


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    a.output.mkdir(mode=0o700)
    checks, cases = [], []
    def check(name, condition):
        if not condition:
            raise ValueError(name)
        checks.append(name)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    md.detail = True
    base = 0x438000
    profiles = [
        ('stock24', 'stock-2.4.0.24.bin', 0x55f034, 0x58602e, 0x585f50, 0x577a02, 0x55eeac),
        ('stock23', 'stock-2.3.0.24.bin', 0x52bf20, 0x562d96, 0x562cb8, 0x55e2da, 0x52bd98),
        ('cfw', 'faceclaw-38-research-only.bin', 0x52bf20, 0x562d96, 0x562cb8, 0x55e2da, 0x52bd98),
    ]
    for key, file, entry, db_init, control, db_select, defaults in profiles:
        _, raw = load_pinned_main((a.simulator / 'inputs/verified-01' / file).read_bytes())
        code = {i.address: i for i in md.disasm(raw[entry-base:entry-base+0x212], entry)}
        def ins(offset, mnemonic, operands):
            i = code.get(entry + offset)
            return i is not None and (i.mnemonic, i.op_str) == (mnemonic, operands)
        def word(address):
            if not base <= address <= base + len(raw) - 4:
                raise ValueError('literal outside pinned main')
            return struct.unpack_from('<I', raw, address-base)[0]
        def literal(offset):
            i = code[entry + offset]
            mem = next(o.mem for o in i.operands if o.type == ARM_OP_MEM and o.mem.base == ARM_REG_PC)
            return word(((i.address + 4) & ~3) + mem.disp)
        def string(address):
            if not base <= address < base + len(raw):
                raise ValueError('string outside pinned main')
            end = raw.find(b'\0', address-base, address-base+80)
            if end < 0:
                raise ValueError('unterminated string')
            return raw[address-base:end].decode('ascii')
        check(key+'-entry', ins(0, 'push', '{r4, r5, r6, lr}'))
        check(key+'-factory-and-NVdb', string(literal(0x38)) == 'factory' and string(literal(0x3a)) == 'NVdb')
        check(key+'-DB1-selected', ins(0x44, 'movs', 'r0, #1') and ins(0x46, 'bl', '#'+hex(db_select)))
        check(key+'-default-descriptor', ins(0x3e, 'add', 'r0, sp, #0x14') and ins(0x40, 'bl', '#'+hex(defaults)))
        check(key+'-init-args', ins(0x4e, 'add', 'r3, sp, #0x14') and ins(0x50, 'movs', 'r2, r5')
              and ins(0x52, 'movs', 'r1, r6') and ins(0x54, 'bl', '#'+hex(db_init)))
        check(key+'-init-failure-returns8', ins(0xc4, 'movs', 'r0, #8') and ins(0xc6, 'b', '#'+hex(entry+0x20e)))
        check(key+'-success-only-continues', ins(0x60, 'beq', '#'+hex(entry+0xc8)))
        check(key+'-lock-unlock-control', ins(0x24, 'movs', 'r1, #2') and ins(0x26, 'bl', '#'+hex(control))
              and ins(0x32, 'movs', 'r1, #3') and ins(0x34, 'bl', '#'+hex(control)))
        check(key+'-magic-key', string(literal(0xc8)) == 'nvMagic')
        check(key+'-magic-constant', literal(0x120) == literal(0x168) == 0x55550022)
        check(key+'-magic-rebuild-call', ins(0x1b8, 'bl', '#'+hex(db_select)) and code[entry+0x1bc].mnemonic == 'bl')
        def block(address, size):
            return {i.address-address: (i.mnemonic, i.op_str) for i in md.disasm(raw[address-base:address-base+size], address)}
        control_body = block(control, 0xde)
        check(key+'-control2-3-are-callbacks', control_body.get(0x86) == ('str', 'r2, [r4, #0x1c]')
              and control_body.get(0x8a) == ('str', 'r2, [r4, #0x20]'))
        rebuild = int(code[entry+0x1bc].op_str[1:], 16)
        rebuild_body = block(rebuild, 0xc8)
        check(key+'-rebuild-sector-loop', rebuild_body.get(0x36) == ('bhs', '#'+hex(rebuild+0x50))
              and rebuild_body.get(0x40, ('', ''))[0] == 'bl'
              and rebuild_body.get(0x4c) == ('beq', '#'+hex(rebuild+0x2e)))
        format_sector = int(rebuild_body[0x40][1][1:], 16)
        format_body = block(format_sector, 0x80)
        check(key+'-format-sector-erases', format_body.get(0x52) == ('ldr', 'r2, [r4, #0xc]')
              and format_body.get(0x58, ('', ''))[0] == 'bl')
        erase_wrapper = int(format_body[0x58][1][1:], 16)
        erase_body = block(erase_wrapper, 0x20)
        check(key+'-erase-partition-wrapper', erase_body.get(0xe) == ('ldr', 'r0, [r0, #8]')
              and erase_body.get(0x10, ('', ''))[0] == 'bl')
        default_code = list(md.disasm(raw[defaults-base:defaults-base+12], defaults))
        check(key+'-nine-defaults', [(i.mnemonic, i.op_str) for i in default_code][2:4] == [('movs', 'r1, #9'), ('str', 'r1, [r0, #4]')])
        # Descriptor points to SRAM, not a ROM array whose bytes can be read as defaults.
        di = default_code[0]
        dm = next(o.mem for o in di.operands if o.type == ARM_OP_MEM)
        table = word(((di.address+4)&~3)+dm.disp)
        check(key+'-default-table-SRAM', 0x20000000 <= table < 0x20400000)
        native = a.simulator / 'mspi1-program-main-02' / key
        report = json.loads((native/'report.json').read_text())
        observed = parse_log((native/'renode.log').read_text())
        check(key+'-native-log-report', observed == report['observed'])
        check(key+'-native-original', (native/'main.bin').read_bytes() == raw)
        parts = []
        for pos in range(0, len(raw)-64, 4):
            if raw[pos:pos+9] == b'01PENVdb\0':
                parts.append((base+pos, *struct.unpack_from('<II', raw, pos+52)))
        check(key+'-partition', len(parts) == 1 and parts[0][1:] == (0x1ff8000, 0x8000))
        stack = observed['stack_context']['words']
        check(key+'-active-partition-on-stack', parts[0][0] in stack and 0x1ff8000 in stack and 16 in stack)
        cases.append(dict(case=key, main_sha256=hashlib.sha256(raw).hexdigest(), initializer=hex(entry),
                          db_init=hex(db_init), default_count=9, default_table=hex(table),
                          default_content_verified=False, physical_factory_data_verified=False))
    result = dict(passed=True, count=len(checks), checks=checks, cases=cases,
                  scope='Static NVdb factory initializer and existing stopped native stack; no blank NVdb execution or hardware access')
    (a.output/'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
