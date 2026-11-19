"""Audit the post-retention RDSR frame without inferring physical pin compatibility."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
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
    checks, cases = [], []
    def check(name, value):
        if not value:
            raise ValueError(name)
        checks.append(name)
    collect(s)
    root = ET.parse(s / 'apollo-dfp-research-01/apollo510.svd').getroot()
    per = next(p for p in root.findall('./peripherals/peripheral') if p.findtext('name') == 'MSPI0')
    regs = {r.findtext('name'): r for r in per.findall('./registers/register')}
    fields = {f.findtext('name'): f for f in regs['DEV0CFG'].findall('./fields/field')}
    check('separate-IO-warning-preserved', fields['SEPIO0'].findtext('bitRange') == '[25:25]'
          and 'separate MOSI and MISO' in fields['SEPIO0'].findtext('description'))
    check('turnaround-qualified-by-CTRL', fields['TURNAROUND0'].findtext('bitRange') == '[13:8]'
          and 'ENTURN' in fields['TURNAROUND0'].findtext('description'))
    pdf = s / 'mspi1-pio-research-01/mx25u25643g-v1.1.pdf'
    check('manufacturer-PDF-pin', hashlib.sha256(pdf.read_bytes()).hexdigest() == '1488ab399222ab2040e3c56fe8ba8b3ba624f19485a66c7b3558207167be2ae5')
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    for key, bundle, hal_delta, driver_delta in [('stock24', 'stock-2.4.0.24.bin', 0, 0), ('stock23', 'stock-2.3.0.24.bin', 0xd3d4, 0x4d18), ('cfw', 'faceclaw-38-research-only.bin', 0xd3d4, 0x4d18)]:
        d = s / 'mspi1-xip-restore-main-02' / key
        _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
        check(key + '-original-bytes', raw == (d / 'main.bin').read_bytes())
        log = (d / 'renode.log').read_text()
        v = parse_log(log)
        check(key + '-report-replay', v == json.loads((d / 'report.json').read_text())['observed'])
        cfgs = [json.loads(l.split(' ', 1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_MSPI1_CONFIG ')]
        check(key + '-one-config-marker', len(cfgs) == 1)
        cfg = cfgs[0]['registers']
        guard = [g for g in v['guards'] if g['accesses']]
        check(key + '-actual-status-frame', len(guard) == 1 and guard[0]['address'] == 0x40061000
              and guard[0]['operation'] == 'write' and guard[0]['value'] == 0x10441 and cfg['12'] == 5 and cfg['132'] == 0x1010861)
        control, config = guard[0]['value'], cfg['132']
        check(key + '-one-byte-RX-instruction-no-address', control >> 16 == 1 and control & 0xc0 == 0x40 and control & 0x20 == 0)
        check(key + '-one-byte-turnaround-and-nonseparate-IO', control & 0x400 != 0
              and (config >> 8) & 63 == 8 and config & 0x2000000 == 0)
        check(key + '-serial-I8-divider1-mode0', config & 31 == 1 and config & 0x80 == 0
              and (config >> 16) & 63 == 1 and config & 0xc000 == 0)
        check(key + '-exact-stop-PC', v['pc'] == 0x4e8a46 - hal_delta)
        helper = 0x47b750 - driver_delta
        ins = {i.address: (i.mnemonic, i.op_str) for i in md.disasm(raw[helper - 0x438000:helper + 0x80 - 0x438000], helper)}
        check(key + '-original-RDSR-helper', ins.get(helper) == ('push', '{r0, r1, r2, r3, r4, lr}')
              and ins.get(helper + 0x16) == ('movs', 'r0, #5')
              and ins.get(helper + 0x18) == ('bl', '#' + hex(0x47b5e0 - driver_delta)))
        check(key + '-helper-return-in-stack', helper + 0x1d in v['stack_context']['words'])
        cases.append(dict(case=key, control=hex(control), config=hex(config), skipped_status_bytes=1,
                          physical_pins_verified=False, physical_sampling_verified=False))
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=cases,
        scope='Logical repeated status hypothesis only; separate-IO mismatch is explicit, not resolved by datasheet framing'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
