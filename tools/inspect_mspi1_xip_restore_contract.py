"""Check pinned field metadata and original atomic XIP retention restore stores."""
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
    peripheral = next(p for p in root.findall('./peripherals/peripheral') if p.findtext('name') == 'MSPI0')
    reg = next(r for r in peripheral.findall('./registers/register') if r.findtext('name') == 'DEV0XIP')
    check('XIP-offset-mask-reset', int(reg.findtext('addressOffset'), 0) == 0x90
          and int(reg.findtext('resetMask'), 0) == 0x3fffffd and int(reg.findtext('resetValue'), 0) == 0)
    fields = {f.findtext('name'): f for f in reg.findall('./fields/field')}
    def enums(name):
        return {int(v.findtext('value'), 0) for v in fields[name].findall('./enumeratedValues/enumeratedValue')}
    check('documented-mode-and-ack-values', enums('XIPMIXED0') == {0, 1, 3, 5, 7, 9, 11}
          and enums('XIPACK0') == {0, 2, 3})
    check('field-layout', fields['XIPMIXED0'].findtext('bitRange') == '[11:8]'
          and fields['XIPACK0'].findtext('bitRange') == '[3:2]'
          and fields['XIPEN0'].findtext('bitRange') == '[0:0]')
    source = s / 'mspi1-source-research-01'
    hal = (source / 'am_hal_mspi.c').read_bytes()
    pin = next(p for p in json.loads((source / 'sources.json').read_text())['files'] if p['path'].endswith('/am_hal_mspi.c'))
    check('HAL-pin', hashlib.sha256(hal).hexdigest() == pin['sha256'])
    text = hal.decode()
    check('HAL-whole-word-XIP-restore', 'MSPIn(pMSPIState->ui32Module)->DEV0XIP = pMSPIState->registerState.regDEV0XIP;' in ' '.join(text.split()))
    for key, bundle, delta in [('stock24', 'stock-2.4.0.24.bin', 0), ('stock23', 'stock-2.3.0.24.bin', 0xd3d4), ('cfw', 'faceclaw-38-research-only.bin', 0xd3d4)]:
        d = s / 'mspi1-power-off-main-02' / key
        _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
        check(key + '-original-bytes', raw == (d / 'main.bin').read_bytes())
        v = parse_log((d / 'renode.log').read_text())
        check(key + '-report-replay', v == json.loads((d / 'report.json').read_text())['observed'])
        entry, pc = 0x4e8f8c - delta, 0x4e9054 - delta
        code = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(raw[entry - 0x438000:pc + 8 - 0x438000], entry))
        ins = {i.address: (i.mnemonic, i.op_str) for i in code}
        check(key + '-entry', ins.get(entry) == ('push', '{r4, r5, r6, lr}'))
        check(key + '-actual-whole-word-restore', ins.get(pc - 4) == ('ldr.w', 'r2, [r5, #0x874]')
              and ins.get(pc) == ('str.w', 'r2, [r1, #0x90]'))
        stores = [(0x4e901c, 0x80), (0x4e902a, 0x84), (0x4e9038, 0x88), (0x4e9046, 0x8c)]
        check(key + '-prior-device-restore-stores', all(ins.get(addr - delta) == ('str.w', f'r2, [r1, #{hex(offset)}]') for addr, offset in stores))
        ctx = v['register_context']
        check(key + '-actual-request', v['pc'] == pc and ctx['r1'] == 0x40061000 and ctx['r2'] == 0xed)
        check(key + '-documented-request-fields', ((ctx['r2'] >> 8) & 15) in enums('XIPMIXED0')
              and ((ctx['r2'] >> 2) & 3) in enums('XIPACK0') and ctx['r2'] & ~0x3fffffd == 0)
        (out / (key + '-restore.asm')).write_text('\n'.join(f'{i.address:#x} {i.mnemonic} {i.op_str}' for i in code) + '\n')
        cases.append(dict(case=key, pc=hex(pc), state_offset='0x874', value=hex(ctx['r2']), hardware_verified=False))
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=cases,
        scope='Static source and previous native observation only; no XIP data or bus timing proof'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
