"""Verify original TX/page-program framing and pinned source requirements."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from pypdf import PdfReader
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from inspect_mspi1_config_contract import collect
from native_replay import parse_log
from pinned_main import load_pinned_main


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    s, out = a.simulator, a.output
    out.mkdir(mode=0o700)
    checks, rows = [], []
    def check(name, value):
        if not value:
            raise ValueError(name)
        checks.append(name)
    collect(s)
    pdf = s / 'mspi1-pio-research-01/mx25u25643g-v1.1.pdf'
    check('manufacturer-PDF-pin', hashlib.sha256(pdf.read_bytes()).hexdigest() == '1488ab399222ab2040e3c56fe8ba8b3ba624f19485a66c7b3558207167be2ae5')
    text = ' '.join(PdfReader(pdf).pages[70].extract_text().split())
    check('program-zero-bits-and-page-wrap', 'programming memory bits to "0"' in text and 'wrap to the beginning of the selected page' in text and 'One to 256 bytes' in text)
    check('program-WIP-and-WEL-completion', 'WIP sets during the tPP timing' in text and 'WEL) bit is cleared' in text)
    root = ET.parse(s / 'apollo-dfp-research-01/apollo510.svd').getroot()
    per = next(p for p in root.findall('./peripherals/peripheral') if p.findtext('name') == 'MSPI0')
    regs = {r.findtext('name'): r for r in per.findall('./registers/register')}
    check('TX-register-offsets', int(regs['TXFIFO'].findtext('addressOffset'), 0) == 0x10 and int(regs['TXENTRIES'].findtext('addressOffset'), 0) == 0x18)
    check('TX-entry-unit', 'words in TX FIFO' in regs['TXENTRIES'].findtext('description'))
    src = s / 'mspi1-source-research-01'
    manifest = json.loads((src / 'sources.json').read_text())
    check('HAL-commit', manifest['commit'] == '61b293a49db34030c545f99101f7ebf6a3050314')
    for filename in ['am_hal_mspi.c', 'am_hal_mspi.h']:
        data = (src / filename).read_bytes()
        pin = next(f for f in manifest['files'] if f['path'].endswith('/' + filename))
        check(filename + '-SHA256', hashlib.sha256(data).hexdigest() == pin['sha256'])
    hal = (src / 'am_hal_mspi.c').read_text()
    check('HAL-write-then-capacity-poll', 'MSPIn(ui32Module)->TXFIFO = pui32Data[ui32Index];' in hal and '(uint32_t)&MSPIn(ui32Module)->TXENTRIES' in hal)
    check('HAL-FIFO16words', '#define AM_HAL_MSPI_MAX_FIFO_SIZE               16' in (src / 'am_hal_mspi.h').read_text())
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    for key, bundle, delta in [('stock24', 'stock-2.4.0.24.bin', 0), ('stock23', 'stock-2.3.0.24.bin', 0xd3d4), ('cfw', 'faceclaw-38-research-only.bin', 0xd3d4)]:
        d = s / 'mspi1-erase-main-01' / key
        _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
        check(key + '-original-main', raw == (d / 'main.bin').read_bytes())
        log = (d / 'renode.log').read_text()
        v = parse_log(log)
        check(key + '-native-report', v == json.loads((d / 'report.json').read_text())['observed'])
        cfg = next(json.loads(l.split(' ', 1)[1])['registers'] for l in log.splitlines() if l.startswith('BLACKWALL_MSPI1_CONFIG '))
        guards = [g for g in v['guards'] if g['accesses']]
        check(key + '-PP16-byte-original-frame', len(guards) == 1 and guards[0]['value'] == 0x1000e1 and cfg['12'] == 2 and cfg['8'] == 0x1fc0000 and cfg['132'] == 0x3010061)
        entry, store, call = 0x4e8944 - delta, 0x4e8a46 - delta, 0x4e8a70 - delta
        code = list(md.disasm(raw[entry - 0x438000:call + 4 - 0x438000], entry))
        ins = {i.address: (i.mnemonic, i.op_str) for i in code}
        check(key + '-CTRL-before-TX-helper', ins.get(store) == ('str.w', 'lr, [r2]') and ins.get(call) == ('bl', '#' + hex(0x4e641e - delta)))
        stack, ctx = v['stack_context'], v['register_context']
        index = (ctx['r1'] - stack['base']) // 4
        check(key + '-transaction-buffer-bounds', ctx['r1'] % 4 == 0 and 0 <= index <= 26 and stack['words'][index] == 16 and 0x20000000 <= stack['words'][index + 5] <= 0x20380000 - 16)
        rows.append(dict(case=key, source_buffer=hex(stack['words'][index + 5]), control='0x1000e1', data_bytes=16, physical_timing_verified=False))
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=rows,
        scope='Original framing and source geometry; no physical program timing or power-loss validation'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
