"""Replay saved stock24 inputs with four explicit source-provenance observers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from native_replay import IMAGE
from run_renode_m55_probe import execute
from run_runtime_connection_m55 import inspect, pin_capture


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source, output):
    if output.exists() or output.resolve().is_relative_to(source.resolve()):
        raise ValueError('Use a new independent private capture directory')
    if output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Proprietary capture must remain outside the repository')
    pinned = json.loads((source / 'capture-files.json').read_text())['files']
    for name, expected in pinned.items():
        path = source / name
        if not path.resolve().is_relative_to(source.resolve()) or digest(path) != expected:
            raise ValueError('Source capture pin differs')
    profile = json.loads((source / 'connection-profile.json').read_text())
    if profile['case'] != 'stock24' or not profile.get('att_time') or profile.get('disconnect_reason') is not None:
        raise ValueError('Lineage recipe supports the reviewed stock24 time scenario only')
    raw = (source / 'main.bin').read_bytes()
    for pc, code in {0x4fad8e: '7ff005fb', 0x4fad92: '42f74afc',
                     0x4fadd2: '0090', 0x4fadd4: '2368'}.items():
        if raw[pc - 0x438000:pc - 0x438000 + len(bytes.fromhex(code))] != bytes.fromhex(code):
            raise ValueError('Unreviewed lineage instruction at ' + hex(pc))
    inputs = json.loads((source / 'connection-inputs.json').read_text())
    if not set(inputs).issubset(pinned):
        raise ValueError('Unpinned source execution inputs')
    output.mkdir(mode=0o700, parents=True)
    (output / 'exports').mkdir()
    for name in inputs:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, destination)
    observer = Path(__file__).with_name('renode-runtime-state-lineage-observer.cs').read_bytes()
    (output / 'lineage-observer.cs').write_bytes(observer)
    with (output / 'activation.cs').open('ab') as handle:
        handle.write(b'\n' + observer)
    runtime = (output / 'run.py').read_text()
    anchor = "    p=json.loads(File.ReadAllText('/work/connection-profile.json'))\n"
    install = """    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallRuntimeStateLineageObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallRuntimeStateLineageObserver
    lineage=BlackwallRuntimeStateLineageObserver(m,cpu,p['tcb_slot'])
"""
    save = """    lineage_rows=[[int(value) for value in row] for row in lineage.Rows]
    File.WriteAllText('/work-output/lineage.json',json.dumps(lineage_rows))
    Console.WriteLine('BLACKWALL_RUNTIME_LINEAGE '+json.dumps(lineage_rows))
"""
    export = "    File.WriteAllText('/work-output/connection.json'"
    if runtime.count(anchor) != 1 or runtime.count(export) != 1:
        raise ValueError('Unknown saved runtime structure')
    runtime = runtime.replace(anchor, anchor + install).replace(export, save + export)
    (output / 'run.py').write_text(runtime)
    names = set(inputs) | {'lineage-observer.cs', 'lineage-source.json'}
    (output / 'lineage-source.json').write_text(json.dumps(dict(
        source_capture_sha256=digest(source / 'capture-files.json'),
        observer_changes_execution_profile=True, cpu_context_forced=False,
        addresses=[0x4fad8e, 0x4fad92, 0x4fadd2, 0x4fadd4]), indent=2) + '\n')
    (output / 'connection-inputs.json').write_text(json.dumps(
        {name: digest(output / name) for name in sorted(names)}, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.source, args.output)
    execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1',
             '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
             '--mount', f'type=bind,source={args.output},target=/work,readonly',
             '--mount', f'type=bind,source={args.output}/exports,target=/work-output',
             IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'],
            args.output, 'renode', timeout=180)
    pin_capture(args.output)
    result = inspect(args.output)
    print(json.dumps(dict(passed=result['passed'], failed_checks=[
        key for key, passed in result['checks'].items() if not passed])))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
