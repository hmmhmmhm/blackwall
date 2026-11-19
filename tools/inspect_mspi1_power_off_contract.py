"""Audit the original MSPI1 retention power-off boundary without running hardware."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from native_replay import parse_log
from pinned_main import load_pinned_main
from inspect_mspi1_config_contract import collect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    s, out = args.simulator, args.output
    out.mkdir(mode=0o700)
    checks, cases = [], []

    def check(name, value):
        if not value:
            raise ValueError(name)
        checks.append(name)

    def marker(log, name):
        rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines()
                if line.startswith(name + ' ')]
        check(name + '-unique', len(rows) == 1)
        return rows[0]

    collect(s)  # Validates the pinned SVD/header before interpreting fields.
    root = ET.parse(s / 'apollo-dfp-research-01/apollo510.svd').getroot()
    peripheral = next(p for p in root.findall('./peripherals/peripheral')
                      if p.findtext('name') == 'PWRCTRL')
    reg = next(r for r in peripheral.findall('./registers/register')
               if r.findtext('name') == 'DEVPWREN')
    fields = {f.findtext('name'): f.findtext('bitRange')
              for f in reg.findall('./fields/field')}
    check('exact-power-register', int(peripheral.findtext('baseAddress'), 0) == 0x40021000
          and int(reg.findtext('addressOffset'), 0) == 4)
    check('distinct-MSPI1-UART1-enables', fields['PWRENMSPI1'] == '[15:15]'
          and fields['PWRENUART1'] == '[10:10]')
    source = s / 'mspi1-source-research-01'
    pins = json.loads((source / 'sources.json').read_text())['files']
    texts = {}
    for name in ('am_hal_pwrctrl.c', 'am_hal_mspi.c'):
        data = (source / name).read_bytes()
        pin = next(p for p in pins if p['path'].endswith('/' + name))
        check(name + '-pin', hashlib.sha256(data).hexdigest() == pin['sha256'])
        texts[name] = data.decode()
    power = texts['am_hal_pwrctrl.c'].split('am_hal_pwrctrl_periph_disable(', 1)[1]
    check('HAL-clears-selected-enable',
          'AM_REGVAL(pwr_ctrl.ui32PwrEnRegAddr) &= ~pwr_ctrl.ui32PeriphEnable;' in power)
    check('HAL-polls-status-with-false-condition',
          'pwr_ctrl.ui32PeriphStatus,\n                                                  false);' in power)
    mspi = texts['am_hal_mspi.c']
    start = mspi.index('case AM_HAL_SYSCTRL_DEEPSLEEP:')
    sleep = mspi[start:mspi.index('return AM_HAL_STATUS_SUCCESS;', start)]
    check('HAL-rejects-pending-queue', 'ui32NumHPEntries || pMSPIState->ui32NumCQEntries' in sleep)
    check('HAL-delays-with-XIP-enabled', 'DEV0XIP_b.XIPEN0' in sleep
          and 'am_hal_delay_us(pMSPIState->ui32XIPOffMinDelay);' in sleep)
    off = sleep.index('am_hal_pwrctrl_periph_disable(')
    clock = sleep.index('mspi_clkgen_ctrl(pMSPIState->ui32Module, false, false,')
    check('HAL-power-off-before-clock-disable', off < clock)

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    for key, bundle, delta in [('stock24', 'stock-2.4.0.24.bin', 0),
                               ('stock23', 'stock-2.3.0.24.bin', 0xbee8),
                               ('cfw', 'faceclaw-38-research-only.bin', 0xbee8)]:
        folder = s / 'mspi1-cqflags-main-02' / key
        _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
        check(key + '-original-bytes', raw == (folder / 'main.bin').read_bytes())
        log = (folder / 'renode.log').read_text()
        observed = parse_log(log)
        check(key + '-report-replay', observed == json.loads((folder / 'report.json').read_text())['observed'])
        entry, pc = 0x494e96 - delta, 0x494f3e - delta
        code = list(md.disasm(raw[entry - 0x438000:entry + 0x160 - 0x438000], entry))
        instructions = {i.address: (i.mnemonic, i.op_str) for i in code}
        check(key + '-function-entry', instructions.get(entry) == ('push', '{r3, r4, r5, lr}'))
        expected = [(-10, 'ldr', 'r0, [sp, #4]'), (-8, 'ldr', 'r1, [r0]'),
                    (-6, 'ldr', 'r0, [sp, #8]'), (-4, 'bics', 'r1, r0'),
                    (-2, 'ldr', 'r0, [sp, #4]'), (0, 'str', 'r1, [r0]')]
        check(key + '-read-clear-write', all(instructions.get(pc + d) == (mn, op)
                                               for d, mn, op in expected))
        ctx, stack = observed['register_context'], observed['stack_context']
        check(key + '-actual-stop-and-arguments', observed['pc'] == pc
              and ctx['r0'] == 0x40021004 and ctx['r1'] == 0x400 and ctx['r5'] == 17)
        check(key + '-stack-enable-status-mask', stack['base'] == ctx['r13']
              and stack['words'][1:5] == [0x40021004, 0x8000, 0x40021008, 0x8000])
        hal_delta = 0 if key == 'stock24' else 0xd3d4
        call = 0x4e935c - hal_delta
        caller_code = list(md.disasm(raw[call - 0x438000:call + 0x20 - 0x438000], call))
        caller = {i.address: (i.mnemonic, i.op_str) for i in caller_code}
        check(key + '-actual-retention-caller', caller.get(call) == ('bl', '#' + hex(entry))
              and stack['words'][9] == call + 5)
        # No conditional branch or return-value check precedes the clock helper.
        expected_after = [(4, 'movs', 'r3, #0'), (6, 'movs', 'r2, #0'),
                          (8, 'movs', 'r1, #0'), (10, 'ldr', 'r0, [r5, #4]'),
                          (12, 'bl', '#' + hex(0x4e7004 - hal_delta))]
        check(key + '-power-result-not-checked-before-clock-disable', all(
            caller.get(call + offset) == (mn, op) for offset, mn, op in expected_after))
        guard = next(g for g in observed['guards'] if g['name'] == 'guard')
        check(key + '-strict-request', guard['operation'] == 'write'
              and guard['address'] == 0x40021004 and guard['value'] == 0x400)
        pio = marker(log, 'BLACKWALL_MSPI1_PIO')
        fifo = marker(log, 'BLACKWALL_MSPI1_RDID')
        cq = marker(log, 'BLACKWALL_MSPI1_CQ_INIT')['registers']
        cfg = marker(log, 'BLACKWALL_MSPI1_CONFIG')['registers']
        xip = marker(log, 'BLACKWALL_MSPI1_XIP')
        check(key + '-quiescent-current-model', not pio['busy'] and not pio['recovering']
              and fifo['rx_entries'] == 0 and cq['672'] & 1 == 0 and cfg['256'] & 1 == 0)
        check(key + '-XIP-remains-enabled-but-no-transactions', cfg['144'] & 1 == 1
              and xip['enabled'] and not xip['backing_data'] and xip['guard_accesses'] == 0)
        (out / (key + '-power-off.asm')).write_text('\n'.join(
            f'{i.address:#x} {i.mnemonic} {i.op_str}' for i in code + caller_code) + '\n')
        cases.append(dict(case=key, entry=hex(entry), stop=hex(pc), request=hex(ctx['r1']),
                          cleared_mask='0x8000', preserved_UART1=True,
                          XIP_enabled=True, physical_external_supply_verified=False))
    report = dict(passed=True, count=len(checks), checks=checks, cases=cases,
                  scope='Static original-byte and previously captured execution audit; no new native execution or device access; off response not yet implemented')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
