"""Inspect the three pinned original font initializers, without supplying XIP data."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM, ARM_REG_PC
from blackwall_package import parse_bundle
from native_replay import parse_log, validate_assets
from pinned_main import load_pinned_main


def inspect(raw, read_pc, check):
    base = 0x438000
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    md.detail = True
    entry = read_pc - 0x1a
    instructions = []
    for i in md.disasm(raw[entry-base:entry-base+0x200], entry):
        instructions.append(i)
        if i.mnemonic == 'pop' and i.op_str == '{r1, r2, r3, r4, r5, pc}':
            break
    check('initializer-entry-and-end', instructions[0].mnemonic == 'push'
          and instructions[0].op_str == '{r1, r2, r3, r4, r5, lr}'
          and instructions[-1].mnemonic == 'pop')
    by_pc = {i.address: i for i in instructions}

    def literal(i):
        mem = next(o.mem for o in i.operands if o.type == ARM_OP_MEM and o.mem.base == ARM_REG_PC)
        return struct.unpack_from('<I', raw, ((i.address+4) & ~3)+mem.disp-base)[0]

    def target(i):
        return int(i.op_str.removeprefix('#'), 0)

    banks = []
    for n, i in enumerate(instructions):
        if i.mnemonic != 'cmp.w' or i.op_str != 'r0, #0x5a5a5a5a':
            continue
        load, pointer, branch = instructions[n-1], instructions[n-2], instructions[n+1]
        check('header-load', load.mnemonic == 'ldr' and load.op_str == 'r0, [r4]')
        check('invalid-magic-branch', branch.mnemonic == 'bne')
        invalid = target(branch)
        tail = [x for x in instructions if invalid <= x.address]
        clear_index = next(j for j, x in enumerate(tail) if x.mnemonic == 'str' and x.op_str == 'r0, [r1, #0x18]')
        clear = tail[clear_index]
        check('invalid-clears-descriptor', tail[clear_index-2].mnemonic == 'movs'
              and tail[clear_index-2].op_str == 'r0, #0')
        font = literal(tail[clear_index-1])
        valid = [x for x in instructions if branch.address < x.address < invalid]
        check('descriptor-from-header34', any(x.mnemonic == 'ldr' and x.op_str == 'r0, [r4, #0x34]' for x in valid))
        check('header38-height', any(x.mnemonic == 'ldrh' and '#0x38]' in x.op_str for x in valid)
              and any(x.mnemonic == 'str' and '#0xc]' in x.op_str for x in valid))
        check('header3a-baseline', any(x.mnemonic == 'ldrh' and '#0x3a]' in x.op_str for x in valid)
              and any(x.mnemonic == 'str' and '#0x10]' in x.op_str for x in valid))
        check('ffff-attribute-sentinel', any(x.mnemonic == 'movw' and x.op_str == 'r0, #0xffff' for x in valid))
        banks.append(dict(address=hex(literal(pointer)), read_pc=hex(load.address),
                          invalid_branch=hex(invalid), descriptor_clear_pc=hex(clear.address),
                          font_object=hex(font)))
    check('two-external-banks', [b['address'] for b in banks] == ['0x80100000', '0x80700000'])
    check('natural-return-one', instructions[-2].mnemonic == 'movs' and instructions[-2].op_str == 'r0, #1')
    check('release-before-return', instructions[-3].mnemonic == 'bl')
    check('first-header-is-native-frontier', banks[0]['read_pc'] == hex(read_pc))
    # Locate the direct parent in the nearby code, then its two chain calls/config literals.
    candidates = []
    for address in range(instructions[-1].address+2, entry+0x240, 2):
        i = next(md.disasm(raw[address-base:address-base+4], address), None)
        if i and i.mnemonic == 'bl' and target(i) == entry:
            candidates.append(i)
    check('unique-nearby-parent', len(candidates) == 1)
    parent = candidates[0]
    nearby = list(md.disasm(raw[parent.address-base:parent.address+0xbe-base], parent.address))
    calls = [i for i in nearby if i.address > parent.address and i.mnemonic == 'bl']
    builder = target(calls[0])
    chain_calls = [i for i in calls if target(i) == builder]
    check('two-chain-builder-calls', len(chain_calls) == 2)
    config = []
    for call in chain_calls:
        idx = nearby.index(call)
        arg = nearby[idx-1]
        check('four-entry-chain-request', nearby[idx-2].mnemonic == 'movs'
              and nearby[idx-2].op_str == 'r1, #4'
              and arg.mnemonic == 'ldr' and arg.op_str.startswith('r0, [pc,'))
        config.append(hex(literal(arg)))
    return dict(initializer=hex(entry), return_pc=hex(instructions[-1].address),
                banks=banks, chain_builder=hex(builder), chain_configs=config,
                parent_call=hex(parent.address), release=hex(target(instructions[-3])))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    a.output.mkdir(mode=0o700)
    checks, cases = [], []
    def check(name, valid):
        if not valid:
            raise ValueError(name)
        checks.append(name)
    for key, filename in [('stock24', 'stock-2.4.0.24.bin'), ('stock23', 'stock-2.3.0.24.bin'), ('cfw', 'faceclaw-38-research-only.bin')]:
        bundle = (a.simulator/'inputs/verified-01'/filename).read_bytes()
        profile, raw = load_pinned_main(bundle)
        parts = parse_bundle(bundle)
        check(key+'-six-validated-components', len(parts) == 6)
        check(key+'-main-component-exact', next(c for c in parts if c.type_id == 0).payload[32:] == raw)
        meta = None
        for level in ['low', 'high']:
            d = a.simulator/'timer0-shared-main-02'/(key+'-'+level)
            r = json.loads((d/'report.json').read_text())
            v = parse_log((d/'renode.log').read_text())
            validate_assets(d, json.loads((d/'derived-inputs.json').read_text())['derived'])
            check(key+'-'+level+'-native-report', v == r['observed'])
            check(key+'-'+level+'-unmodified-main', (d/'main.bin').read_bytes() == raw)
            check(key+'-'+level+'-first-header-register', v['register_context']['r4'] == 0x80100000)
            current = inspect(raw, v['pc'], lambda n, ok: check(key+'-'+level+'-'+n, ok))
            check(key+'-'+level+'-same-contract', meta is None or current == meta)
            meta = current
        cases.append(dict(case=key, profile=profile, raw_sha256=hashlib.sha256(raw).hexdigest(),
                          components=[dict(name=c.name, bytes=len(c.payload)) for c in parts], **meta))
    sources = a.simulator/'xip-font-source-research-01'
    manifest = json.loads((sources/'sources.json').read_text())
    # These are supporting developer research, not substitute hardware evidence.
    check('reference-commit', manifest['commit'] == '67b5d0f1cef6031541cceccf80c57494663d1600')
    for f in manifest['files']:
        data = (sources/f['local']).read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        check('reference-'+f['path'], len(data) == f['bytes']
              and hashlib.sha256(data).hexdigest() == f['sha256'] and blob == f['git_blob'])
    result = dict(passed=True, count=len(checks), checks=checks, cases=cases,
                  external_font_asset_available=False, external_font_format_complete=False,
                  native_execution_added=False, hardware_accessed=False,
                  boot_verified=False, display_verified=False,
                  scope='Static original initializer contract and six previous native frontiers; no XIP bytes supplied or missing-font fallback executed')
    (a.output/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, count=len(checks), cases=cases)))


if __name__ == '__main__':
    main()
