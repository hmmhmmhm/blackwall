"""Check legacy SE20 four-byte frame and manufacturer device-state requirements."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from pypdf import PdfReader
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
    def check(name, value):
        if not value:
            raise ValueError(name)
        checks.append(name)
    collect(s)
    pdf = s / 'mspi1-pio-research-01/mx25u25643g-v1.1.pdf'
    check('manufacturer-PDF-pin', hashlib.sha256(pdf.read_bytes()).hexdigest() == '1488ab399222ab2040e3c56fe8ba8b3ba624f19485a66c7b3558207167be2ae5')
    pages = PdfReader(pdf).pages
    sector = ' '.join(pages[66].extract_text().split())
    wel = ' '.join(pages[24].extract_text().split())
    check('sector-size-and-address-selection', '4K-byte sector' in sector and 'Any address of the sector' in sector)
    check('self-timed-WIP-and-WEL-completion', 'self-timed Sector Erase' in sector and 'WIP sets 1' in sector and 'WEL) bit is cleared' in sector)
    check('legacy-SE-address-mode-and-protection', 'enter the 4-byte address read mode' in sector and 'BP3, BP2, BP1, BP0' in sector)
    check('WEL-clear-after-SE-completion', 'SE/SE4B command completion' in wel)
    root = ET.parse(s / 'apollo-dfp-research-01/apollo510.svd').getroot()
    per = next(p for p in root.findall('./peripherals/peripheral') if p.findtext('name') == 'MSPI0')
    fields = lambda name: {f.findtext('name'): f for r in per.findall('./registers/register') if r.findtext('name') == name for f in r.findall('./fields/field')}
    ctrl = fields('CTRL')
    check('SE-instruction-address-TX-layout', ctrl['SENDI'].findtext('bitRange') == '[6:6]' and ctrl['SENDA'].findtext('bitRange') == '[5:5]' and ctrl['TXRX'].findtext('bitRange') == '[7:7]')
    cfg = fields('DEV0CFG')
    check('four-byte-address-field', cfg['ASIZE0'].findtext('bitRange') == '[6:5]' and next(e.findtext('value') for e in cfg['ASIZE0'].findall('./enumeratedValues/enumeratedValue') if e.findtext('name') == 'A4') == '3')
    cases = []
    for key in ['stock24', 'stock23', 'cfw']:
        d = s / 'mspi1-array-main-02' / key
        log = (d / 'renode.log').read_text()
        v = parse_log(log)
        check(key + '-native-report', v == json.loads((d / 'report.json').read_text())['observed'])
        def marker(tag):
            matches = [json.loads(l.split(' ', 1)[1]) for l in log.splitlines() if l.startswith(tag + ' ')]
            if len(matches) != 1:
                raise ValueError(tag)
            return matches[0]
        regs = marker('BLACKWALL_MSPI1_CONFIG')['registers']
        guard = [g for g in v['guards'] if g['accesses']]
        check(key + '-actual-SE20-command', len(guard) == 1 and guard[0]['address'] == 0x40061000 and guard[0]['operation'] == 'write' and guard[0]['value'] == 0xe1 and regs['12'] == 0x20 and regs['8'] == 0x1fc0000)
        check(key + '-no-data-four-address-bytes', regs['132'] == 0x3010061 and regs['4'] == 0 and regs['136'] & 0x1f == 0)
        check(key + '-NOR-mode-and-WEL', marker('BLACKWALL_NOR_ADDRESS')['four_byte'] and marker('BLACKWALL_NOR_LATCH')['current'] == 0x42)
        cases.append(dict(case=key, erase_sector='0x1fc0000', actual_device_contents_known=False))
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=cases,
        scope='Source/frame contract; chosen emulator latency and power-loss behavior are not device measurements'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
