"""Find bounded GPU ring setup candidates; no firmware or GPU execution."""
import argparse
import hashlib
import json
from pathlib import Path

import capstone
from audit_assets import PINS
from blackwall_package import parse_bundle
from emulate_codec_query import PROFILES

BASE = 0x438000


def analyze(bundle, anchor):
    data = bundle.read_bytes()
    if hashlib.sha256(data).hexdigest() != PINS[anchor['profile']] or anchor['bundle_sha256'] != PINS[anchor['profile']]:
        raise ValueError('Pinned input/anchor mismatch')
    raw = next(p for p in parse_bundle(data) if p.type_id == 0).payload[32:]
    if hashlib.sha256(raw).hexdigest() != anchor['main_sha256']:
        raise ValueError('Main/anchor mismatch')
    writer = anchor['writer']
    cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    cs.skipdata = True
    candidates = []
    for address, size, mnemonic, operands in cs.disasm_lite(raw, BASE):
        if mnemonic != 'bl' or operands != '#'+writer:
            continue
        before = [(i.mnemonic, i.op_str) for i in cs.disasm(raw[address-BASE-6:address-BASE], address-6)]
        if before != [('movs','r1, #0'),('mov.w','r0, #0x148')]:
            continue
        after = list(cs.disasm(raw[address-BASE+size:address-BASE+size+34],address+size))
        ops = [(i.mnemonic,i.op_str) for i in after]
        expected = [('ldr','r1, [r4, #8]'),('movs','r0, #0xec'),('orr','r1, r1, #6'),
                    ('bl','#'+writer),('ldr','r1, [r4, #8]'),('movs','r0, #0xf0'),
                    ('bl','#'+writer),('ldr','r1, [r4, #0x10]'),('movs','r0, #0xf4'),
                    ('bl','#'+writer),('movs','r0, #0'),('add','sp, #4'),('pop','{r4, r5, r6, r7, pc}')]
        if ops != expected:
            continue
        candidates.append(dict(call=hex(address),ordered_register_offsets=['0x148','0xec','0xf0','0xf4'],
            arguments=['0','descriptor[8] | 6','descriptor[8]','descriptor[16]'],
            context=[f'{i.address:x}: {i.mnemonic} {i.op_str}' for i in after],
            scope='linear static candidate; descriptor field meanings and hardware side effects not proven'))
    if len(candidates) != 1:
        raise ValueError(f'Expected one bounded setup candidate: {len(candidates)}')
    return dict(profile=anchor['profile'],bundle_sha256=anchor['bundle_sha256'],main_sha256=anchor['main_sha256'],candidates=candidates)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('inputs',type=Path)
    p.add_argument('initialization_report',type=Path)
    p.add_argument('output',type=Path)
    args = p.parse_args()
    source = args.initialization_report.read_bytes()
    anchors = json.loads(source)
    if not anchors['passed'] or {r['profile'] for r in anchors['rows']} != {'stock_base','stock_current','cfw'}:
        raise ValueError('Need three-profile verified initialization report')
    rows = [analyze(args.inputs/PROFILES[r['profile']]['file'],r) for r in anchors['rows']]
    args.output.mkdir(mode=0o700)
    report=dict(passed=True,scope='static ring setup call-pattern candidates only',rows=rows,
                initialization_report_sha256=hashlib.sha256(source).hexdigest(),boot_verified=False,hardware_validated=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'profiles':len(rows)}))


if __name__ == '__main__':
    main()
