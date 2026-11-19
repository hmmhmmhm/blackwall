"""Observe initialized font configs in original main; no XIP data or guest writes."""
import argparse
import json
import shutil
from pathlib import Path

from native_replay import FILES, IMAGE, digest, parse_log, validate_assets
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--case', choices=['stock24', 'stock23', 'cfw'], required=True)
    p.add_argument('--audit-existing', action='store_true', help='Audit saved terminal evidence after an audit failure; never rerun or rewrite inputs')
    a = p.parse_args()
    s, out = a.simulator, a.output
    contract = json.loads((s/'xip-font-contract-03/report.json').read_text())
    if not contract['passed'] or contract['count'] != 173:
        raise ValueError('Missing source contract')
    meta = next(c for c in contract['cases'] if c['case'] == a.case)
    src = s/'timer0-shared-main-02'/(a.case+'-low')
    prior = json.loads((src/'report.json').read_text())
    validate_assets(src, json.loads((src/'derived-inputs.json').read_text())['derived'])
    if parse_log((src/'renode.log').read_text()) != prior['observed'] or (src/'strict.cs').read_bytes() != models(s):
        raise ValueError('Source replay/model differs')
    if not a.audit_existing:
        out.mkdir(mode=0o700, parents=True)
        for name in FILES:
            shutil.copyfile(src/name, out/name)
    entry = int(meta['initializer'], 0)
    pc = int(meta['banks'][0]['read_pc'], 0)
    sites = [('font-object-0', entry, int(meta['banks'][0]['font_object'], 0), 9),
             ('font-object-1', entry+2, int(meta['banks'][1]['font_object'], 0), 9),
             ('font-chain-config-0', pc-4, int(meta['chain_configs'][0], 0), 12),
             ('font-chain-config-1', pc, int(meta['chain_configs'][1], 0), 12)]
    extra = ''.join("    observer.AddPoint('%s',%d)\n    observer.CaptureSram(m,'%s',%d,%d)\n" % (label, address, label, ram, words)
                    for label, address, ram, words in sites)
    runtime = (src/'run.py').read_text()
    if runtime.count('    e.StartAll()\n') != 1:
        raise ValueError('Unexpected start boundary')
    runtime = runtime.replace('    e.StartAll()\n', extra+'    e.StartAll()\n')
    compile(runtime, 'run.py', 'exec')
    if a.audit_existing:
        if (out/'run.py').read_text() != runtime:
            raise ValueError('Saved observation program differs')
        derived = json.loads((out/'derived-inputs.json').read_text())['derived']
        validate_assets(out, derived)
        if any((out/f).read_bytes() != (src/f).read_bytes() for f in FILES if f != 'run.py'):
            raise ValueError('Saved non-observer input differs')
    else:
        (out/'run.py').write_text(runtime)
        derived = {f: digest(out/f) for f in FILES}
        (out/'derived-inputs.json').write_text(json.dumps(dict(derived=derived, base={f:digest(src/f) for f in FILES}), indent=2)+'\n')
    command = ['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={out},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc']
    log = (out/'renode.log').read_text() if a.audit_existing else execute(command, out, 'renode', timeout=None)
    validate_assets(out, derived)
    v = parse_log(log)
    rows = [json.loads(l.split(' ', 1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_OBSERVATION ')]
    if len(rows) != 1:
        raise ValueError('Missing observer report')
    obs = rows[0]
    prior_cpu = dict(prior['observed'])
    observed_cpu = dict(v)
    instruction_delta = observed_cpu.pop('instructions') - prior_cpu.pop('instructions')
    # The faulting-load observer correlates with one extra accounted instruction.
    # Preserve the measured count; engine internals have not been independently proved.
    if observed_cpu != prior_cpu or instruction_delta != 1 or obs['dropped_events'] or obs['sequence'] != len(obs['events']):
        raise ValueError('CPU boundary changed or event loss')
    labels = [x[0] for x in sites]
    projected = [dict(e, sequence=i+1) for i, e in enumerate(e for e in obs['events'] if e['label'] not in labels)]
    if projected != prior['selected_observation']['events']:
        raise ValueError('Prior execution trace differs')
    snapshots = {}
    for label, _, address, count in sites:
        point = next(x for x in obs['points'] if x['label'] == label)
        if point['hits'] != 1 or point['snapshot']['address'] != address or len(point['snapshot']['words']) != count:
            raise ValueError('Missing bounded snapshot: '+label)
        snapshots[label] = point['snapshot']['words']
    result = dict(passed=True, case=a.case, observed=v, selected_observation=obs,
                  snapshots=snapshots, instruction_accounting_delta=instruction_delta,
                  hardware_accessed=False, guest_writes_added=False,
                  scope='Read-only original initialized font objects/configs; same first XIP guard and prior events; no font load/chain creation/display proof')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, case=a.case, snapshots=snapshots)), flush=True)


if __name__ == '__main__':
    main()
