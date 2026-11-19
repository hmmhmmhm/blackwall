"""Export existing virtual NOR before/after the original device time action."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from kvtime_layout import discover

from native_replay import IMAGE
from run_renode_m55_probe import execute
from run_runtime_connection_m55 import inspect, pin_capture


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source, output):
    if output.exists() or output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Use a new private output outside the repository')
    pinned = json.loads((source / 'capture-files.json').read_text())['files']
    for name, expected in pinned.items():
        path = source / name
        if not path.resolve().is_relative_to(source.resolve()) or digest(path) != expected:
            raise ValueError('Source capture differs')
    profile = json.loads((source / 'connection-profile.json').read_text())
    if (profile['case'] not in ('stock24','stock23','cfw') or not profile.get('att_time') or profile.get('control')
            or profile.get('readonly_control') or profile.get('att_corrupt_crc')
            or profile.get('disconnect_reason') is not None):
        raise ValueError('Use a reviewed original-three time scenario')
    layout=discover((source/'main.bin').read_bytes(),profile)
    inputs = json.loads((source / 'connection-inputs.json').read_text())
    if not set(inputs).issubset(pinned):
        raise ValueError('Unpinned execution input')
    runtime = (source / 'run.py').read_text()
    start = "    if not m.IsPaused or int(cpu.PC.RawValue)!=p['getter']:raise ValueError('Expected retained original main hold')\n"
    finish = "    File.WriteAllText('/work-output/connection.json'"
    if runtime.count(start) != 1 or runtime.count(finish) != 1:
        raise ValueError('Unreviewed runtime structure')
    capture = """    def nor_snapshot(phase):
        q=g.Mspi1Config.Pio
        windows=[]
        for name,w in [('kv-nv',q.ArrayBacking),('littlefs',q.ArrayBacking.AdditionalWindow)]:
            ok,data=w.TryRead(w.Start,w.Length)
            if not ok or data is None:raise ValueError('Missing reviewed NOR backing')
            File.WriteAllBytes('/work-output/nor-'+phase+'-'+name+'.bin',data)
            windows.append(dict(name=name,start=int(w.Start),length=int(w.Length)))
        File.WriteAllBytes('/work-output/db-'+phase+'.bin',b.ReadBytes(0x200615ac,0x8ac,True))
        return dict(windows=windows,program_starts=int(q.PageProgramStarts),program_completions=int(q.PageProgramCompletions),program_bytes=int(q.ProgramBytesCommitted),program_busy=bool(q.ProgramBusy),erase_starts=int(q.SectorEraseStarts),erase_completions=int(q.SectorEraseCompletions),erase_busy=bool(q.EraseBusy),array_reads=int(q.ArrayReadTransfers),last_program=int(q.LastProgramAddress))
    nor_before=nor_snapshot('before')
"""
    final = """    nor_result=dict(before=nor_before,after=nor_snapshot('after'),source='existing virtual device backing; no host data mutation')
    File.WriteAllText('/work-output/nor-commit.json',json.dumps(nor_result))
    Console.WriteLine('BLACKWALL_RUNTIME_NOR_COMMIT '+json.dumps(nor_result))
"""
    runtime = runtime.replace(start, start + capture).replace(finish, final + finish)
    runtime=runtime.replace('b.ReadBytes(0x200615ac,0x8ac,True)',
                            'b.ReadBytes('+str(layout['database'])+',0x8ac,True)')
    output.mkdir(mode=0o700, parents=True)
    (output / 'exports').mkdir()
    for name in inputs:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        result=subprocess.run(['cp','-c',str(source/name),str(destination)],capture_output=True)
        if result.returncode:shutil.copyfile(source/name,destination)
    (output / 'run.py').write_text(runtime)
    (output / 'nor-source.json').write_text(json.dumps(dict(
        source_capture_sha256=digest(source / 'capture-files.json'),
        observation_only=True, host_backing_mutation=False,
        layout=layout,ranges=[dict(start=0x1fc0000,length=0x40000),dict(start=0x1400000,length=0xbc0000)]), indent=2) + '\n')
    names = set(inputs) | {'nor-source.json'}
    (output / 'connection-inputs.json').write_text(json.dumps(
        {name:digest(output / name) for name in sorted(names)}, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.source, args.output)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1',
             '--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
             '--mount',f'type=bind,source={args.output},target=/work,readonly',
             '--mount',f'type=bind,source={args.output}/exports,target=/work-output',
             IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],
            args.output,'renode',timeout=180)
    pin_capture(args.output)
    result = inspect(args.output)
    print(json.dumps(dict(passed=result['passed'],checks=len(result['checks']))))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
