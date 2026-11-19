"""Restore a measured main SRAM region in synthetic letter fixtures, not hardware."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from inspect_ambiq_target import BASE, decode
from native_replay import parse_log, validate_assets
from pinned_main import load_pinned_main


def sha(data):
    return hashlib.sha256(data).hexdigest()


def discover_blend(raw):
    signature = bytes.fromhex('2de9f8438cb0884616001c00')
    if raw.count(signature) != 1:
        raise ValueError('Ambiguous glyph helper')
    helper = BASE + raw.index(signature)
    wrapper = next(i.operands[0].imm for i in decode(raw, helper, 0x50) if i.mnemonic == 'bl')
    cache = next(i.operands[0].imm for i in decode(raw, wrapper, 0x16) if i.mnemonic == 'bl')
    core = [i.operands[0].imm for i in decode(raw, cache, 0x70) if i.mnemonic == 'bl'][-1]
    body = decode(raw, core, 0xac)
    literals = [i for i in body if i.mnemonic.startswith('ldr') and 'pc' in i.op_str]
    addresses = [struct.unpack_from('<I', raw, ((i.address + 4) & ~3) + i.operands[1].mem.disp - BASE)[0]
                 for i in literals]
    if len(addresses) != 2 or addresses[0] != addresses[1]:
        raise ValueError('Unexpected Nema flags loads')
    if [(body[j].mnemonic, body[j].op_str) for j in (3, 4)] != [
            ('ldr.w', 'r1, [pc, #0x540]'), ('ldrb', 'r0, [r1, #1]')]:
        raise ValueError('Unexpected Nema flag consumer')
    if not 0x20000000 <= addresses[0] < 0x20080000 - 64:
        raise ValueError('Nema state is outside fixture SRAM')
    return dict(helper=helper, wrapper=wrapper, cache=cache, core=core, region=addresses[0])


def validate_region(simulator, case, raw, snapshot, sram):
    patch = snapshot.get('nema_state_region')
    contract = discover_blend(raw)
    source = simulator / 'nema-capability-main-01' / case
    if (not patch or patch['contract'] != contract
            or patch['main_capture'] != str(source.relative_to(simulator))):
        raise ValueError('Missing canonical Nema state; run prepare_nema_state_captures.py first')
    for name, expected in patch['source_hashes'].items():
        if sha((source / name).read_bytes()) != expected:
            raise ValueError('Nema state source changed')
    required = {'report.json', 'renode.log', 'plan.json', 'derived-inputs.json'}
    if set(patch['source_hashes']) != required:
        raise ValueError('Incomplete Nema state provenance')
    capture = json.loads((source / 'report.json').read_text())
    plan = json.loads((source / 'plan.json').read_text())
    marker = 'BLACKWALL_CANDIDATE_' + plan['id'] + ' '
    diagnostics = [json.loads(line[len(marker):]) for line in (source / 'renode.log').read_text().splitlines()
                   if line.startswith(marker)]
    if diagnostics != [capture['diagnostics']]:
        raise ValueError('Nema state diagnostics differ from native log')
    validate_assets(source, json.loads((source / 'derived-inputs.json').read_text())['derived'])
    if (not capture['passed'] or not capture['semantic_validation']['passed']
            or parse_log((source / 'renode.log').read_text()) != capture['observed']
            or (source / 'main.bin').read_bytes() != raw or not capture['diagnostics']['paused']):
        raise ValueError('Unverified Nema state source')
    region = next(r for r in capture['diagnostics']['regions'] if r['base'] == contract['region'])
    data = struct.pack('<16I', *region['words'])
    offset = contract['region'] - 0x20000000
    if patch['after'] != data.hex() or sram[offset:offset + 64] != data:
        raise ValueError('Fixture omits or changes canonical Nema state')
    return contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('captures', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if any((p / '.git').exists() for p in [output, *output.parents]):
        raise ValueError('Private output required')
    output.mkdir(mode=0o700)
    report = json.loads((args.captures / 'report.json').read_text())
    patches = {}
    for case, filename in [('stock24', 'stock-2.4.0.24.bin'), ('stock23', 'stock-2.3.0.24.bin'),
                           ('cfw', 'faceclaw-38-research-only.bin')]:
        _, raw = load_pinned_main((args.simulator / 'inputs/verified-01' / filename).read_bytes())
        contract = discover_blend(raw)
        source = args.simulator / 'nema-capability-main-01' / case
        validate_assets(source, json.loads((source / 'derived-inputs.json').read_text())['derived'])
        capture = json.loads((source / 'report.json').read_text())
        if (not capture['passed'] or not capture['semantic_validation']['passed']
                or parse_log((source / 'renode.log').read_text()) != capture['observed']
                or (source / 'main.bin').read_bytes() != raw or not capture['diagnostics']['paused']):
            raise ValueError('Unverified main snapshot')
        region = next(r for r in capture['diagnostics']['regions'] if r['base'] == contract['region'])
        if len(region['words']) != 16:
            raise ValueError('Unexpected region extent')
        data = struct.pack('<16I', *region['words'])
        original = args.captures / 'captures' / case / 'full-letter'
        snapshot = json.loads((original / 'snapshot.json').read_text())
        if sha(raw) != snapshot['raw_sha256']:
            raise ValueError('Original main changed')
        for name, expected in snapshot['image_hashes'].items():
            if sha((original / name).read_bytes()) != expected:
                raise ValueError('Original fixture changed')
        sram = bytearray((original / 'sram.bin').read_bytes())
        offset = contract['region'] - 0x20000000
        before = bytes(sram[offset:offset + len(data)])
        sram[offset:offset + len(data)] = data
        patch = dict(contract=contract, before=before.hex(), after=data.hex(),
                     changed_bytes=sum(x != y for x, y in zip(before, data)),
                     main_capture=str(source.relative_to(args.simulator)),
                     source_hashes={n: sha((source / n).read_bytes()) for n in
                                    ['report.json', 'renode.log', 'plan.json', 'derived-inputs.json']})
        snapshot['nema_state_region'] = patch
        snapshot['image_hashes']['sram.bin'] = sha(sram)
        validate_region(args.simulator, case, raw, snapshot, sram)
        folder = output / 'captures' / case / 'full-letter'
        folder.mkdir(mode=0o700, parents=True)
        (folder / 'sram.bin').write_bytes(sram)
        (folder / 'work.bin').write_bytes((original / 'work.bin').read_bytes())
        (folder / 'snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
        patches[case] = patch
    report['nema_state_regions'] = patches
    report['source_report_sha256'] = sha((args.captures / 'report.json').read_bytes())
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'preparer.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({c: dict(core=hex(p['contract']['core']), region=hex(p['contract']['region']),
                             changed_bytes=p['changed_bytes']) for c, p in patches.items()}))


if __name__ == '__main__':
    main()
