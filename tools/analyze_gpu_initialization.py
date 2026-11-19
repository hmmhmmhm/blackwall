"""Match a bounded GPU IRQ initialization signature in three pinned G2 images."""
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


def nvic_targets(raw, cs, priority_target, enable_target):
    """Check the positive-IRQ paths and their PC-relative NVIC base literals."""
    def instructions(address, size):
        if not BASE <= address <= BASE + len(raw) - size:
            raise ValueError('NVIC candidate outside image')
        return [(i.mnemonic, i.op_str) for i in cs.disasm(raw[address-BASE:address-BASE+size], address)]

    a = priority_target
    priority = instructions(a, 18)
    if priority != [('movs','r2, r0'),('sxth','r2, r2'),('cmp','r2, #0'),
                    ('bmi',f'#{a+20:#x}'),('lsls','r1, r1, #4'),
                    ('ldr.w','r2, [pc, #0x32c]'),('sxth','r0, r0'),('strb','r1, [r2, r0]')]:
        raise ValueError('Priority callee positive-IRQ path differs')
    priority_literal = ((a+10+4) & ~3) + 0x32c
    a = enable_target
    enable = instructions(a, 28)
    if enable != [('movs','r1, r0'),('sxth','r1, r1'),('cmp','r1, #0'),
                  ('bmi',f'#{a+28:#x}'),('movs','r2, #1'),('ands','r1, r0, #0x1f'),
                  ('lsls','r2, r1'),('ldr.w','r1, [pc, #0x358]'),('sxth','r0, r0'),
                  ('lsrs','r0, r0, #5'),('str.w','r2, [r1, r0, lsl #2]')]:
        raise ValueError('Enable callee positive-IRQ path differs')
    enable_literal = ((a+16+4) & ~3) + 0x358
    def literal(address):
        if not BASE <= address <= BASE + len(raw) - 4:
            raise ValueError('NVIC literal outside image')
        return struct.unpack_from('<I', raw, address-BASE)[0]
    if literal(priority_literal) != 0xe000e400 or literal(enable_literal) != 0xe000e100:
        raise ValueError('NVIC base literal differs')
    return dict(priority_target=hex(priority_target), enable_target=hex(enable_target),
                irq28_priority_byte_address='0xe000e41c', priority4_encoded_byte='0x40',
                irq28_enable_address='0xe000e100', irq28_enable_mask='0x10000000',
                scope='static positive-IRQ callee paths; not runtime NVIC execution')


def analyze(bundle, native):
    data = bundle.read_bytes()
    profile = next((k for k in ('stock_base', 'stock_current', 'cfw') if PINS[k] == hashlib.sha256(data).hexdigest()), None)
    if profile is None or native['bundle_sha256'] != PINS[profile]:
        raise ValueError('Pinned bundle/native evidence mismatch')
    raw = next(p for p in parse_bundle(data) if p.type_id == 0).payload[32:]
    if native['raw_main_sha256'] != hashlib.sha256(raw).hexdigest():
        raise ValueError('Native main differs')
    events = [g for g in native['observed']['guards'] if g['accesses']]
    if len(events) != 1 or events[0]['accesses'] != 1 or (events[0]['address'], events[0]['width'], events[0]['operation'], events[0]['value']) != (0x400900f8, 4, 'write', 0):
        raise ValueError('Expected first GPU IRQ-clear boundary absent')
    pc = native['observed']['pc']; helper = pc-6
    if not BASE <= helper < pc < BASE+len(raw):
        raise ValueError('Writer lies outside pinned image')
    cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    writer = [(i.mnemonic, i.op_str) for i in cs.disasm(raw[helper-BASE:pc-BASE+2], helper)]
    if len(writer) != 4 or [i[0] for i in writer] != ['ldr','ldr','adds','str'] or writer[2:] != [('adds','r0, r0, r2'),('str','r1, [r0]')]:
        raise ValueError('Unverified register-writer signature')
    cs.skipdata = True
    matches = []; calls = 0
    for address, size, mnemonic, operands in cs.disasm_lite(raw, BASE):
        if mnemonic != 'bl' or operands != hex(helper).replace('0x','#0x'):
            continue
        calls += 1
        before = [(i.mnemonic,i.op_str) for i in cs.disasm(raw[address-BASE-4:address-BASE], address-4)]
        after = list(cs.disasm(raw[address-BASE+size:address-BASE+size+18], address+size))
        if before != [('movs','r1, #0'),('movs','r0, #0xf8')] or len(after) < 5:
            continue
        observed = [(i.mnemonic,i.op_str) for i in after[:5]]
        if observed[0][0] != 'movs' or not observed[0][1].startswith('r1, #') or observed[1] != ('movs','r0, #0x1c') or observed[2][0] != 'bl' or observed[3] != ('movs','r0, #0x1c') or observed[4][0] != 'bl':
            continue
        priority = int(observed[0][1].split('#')[1], 0)
        if priority != 4:
            raise ValueError('Unexpected IRQ priority argument')
        callees = nvic_targets(raw, cs, int(observed[2][1][1:], 0), int(observed[4][1][1:], 0))
        matches.append(dict(call=hex(address), irq=28, priority=priority,
            nvic_callees=callees,
            context=[f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in cs.disasm(raw[address-BASE-6:address-BASE+size+18],address-6)]))
    return dict(profile=profile,bundle_sha256=PINS[profile],main_sha256=native['raw_main_sha256'],writer=hex(helper),
                observed_write_pc=hex(pc),candidate_writer_calls=calls,irq_initialization_matches=matches,
                unique_signature_matched=len(matches)==1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('inputs', type=Path)
    p.add_argument('comparison', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    comparison = json.loads(args.comparison.read_text())
    if not comparison['passed'] or len(comparison['rows']) != 6:
        raise ValueError('Need completed six-case native comparison')
    rows = []
    for key in ('stock_base','stock_current','cfw'):
        choices = [r for r in comparison['rows'] if r['case'] == key+'-lp-active']
        if len(choices)!=1 or not choices[0]['passed']: raise ValueError('Missing LP evidence')
        frozen = Path(choices[0]['native']).read_bytes()
        if hashlib.sha256(frozen).hexdigest()!=choices[0]['native_sha256']: raise ValueError('Native evidence changed')
        rows.append(analyze(args.inputs/PROFILES[key]['file'],json.loads(frozen)))
    args.output.mkdir(mode=0o700)
    report=dict(scope='static signature matching anchored to observed GPU write; not recovered symbols, SDK version identity or hardware proof',
                passed=all(r['unique_signature_matched'] for r in rows),rows=rows,
                comparison_sha256=hashlib.sha256(args.comparison.read_bytes()).hexdigest(),hardware_validated=False,boot_verified=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'profiles':[(r['profile'],r['irq_initialization_matches']) for r in rows]}))
    if not report['passed']:raise SystemExit(1)


if __name__ == '__main__':
    main()
