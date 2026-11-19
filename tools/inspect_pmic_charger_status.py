"""Inspect pinned PMIC sources and immutable ARM status wrappers; never run guest/device code."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB
from native_replay import parse_log
from pinned_main import load_pinned_main

COMMIT = '4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f'
BASE = 0x438000
REGISTERS = {
    'BCHGILIMSTATUS': (0x32d, 0x01),
    'NTCSTATUS': (0x332, 0x0f),
    'DIETEMPSTATUS': (0x333, 0x01),
    'BCHGCHARGESTATUS': (0x334, 0xff),
    'BCHGERRREASON': (0x336, 0x7f),
    'BCHGERRSENSOR': (0x337, 0xff),
}


def function(source, name):
    match = re.search(r'npmx_error_t ' + name + r'\([^{}]+\)\s*\{', source)
    if match is None:
        raise ValueError('Missing SDK function: ' + name)
    start = match.start()
    return source[start:source.index('\n}', match.end()) + 2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    simulator, output = args.simulator, args.output
    if output.exists():
        raise ValueError('Fresh output required')
    checks = []

    def check(name, predicate):
        if not predicate:
            raise ValueError(name)
        checks.append(name)

    source_dir = simulator / 'npmx-charger-status-research-01'
    manifest = json.loads((source_dir / 'sources.json').read_text())
    tree = json.loads((simulator / 'npmx-research-01/tree.json').read_text())
    check('pinned-commit', manifest['commit'] == tree['sha'] == COMMIT)
    for item in manifest['files']:
        data = (source_dir / Path(item['path']).name).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        check(item['path'] + '-sha256', hashlib.sha256(data).hexdigest() == item['sha256'])
        check(item['path'] + '-git-blob', blob == item['git_blob'] == next(
            entry['sha'] for entry in tree['tree'] if entry['path'] == item['path']))
    header = (source_dir / 'npm1300.h').read_text()
    driver = (source_dir / 'npmx_charger.c').read_text()
    check('charger-base', '#define NPM_BCHARGER_BASE                 0x00000300UL' in header)
    registers = {}
    for name, (address, mask) in REGISTERS.items():
        declaration = re.search(r'__IM uint8_t\s+' + name + r';\s*/\*!< \(@ (0x[0-9A-F]+)\)', header)
        check(name + '-readonly-offset', declaration is not None and int(declaration[1], 16) + 0x300 == address)
        reset = re.search(r'#define BCHARGER_' + name + r'_ResetValue \((0x[0-9A-Fa-f]+)UL\)', header)
        check(name + '-source-reset-zero', reset is not None and int(reset[1], 16) == 0)
        bits = {field: int(position) for field, position in re.findall(
            r'#define BCHARGER_' + name + r'_(\w+)_Pos \((\d+)UL\)', header)}
        check(name + '-fields', sum(1 << position for position in bits.values()) == mask)
        registers[name] = dict(address=address, reset=0, field_mask=mask, fields=bits)
    check('reserved-335', bool(re.search(r'BCHGCHARGESTATUS;.*?__IM uint8_t\s+RESERVED3;.*?BCHGERRREASON;', header, re.S)))
    sdk = {}
    for name, register in [('npmx_charger_status_get', 'BCHGCHARGESTATUS'),
                           ('npmx_charger_ntc_status_get', 'NTCSTATUS'),
                           ('npmx_charger_die_temp_status_get', 'DIETEMPSTATUS')]:
        body = function(driver, name)
        check(name + '-single-byte', bool(re.search(r'NPM_BCHARGER->' + register + r'\).*?,\s*1\);', body, re.S)))
        sdk[name] = dict(register=register, count=1)
    errors = function(driver, 'npmx_charger_errors_check')
    check('sdk-error-pair', 'NPM_BCHARGER->BCHGERRREASON' in errors and 'NPM_BCHARGER_ERR_COUNT' in errors)
    peripherals = (source_dir / 'npm1300_peripherals.h').read_text()
    check('sdk-error-count-two', bool(re.search(r'#define NPM_BCHARGER_ERR_COUNT\s+2UL', peripherals)))
    check('sdk-error-clear-release', 'NPMX_CHARGER_TASK_CLEAR_ERROR' in errors and 'NPMX_CHARGER_TASK_RELEASE' in errors)
    sdk['npmx_charger_errors_check'] = dict(address=0x336, count=2, may_write_clear_and_release=True)

    # Exact complete function, including its BL displacement, matches the three pinned images.
    # This is a static wrapper candidate, not proof that this function has run in a native replay.
    signature = bytes.fromhex('80b50a0001234ff44d710068406800f0d8fd02bd')
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    wrappers = []
    replay = simulator / 'pmic-queued-main-01'
    for key, bundle, address, target in [
        ('stock24', 'stock-2.4.0.24.bin', 0x580566, 0x581128),
        ('stock23', 'stock-2.3.0.24.bin', 0x57d52e, 0x57e0f0),
        ('cfw', 'faceclaw-38-research-only.bin', 0x57d52e, 0x57e0f0),
    ]:
        _, raw = load_pinned_main((simulator / 'inputs/verified-01' / bundle).read_bytes())
        check(key + '-immutable-main', raw == (replay / key / 'main.bin').read_bytes())
        offset = raw.find(signature)
        check(key + '-unique-status-wrapper', offset == address - BASE and raw.find(signature, offset + 1) == -1)
        instructions = list(decoder.disasm(signature, address))
        check(key + '-status-read-args', [(item.mnemonic, item.op_str) for item in instructions][1:4] == [
            ('movs', 'r2, r1'), ('movs', 'r3, #1'), ('mov.w', 'r1, #0x334')])
        check(key + '-backend-call', instructions[6].mnemonic == 'bl' and instructions[6].op_str == hex(target).replace('0x', '#0x'))
        # Adjacent original error wrapper also passes length two at 0x336 to the same backend.
        following = list(decoder.disasm(raw[offset + 20:offset + 46], address + 20))
        check(key + '-error-read-args', ('movs', 'r3, #2') in [(x.mnemonic, x.op_str) for x in following]
              and ('movw', 'r1, #0x336') in [(x.mnemonic, x.op_str) for x in following]
              and ('bl', '#0x' + format(target, 'x')) in [(x.mnemonic, x.op_str) for x in following])
        log = (replay / key / 'renode.log').read_text()
        observed = parse_log(log)
        report = json.loads((replay / key / 'report.json').read_text())
        check(key + '-saved-native-terminal', observed == report['observed'] and 'Renode is quitting' in log)
        active = [guard for guard in observed['guards'] if guard['accesses']]
        check(key + '-pointer-not-data-read', len(active) == 1 and active[0]['operation'] == 'peer-write-unsupported'
              and active[0]['value'] == 0x334 and active[0]['width'] == 2)
        wrappers.append(dict(case=key, address=address, backend=target, bytes=signature.hex(),
                             instructions=[dict(address=i.address, mnemonic=i.mnemonic, operands=i.op_str) for i in instructions],
                             native_status_payload_observed=False))
    output.mkdir(mode=0o700)
    (output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (output / 'report.json').write_text(json.dumps(dict(
        passed=True, count=len(checks), checks=checks, source_manifest=manifest, registers=registers,
        reserved_addresses=[0x335], sdk=sdk, static_original_arm_wrappers=wrappers,
        hardware_validated=False, boot_verified=False, installable=False,
        scope='Static source/ARM inspection and saved replay evidence only. No new guest execution, PMIC state model, or physical operation.'
    ), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks), output=str(output))))


if __name__ == '__main__':
    main()
