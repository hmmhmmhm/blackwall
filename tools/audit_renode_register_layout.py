"""Compare selected Apollo4 model offsets with pinned Apollo510 C layouts; no device I/O."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

HEADER_SHA = 'b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797'
INFRA_COMMIT = '042a58285ee91453f99d31f19e8aa140102ec540'
PAIRS = {
    'SystemTimer': ('STIMER', {
        'Configuration': 'STCFG', 'SystemTimerCount': 'STTMR',
        'Compare0': 'SCMPR0', 'Compare7': 'SCMPR7', 'Capture0': 'SCAPT0',
        'SystemTimerNVRAM0': 'SNVR0', 'SystemTimerNVRAM1': 'SNVR1',
        'SystemTimerNVRAM2': 'HALSTATES', 'InterruptEnable': 'STMINTEN',
        'InterruptStatus': 'STMINTSTAT', 'InterruptClear': 'STMINTCLR', 'InterruptSet': 'STMINTSET'}),
    'Watchdog': ('WDT', {
        'Configuration': 'CFG', 'Restart': 'RSTRT', 'Lock': 'LOCK', 'CounterValue': 'COUNT',
        'InterruptEnable': 'WDTIEREN', 'InterruptStatus': 'WDTIERSTAT',
        'InterruptClear': 'WDTIERCLR', 'InterruptSet': 'WDTIERSET'}),
    'PowerController': ('PWRCTRL', {
        'MCUPerformanceControl': 'MCUPERFREQ', 'DevicePowerEnable': 'DEVPWREN',
        'DevicePowerStatus': 'DEVPWRSTATUS', 'MemoryPowerEnable': 'MEMPWREN',
        'MemoryPowerStatus': 'MEMPWRSTATUS', 'MemoryRetConfiguration': 'MEMRETCFG',
        'SharedSRAMPowerEnable': 'SSRAMPWREN', 'SharedSRAMPowerStatus': 'SSRAMPWRST',
        'SharedSRAMRetConfiguration': 'SSRAMRETCFG', 'MultimediaSystemOverride': 'MMSOVERRIDE',
        'VoltageRegulatorsControl': 'VRCTRL', 'VoltageRegulatorsStatus': 'VRSTATUS'}),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', type=Path)
    parser.add_argument('apollo_header', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--clang', default='/opt/homebrew/opt/llvm@21/bin/clang')
    args = parser.parse_args()
    header = args.apollo_header.read_bytes()
    if hashlib.sha256(header).hexdigest() != HEADER_SHA:
        raise ValueError('Apollo510 header hash mismatch')
    manifest = json.loads((args.sources/'verified-manifest.json').read_text())
    if manifest['matching_infrastructure_gitlink'] != INFRA_COMMIT:
        raise ValueError('Unreviewed Renode infrastructure revision')
    checks, definitions, rows = [], [], []
    for model, (prefix, pairs) in PAIRS.items():
        filename = f'AmbiqApollo4_{model}.cs'
        data = (args.sources/('renode-infrastructure-'+filename)).read_bytes()
        pin = next(s for s in manifest['sources'] if s['repo'] == 'renode/renode-infrastructure'
                   and s['path'].endswith('/'+filename) and s['commit'] == INFRA_COMMIT)
        if hashlib.sha256(data).hexdigest() != pin['sha256']:
            raise ValueError('Renode source hash mismatch: '+model)
        match = re.search(r'enum Registers(?:\s*:\s*long)?\s*\{([^}]+)\}', data.decode())
        if match is None:
            raise ValueError('Cannot locate register enum: '+model)
        offsets = {name: int(value, 16) for name, value in
                   re.findall(r'(\w+)\s*=\s*(0x[0-9A-Fa-f]+)', match[1])}
        text = header.decode()
        end = text.index('} '+prefix+'_Type;')
        start = text.rfind('typedef struct {', 0, end)
        if start < 0:
            raise ValueError('Cannot extract C layout: '+prefix)
        definitions.append(text[start:end]+'} '+prefix+'_Type;')
        for renode_name, ambiq_name in pairs.items():
            offset = offsets[renode_name]
            checks.append(f'_Static_assert(offsetof({prefix}_Type, {ambiq_name}) == {offset}, "{model}.{renode_name}");')
            rows.append({'block': prefix, 'renode_register': renode_name, 'apollo510_register': ambiq_name,
                         'offset': hex(offset), 'location_verified': False,
                         'behavior_compatibility': 'unverified',
                         'known_semantic_difference': renode_name == 'SystemTimerNVRAM2'})
    args.output.mkdir(mode=0o700)
    source = args.output/'layout-check.c'
    source.write_text('#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n'
                      '#define __IM volatile const\n#define __OM volatile\n'
                      +'\n'.join(definitions+checks)+'\n')
    command = [args.clang, '--target=arm-none-eabi', '-mcpu=cortex-m55', '-mthumb',
               '-std=c11', '-c', str(source), '-o', str(args.output/'layout-check.o')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    (args.output/'compiler.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise ValueError('C layout verification failed; see compiler.log')
    for row in rows:
        row['location_verified'] = True
    report = {'scope': 'selected register offsets only; not behavior, IRQ, timing or full chip compatibility',
              'header_sha256': HEADER_SHA, 'renode_infrastructure_commit': INFRA_COMMIT,
              'compiler_command': command, 'rows': rows, 'hardware_validated': False,
              'engine_execution_verified': False}
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'verified_register_locations': len(rows), 'behavior_compatibility': 'unverified'}))


if __name__ == '__main__':
    main()
