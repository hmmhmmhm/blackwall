"""Read bounded simulated low SRAM after the original main stops; no new CPU hooks."""
import argparse
import json
import shutil
import struct
from pathlib import Path

from native_replay import FILES, IMAGE, digest, parse_log, validate_assets
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models

SRAM_START = 0x20000000
SRAM_BYTES = 0x6000


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--case', choices=['stock24', 'stock23', 'cfw'], required=True)
    a = p.parse_args()
    s, out = a.simulator, a.output
    source = s/'timer0-shared-main-02'/(a.case+'-low')
    prior = json.loads((source/'report.json').read_text())
    source_hashes = json.loads((source/'derived-inputs.json').read_text())['derived']
    validate_assets(source, source_hashes)
    if parse_log((source/'renode.log').read_text()) != prior['observed'] or (source/'strict.cs').read_bytes() != models(s):
        raise ValueError('Source replay/model differs')
    contract = json.loads((s/'xip-font-contract-03/report.json').read_text())
    if not contract['passed'] or contract['count'] != 173:
        raise ValueError('Missing XIP source contract')
    meta = next(c for c in contract['cases'] if c['case'] == a.case)
    out.mkdir(mode=0o700, parents=True)
    for name in FILES:
        shutil.copyfile(source/name, out/name)
    runtime = (source/'run.py').read_text()
    boundary = '    e.PauseAll()\n'
    if runtime.count(boundary) != 1:
        raise ValueError('Unexpected pause boundary')
    extra = "    from System import Console\n    if not m.IsPaused:raise ValueError('Host font capture requires paused CPU')\n"
    extra += "    font_memory=[int(m.SystemBus.ReadDoubleWord(%d+4*i)) for i in range(%d)]\n" % (SRAM_START, SRAM_BYTES//4)
    extra += "    Console.WriteLine('BLACKWALL_FONT_MEMORY '+json.dumps(dict(base=%d,words=font_memory,paused=bool(m.IsPaused))))\n" % SRAM_START
    runtime = runtime.replace(boundary, boundary+extra)
    compile(runtime, 'run.py', 'exec')
    (out/'run.py').write_text(runtime)
    derived = {f: digest(out/f) for f in FILES}
    (out/'derived-inputs.json').write_text(json.dumps(dict(derived=derived, base=source_hashes), indent=2)+'\n')
    command = ['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={out},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc']
    log = execute(command, out, 'renode', timeout=None)
    validate_assets(out, derived)
    observed = parse_log(log)
    if observed != prior['observed']:
        raise ValueError('Original CPU/device state or instruction count changed')
    def marker(name):
        rows = [json.loads(l.split(' ', 1)[1]) for l in log.splitlines() if l.startswith(name+' ')]
        if len(rows) != 1:
            raise ValueError('Missing marker: '+name)
        return rows[0]
    memory = marker('BLACKWALL_FONT_MEMORY')
    if memory['base'] != SRAM_START or len(memory['words']) != SRAM_BYTES//4 or not memory['paused']:
        raise ValueError('Invalid bounded paused SRAM capture')
    obs = marker('BLACKWALL_OBSERVATION')
    if obs != prior['selected_observation']:
        raise ValueError('Original observation trace changed')
    data = struct.pack('<'+'I'*len(memory['words']), *memory['words'])
    (out/'low-sram.bin').write_bytes(data)
    def words(address, count):
        offset = address-SRAM_START
        if offset < 0 or offset+4*count > len(data) or address & 3:
            raise ValueError('Font config outside captured low SRAM')
        return list(struct.unpack_from('<'+'I'*count, data, offset))
    configs, fonts = [], {}
    for address in meta['chain_configs']:
        config = words(int(address, 0), 12)
        if config[::3] != [0]*4:
            raise ValueError('Unexpected font config kind')
        pointers = config[1::3]
        configs.append(dict(address=address, pointers=[hex(x) for x in pointers]))
        for pointer in pointers:
            fonts[hex(pointer)] = words(pointer, 9)
    for bank in meta['banks']:
        if fonts[bank['font_object']][6] != 0:
            raise ValueError('Unexpected external font descriptor')
    result = dict(passed=True, case=a.case, observed=observed, selected_observation=obs,
                  configs=configs, fonts=fonts, sram=dict(base=SRAM_START, bytes=len(data), sha256=digest(out/'low-sram.bin')),
                  hardware_accessed=False, guest_writes_added=False,
                  scope='Paused simulated low SRAM from original main, exact prior CPU including instruction count and event trace; no XIP data or font callback execution added')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, case=a.case, fonts={k:[hex(x) for x in v] for k,v in fonts.items()})), flush=True)


if __name__ == '__main__':
    main()
