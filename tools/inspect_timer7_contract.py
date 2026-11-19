"""Execute pinned original timer configuration/output/comparator functions in isolation.

No full boot claim: MMIO here is ordinary backing memory, not a timer model.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_PRIMASK
from pinned_main import load_pinned_main

BASE = 0x438000
TIMER = 0x40008000
PINS = {
    'am_hal_timer.c': 'db94b86ca9207f12ec023962f7848c2d22dabb1d54f285f2fd13df6f0ca69d7b',
    'am_hal_timer.h': '0a75d83ff508fb61b92aaa759f6229c69aee4841bec606cf17ff399ad5eeff35',
    'apollo510.h': 'b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797',
}


def invoke(raw, entry, r0, r1, seed=(), config=None, primask=0):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    extent = (len(raw) + 4095) & ~4095
    u.mem_map(BASE, extent)
    u.mem_write(BASE, raw)
    u.mem_protect(BASE, extent, UC_PROT_READ | UC_PROT_EXEC)
    u.mem_map(0x20000000, 0x20000)
    u.mem_map(TIMER, 0x1000)
    if config is not None:
        u.mem_write(0x20000100, bytes(config))
    for address, value in seed:
        u.mem_write(address, struct.pack('<I', value))
    writes = []
    def record(uc, access, address, width, value, data):
        if TIMER <= address < TIMER + 0x1000:
            writes.append([address, width, value])
        elif not 0x20000000 <= address < 0x20020000:
            raise ValueError('Unexpected isolated write: ' + hex(address))
    u.hook_add(UC_HOOK_MEM_WRITE, record)
    sentinel = 0x20010000
    u.reg_write(UC_ARM_REG_SP, 0x2001f000)
    u.reg_write(UC_ARM_REG_LR, sentinel | 1)
    u.reg_write(UC_ARM_REG_R0, r0)
    u.reg_write(UC_ARM_REG_R1, r1)
    u.reg_write(UC_ARM_REG_PRIMASK, primask)
    u.emu_start(entry | 1, sentinel, count=2000)
    if u.reg_read(UC_ARM_REG_PC) != sentinel:
        raise ValueError('Original function did not return within instruction bound')
    return u.reg_read(UC_ARM_REG_R0), writes, u.reg_read(UC_ARM_REG_PRIMASK)


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
    source = a.simulator / 'timer-source-research-01'
    for name, digest in PINS.items():
        check(name + '-pin', hashlib.sha256((source / name).read_bytes()).hexdigest() == digest)
    hal = (source / 'am_hal_timer.c').read_text()
    header = (source / 'apollo510.h').read_text()
    check('source-output-mask', 'ui32OutcfgMsk = 0x7F << ui32CfgShf;' in hal)
    check('source-output-bank', 'outcfg = &(TIMER->OUTCFG0) + (ui32PadNum >> 2);' in hal)
    check('source-irq74', 'TIMER7_IRQn               =  74' in header)
    for key, filename, delta in [
        ('stock24', 'stock-2.4.0.24.bin', 0),
        ('stock23', 'stock-2.3.0.24.bin', -0x4d2c),
        ('cfw', 'faceclaw-38-research-only.bin', -0x4d2c),
    ]:
        _, raw = load_pinned_main((a.simulator / 'inputs/verified-01' / filename).read_bytes())
        probes = []
        cfg = bytearray(24)
        cfg[2] = 4  # PWM
        struct.pack_into('<H', cfg, 6, 1)  # inactive trigger selector, TMODE=0
        struct.pack_into('<II', cfg, 16, 0xffffffff, 0xffffffff)
        ctrl = TIMER + 0x2e0
        for initial in [0, 0x41]:
            result, writes, mask = invoke(raw, 0x47d372 + delta, 7, 0x20000100, [(ctrl, initial)], cfg)
            expected = [[ctrl, 4, initial & ~1], [ctrl, 4, 0x40], [ctrl+16, 4, 0x100],
                        [ctrl+8, 4, 0xffffffff], [ctrl+12, 4, 0xffffffff], [ctrl, 4, 0x42]]
            check(key + '-configure-' + hex(initial), result == 0 and writes == expected and mask == 0)
            probes.append(dict(kind='configure', initial=initial, writes=writes))
        for channel in [14, 15]:
            result, writes, _ = invoke(raw, 0x47d372 + delta, channel, 0x20000100, config=cfg)
            check(key + '-reserved-config-' + str(channel), result == 3 and writes == [])
        # Original output helper executes its real interrupt-mask callee; no call interception.
        for pad in [144, 145, 146, 147]:
            address = TIMER + 0x80 + (pad // 4) * 4
            shift = (pad % 4) * 8
            initial = 0xa5a5a5a5
            for primask in [0, 1]:
                result, writes, mask = invoke(raw, 0x47d5c8 + delta, pad, 14, [(address, initial)], primask=primask)
                expected = (initial & ~(0x7f << shift)) | (14 << shift)
                check(key + '-output-' + str(pad) + '-' + str(primask), result == 0 and writes == [[address, 4, expected]] and mask == primask)
                probes.append(dict(kind='output', pad=pad, primask=primask, writes=writes))
        for pad, selector in [(224, 14), (145, 40)]:
            result, writes, _ = invoke(raw, 0x47d5c8 + delta, pad, selector)
            check(key + '-invalid-output-' + str(pad) + '-' + str(selector), result == 6 and writes == [])
        for function, offset, value in [(0x47d606, 8, 24000), (0x47d620, 12, 16800)]:
            result, writes, _ = invoke(raw, function + delta, 7, value)
            check(key + '-compare-' + str(offset), result == 0 and writes == [[ctrl+offset, 4, value]])
            probes.append(dict(kind='compare', value=value, writes=writes))
            for channel in [14, 15]:
                result, writes, _ = invoke(raw, function + delta, channel, value)
                check(key + '-reserved-compare-' + str(offset) + '-' + str(channel), result == 3 and writes == [])
        cases.append(dict(case=key, main_sha256=hashlib.sha256(raw).hexdigest(), config_entry=hex(0x47d372+delta),
                          output_entry=hex(0x47d5c8+delta), probes=probes))
    report = dict(passed=True, count=len(checks), checks=checks, cases=cases, hardware_accessed=False,
                  full_main_executed=False, scope='Original isolated functions only. No forced internal branches/call returns. '
                  'Comparator input values test setters, not execution of the floating-point PWM frequency/duty helper. '
                  'No counter, waveform, pin electrical state, physical timing, full boot or display verification.')
    (a.output / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, count=len(checks), cases=len(cases))))


if __name__ == '__main__':
    main()
