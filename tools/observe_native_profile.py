"""Add bounded PC observations to frozen original mains without altering guest code or models."""
import argparse, hashlib, json, shutil
from pathlib import Path
import capstone
from capstone.arm import ARM_OP_IMM
from native_replay import preflight, validate_assets, parse_log, boundary_state, FILES, IMAGE, digest
from pinned_main import load_pinned_main, MAIN_LAYOUT
from execution_observer import instrument as runtime
from run_renode_m55_probe import execute

ROOT=Path(__file__).resolve().parents[1]
SPEC_SHA='2fd9623e3ae14d341bfa43b1573fa4e4f93a43c0f7a3d89c921238c004926664'
RECIPE_SHA='b961ac0b135b6a7d544ea0e566e49bb51a64c7d0b4503d4829e7421c7b90d92c'

def catalog(simulator, source):
    upstream=simulator/'upstream/g2flash-845f665/patches'
    if digest(upstream/'cfw_patches.json')!=SPEC_SHA or digest(upstream/'patch_compress.py')!=RECIPE_SHA:
        raise ValueError('Pinned patch source changed')
    spec=json.loads((upstream/'cfw_patches.json').read_text())
    images={}
    for key,file in [('stock_base','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        bundle=(simulator/'inputs/verified-01'/file).read_bytes()
        actual,raw=load_pinned_main(bundle)
        if actual!=key or raw!=(source/('stock23' if key=='stock_base' else 'cfw')/'main.bin').read_bytes():raise ValueError('Original image differs')
        images[key]=(bundle,raw)
    if spec['base_sha256']!=hashlib.sha256(images['stock_base'][0]).hexdigest() or spec['output_sha256']!=hashlib.sha256(images['cfw'][0]).hexdigest():raise ValueError('Patch bundle provenance differs')
    cs=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS);cs.detail=True
    offset=MAIN_LAYOUT['stock_base'][0];base=0x438000
    raw_end=base+len(images['stock_base'][1]);cfw_end=base+len(images['cfw'][1])
    sites=[];targets={};excluded=[];tlsf=None
    for index,op in enumerate(spec['patches']):
        off=op['offset'];old=bytes.fromhex(op['old']);new=bytes.fromhex(op['new'])
        if images['stock_base'][0][off:off+len(old)]!=old or images['cfw'][0][off:off+len(new)]!=new:raise ValueError('Patch operation byte mismatch')
        if not old or not offset<=off<offset+len(images['stock_base'][1]):continue
        address=base+off-offset
        # Both exclusions are data writes in the pinned source recipe, despite decoding as Thumb.
        if index in (5,11):
            excluded.append(dict(index=index,address=address,reason='callback pointer' if index==5 else 'connection interval data',description=op['desc']));continue
        before=list(cs.disasm(old,address));after=list(cs.disasm(new,address))
        if address&1 or sum(x.size for x in before)!=len(old) or sum(x.size for x in after)!=len(new):raise ValueError('Incomplete instruction patch decoding')
        sites.append(dict(label='patch-site-'+str(index),address=address,kind='patch-site',operation_index=index,description=op['desc'],old_instructions=[x.mnemonic+' '+x.op_str for x in before],new_instructions=[x.mnemonic+' '+x.op_str for x in after]))
        if index==14:
            if len(before)!=1 or len(after)!=1 or any(x.mnemonic!='movs.w' or x.size!=4 or x.reg_name(x.operands[0].reg)!='r2' or x.operands[1].type!=ARM_OP_IMM for x in (before[0],after[0])):
                raise ValueError('Reviewed TLSF size instruction differs')
            tlsf=dict(label='control-after-primary-tlsf',address=address+4,kind='register-effect',expected_r2=dict(stock23=before[0].operands[1].imm,cfw=after[0].operands[1].imm))
        if len(after)==1 and after[0].mnemonic in ('bl','b.w') and after[0].operands[0].type==ARM_OP_IMM:
            target=after[0].operands[0].imm
            if raw_end<=target<cfw_end:
                if target&1 or not list(cs.disasm(images['cfw'][1][target-base:target-base+4],target,count=1)):raise ValueError('Invalid injected code target')
                targets.setdefault(target,[]).append(index)
    if len(sites)!=30 or len(excluded)!=2 or tlsf is None:raise ValueError('Reviewed instruction/data classification differs')
    payload=[dict(label='cfw-target-'+hex(a),address=a,kind='cfw-target',source_operations=indices) for a,indices in sorted(targets.items())]
    return dict(patch_source_sha256=SPEC_SHA,recipe_sha256=RECIPE_SHA,upstream_commit='845f665e0dfdcfd06b7d3a294388de6f17a5bd59',capstone_version=capstone.__version__,sites=sites,payload_targets=payload,excluded_data=excluded,tlsf_effect_point=tlsf,scope='30 source-reviewed in-place instruction sites and direct injected branch targets, not all code/data coverage')

def audit_observation(log, points):
    rows=[json.loads(x.split('BLACKWALL_OBSERVATION ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_OBSERVATION ')]
    if len(rows)!=1:raise ValueError('Missing or ambiguous observation')
    r=rows[0];actual={p['label']:p for p in r['points']}
    if len(actual)!=len(points) or len(r['points'])!=len(points) or any(p['label'] not in actual or actual[p['label']]['address']!=p['address'] for p in points):raise ValueError('Observation point set differs')
    if any(p['hits']<0 or (p['hits']==0)!=(p['first_sequence']==0) for p in r['points']):raise ValueError('Invalid point counts')
    if r['capacity']!=128 or r['sequence']<0 or r['dropped_events']<0 or sum(p['hits'] for p in r['points'])!=r['sequence'] or len(r['events'])>128 or r['dropped_events']+len(r['events'])!=r['sequence']:raise ValueError('Observation history differs')
    if [e['sequence'] for e in r['events']]!=list(range(r['sequence']-len(r['events'])+1,r['sequence']+1)):raise ValueError('Event order differs')
    if any(e['label'] not in actual or e['pc']!=e['address'] or actual[e['label']]['address']!=e['address'] for e in r['events']):raise ValueError('Hook PC differs')
    if actual['control-reset']['hits']!=1 or actual['control-stop']['hits']!=1:raise ValueError('Positive control not observed')
    return r

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('profile',type=Path);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator.resolve();source=s/'iom-startup-main-comparison-01';o=a.output.resolve()
    if o.exists():raise ValueError('Use a fresh evidence directory')
    profile=json.loads(a.profile.read_text());preflight(profile,source);cat=catalog(s,source)
    observer=(ROOT/'tools/renode-execution-observer.cs').read_text()
    o.mkdir(mode=0o700);(o/'catalog.json').write_text(json.dumps(cat,indent=2)+'\n')
    (o/'base-profile.json').write_bytes(a.profile.read_bytes());(o/'observer.cs').write_text(observer)
    (o/'observe_native_profile.py').write_bytes(Path(__file__).read_bytes())
    results=[]
    for case in profile['cases'][:2]:
        name=case['name'];run=o/name;run.mkdir(mode=0o700)
        points=list(cat['sites'])+(cat['payload_targets'] if name=='cfw' else [])+[cat['tlsf_effect_point']]
        raw=(source/name/'main.bin').read_bytes()
        points+= [dict(label='control-reset',address=int.from_bytes(raw[4:8],'little')&~1,kind='control'),dict(label='control-stop',address=case['expected_boundary']['pc'],kind='control')]
        for file in FILES:shutil.copyfile(source/name/file,run/file)
        validate_assets(run,case['files'])
        (run/'strict.cs').write_text((run/'strict.cs').read_text()+'\n'+observer)
        (run/'run.py').write_text(runtime((run/'run.py').read_text(),points))
        validate_assets(run,{f:case['files'][f] for f in FILES if f not in ('strict.cs','run.py')})
        inputs={file:digest(run/file) for file in sorted(FILES)}
        (run/'derived-inputs.json').write_text(json.dumps(dict(base_profile_sha256=digest(a.profile),original_files=case['files'],derived_files=inputs,points=points),indent=2)+'\n')
        command=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={run},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc']
        log=execute(command,run,'renode');native=parse_log(log);observation=audit_observation(log,points)
        validate_assets(run,inputs)
        boundary_matches=boundary_state(native)==case['expected_boundary']
        effect_events=[e for e in observation['events'] if e['label']=='control-after-primary-tlsf']
        expected_r2=cat['tlsf_effect_point']['expected_r2'][name]
        effect_matches=len(effect_events)==1 and effect_events[0]['r2']==expected_r2
        report=dict(name=name,passed=boundary_matches and effect_matches,observed=native,observation=observation,boundary_matches=boundary_matches,tlsf_r2_expected=expected_r2,tlsf_r2_matches=effect_matches,boot_verified=False,hardware_validated=False,installable=False)
        (run/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        if not boundary_matches:raise ValueError('Observation changed selected native endpoint: '+name)
        if not effect_matches:raise ValueError('TLSF instruction effect not verified: '+name)
        hits=[p for p in observation['points'] if p['hits'] and p['label'].startswith(('patch-site','cfw-target'))]
        row=dict(name=name,boundary_matches=True,point_count=len(points),events=observation['sequence'],dropped_events=observation['dropped_events'],patch_or_payload_hits=hits,tlsf_r2=effect_events[0]['r2'])
        results.append(row);print(json.dumps(row),flush=True)
    (o/'report.json').write_text(json.dumps(dict(passed=True,cases=results,scope=cat['scope'],full_boot=False,integrated_display=False,physical_access=False),indent=2)+'\n')

if __name__=='__main__':main()
