"""Replay hash-pinned, frozen Renode inputs without regenerating or modifying the model.

Profiles are locally reviewed execution instructions, not untrusted firmware packages.
No devices, networking, source regeneration, PC overrides, or snapshots are used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
from time import perf_counter

from pinned_main import MAIN_LAYOUT, PINS
from run_renode_m55_probe import execute

IMAGE='sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649'
FILES={'board.repl','itcm-fill.bin','sram-fill.bin','main.bin','probe.resc','run.py','result.py','strict.cs'}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate_assets(directory, files):
    directory=directory.resolve()
    for name, expected in files.items():
        p=directory/name
        if Path(name).name!=name or p.resolve().parent!=directory or not p.is_file():
            raise ValueError('Invalid replay file path: '+name)
        if digest(p)!=expected:raise ValueError('Replay file hash differs: '+name)
        if p.suffix=='.py':compile(p.read_text(),name,'exec')

def boundary_state(observed):
    """Endpoint-specific counters are separate from common image/memory invariants."""
    uart_fields=('module','writes','reads','phase','requests','responses','power_downs','tx_bytes','irq_exception_entries')
    iom_fields=('module','writes','reads','power_phase','power_requests','power_responses','power_downs','commands','last_i2c_configuration')
    return dict(pc=observed['pc'],guards=[dict(g) for g in observed['guards'] if g['accesses']],
                uarts=[{k:u[k] for k in uart_fields} for u in observed['uarts']],
                ioms=[dict({k:i[k] for k in iom_fields},cq_pairs=i['cq']['pairs']) for i in observed['ioms']])

def parse_log(log):
    rows=[json.loads(line.split('BLACKWALL_REPORT ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_REPORT ')]
    if len(rows)!=1:raise ValueError('Missing or ambiguous native report')
    observed=rows[0]
    count=sum(g['accesses'] for g in observed['guards'])
    if count!=1 or observed['memory_policy']['violations'] or observed['system_control']['violations']:
        raise ValueError('Expected one strict MMIO stop and no execution policy violation')
    if not observed['machine_paused_before_host']:raise ValueError('Host window expired before native stopped')
    for line in log.splitlines():
        lower=line.lower()
        if (('[warning]' in lower and 'translation cache size' not in lower)
            or ('[error]' in lower and 'this machine has aborted' not in lower)
            or any(w in lower for w in ('unhandled','non existing','non-existing','could not execute','blackwall_runtime_error'))):
            raise ValueError('Unexpected engine message: '+line)
    return observed

def preflight(profile, source):
    if profile['schema']!=1 or profile['image_id']!=IMAGE:raise ValueError('Unsupported profile schema/runtime')
    cases=profile['cases']
    if [c['name'] for c in cases]!=['stock23','cfw','stock24']:raise ValueError('Expected the reviewed original-three comparison')
    for c in cases:
        p=source/c['name']
        if p.resolve().parent!=source.resolve():raise ValueError('Invalid case directory')
        if set(c['files'])!=FILES:raise ValueError('Incomplete frozen input set')
        validate_assets(p,c['files'])
        validate_assets(p,{'report.json':c['reference_report_sha256'],'renode.log':c['reference_log_sha256']})
        r=json.loads((p/'report.json').read_text())
        raw=(p/'main.bin').read_bytes();key=c['firmware_profile']
        if key not in MAIN_LAYOUT or len(raw)!=MAIN_LAYOUT[key][1] or hashlib.sha256(raw).hexdigest()!=MAIN_LAYOUT[key][3]:
            raise ValueError('Not the pinned original main: '+c['name'])
        if r['profile']!=key or r['bundle_sha256']!=PINS[key] or r['image_id']!=IMAGE:
            raise ValueError('Reference provenance differs')
        if r['raw_main_sha256']!=c['files']['main.bin'] or r['reset_vector']!=hex(struct.unpack_from('<I',raw,4)[0]):
            raise ValueError('Reference raw/vector differs')
        if r['selected_hypotheses']!=c['selected_hypotheses'] or r['assumptions']!=profile['assumptions']:
            raise ValueError('Reference assumptions differ')
        if r['boot_verified'] or r['hardware_validated'] or r['installable']:raise ValueError('Unproven reference completion claim')
        observed=parse_log((p/'renode.log').read_text())
        if observed!=r['observed'] or boundary_state(observed)!=c['expected_boundary']:raise ValueError('Reference boundary differs')
    a=source/'stock23';b=source/'cfw'
    for name in ('board.repl','strict.cs','probe.resc','result.py'):
        if (a/name).read_bytes()!=(b/name).read_bytes():raise ValueError('Stock/CFW configuration differs: '+name)
    if (a/'run.py').read_text().replace('3758688','3829832')!=(b/'run.py').read_text():
        raise ValueError('Stock/CFW runtime differs beyond main length')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('profile',type=Path);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--check-only',action='store_true',help='Validate all input hashes/provenance/scripts without Docker or output writes')
    a=p.parse_args();started=perf_counter()
    profile=json.loads(a.profile.read_text());source=a.source.resolve();output=a.output.resolve()
    if output.exists():raise ValueError('Use a new output directory to preserve evidence')
    preflight(profile,source)
    if a.check_only:
        print(json.dumps(dict(passed=True,stage='host-preflight',cases=3,native_executed=False)));return
    inspected=json.loads(subprocess.run(['docker','image','inspect',IMAGE],capture_output=True,text=True,check=True,timeout=15).stdout)[0]
    if inspected['Id']!=IMAGE or inspected['Architecture']!='arm64' or inspected['Os']!='linux':raise ValueError('Runtime image differs')
    output.mkdir(mode=0o700)
    shutil.copyfile(a.profile,output/'profile.json')
    (output/'native_replay.py').write_bytes(Path(__file__).read_bytes())
    (output/'execute-helper.py').write_bytes(Path(__file__).with_name('run_renode_m55_probe.py').read_bytes())
    preparation=perf_counter()-started;rows=[]
    for case in profile['cases']:
        t=perf_counter();name=case['name'];run=output/name;run.mkdir(mode=0o700)
        for file in FILES:shutil.copyfile(source/name/file,run/file)
        validate_assets(run,case['files'])
        copy_time=perf_counter()-t
        command=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={run},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc']
        (run/'command.json').write_text(json.dumps(command,indent=2)+'\n')
        t=perf_counter();log=execute(command,run,'renode');native_time=perf_counter()-t
        t=perf_counter();observed=parse_log(log);validate_assets(run,case['files'])
        actual=boundary_state(observed)
        report=dict(case=name,observed=observed,boundary_matches=actual==case['expected_boundary'],
                    selected_hypotheses=case['selected_hypotheses'],raw_main_sha256=case['files']['main.bin'],
                    image_id=IMAGE,boot_verified=False,hardware_validated=False,installable=False,
                    host_seconds=dict(case_preparation=copy_time,native_including_compile_and_cleanup=native_time,audit=perf_counter()-t))
        (run/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        if not report['boundary_matches']:raise ValueError('Frozen endpoint differs: '+name+'; inspect saved report')
        rows.append(dict(case=name,pc=hex(observed['pc']),boundary_matches=True,host_seconds=report['host_seconds']))
        print(json.dumps(rows[-1]),flush=True)
    report=dict(passed=True,profile_id=profile['id'],profile_sha256=digest(a.profile),image_id=IMAGE,cases=rows,
                preparation_seconds=preparation,total_host_seconds=perf_counter()-started,
                measurement='single cold-process replay; native includes compilation, fixed host sleep and cleanup; not guest speed or a speedup',
                boot_verified=False,hardware_validated=False,installable=False)
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
