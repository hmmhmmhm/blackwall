"""Boot a fresh frozen G2 board from a verified virtual writer's actual MRAM output."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from run_boot_validation import runtime,GUARDS,classify,PINS
from run_original_boot_screen import ROOT,PRIVATE,PROFILE,read_json,validate_profile,checked_asset,checked_path,validate_runtime,sha,write_json,EXPORTS,assess,valid_frame
from run_renode_m55_probe import execute


def digest(data):return hashlib.sha256(data).hexdigest()


def validate_lineage(report,mram,mode,*,boot_state="patched"):
    if mode not in ('restored','incomplete','interrupted-valid-vectors') or len(mram)!=0x400000:
        raise ValueError('Reviewed mode and full4MiB MRAM required')
    if boot_state not in ('patched','stock-prefix'):raise ValueError('Reviewed boot state required')
    if boot_state=='patched':
        if report.get('passed') is not True or report.get('full_main_restore') is not True or report.get('checks',{}).get('whole_mram_expected') is not True:
            raise ValueError('Verified whole-main ARM writer output required')
    elif mode!='restored' or report.get('boot_restore') is not True or report.get('destination') not in (0x410000,0x434910):
        raise ValueError('Explicit boot restoration snapshot required')
    if report.get('rom_programming_modeled') is not True or report.get('hardware_accessed') is not False or digest(mram)!=report.get('final_mram_sha256'):
        raise ValueError('Virtual writer provenance/hash mismatch')
    if boot_state=='patched':
        if digest(mram[0x10000:0x37000])!=PINS['patched']:raise ValueError('Pinned research boot required')
    elif digest(mram[0x10000:0x10000+149773])!=PINS['boot']:
        raise ValueError('Exact original stock boot prefix required; tail is assessed separately')
    # Frozen metadata owner returns zero slots. Never silently replace a nonzero
    # persistent snapshot with those synthetic zeros on reboot.
    metadata=bytearray(mram[0x3f8000:]);marker=int.from_bytes(metadata[0x6000:0x6004],'little');metadata[0x6000:0x6004]=bytes(4)
    if marker not in (0,0xffffffff) or any(metadata):raise ValueError('Metadata must match the declared zero-slot and clear-marker fixture')
    main=mram[0x38000:0x38000+3700068]
    if mode=='restored':
        if (boot_state=='patched' and report.get('destination')!=0x438000) or digest(main)!=PINS['main']:
            raise ValueError('Vector commit and exact restored stock main required')
    elif mode=='incomplete':
        if report.get('destination')!=0x438010 or main[:16]!=bytes(16):
            raise ValueError('Incomplete body fixture must retain uncommitted vectors')
    elif report.get('destination')!=0x438010 or report.get('observed',{}).get('power_interrupted') is not True or int.from_bytes(main[:4],'little')!=0x2007fb00 or int.from_bytes(main[4:8],'little')!=0x5fbe3f or digest(main)==PINS['main']:
        raise ValueError('Interrupted incomplete main with retained stock vectors required')


def reboot_path_matches(points,events,mode):
    labels=[e['label'] for e in events if e['label'] in ('sp-predicate','sp-accepted','sp-rejected-target','stock-handoff','main-reset')]
    if 'sp-predicate' not in labels:return False
    tail=labels[labels.index('sp-predicate'):]
    if mode=='incomplete':return tail[:2]==['sp-predicate','sp-rejected-target'] and points['stock-handoff']==points['main-reset']==0
    return tail[:4]==['sp-predicate','sp-accepted','stock-handoff','main-reset'] and points['main-reset']>0


def run(writer_output,output,mode,*,screen=False,boot_state="patched"):
    writer_output=Path(writer_output).resolve();output=Path(output).resolve()
    if not writer_output.is_relative_to(PRIVATE) or output.exists() or not output.is_relative_to(PRIVATE) or output.is_relative_to(ROOT):raise ValueError('Private writer input and fresh private output required')
    if screen and mode!='restored':raise ValueError('Screen check requires complete restored main')
    report=read_json(writer_output/'report.json');mram=(writer_output/'exports/final-mram.bin').read_bytes();validate_lineage(report,mram,mode,boot_state=boot_state)
    profile=read_json(PROFILE);validate_profile(profile)
    assets={k:checked_asset(PRIVATE,v) for k,v in profile['assets'].items()}
    sources={}
    for name,spec in profile['components'].items():
        p=checked_path(ROOT if spec['origin']=='repo' else PRIVATE,spec['path'])
        if sha(p)!=spec['sha256']:raise ValueError('Frozen source changed: '+name)
        sources[name]=p.read_bytes()
    strict=sources['strict.cs'];old=b'value=Profile=="cleared"?0xffffffffu:0x55555555u'
    if strict.count(old)!=1:raise ValueError('Unique frozen OTA marker owner required')
    marker=int.from_bytes(mram[0x3fe000:0x3fe004],'little')
    # The only model adaptation is the marker read value from the actual MRAM.
    strict=strict.replace(old,('value=Profile=="cleared"?0x%08xu:0x55555555u'%marker).encode())
    boot_length=159744 if boot_state=="patched" else 149773
    source=runtime(boot_length)
    if screen:
        source=sources['run.py'].decode()
        if source.count('149773')!=2:raise ValueError('Frozen screen boot length references changed')
        source=source.replace('149773',str(boot_length))
    extra="for label,address in [('sp-predicate',0x42e400),('sp-accepted',0x42e406),('sp-rejected-target',0x42e1f6)]:observer.AddPoint(label,address)\n"
    source=source.replace('start=int(m.ElapsedVirtualTime',extra+'start=int(m.ElapsedVirtualTime')
    # Same reviewed worker point as this pinned research image, not the old placeholder.
    candidate=PRIVATE/'recovery/private-boot-24-candidate-01'
    meta=read_json(candidate/'source/build/patch.json');worker=meta['base']+meta['functions']['uart2_worker']['offset']
    source=source.replace('0x4352a0',hex(worker));validate_runtime(source)
    output.mkdir(parents=True,mode=0o700);(output/'exports').mkdir(mode=0o700)
    for name,data in [('strict.cs',strict),('board.repl',sources['board.repl']),('boot-region.bin',mram[0x10000:0x38000]),('main-region.bin',mram[0x38000:0x3f8000])]:
        (output/name).write_bytes(data);(output/name).chmod(0o600)
    (output/'run.py').write_text(source);shutil.copy2(__file__,output/'runner-source.py')
    script=sources['probe.resc'].decode()
    if screen:
        for name in ('input-delay.cs','screen-observer.cs'):(output/name).write_bytes(sources[name])
    else:script=script.replace('include @/work/input-delay.cs\n','').replace('include @/work/screen-observer.cs\n','')
    script=script.replace('@/reference/main.bin','@/work/main-region.bin').replace('@/input-boot.bin','@/work/boot-region.bin')
    (output/'probe.resc').write_text(script)
    manifest=dict(mode=mode,screen=screen,boot_state=boot_state,boot_executable_bytes=boot_length,writer_completed=report.get('passed') is True,writer_output=str(writer_output),writer_report_sha256=sha(writer_output/'report.json'),
                  persistent_input_sha256=digest(mram),marker=marker,boot_sha256=digest(mram[0x10000:0x10000+boot_length]),boot_footprint_sha256=digest(mram[0x10000:0x37000]),main_sha256=digest(mram[0x38000:0x38000+3700068]),
                  components={n:sha(output/n) for n in ('strict.cs','board.repl','run.py','probe.resc','runner-source.py','boot-region.bin','main-region.bin')},
                  scope='Fresh bootloader reset from actual writer MRAM windows/zero metadata; separate machine from the isolated RAM-call bridge',forced_execution=False,hardware_accessed=False)
    write_json(output/'manifest.json',manifest)
    cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
         '--mount',f'type=bind,source={output},target=/work,readonly','--mount',f'type=bind,source={assets["main"].parent},target=/reference,readonly',
         '--mount',f'type=bind,source={output/"exports"},target=/work-output',profile['image_id'],'--disable-gui','--console','-p','-e','quit','/work/probe.resc']
    write_json(output/'launcher.json',dict(command=cmd));log=execute(cmd,output,'native',timeout=420 if screen else 220,stream=True)
    if screen:return collect_screen(output,writer_output,manifest)
    result=read_json(output/'exports/result.json');points={p['label']:p['hits'] for p in result['points']}
    result['handoff']=points['stock-handoff'];result['main']=points['main-reset'];result['classification']=classify(result)
    checks=dict(images_unchanged=sha(output/'exports/guest-boot.bin')==manifest['boot_sha256'] and sha(output/'exports/guest-main.bin')==manifest['main_sha256'],
                input_snapshot_unchanged=digest((writer_output/'exports/final-mram.bin').read_bytes())==manifest['persistent_input_sha256'],
                boot_reset=points['boot-reset']>0,no_observation_drop=result['events_dropped']==0,
                reached_expected=reboot_path_matches(points,result['events'],mode))
    if mode=='restored':checks['no_fault_or_guard']=result['classification']=='main-entered'
    result.update(passed=all(checks.values()),checks=checks,hardware_accessed=False,boot_rom_executed=False,same_board_recovery_verified=False,
                  restored_main_reboot_verified=mode=='restored' and boot_state=='patched' and all(checks.values()),boot_prefix_reboot_verified=boot_state=='stock-prefix' and all(checks.values()),writer_completed=report.get('passed') is True)
    cleanup=[]
    for name in ('boot-region.bin','main-region.bin','exports/guest-boot.bin','exports/guest-main.bin'):
        p=output/name;cleanup.append(dict(name=name,bytes=p.stat().st_size,sha256=sha(p)));p.unlink()
    result['cleanup']=cleanup;write_json(output/'report.json',result)
    print(json.dumps(dict(mode=mode,passed=result['passed'],classification=result['classification'],main=result['main'],handoff=result['handoff'],pc=hex(result['pc']))),flush=True)
    if not result['passed']:raise ValueError('Restored boot contract failed; inspect saved report')
    return result


def collect_screen(output,writer_output,manifest):
    e=output/'exports';v={k:read_json(e/n) for k,n in EXPORTS.items()}
    v['image_equal']=sha(e/'guest-boot.bin')==manifest['boot_sha256'] and sha(e/'guest-main.bin')==manifest['main_sha256']
    before=(e/'cadence-before-sram.bin').read_bytes() if (e/'cadence-before-sram.bin').exists() else None;after=(e/'cadence-after-sram.bin').read_bytes() if (e/'cadence-after-sram.bin').exists() else None
    v['cadence_equal']=before is not None and before==after
    raw=(e/'complete-screen.bin').read_bytes() if (e/'complete-screen.bin').exists() else b''
    v['frame_equal']=valid_frame(v['screen'],raw,(e/'main-state-sram.bin').read_bytes()) if raw else False
    checks=assess(v)
    checks['declared_cleared_marker']=checks['declared_cleared_marker'] and manifest['marker']==0xffffffff
    checks['writer_snapshot_unchanged']=sha(writer_output/'exports/final-mram.bin')==manifest['persistent_input_sha256']
    result=dict(passed=all(checks.values()),checks=checks,restored_main_reboot_verified=manifest.get('boot_state','patched')=='patched' and all(checks.values()),boot_prefix_reboot_verified=manifest.get('boot_state')=='stock-prefix' and all(checks.values()),writer_completed=manifest.get('writer_completed',True),
                frame_sha256=digest(raw),cadence_sram_sha256=digest(before) if before is not None else None,frame_bytes=len(raw),hardware_accessed=False,
                same_board_recovery_verified=False,boot_rom_executed=False,scope='Actual MRAM → '+manifest.get('boot_state','patched')+' boot reset → stock main → first guest framebuffer, existing virtual touch/peer/reference GPU/sensor models')
    cleanup=[]
    for name in ('boot-region.bin','main-region.bin','exports/guest-boot.bin','exports/guest-main.bin','exports/cadence-before-sram.bin','exports/cadence-after-sram.bin'):
        p=output/name
        if p.exists():cleanup.append(dict(name=name,bytes=p.stat().st_size,sha256=sha(p)));p.unlink()
    result['cleanup']=cleanup;write_json(output/'report.json',result);print(json.dumps(result),flush=True)
    if not result['passed']:raise ValueError('Restored screen contract failed; inspect saved report')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('writer_output',type=Path);p.add_argument('output',type=Path);p.add_argument('--mode',choices=['restored','incomplete','interrupted-valid-vectors'],required=True);p.add_argument('--screen',action='store_true');p.add_argument('--boot-state',choices=['patched','stock-prefix'],default='patched');a=p.parse_args();run(a.writer_output,a.output,a.mode,screen=a.screen,boot_state=a.boot_state)
if __name__=='__main__':main()
