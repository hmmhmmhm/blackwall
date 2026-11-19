"""Inspect UART1 IRQ16 in pinned images at a verified IER write boundary."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import capstone
from audit_assets import PINS
from blackwall_package import parse_bundle
from emulate_codec_query import PROFILES

BASE = 0x438000


def analyze(bundle, native):
    data = bundle.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest not in {PINS[k] for k in ('stock_base', 'stock_current', 'cfw')}:
        raise ValueError('Unreviewed image')
    if native['bundle_sha256'] != digest:
        raise ValueError('Native/image mismatch')
    raw = next(c for c in parse_bundle(data) if c.type_id == 0).payload[32:]
    if hashlib.sha256(raw).hexdigest() != native['raw_main_sha256']:
        raise ValueError('Main mismatch')
    guards = [g for g in native['observed']['guards'] if g['accesses']]
    if len(guards) != 1 or tuple(guards[0][k] for k in ('address','value','width','operation')) != (0x4003a038,0x471,4,'write'):
        raise ValueError('Expected UART1 interrupt-mask boundary')
    cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)

    def instructions(address, size):
        if not BASE <= address <= BASE + len(raw) - size:
            raise ValueError('Code outside main')
        return list(cs.disasm(raw[address-BASE:address-BASE+size], address))

    vector = struct.unpack_from('<I', raw, (16+16)*4)[0]
    if not vector & 1:
        raise ValueError('Expected Thumb vector')
    wrapper = instructions(vector & ~1, 22)
    if (len(wrapper) != 8 or (wrapper[5].mnemonic,wrapper[5].op_str) != ('movs','r0, #1')
            or wrapper[6].mnemonic != 'bl' or wrapper[7].mnemonic != 'pop'):
        raise ValueError('UART1 vector/module wrapper differs')
    common = int(wrapper[6].op_str[1:], 0)
    common_code = instructions(common, 120)
    calls = [int(i.op_str[1:], 0) for i in common_code if i.mnemonic == 'bl']
    if len(calls) != 5:
        raise ValueError('UART common handler call structure differs')
    registers = native['observed'].get('register_context')
    context = instructions((registers['r14'] & ~1)-40, 100) if registers else None
    def text(items):
        return [f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in items]
    return dict(bundle_sha256=digest,main_sha256=native['raw_main_sha256'],irq=16,
                vector=hex(vector),wrapper=text(wrapper),common=hex(common),
                common_code=text(common_code),common_callees=[dict(address=hex(a),code=text(instructions(a,64))) for a in calls[:3]],
                ier_call_context=text(context) if context is not None else None,hardware_validated=False,
                scope='bounded static inspection of actual main; no recovered symbol or physical ISR claim')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    rows = []
    for key,name in [('stock_current','stock24'),('stock_base','stock23'),('cfw','cfw')]:
        native = json.loads((args.simulator/f'uart1-clock-main-{name}-01/report.json').read_text())
        rows.append(analyze(args.simulator/'inputs/verified-01'/PROFILES[key]['file'], native))
    args.output.mkdir(mode=0o700)
    (args.output/'report.json').write_text(json.dumps(dict(passed=True,rows=rows,boot_verified=False,hardware_validated=False),indent=2)+'\n')
    print(json.dumps(dict(passed=True,irq16_vectors=[r['vector'] for r in rows])))


if __name__ == '__main__':
    main()
