"""Bound original normal-sleep preparation at WFI using explicit register fixtures."""
import argparse
import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from analyze_adc_metadata import SVD_SHA
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_mspi0_retention_profiles import inspect as verify_capture
from inspect_nema_blocking_wait import cpu, STOP
from prepare_vendor_startup_candidate import sha


class Registers:
    def __init__(self, control, scr, ccr, flush):
        self.values = {0x40021050: control, 0xe000ed10: scr, 0xe000ed14: ccr,
                       0xe001e300: 0, 0x47ff0000: flush}
        self.events = []
        self.unknown = []

    def read(self, u, address, size):
        if size != 4 or address not in self.values:
            self.unknown.append(dict(operation='read', address=address, size=size))
            u.emu_stop()
            return 0xffffffff
        value = self.values[address]
        self.events.append(dict(operation='read', address=address, value=value))
        return value

    def write(self, u, address, size, value):
        if size != 4 or address not in (0xe000ed10, 0xe001e300):
            self.unknown.append(dict(operation='write', address=address, size=size, value=value))
            u.emu_stop()
            return
        self.events.append(dict(operation='write', address=address, value=value))
        self.values[address] = value

    def attach(self, u):
        u.mem_unmap(0xe000e000, 0x2000)
        for base, size in [(0xe000e000, 0x2000), (0xe001e000, 0x1000), (0x40021000, 0x1000), (0x47ff0000, 0x1000)]:
            u.mmio_map(base, size, lambda c, o, n, x, b=base: self.read(c, b + o, n), None,
                       lambda c, o, n, v, x, b=base: self.write(c, b + o, n, v), None)


def inspect(s, case, values):
    capture = verify_capture(s, case, 'active')
    f = s / 'mspi0-retention-main-02' / case
    raw, data = (f / 'main.bin').read_bytes(), (f / 'exports/sram-full.bin').read_bytes()
    r = json.loads((f / 'report.json').read_text())['observed']['register_context']
    pc, sp = r['r15'], r['r13']
    if bytes(data[sp - 0x20000000 + 4:sp - 0x20000000 + 7]) != b'\0\0\0':
        raise ValueError('Native active CPDLPSTATE fixture differs')
    frame = struct.unpack_from('<16I', data, sp - 0x20000000)
    parent = frame[15] & ~1
    entry = decode(raw, parent - 4, 4)[0].operands[0].imm
    if frame[6] != 0 or entry != pc - 0x24e:
        raise ValueError('Different original normal-sleep caller/frame')
    if [(i.mnemonic, i.op_str) for i in decode(raw, entry, 6)] != [('push.w', '{r0, r4, r5, r6, r7, r8, sb, sl, fp, lr}'), ('sub', 'sp, #0x18')]:
        raise ValueError('Different sleep prologue')
    if [(i.mnemonic, i.op_str) for i in decode(raw, pc + 2, 4)] != [('ubfx', 'r0, r0, #2, #1')]:
        raise ValueError('Different SLEEPMODE extraction')
    wfi = pc + 0x68
    if decode(raw, wfi, 2)[0].mnemonic != 'wfi' or literal(raw, decode(raw, pc + 0x5e, 4)[0]) != 0x47ff0000:
        raise ValueError('Different WFI/flush frontier')
    call = decode(raw, pc + 0x4e, 4)[0]
    config = call.operands[0].imm
    if call.mnemonic != 'bl' or literal(raw, decode(raw, config + 0x34, 2)[0]) != 0xe001e300:
        raise ValueError('Different CPDLPSTATE setter')

    def execute(control=0, scr=0x16, ccr=0x30000, flush=0, active=(0, 0, 0)):
        memory = bytearray(data)
        memory[sp - 0x20000000 + 4:sp - 0x20000000 + 7] = bytes(active)
        u = cpu(raw, bytes(memory), sp)
        for n in range(15):
            u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), r['r' + str(n)])
        bank = Registers(control, scr, ccr, flush)
        bank.attach(u)
        trace, status = [], []
        def code(c, address, size, user):
            trace.append(address)
            if address == pc + 0x52:
                status.append(c.reg_read(arm.UC_ARM_REG_R0))
            if address == wfi:
                c.emu_stop()
        u.hook_add(UC_HOOK_CODE, code)
        u.emu_start(pc | 1, STOP, count=20000)
        if u.reg_read(arm.UC_ARM_REG_PC) != wfi or bank.unknown:
            raise ValueError('Normal sleep escaped WFI boundary: ' + repr(bank.unknown))
        rejected = active[0] == 3 and bool(ccr & 0x30000)
        expected = (active[0] << 8) | ((active[1] if active[1] in (2, 3) else 1) << 4) | 1
        if status != [1 if rejected else 0] or bank.values[0xe000ed10] != scr & ~4:
            raise ValueError('Different config result/SCR update')
        writes = [e for e in bank.events if e['operation'] == 'write']
        expected_writes = ([] if rejected else [dict(operation='write', address=0xe001e300, value=expected)])
        expected_writes.append(dict(operation='write', address=0xe000ed10, value=scr & ~4))
        if writes != expected_writes or bank.values[0xe001e300] != (0 if rejected else expected):
            raise ValueError('Different normal-sleep power writes')
        if bank.events[-1] != dict(operation='read', address=0x47ff0000, value=flush):
            raise ValueError('APB flush omitted before WFI')
        return dict(control=control, scr=scr, ccr=ccr, flush=flush, active=list(active),
                    config_result=status[0], writes=writes, stop=wfi, instructions=len(trace),
                    trace_sha256=hashlib.sha256(struct.pack('<' + 'I' * len(trace), *trace)).hexdigest())

    rows = [execute(control=x) for x in values]
    signatures = {}
    for x in rows:
        key = (x['control'] >> 2) & 1
        signature = (x['trace_sha256'], x['instructions'], x['writes'])
        if key not in signatures:
            signatures[key] = signature
        elif signature != signatures[key]:
            raise ValueError('Other CPUPWRCTRL bits changed bounded behavior')
    matrix = [execute(scr=scr, ccr=ccr, flush=flush, active=(rlp, elp, 0))
              for scr in (0, 4, 0x16) for ccr in (0, 0x30000) for flush in (0, 0xffffffff)
              for rlp in (0, 3) for elp in (0, 1, 2, 3)]
    return dict(case=case, capture=capture, normal_sleep_entry=entry, parent_return=parent,
                config_setter=config, wfi_boundary=wfi, observed_native_sleep_argument=frame[6],
                control_samples=rows, mode_samples=matrix,
                native_case_cpd_configuration=0x11, pinned_sdk_default_cpd_configuration=0x21,
                sdk_elp_default_matches_binary=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence')
    s = a.simulator
    svd = s / 'apollo-dfp-research-01/apollo510.svd'
    if sha(svd) != SVD_SHA:
        raise ValueError('Changed public metadata')
    peripheral = next(x for x in ET.parse(svd).getroot().findall('./peripherals/peripheral') if x.findtext('name') == 'PWRCTRL')
    reg = next(x for x in peripheral.findall('./registers/register') if x.findtext('name') == 'CPUPWRCTRL')
    mask = int(reg.findtext('resetMask'), 0)
    fields = {x.findtext('name'): x.findtext('bitRange') for x in reg.findall('./fields/field')}
    if mask != 0x1efc or fields['SLEEPMODE'] != '[2:2]':
        raise ValueError('Different sleep control definition')
    bits = [n for n in range(32) if mask & (1 << n)]
    values = [sum(((v >> n) & 1) << bit for n, bit in enumerate(bits)) for v in range(1 << len(bits))]
    tree = json.loads((s / 'mspi0-queue-sdk-01/tree.json').read_text())
    if tree['sha'] != '61b293a49db34030c545f99101f7ebf6a3050314' or tree['truncated']:
        raise ValueError('Different SDK tree')
    sdk = []
    for path in ['mcu/apollo510/hal/mcu/am_hal_sysctrl.c', 'mcu/apollo510/hal/am_hal_sysctrl.h']:
        local = s / 'upstream/hal-ambiq-61b293a' / Path(path).name
        data = local.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if not any(x['path'] == path and x['sha'] == blob for x in tree['tree']):
            raise ValueError('Changed pinned SDK ' + path)
        sdk.append(dict(path=path, git_blob=blob, sha256=sha(local)))
    power_header = s / 'mspi1-source-research-01/am_hal_pwrctrl.h'
    power_path = 'mcu/apollo510/hal/am_hal_pwrctrl.h'
    data = power_header.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if not any(x['path'] == power_path and x['sha'] == blob for x in tree['tree']):
        raise ValueError('Changed pinned power enums')
    enum = re.search(r'typedef enum\s*\{([^{}]+)\}\s*am_hal_pwrctrl_pwrmodctl_elp_e', data.decode())
    if not enum or [x.strip() for x in enum[1].split(',')] != ['AM_HAL_PWRCTRL_ELP_ON', 'AM_HAL_PWRCTRL_ELP_ON_CLK_OFF', 'AM_HAL_PWRCTRL_ELP_RET', 'AM_HAL_PWRCTRL_ELP_OFF']:
        raise ValueError('Different pinned ELP enum values')
    source = (s / 'upstream/hal-ambiq-61b293a/am_hal_sysctrl.c').read_text()
    normal = source[source.index('if (PWRCTRL->CPUPWRCTRL_b.SLEEPMODE)'):source.index('am_hal_pwrctrl_pwrmodctl_cpdlp_config(sNSCpdlpConfig);')]
    if normal.count('sNSCpdlpConfig.eElpConfig = AM_HAL_PWRCTRL_ELP_RET;') != 2:
        raise ValueError('Different pinned SDK normal-sleep ELP defaults')
    sdk.append(dict(path=power_path, git_blob=blob, sha256=sha(power_header)))
    cmsis = json.loads((s / 'upstream/cmsis-6.3.0/manifest.json').read_text())
    pin = next(x for x in cmsis['files'] if x['path'].endswith('/core_cm55.h'))
    if cmsis['commit'] != '45dab712ad84f8cbbf2b7bfc089c19088507df6f' or sha(s / 'upstream/cmsis-6.3.0/core_cm55.h') != pin['sha256']:
        raise ValueError('Changed pinned Cortex-M55 header')
    rows = [inspect(s, case, values) for case in ('stock24', 'stock23', 'cfw')]
    a.output.mkdir(mode=0o700)
    result = dict(passed=True, cases=rows, sdk=sdk, cmsis=pin,
                  source_scenarios=sum(len(x['control_samples']) + len(x['mode_samples']) for x in rows),
                  engine='Original ARM on Unicorn M7; saved GPR/RAM with synthetic Thumb/MMIO/SCS fixtures and explicit caller-frame variants; stops before WFI.',
                  actual_sleep_executed=False, actual_wake_verified=False, native_rerun=False,
                  model_changed=False, hardware_accessed=False, boot_verified=False, display_verified=False)
    (a.output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    print('Verified original3 normal-sleep preparation:', result['source_scenarios'], 'scenarios; WFI not executed; SDK ELP default differs')


if __name__ == '__main__':
    main()
