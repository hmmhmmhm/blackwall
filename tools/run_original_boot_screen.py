"""Reproduce pinned stock G2 bootloader → main → screen on a virtual temple.

Firmware and the reviewed frozen hardware model remain in the private asset tree.
No physical device discovery or hardware installation operations are provided.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import zlib

from run_renode_m55_probe import execute

ROOT=Path(__file__).resolve().parents[1]
PROFILE=ROOT/'docs/data/original-boot-stock24-profile.json'
COMPONENTS={'strict.cs','board.repl','probe.resc','run.py','input-delay.cs','screen-observer.cs'}
BOOT_POINTS=[('boot-reset',0x432cb2),('boot-crt',0x432cd4),('boot-fpu',0x432cf0),('boot-c-init',0x432d14),('boot-data-init',0x432d34),('boot-main',0x41b862),('boot-init-dispatch',0x41fa08),('boot-board-init',0x430536),('boot-manager',0x42e650),('stock-handoff',0x42dfe8),('main-reset',0x5fbe3e)]
EXPORTS={'native':'boot-reset.json','wire':'wire-activation.json','context':'handoff-context.json','screen':'screen.json','marker':'marker.json','delegated':'delegated-guards.json'}
SCENARIOS=('normal','unknown-boot-marker')
PINNED_IMAGES={'boot':dict(bytes=149773,sha256='ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665'),'main':dict(bytes=3700068,sha256='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a')}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def read_json(path):return json.loads(Path(path).read_text())
def same(a,b):return json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True)
def zero(value):return type(value) is int and value==0


def checked_path(root,relative):
    root=Path(root).resolve();p=(root/relative).resolve()
    if not p.is_relative_to(root):raise ValueError('Path escapes its declared root')
    return p


def checked_asset(root,spec,override=None):
    p=Path(override).resolve() if override else checked_path(root,spec['path'])
    b=p.read_bytes()
    if len(b)!=spec['bytes'] or hashlib.sha256(b).hexdigest()!=spec['sha256']:
        raise ValueError('Asset size/hash mismatch: '+str(p))
    if 'sp' in spec and (len(b)<8 or struct.unpack_from('<II',b)!=(spec['sp'],spec['reset'])):
        raise ValueError('Asset vector mismatch: '+str(p))
    return p


def crc16(data):
    v=0
    for b in data:
        v^=b
        for unused in range(8):v=(v>>1)^(0xa001 if v&1 else 0)
    return v


def decode_frame(data):
    if not isinstance(data,list) or any(type(v) is not int or not 0<=v<=255 for v in data):raise ValueError('Invalid byte frame')
    if len(data)<11 or data[0]!=1:raise ValueError('Unsupported frame')
    n=data[3]*256+data[4]
    if len(data)!=n+11 or crc16(data[:7])!=data[7]*256+data[8] or crc16(data[9:-2])!=data[-2]*256+data[-1]:raise ValueError('Frame CRC/length differs')
    return dict(identifier=data[1]*256+data[2],channel=data[6],payload=data[9:-2])


def valid_frame(screen,raw,ram):
    n=576*288;o=screen['address']-0x20000000
    return (screen['width']==576 and screen['height']==288 and screen['bytes']==n and len(raw)==n
            and 0<=o<=len(ram)-n and raw==ram[o:o+n] and min(raw)!=max(raw)
            and screen['has_detail'] is True and screen['nonzero']==sum(v!=0 for v in raw))


def valid_wire(w):
    try:
        requests={}
        for q in w['requests']:
            d=decode_frame(q['data'])
            if any(not same(d[k],q[k]) for k in d) or d['identifier'] in requests:return False
            requests[d['identifier']]=d
        if len(w['replies'])!=3:return False
        kinds=[]
        for q in w['replies']:
            d=decode_frame(q['data']);source=requests[q['identifier']]
            if d['identifier']!=q['identifier'] or d['channel']!=0 or d['payload']!=[q['kind']]:return False
            if q['accepted'] is not True or q['guest_state_unchanged'] is not True or not same(q['before'],q['after']):return False
            if q['kind']==10 and source['channel']==1:kinds.append(10)
            elif q['kind']==2 and source['channel']==2 and source['payload']==[2,1,1,0,0,0,0,0]:kinds.append(2)
            else:return False
        return kinds==[10,10,2]
    except (KeyError,ValueError,TypeError):return False


def assess(v):
    """Facts derived from native records and independently compared raw artifacts."""
    a=v['native'];w=v['wire'];sc=v['screen'];points={p['label']:p for p in a['points']}
    boot=[points.get(label,{}) for label,address in BOOT_POINTS]
    contexts={q['label']:q for q in v['context']['contexts']}
    b=contexts.get('boot-reset',{});h=contexts.get('stock-handoff',{});m=contexts.get('main-reset',{})
    cadence=w.get('cadence',{});touch=w.get('touch',{});stop=w.get('first_complete_stop',{})
    return dict(
        original_boot_main_path=all(p.get('address')==address and p.get('hits',0)>=1 for p,(_,address) in zip(boot,BOOT_POINTS)) and all(p.get('first',0)>0 for p in boot) and all(x['first']<y['first'] for x,y in zip(boot,boot[1:])),
        original_ui_renderer=all(points.get(label,{}).get('address')==address and points.get(label,{}).get('hits',0)>0 and points[label]['first']>boot[-1].get('first',0) for label,address in [('ui-dispatch',0x4456e8),('app1-callback',0x4b7a58),('renderer-entry',0x4439a4)]),
        original_stack_lineage=(b.get('pc')==0x432cb2 and b.get('vtor')==0x410000 and b.get('msp')==0x2007fb00 and b.get('control')==0 and b.get('psp')==0 and h.get('pc')==0x42dfe8 and h.get('vtor')==0x410000 and h.get('control')==2 and h.get('msp')==0x2007fa90 and m.get('pc')==0x5fbe3e and m.get('vtor')==0x438000 and m.get('msp')==h.get('msp') and m.get('psp')==m.get('sp')==0x2007fb00 and m.get('control')==2 and m.get('process_stack_selected') is True),
        no_cpu_or_policy_fault=all(zero(a[k]) for k in ['cfsr','hfsr','system_control_violations']) and zero(a['policy']['violations']),
        no_mmio_or_delegated_fault=all(zero(g['accesses']) for g in a['guards']) and zero(v['delegated']['rtc_accesses']),
        complete_observations=zero(a['events_dropped']) and bool(a['events']) and [e['sequence'] for e in a['events']]==list(range(1,len(a['events'])+1)),
        stopped_at_completed_frame=(stop.get('stopped') is True and stop.get('pc')==a['pc']==0x560f6a and a['stop_reason']=='wire-complete' and a['halted'] is False),
        touch_without_state_edits=(touch.get('accepted') is True and touch.get('released') is True and touch.get('guest_state_unchanged') is True and same(touch.get('before'),touch.get('after'))),
        actual_tx_correlated_wire=(w.get('completed') is True and w.get('guest_writes') is False and w.get('hardware_accessed') is False and valid_wire(w)),
        architectural_cadence=(cadence.get('architectural_state_unchanged') is True and same(cadence.get('before'),cadence.get('after')) and cadence.get('mode_word')==22 and cadence.get('mips_before')==10 and cadence.get('mips_after')==167),
        declared_cleared_marker=(v['marker']['profile']=='cleared' and v['marker']['boot_reads']==1 and v['marker']['startup_reads']==1),
        complete_frame=(type(sc['captures']) is int and sc['captures']>0 and sc['has_detail'] is True and sc['bytes']==576*288 and zero(sc['rejections']) and sc['fault']==''),
        source_images_unchanged=v['image_equal'] is True,
        paused_cadence_ram_unchanged=v['cadence_equal'] is True,
        frame_is_actual_guest_buffer=v['frame_equal'] is True,
        post_read_cpu_unchanged=v['delegated']['post_observer_unchanged'] is True)


def validate_runtime(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
            if node.func.attr in ('SetRegister','SeedRegister','WriteByte','WriteWord','WriteDoubleWord','WriteQuadWord','WriteBytes'):raise ValueError('Runtime may not write guest CPU or memory')
        if isinstance(node,(ast.Assign,ast.AugAssign,ast.AnnAssign)):
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target,ast.Attribute) and target.attr in ('PC','SP','VectorTableOffset','Control','OtherSP','IsHalted'):raise ValueError('Runtime may not force execution state')


def validate_profile(profile):
    if profile['schema']!=2 or profile['profile_id']!='stock24-original-boot-screen-v1' or set(profile['components'])!=COMPONENTS:raise ValueError('Reviewed stock24 profile required')
    a=profile['assets']
    if any(a[k]['sha256']!=pin['sha256'] or a[k]['bytes']!=pin['bytes'] for k,pin in PINNED_IMAGES.items()):raise ValueError('Unreviewed stock firmware image')
    if set(a)!={'boot','main','sram','itcm'} or (a['boot']['address'],a['main']['address'],a['sram']['address'],a['itcm']['address'])!=(0x410000,0x438000,0x20000000,0):raise ValueError('Unexpected address layout')
    if (a['boot']['sp'],a['boot']['reset'],a['main']['sp'],a['main']['reset'])!=(0x2007fb00,0x432cb3,0x2007fb00,0x5fbe3f):raise ValueError('Unreviewed vectors')
    if profile['budgets']!=dict(initial_virtual_ms=20000,initial_host_seconds=300,docker_seconds=420):raise ValueError('Unreviewed budgets')
    if profile['image_id']!='sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649':raise ValueError('Pinned Renode image required')


def scenario_component(name,data,scenario):
    if scenario=='normal' or name!='board.repl':return data
    before=b'    profile: "cleared"'
    if data.count(before)!=1:raise ValueError('Unique known marker profile required')
    return data.replace(before,b'    profile: "unknown"')


def command_for(folder,assets,image):
    return ['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={folder},target=/work,readonly','--mount',f'type=bind,source={assets["main"].parent},target=/reference,readonly','--mount',f'type=bind,source={assets["boot"]},target=/input-boot.bin,readonly','--mount',f'type=bind,source={folder/"exports"},target=/work-output',image,'--disable-gui','--console','-p','-e','quit','/work/probe.resc']


def derive(profile_path,private_root,output,scenario='normal',boot_image=None,main_image=None):
    private_root=Path(private_root).resolve();out=Path(output).resolve();p=read_json(profile_path);validate_profile(p)
    if scenario not in SCENARIOS:raise ValueError('Unknown scenario')
    if out.exists() or not out.is_relative_to(private_root) or out.is_relative_to(ROOT):raise ValueError('Use a fresh private output directory')
    assets={k:checked_asset(private_root,v,boot_image if k=='boot' else main_image if k=='main' else None) for k,v in p['assets'].items()}
    if not all(assets[k].parent==assets['main'].parent for k in ['sram','itcm']):raise ValueError('Reviewed shared readonly reference directory required')
    sources={}
    for name,spec in p['components'].items():
        root=ROOT if spec['origin']=='repo' else private_root
        path=checked_path(root,spec['path'])
        if sha(path)!=spec['sha256']:raise ValueError('Component hash mismatch: '+name)
        sources[name]=path.read_bytes()
    validate_runtime(sources['run.py'].decode())
    out.mkdir(mode=0o700,parents=True);(out/'exports').mkdir(mode=0o700)
    for name,data in sources.items():(out/name).write_bytes(scenario_component(name,data,scenario))
    for name,src in [('runner-source.py',Path(__file__)),('execute-source.py',ROOT/'tools/run_renode_m55_probe.py'),('process-source.py',ROOT/'tools/native_process_recovery.py')]:shutil.copy2(src,out/name)
    manifest=dict(schema=2,profile=p,profile_sha256=sha(profile_path),scenario=scenario,assets={k:dict(v,path=str(assets[k])) for k,v in p['assets'].items()},components={n:sha(out/n) for n in COMPONENTS},host_sources={n:sha(out/n) for n in ['runner-source.py','execute-source.py','process-source.py']})
    write_json(out/'manifest.json',manifest);cmd=command_for(out,assets,p['image_id']);write_json(out/'launcher.json',dict(command=cmd))
    return out


def collect_witnesses(folder):
    """Verify full temporary dumps before retiring reproducible duplicates."""
    manifest=read_json(folder/'manifest.json');e=folder/'exports';images={}
    for name in ['boot','main']:
        q=e/('guest-'+name+'.bin');d=q.read_bytes();spec=manifest['assets'][name]
        images[name]=dict(bytes=len(d),sha256=hashlib.sha256(d).hexdigest(),canonical_sha256=spec['sha256'])
    before=(e/'cadence-before-sram.bin').read_bytes() if (e/'cadence-before-sram.bin').exists() else None
    after=(e/'cadence-after-sram.bin').read_bytes() if (e/'cadence-after-sram.bin').exists() else None
    witnesses=dict(images=images,image_equal=all(v['sha256']==v['canonical_sha256'] and v['bytes']==manifest['assets'][k]['bytes'] for k,v in images.items()),cadence_equal=before is not None and before==after,cadence_sha256=hashlib.sha256(before).hexdigest() if before is not None else None)
    write_json(e/'artifact-witnesses.json',witnesses)
    return witnesses


def native_records(folder):
    e=folder/'exports';v={k:read_json(e/n) for k,n in EXPORTS.items()};proof=read_json(e/'artifact-witnesses.json')
    # Image identity is checked against manifest pins, not a saved success boolean.
    specs=read_json(folder/'manifest.json')['assets']
    v['image_equal']=all(proof['images'][k]['sha256']==specs[k]['sha256'] and proof['images'][k]['bytes']==specs[k]['bytes'] for k in ['boot','main'])
    before=e/'cadence-before-sram.bin';after=e/'cadence-after-sram.bin'
    v['cadence_equal']=(before.read_bytes()==after.read_bytes()) if before.exists() and after.exists() else proof['cadence_equal']
    raw=(e/'complete-screen.bin').read_bytes() if (e/'complete-screen.bin').exists() else b''
    v['frame_equal']=valid_frame(v['screen'],raw,(e/'main-state-sram.bin').read_bytes()) if raw else False
    return v


def logged_json(log,tag):
    lines=[line.split(tag,1)[1] for line in log.splitlines() if tag in line]
    if len(lines)!=1:raise ValueError('Missing/ambiguous native log record: '+tag)
    return json.JSONDecoder().raw_decode(lines[0])[0]


def audit(folder,audit_output):
    folder=Path(folder).resolve();out=Path(audit_output).resolve()
    if out.exists() or out.is_relative_to(folder):raise ValueError('Audit must use a fresh separate directory')
    out.mkdir(mode=0o700,parents=True);checks={};errors=[]
    try:
        m=read_json(folder/'manifest.json');validate_profile(m['profile']);
        if m['scenario'] not in SCENARIOS:raise ValueError('Unknown scenario')
        checks['profile_pin']=hashlib.sha256((json.dumps(m['profile'],ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()==m['profile_sha256']
        checks['component_pins']=all(sha(folder/n)==h for n,h in m['components'].items())
        checks['component_contract']=all(m['components'][n]==spec['sha256'] for n,spec in m['profile']['components'].items() if n!='board.repl' or m['scenario']=='normal')
        if m['scenario']=='unknown-boot-marker':
            b=(folder/'board.repl').read_bytes();checks['marker_only_change']=hashlib.sha256(b.replace(b'    profile: "unknown"',b'    profile: "cleared"')).hexdigest()==m['profile']['components']['board.repl']['sha256']
        checks['host_source_pins']=all(sha(folder/n)==h for n,h in m['host_sources'].items())
        validate_runtime((folder/'run.py').read_text());checks['no_forced_guest_state']=True
        for k,spec in m['assets'].items():
            checked_asset(Path('/'),spec,spec['path'])
        checks['assets_still_pinned']=True
        assets={k:Path(v['path']) for k,v in m['assets'].items()};checks['launcher_contract']=read_json(folder/'launcher.json')['command']==command_for(folder,assets,m['profile']['image_id'])
        checks['owned_container_removed']=read_json(folder/'renode.process.json')['status']=='removed'
        process=read_json(folder/'execution.json');checks['execution_exit_zero']=process['exit_code']==0
        if (folder/'artifacts.json').exists():checks['retained_artifact_pins']=all(sha(folder/n)==h for n,h in read_json(folder/'artifacts.json').items())
        v=native_records(folder);log=(folder/'renode.log').read_text();checks['native_log_records_match']=all(same(logged_json(log,tag),v[k]) for k,tag in [('native','BLACKWALL_BOOT_RESET '),('wire','BLACKWALL_BOOT_WIRE '),('screen','BLACKWALL_BOOT_SCREEN '),('delegated','BLACKWALL_DELEGATED_GUARDS ')])
        if m['scenario']=='normal':facts=assess(v);boundary=dict(kind='bounded-capture')
        else:
            a=v['native'];p={q['label']:q for q in a['points']}
            facts=dict(no_frame=v['screen']['captures']==0 and v['screen']['bytes']==0,no_main=p['main-reset']['hits']==0,no_handoff=p['stock-handoff']['hits']==0,no_external_inputs=v['wire']['completed'] is False and v['wire']['requests']==[] and v['wire']['replies']==[],boot_manager_reached=p['boot-manager']['hits']==1,original_inputs=v['image_equal'],unknown_marker=v['marker']['profile']=='unknown',no_cpu_fault=zero(a['cfsr']) and zero(a['hfsr']) and zero(a['policy']['violations']))
            boundary=dict(kind='strict-mmio',pc=0x42e582,address=0x7fe000,operation='read',width=4,value=0)
        from run_native_candidate import finish_capture
        events=v['native']['events'];result=dict(schema=2,case=m['profile']['profile_id'],scenario=m['scenario'],boundary_kind=boundary['kind'],observed=v['native'],facts=dict(checks,**facts),identity={k:m['assets'][k]['sha256'] for k in PINNED_IMAGES},selected_observation=dict(sequence=events[-1]['sequence'] if events else 0,dropped_events=v['native']['events_dropped'],events=events))
        contract=dict(boundary=boundary,comparison=dict(policy='bounded-invariants',paths=[['identity']]),checks=[dict(path=['facts',k],eq=True) for k in result['facts']],allowed_differences=['Host polling can vary the initial virtual endpoint; no exact CPU/time equivalence is claimed','Initial fade alpha/raw SHA may vary; each frame must be complete and exactly match same-time guest SRAM'],unresolved_differences=m['profile']['scope_notes'])
        result=finish_capture(result,dict(identity={k:v['sha256'] for k,v in PINNED_IMAGES.items()}),contract)
        result['execution_passed']=checks['execution_exit_zero']
    except (KeyError,ValueError,OSError,TypeError) as error:
        errors.append(str(error));result=dict(schema=2,execution_passed=checks.get('execution_exit_zero',False),passed=False,semantic_validation=dict(passed=False),checks=checks,errors=errors)
    write_json(out/'report.json',result)
    return result


def render_preview(folder):
    e=folder/'exports';p=e/'complete-screen.bin'
    if not p.exists():return
    raw=p.read_bytes()
    if len(raw)!=576*288:return
    def chunk(tag,d):return struct.pack('>I',len(d))+tag+d+struct.pack('>I',zlib.crc32(tag+d)&0xffffffff)
    peak=max(raw)
    preview=bytes(v*255//peak for v in raw) if peak>0 else raw
    for name,data in [('complete-screen.png',raw),('contrast-preview.png',preview)]:
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',576,288,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+data[y*576:(y+1)*576] for y in range(288))))+chunk(b'IEND',b'')
        (e/name).write_bytes(png)


def cleanup(folder):
    if read_json(folder/'renode.process.json')['status']!='removed':raise ValueError('Owned container is not terminal')
    witness=read_json(folder/'exports/artifact-witnesses.json')
    if not witness['image_equal']:raise ValueError('Preserve changed firmware dumps for diagnosis')
    removed=[]
    for name in ['guest-boot.bin','guest-main.bin','cadence-before-sram.bin','cadence-after-sram.bin']:
        q=folder/'exports'/name
        if not q.exists():continue
        removed.append(dict(path=str(q.relative_to(folder)),bytes=q.stat().st_size,sha256=sha(q)));q.unlink()
    write_json(folder/'cleanup.json',dict(removed=removed,recovered_bytes=sum(x['bytes'] for x in removed),owned_container_removed=True))
    pins={str(p.relative_to(folder)):sha(p) for p in sorted((folder/'exports').iterdir()) if p.is_file()}
    pins['cleanup.json']=sha(folder/'cleanup.json');pins['execution.json']=sha(folder/'execution.json');pins['renode.log']=sha(folder/'renode.log');write_json(folder/'artifacts.json',pins)


def run(folder):
    folder=Path(folder);m=read_json(folder/'manifest.json')
    for n,h in m['components'].items():
        if sha(folder/n)!=h:raise ValueError('Derived component changed before run: '+n)
    for spec in m['assets'].values():checked_asset(Path('/'),spec,spec['path'])
    image=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',m['profile']['image_id']],text=True,timeout=15).strip()
    if image!=m['profile']['image_id']:raise ValueError('Docker image differs')
    try:
        execute(read_json(folder/'launcher.json')['command'],folder,'renode',timeout=420,stream=True)
        write_json(folder/'execution.json',dict(exit_code=0))
    except Exception as error:
        write_json(folder/'execution.json',dict(exit_code=None,error=str(error)));raise
    collect_witnesses(folder);render_preview(folder)
    before=audit(folder,folder.parent/(folder.name+'-audit-before-cleanup'))
    cleanup(folder)
    after=audit(folder,folder.parent/(folder.name+'-audit'))
    return bool(before['passed'] and after['passed'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',type=Path,default=PROFILE);p.add_argument('--private-root',type=Path);p.add_argument('--output',type=Path);p.add_argument('--scenario',choices=SCENARIOS,default='normal');p.add_argument('--boot-image',type=Path);p.add_argument('--main-image',type=Path);p.add_argument('--derive-only',action='store_true');p.add_argument('--audit-existing',type=Path);p.add_argument('--audit-output',type=Path);a=p.parse_args()
    if a.audit_existing:
        if not a.audit_output:p.error('--audit-output is required')
        report=audit(a.audit_existing,a.audit_output);print(json.dumps(dict(passed=report['passed'],execution_passed=report['execution_passed'],report=str(a.audit_output/'report.json'))));return 0 if report['passed'] else 1
    if not a.output:p.error('--output is required')
    if not a.private_root:p.error('--private-root is required for a new run')
    out=derive(a.profile,a.private_root,a.output,a.scenario,a.boot_image,a.main_image)
    if a.derive_only:print(json.dumps(dict(derived=str(out))));return 0
    passed=run(out);print(json.dumps(dict(passed=passed,output=str(out))));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
