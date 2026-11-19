"""Check bounded QREAD4B geometry against exact register metadata and original requests."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from inspect_mspi1_config_contract import collect
from native_replay import parse_log


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    s, out = a.simulator, a.output
    out.mkdir(mode=0o700)
    checks = []
    def check(name, condition):
        if not condition:
            raise ValueError(name)
        checks.append(name)
    collect(s)
    root = ET.parse(s / 'apollo-dfp-research-01/apollo510.svd').getroot()
    per = next(p for p in root.findall('./peripherals/peripheral') if p.findtext('name') == 'MSPI0')
    regs = {r.findtext('name'): r for r in per.findall('./registers/register')}
    fields = lambda name: {f.findtext('name'): f for f in regs[name].findall('./fields/field')}
    ctrl = fields('CTRL')
    check('instruction-address-RX-turnaround-layout', ctrl['SENDI'].findtext('bitRange') == '[6:6]'
          and ctrl['SENDA'].findtext('bitRange') == '[5:5]' and ctrl['TXRX'].findtext('bitRange') == '[7:7]'
          and ctrl['ENTURN'].findtext('bitRange') == '[10:10]' and ctrl['XFERBYTES'].findtext('bitRange') == '[31:16]')
    modes = {x.findtext('name'): int(x.findtext('value'), 0) for x in fields('CTRL1')['PIOMIXED'].findall('./enumeratedValues/enumeratedValue')}
    check('PIO-D4-exact-value', modes['D4'] == 5 and fields('CTRL1')['PIOMIXED'].findtext('bitRange') == '[3:0]')
    check('FIFO-entry-unit-is-words', fields('RXENTRIES')['RXENTRIES'].findtext('bitRange') == '[5:0]'
          and '32-bit words' in fields('RXENTRIES')['RXENTRIES'].findtext('description'))
    ddr = fields('DEV0DDR')
    for bit, name in enumerate(['EMULATEDDR0', 'QUADDDR0', 'ENABLEDQS0', 'DQSSYNCNEG0', 'ENABLEFINEDELAY0']):
        check('unmodeled-control-' + name, ddr[name].findtext('bitRange') == f'[{bit}:{bit}]')
    header = (s / 'mspi1-source-research-01/am_hal_mspi.h').read_bytes()
    check('HAL-header-pin', hashlib.sha256(header).hexdigest() == '2a682bb7c1618982d6a802f3220a38696cd594c89d90e64b1a698d226b0a557b')
    check('HAL16-word-FIFO-capacity', '#define AM_HAL_MSPI_MAX_FIFO_SIZE               16' in header.decode())
    pdf = s / 'mspi1-pio-research-01/mx25u25643g-v1.1.pdf'
    check('manufacturer-PDF-pin', hashlib.sha256(pdf.read_bytes()).hexdigest() == '1488ab399222ab2040e3c56fe8ba8b3ba624f19485a66c7b3558207167be2ae5')
    rows = []
    for key in ['stock24', 'stock23', 'cfw']:
        d = s / 'mspi1-continuous-status-main-01' / key
        log = (d / 'renode.log').read_text()
        v = parse_log(log)
        check(key + '-native-report', v == json.loads((d / 'report.json').read_text())['observed'])
        def marker(tag):
            matches = [json.loads(l.split(' ', 1)[1]) for l in log.splitlines() if l.startswith(tag + ' ')]
            if len(matches) != 1:
                raise ValueError(tag)
            return matches[0]
        cfg = marker('BLACKWALL_MSPI1_CONFIG')['registers']
        guard = [g for g in v['guards'] if g['accesses']]
        check(key + '-exact-original-array-request', len(guard) == 1 and guard[0]['address'] == 0x40061000
              and guard[0]['operation'] == 'write' and guard[0]['value'] == 0x100461 and cfg['12'] == 0x6c and cfg['8'] == 0x1fc0000)
        check(key + '-serial-instruction-quad-data', cfg['4'] == 5 and cfg['132'] & ~0x1c00000 == 0x10861 and cfg['136'] & 0x1f == 0)
        check(key + '-QE-ready-and-word-capacity', marker('BLACKWALL_NOR_LATCH')['current'] & 0x41 == 0x40
              and ((guard[0]['value'] >> 16) + 3) // 4 <= 16)
        rows.append(dict(case=key, receive_bytes=16, receive_words=4, FIFO_max_words=16,
                         logical_lane_configuration='1-1-4', pin_routing_verified=False))
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=rows,
        scope='Register and request geometry only; no physical lane/timing or chip revision proof'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
