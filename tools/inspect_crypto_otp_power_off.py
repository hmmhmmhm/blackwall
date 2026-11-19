"""Inspect original main cleanup and pinned HAL power-off contracts without execution."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM, ARM_REG_PC
from native_replay import parse_log, validate_assets
from pinned_main import load_pinned_main


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    s = args.simulator
    args.output.mkdir(mode=0o700)
    checks, cases = [], []

    def check(name, condition):
        if not condition:
            raise ValueError(name)
        checks.append(name)

    source = s / 'mspi1-source-research-01'
    manifest = json.loads((source / 'sources.json').read_text())
    data = (source / 'am_hal_pwrctrl.c').read_bytes()
    pin = next(f for f in manifest['files'] if f['path'].endswith('/am_hal_pwrctrl.c'))
    check('HAL-pin', manifest['commit'] == '61b293a49db34030c545f99101f7ebf6a3050314'
          and hashlib.sha256(data).hexdigest() == pin['sha256'])
    hal = data.decode()
    off = hal[hal.index('am_hal_pwrctrl_periph_disable(am_hal_pwrctrl_periph_e'):]
    off = off[:off.index('} // am_hal_pwrctrl_periph_disable()')]
    check('HAL-revision-dependent-OTP-guard', '!APOLLO5_GE_B1 && (PWRCTRL->DEVPWRSTATUS_b.PWRSTCRYPTO)' in off)
    check('HAL-OTP-idle-before-clear', off.index('(uint32_t)&OTP->PTMSTAT') < off.index('AM_REGVAL(pwr_ctrl.ui32PwrEnRegAddr) &= ~pwr_ctrl.ui32PeriphEnable'))
    check('HAL-OTP-wait-100000us', '#define AM_HAL_PWRCTRL_MAX_WAIT_OTP_US      100000' in hal)
    check('HAL-power-wait-5us', '#define AM_HAL_PWRCTRL_MAX_WAIT_US          5' in hal)
    check('HAL-status-before-clock-release', off.index('pwrctrl_periph_disable_msk_check(ePeripheral)') < off.index('am_hal_clkmgr_clock_release(AM_HAL_CLKMGR_CLK_ID_HFRC, AM_HAL_CLKMGR_USER_ID_CRYPTO)'))
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    md.detail = True
    for key, filename, delta, consumer in [
        ('stock24', 'stock-2.4.0.24.bin', 0, 0x4d1a80),
        ('stock23', 'stock-2.3.0.24.bin', 0xbee8, 0x4c40d0),
        ('cfw', 'faceclaw-38-research-only.bin', 0xbee8, 0x4c40d0),
    ]:
        d = s / 'otp-serial-slots-main-01' / key
        observed = parse_log((d / 'renode.log').read_text())
        report = json.loads((d / 'report.json').read_text())
        validate_assets(d, json.loads((d / 'derived-inputs.json').read_text())['derived'])
        check(key + '-native-report', observed == report['observed'])
        _, raw = load_pinned_main((s / 'inputs/verified-01' / filename).read_bytes())
        check(key + '-original-main', raw == (d / 'main.bin').read_bytes())
        entry, store = 0x494e96 - delta, 0x494f3e - delta
        code = {i.address: i for i in md.disasm(raw[entry-0x438000:entry+0x15e-0x438000], entry)}

        def ins(offset, mnemonic, operand):
            i = code.get(entry + offset)
            return i is not None and (i.mnemonic, i.op_str) == (mnemonic, operand)

        def literal(offset):
            addr = entry + offset
            mem = next(o.mem for o in code[addr].operands if o.type == ARM_OP_MEM and o.mem.base == ARM_REG_PC)
            return struct.unpack_from('<I', raw, (((addr+4) & ~3) + mem.disp)-0x438000)[0]

        def branch(offset, target):
            return ins(offset, 'b', '#' + hex(entry + target))

        check(key+'-already-off-success', ins(0x24, 'movs', 'r0, #0') and branch(0x26, 0x15a))
        check(key+'-OTP-enum29', ins(0x2c, 'cmp', 'r0, #0x1d'))
        check(key+'-revision-threshold22', ins(0x3a, 'cmp', 'r0, #0x22') and ins(0x3c, 'bhs', '#'+hex(entry+0x4e)))
        check(key+'-older-revision-crypto-guard', literal(0x3e) == 0x40021008 and ins(0x42, 'ubfx', 'r0, r0, #0x15, #1') and ins(0x4a, 'movs', 'r0, #3') and branch(0x4c, 0x15a))
        check(key+'-OTP-wait-arguments', ins(0x4e, 'movs', 'r0, #1') and ins(0x50, 'str', 'r0, [sp]') and ins(0x52, 'movs', 'r3, #0') and ins(0x54, 'movs', 'r2, #1') and literal(0x56) == 0x40014ac4 and literal(0x5a) == 100000)
        check(key+'-OTP-wait-error-exit', ins(0x64, 'cmp', 'r4, #0') and ins(0x66, 'beq', '#'+hex(entry+0x6c)) and ins(0x68, 'movs', 'r0, r4') and branch(0x6a, 0x15a))
        check(key+'-clear-selected-mask', ins(0xa4, 'bics', 'r1, r0') and ins(0xa8, 'str', 'r1, [r0]'))
        check(key+'-off-status-wait', ins(0xbc, 'movs', 'r0, #0') and ins(0xbe, 'str', 'r0, [sp]') and ins(0xc0, 'ldr', 'r3, [sp, #0x10]') and ins(0xc2, 'ldr', 'r2, [sp, #0x10]') and ins(0xc4, 'ldr', 'r1, [sp, #0xc]') and ins(0xc6, 'movs', 'r0, #5'))
        check(key+'-status-error-skips-clock', ins(0xce, 'cmp', 'r4, #0') and ins(0xd0, 'bne', '#'+hex(entry+0x154)))
        check(key+'-crypto-clock-release-arguments', ins(0xd6, 'cmp', 'r0, #0x17') and ins(0xda, 'movs', 'r1, #0x17') and ins(0xdc, 'movs', 'r0, #4') and code[entry+0xde].mnemonic == 'bl')
        check(key+'-return-status', ins(0x158, 'movs', 'r0, r4') and ins(0x15c, 'pop', '{r4, r5, pc}'))
        caller = {i.address-consumer: (i.mnemonic, i.op_str) for i in md.disasm(raw[consumer+0x1d0-0x438000:consumer+0x1e0-0x438000], consumer+0x1d0)}
        check(key+'-cleanup-ignores-both-returns', caller[0x1d0] == ('movs', 'r0, #0x17') and caller[0x1d2] == ('bl', '#'+hex(entry)) and caller[0x1d6] == ('movs', 'r0, #0x1d') and caller[0x1d8] == ('bl', '#'+hex(entry)) and caller[0x1dc] == ('cmp', 'r7, #0'))
        ctx, stack = observed['register_context'], observed['stack_context']['words']
        check(key+'-actual-paused-cleanup', ctx['r15'] == store and ctx['r5'] == 23 and ctx['r1'] == 0x08000400 and stack[1:5] == [0x40021004, 0x200000, 0x40021008, 0x200000])
        cases.append(dict(case=key, disable_entry=hex(entry), paused_store=hex(store), chip_revision_register=hex(literal(0x30)), crypto_cleanup_call=hex(consumer+0x1d2), otp_cleanup_call=hex(consumer+0x1d8), clock_release_call=hex(entry+0xde)))
    result = dict(passed=True, count=len(checks), checks=checks, cases=cases,
                  scope='Static original-code/HAL contract and prior native pause evidence; no new main execution, hardware access or recovery validation')
    (args.output/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
