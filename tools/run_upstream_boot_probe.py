"""Probe exact public-default upstream 2.3 releases on a declared virtual board."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from run_boot_validation import runtime,classify
from run_original_boot_screen import PRIVATE,PROFILE,read_json,write_json,sha,checked_asset,checked_path,validate_profile,validate_runtime
from run_renode_m55_probe import execute

RELEASES={'current':'7010d103d02a49333362ec185fb04c9657626f97cec5240063375d1c52e55a7e','previous':'06f8a8d59f6351461aa9ce45cbc2a6697172cdca872ec77552325301ae175cc4'}
MAIN='69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c'
BUILD=PRIVATE/'recovery/upstream-stock23-bw558-01'


def check_release(data,release):
    if release not in RELEASES or len(data)!=159744 or hashlib.sha256(data).hexdigest()!=RELEASES[release]:raise ValueError('Exact upstream supported release required')


def interpret(points):
    return dict(worker_entered=points.get('patched-worker',0)>0,main_entered=points.get('main-reset',0)>0,authentication_verified=False,recovery_verified=False,hardware_accessed=False)


def runtime23():
    source=runtime(159744)
    for old,new in [('3700068','3922604'),('0x432cb2','0x432ca2'),('0x42e650','0x42e640'),('0x42e582','0x42e572'),('0x42dfe8','0x42dfd8'),('0x5fbe3e','0x61902a'),('0x4354b8','0x4354a8'),('0x4352a0','0x434e64')]:
        if old not in source:raise ValueError('Unreviewed runtime anchor: '+old)
        source=source.replace(old,new)
    extra="""observer.AddPoint('power-slots-before-manager',0x4354ac)
observer.CaptureSram(m,'patched-manager',0x20000494,6)
observer.CaptureSram(m,'power-slots-before-manager',0x20026e44,2)
observer.AddPoint('storage-wrapper',0x4364a8)
"""
    source=source.replace('start=int(m.ElapsedVirtualTime',extra+'start=int(m.ElapsedVirtualTime')
    source=source.replace("result['power_owners']=", "result['uart2_tx']=[int(x) for x in g.Uarts[2].TxBytes]\nresult['power_owners']=")
    validate_runtime(source);return source


def with_chip_revision(board,revision):
    if type(revision) is not int or revision not in (0x21,0x22,0x23,0x24):raise ValueError('Explicit synthetic revision21..24 required')
    old='    chipRevision: 35\n'
    if board.count(old)!=1:raise ValueError('Unique shared chip identity owner required')
    return board.replace(old,'    chipRevision: '+str(revision)+'\n')


def derive(release,output,trim=-1,*,chip_revision=0x23,b0_ton=False):
    output=Path(output).resolve()
    if type(trim) is not int or trim not in (-1,0,1,2):raise ValueError('Explicit synthetic trim -1/0/1/2 required')
    if type(b0_ton) is not bool or b0_ton and (chip_revision!=0x21 or trim!=1):raise ValueError('B0 TON requires explicit synthetic chip21/trim1')
    if release not in RELEASES or output.exists() or not output.is_relative_to(PRIVATE) or output.is_relative_to(ROOT):raise ValueError('Fresh private output and pinned release required')
    boot=(BUILD/'source/build/bootloader.bin').read_bytes();check_release(boot,'current')
    if release=='previous':
        previous=bytearray(boot);previous[0xb89e:0xb8a0]=bytes.fromhex('04f0');previous[0x1e656:0x1e658]=bytes.fromhex('06f0');previous[0x264a8:0x264c8]=b'\xff'*32;boot=bytes(previous)
    check_release(boot,release)
    main=(BUILD/'main-2.3.2.14.bin').read_bytes()
    if hashlib.sha256(main).hexdigest()!=MAIN or len(main)!=3922604 or struct.unpack_from('<II',main)!=(0x2007fb00,0x61902b):raise ValueError('Stock2.3.2.14 main identity mismatch')
    if struct.unpack_from('<II',boot)!=(0x2007fb00,0x432ca3):raise ValueError('Stock2.3 boot vector mismatch')
    p=read_json(PROFILE);validate_profile(p);sources={}
    for name,spec in p['components'].items():
        path=checked_path(ROOT if spec['origin']=='repo' else PRIVATE,spec['path'])
        if sha(path)!=spec['sha256']:raise ValueError('Frozen component changed')
        sources[name]=path.read_bytes()
    board=with_chip_revision(sources['board.repl'].decode(),chip_revision)
    for old,new in [('bootReadPc: 0x42e582','bootReadPc: 0x42e572'),('startupPc: 0x44ac6c','startupPc: 0x44a962'),('setterEntry: 0x483708','setterEntry: 0x480d54')]:
        if board.count(old)!=1:raise ValueError('Versioned marker consumer not unique: '+old)
        board=board.replace(old,new)
    if trim>=0:
        from verify_info1_trim_profile import bind_trim_profile
        sources['strict.cs']=bind_trim_profile(sources['strict.cs'].decode()).encode()
        anchor='guard_iom7_tail: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40057400\n'
        if board.count(anchor)!=1:raise ValueError('INFO1 metadata owner not unique')
        board=board.replace(anchor,anchor+'    info1TrimRevision: '+str(trim)+'\n')
    if b0_ton:
        from verify_b0_ton_profile import bind_b0_ton
        sources['strict.cs']=bind_b0_ton(sources['strict.cs'].decode()).encode()
        anchor='    halStorage: true\n'
        if board.count(anchor)!=1:raise ValueError('Unique HAL owner required')
        board=board.replace(anchor,anchor+'    b0TonConfiguration: true\n')
    output.mkdir(parents=True,mode=0o700);(output/'exports').mkdir(mode=0o700)
    run_source=runtime23()
    if b0_ton:
        anchor="result['power_owners']="
        if run_source.count(anchor)!=1:raise ValueError('Unique power exporter required')
        run_source=run_source.replace(anchor,"result['b0_ton_registers']=[dict(address=int(p.Key),value=int(p.Value.Value),reads=int(p.Value.Reads),writes=int(p.Value.Writes)) for p in g.HalStorage.Registers if int(p.Key) in (0x40020340,0x40020344,0x4002034c,0x40020354,0x40020358)]\n"+anchor)
        run_source=run_source.replace(anchor,"result['b0_power_state']=dict(override_steps=int(g.BuckOverrideStep),override_complete=bool(g.BuckOverrideComplete),buck_steps=int(g.BuckStart.StepsCompleted),core_applied=bool(g.CoreLdo.Applied),core_reduced=int(g.CoreLdo.ReducedTrim),mem_steps=int(g.MemLdo.StepsCompleted))\n"+anchor)
        validate_runtime(run_source)
    for name,data in [('boot.bin',boot),('main.bin',main),('strict.cs',sources['strict.cs']),('board.repl',board.encode()),('run.py',run_source.encode())]:
        (output/name).write_bytes(data);(output/name).chmod(0o600)
    script=sources['probe.resc'].decode().replace('include @/work/input-delay.cs\n','').replace('include @/work/screen-observer.cs\n','').replace('@/reference/main.bin','@/work/main.bin').replace('@/input-boot.bin','@/work/boot.bin')
    (output/'probe.resc').write_text(script);shutil.copy2(__file__,output/'runner-source.py')
    manifest=dict(release=release,synthetic_chip_revision=chip_revision,physical_chip_revision_observed=False,b0_ton_configuration=b0_ton,synthetic_trim=trim,physical_trim_observed=False,upstream_commit='42e27e9c999a340e8b7af406b83a52dc56fcf926',boot_sha256=RELEASES[release],main_sha256=MAIN,main_bytes=len(main),components={n:sha(output/n) for n in ['strict.cs','board.repl','run.py','probe.resc','runner-source.py']},hardware_accessed=False,main_abi_after_reset_unverified=True,initial_sram='Reviewed generic fill, not a physical device dump')
    write_json(output/'manifest.json',manifest)
    reference=checked_asset(PRIVATE,p['assets']['main']).parent
    cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={output},target=/work,readonly','--mount',f'type=bind,source={reference},target=/reference,readonly','--mount',f'type=bind,source={output/"exports"},target=/work-output',p['image_id'],'--disable-gui','--console','-p','-e','quit','/work/probe.resc']
    write_json(output/'launcher.json',dict(command=cmd));return cmd


def run(release,output,trim=-1,*,chip_revision=0x23,b0_ton=False):
    output=Path(output).resolve();cmd=derive(release,output,trim,chip_revision=chip_revision,b0_ton=b0_ton);log=execute(cmd,output,'native',timeout=220,stream=True)
    d=read_json(output/'exports/result.json');points={p['label']:p['hits'] for p in d['points']}
    d['main']=points['main-reset'];d['handoff']=points['stock-handoff'];d['classification']=classify(d);d['scope']=interpret(points)
    d['images_unchanged']=sha(output/'exports/guest-boot.bin')==RELEASES[release] and sha(output/'exports/guest-main.bin')==MAIN
    d['cleanup']=[]
    for n in ['boot.bin','main.bin','exports/guest-boot.bin','exports/guest-main.bin']:
        p=output/n;d['cleanup'].append(dict(path=n,bytes=p.stat().st_size,sha256=sha(p)));p.unlink()
    write_json(output/'report.json',d)
    print(json.dumps({'release':release,'synthetic_trim':trim,'pc':hex(d['pc']),'classification':d['classification'],'scope':d['scope'],'images_unchanged':d['images_unchanged'],'snapshots':d['snapshots'],'uart2_tx':d['uart2_tx']}),flush=True)
    return d


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('release',choices=RELEASES);p.add_argument('output',type=Path);p.add_argument('--trim',type=int,choices=(-1,0,1,2),default=-1);p.add_argument('--b0-ton',action='store_true');p.add_argument('--chip-revision',type=lambda s:int(s,0),choices=(0x21,0x22,0x23,0x24),default=0x23);a=p.parse_args();run(a.release,a.output,a.trim,chip_revision=a.chip_revision,b0_ton=a.b0_ton)

if __name__=='__main__':main()
