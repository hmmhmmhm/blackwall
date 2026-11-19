"""Pause original kvTime programming at a real WIP polling return.

Exports only already committed NOR; pending operations are not made durable.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from inspect_ambiq_target import decode
from native_replay import IMAGE
from probe_runtime_kv_restart import digest
from run_renode_m55_probe import execute
from run_runtime_connection_m55 import pin_capture, inspect
from verify_kv_persistence_cycle import validate_capture


def build(source, output, simulator, stop):
    if output.exists() or not output.resolve().is_relative_to(simulator.resolve()) or not 0 <= stop <= 7:
        raise ValueError('Use a new private output and a 0..7 boundary')
    validate_capture(source)
    p=json.loads((source/'connection-profile.json').read_text())
    if p['case'] not in ('stock24','stock23','cfw') or not p.get('att_time'):
        raise ValueError('Original-three time action required')
    entry=0x47b750-(0 if p['case']=='stock24' else 0x4d18)
    raw=(source/'main.bin').read_bytes()
    instructions={i.address:(i.mnemonic,i.op_str) for i in decode(raw,entry,0x7c)}
    for off,want in {0:('push','{r0, r1, r2, r3, r4, lr}'),0x6e:('lsls','r0, r0, #0x1f'),
                     0x78:('add','sp, #0x10'),0x7a:('pop','{r4, pc}')}.items():
        if instructions.get(entry+off)!=want:raise ValueError('Unknown original status return')
    inputs=json.loads((source/'connection-inputs.json').read_text())
    if not set(inputs).issubset(json.loads((source/'capture-files.json').read_text())['files']):
        raise ValueError('Unpinned source inputs')
    output.mkdir(mode=0o700,parents=True);(output/'exports').mkdir()
    for name in inputs:
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        if subprocess.run(['cp','-c',str(source/name),str(target)],capture_output=True).returncode:
            shutil.copyfile(source/name,target)
    observer=Path(__file__).with_name('renode-nor-program-cut-observer.cs').read_bytes()
    (output/'cut-observer.cs').write_bytes(observer)
    with (output/'activation.cs').open('ab') as f:f.write(b'\n'+observer)
    runtime=(source/'run.py').read_text()
    anchor="    nor_before=nor_snapshot('before')\n"
    install="""    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallNorProgramCutObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallNorProgramCutObserver
    cut=BlackwallNorProgramCutObserver(m,cpu,g.Mspi1Config.Pio,STATUS_RETURN,STOP_PROGRAM)
""".replace('STATUS_RETURN',str(entry+0x78)).replace('STOP_PROGRAM',str(stop))
    export="    File.WriteAllText('/work-output/connection.json'"
    save="""    cut_result=dict(stopped=bool(cut.Stopped),paused=bool(m.IsPaused),rows=[[int(v) for v in row] for row in cut.Rows],initial_starts=int(cut.InitialStarts),initial_completions=int(cut.InitialCompletions),initial_bytes=int(cut.InitialBytes),stop_program=STOP_PROGRAM,app_returned=bool(app.Stopped),pc=int(cpu.PC.RawValue),pending_discarded_by_fresh_restart=True,physical_power_cut=False)
    File.WriteAllText('/work-output/program-cut.json',json.dumps(cut_result))
    Console.WriteLine('BLACKWALL_PROGRAM_CUT '+json.dumps(cut_result))
""".replace('STOP_PROGRAM',str(stop))
    if runtime.count(anchor)!=1 or runtime.count(export)!=1:
        raise ValueError('Unknown saved kvTime workflow')
    (output/'run.py').write_text(runtime.replace(anchor,anchor+install).replace(export,save+export))
    (output/'cut-source.json').write_text(json.dumps(dict(source_capture_sha256=digest(source/'capture-files.json'),
        stop_program=stop,status_return=entry+0x78,observer_changes_execution_profile=True,
        guest_context_forced=False,model_unchanged=True),indent=2)+'\n')
    names=set(inputs)|{'cut-observer.cs','cut-source.json'}
    (output/'connection-inputs.json').write_text(json.dumps({n:digest(output/n) for n in sorted(names)},indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path)
    p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--stop-program',type=int,required=True);a=p.parse_args()
    build(a.source,a.output,a.simulator,a.stop_program)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128',
             '--cap-drop','ALL','--security-opt','no-new-privileges',
             '--mount',f'type=bind,source={a.output},target=/work,readonly',
             '--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,
             '--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=180)
    pin_capture(a.output)
    result=json.loads((a.output/'exports/program-cut.json').read_text());print(json.dumps(result))
    if not a.stop_program:
        verdict=inspect(a.output)
        if not verdict['passed']:raise SystemExit(1)
    elif not result['stopped'] or result['app_returned']:
        raise SystemExit(1)


if __name__=='__main__':main()
