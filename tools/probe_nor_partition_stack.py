"""Extend paused original-main stack observation; never supply NOR bytes or alter guest flow."""
import argparse
import json
import shutil
from pathlib import Path
from native_replay import FILES, IMAGE, parse_log, validate_assets, digest
from run_renode_m55_probe import execute


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    s, out = a.simulator, a.output
    out.mkdir(mode=0o700)
    rows = []
    for key in ['stock24', 'stock23', 'cfw']:
        src = s / 'mspi1-continuous-status-main-01' / key
        prior = json.loads((src / 'report.json').read_text())
        if parse_log((src / 'renode.log').read_text()) != prior['observed']:
            raise ValueError('Prior report differs')
        validate_assets(src, json.loads((src / 'derived-inputs.json').read_text())['derived'])
        d = out / key
        d.mkdir(mode=0o700)
        for f in FILES:
            shutil.copyfile(src / f, d / f)
        runtime = (src / 'run.py').read_text()
        lines = runtime.splitlines(keepends=True)
        positions = [i for i, line in enumerate(lines) if line.lstrip().startswith('stack_context=')]
        if len(positions) != 1:
            raise ValueError('Unexpected stack observation')
        i = positions[0]
        if lines[i].count('range(32)') != 1 or lines[i].count('-128') != 1:
            raise ValueError('Unexpected stack bounds')
        lines[i] = lines[i].replace('range(32)', 'range(96)').replace('-128', '-384')
        runtime = ''.join(lines)
        compile(runtime, 'run.py', 'exec')
        (d / 'run.py').write_text(runtime)
        derived = {f: digest(d / f) for f in FILES}
        (d / 'derived-inputs.json').write_text(json.dumps(dict(derived=derived, base={f: digest(src / f) for f in FILES}), indent=2) + '\n')
        log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={d},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], d, 'renode', timeout=None)
        v = parse_log(log)
        validate_assets(d, derived)
        baseline = prior['observed']
        for field in v:
            if field != 'stack_context' and v[field] != baseline[field]:
                raise ValueError('Observation replay changed ' + field)
        if len(v['stack_context']['words']) != 96 or v['stack_context']['words'][:32] != baseline['stack_context']['words']:
            raise ValueError('Original stack prefix differs')
        r = dict(passed=True, observed=v, case=key, scope='Read-only paused stack extension; no NOR data, new model, full boot or hardware evidence')
        (d / 'report.json').write_text(json.dumps(r, indent=2) + '\n')
        rows.append(dict(case=key, pc=hex(v['pc']), stack_words=96))
        print(json.dumps(rows[-1]), flush=True)
    (out / 'report.json').write_text(json.dumps(dict(passed=True, cases=rows), indent=2) + '\n')


if __name__ == '__main__':
    main()
