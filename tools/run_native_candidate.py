"""Execute a reviewed data-driven candidate against frozen original-reset inputs."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,MAIN_LAYOUT,digest,validate_assets
from run_renode_m55_probe import execute
from firmware_candidate import load_candidate, metadata as firmware_metadata, candidate_runtime

def observe(log,allow_bounded_capture=False):
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_REPORT ')]
    if len(rows)!=1:raise ValueError('Missing unique CPU report')
    v=rows[0];mmio=sum(g['accesses'] for g in v['guards']);system=v['system_control']['violations'];memory=v['memory_policy']['violations']
    bounded=allow_bounded_capture and not v['machine_paused_before_host'] and (mmio,system,memory)==(0,0,0)
    if not bounded and (not v['machine_paused_before_host'] or memory or (mmio,system) not in [(1,0),(0,1)]):raise ValueError('Ambiguous stop, memory violation, or host timeout')
    kind='bounded-capture' if bounded else 'strict-mmio' if mmio else 'unsupported-system-control'
    for l in log.splitlines():
        lower=l.lower()
        if (('[warning]' in lower and 'translation cache size' not in lower) or ('[error]' in lower and 'this machine has aborted' not in lower) or any(t in lower for t in ['unhandled','non existing','non-existing','could not execute','blackwall_runtime_error'])):raise ValueError('Unexpected native message: '+l)
    return v,kind

def local(root,name):
    path=(root/name).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('Plan path escapes its root')
    return path

def observation_runtime(runtime,plan):
    mode=plan.get('execution_mode')
    if mode is None:return runtime
    if mode!='until-guest-stop' or plan['schema']!=2 or 'host_capture_seconds' in plan:
        raise ValueError('Explicit schema2 guest-stop mode cannot use a host capture deadline')
    pattern=r'^    while not m\.IsPaused(?: and live_seconds<[0-9]+)?:\n'
    if len(re.findall(pattern,runtime,re.MULTILINE))!=1 or len(re.findall(r'^    while not m\.IsPaused[^\n]*:\n',runtime,re.MULTILINE))!=1:
        raise ValueError('Missing unique reviewed guest observation loop')
    return re.sub(pattern,'    while not m.IsPaused:\n',runtime,count=1,flags=re.MULTILINE)

def memory_export_policy(plan):
    policy=plan.get('memory_export_policy','guest-stop')
    if policy not in ('guest-stop','paused-after-observation'):raise ValueError('Unknown memory export policy')
    if policy=='paused-after-observation':
        seconds=plan.get('host_capture_seconds')
        if (plan.get('schema')!=2 or type(seconds) is not int or not 10<=seconds<=300
            or plan.get('execution_mode') is not None or not plan.get('post_stop_memory_exports')):
            raise ValueError('Paused snapshot requires explicit finite schema2 observation and memory exports')
    return policy

def memory_exports(plan):
    memory_export_policy(plan)
    exports=plan.get('post_stop_memory_exports',[])
    if not isinstance(exports,list) or len(exports)>4 or exports and plan['schema']!=2:
        raise ValueError('Memory exports require a bounded schema2 plan')
    names=set()
    for item in exports:
        if not isinstance(item,dict) or set(item)!={'name','address','length'}:
            raise ValueError('Invalid memory export fields')
        name,address,length=item['name'],item['address'],item['length']
        if not isinstance(name,str) or not re.fullmatch('[a-z][a-z0-9-]{0,63}\\.bin',name) or name in names:
            raise ValueError('Unique local binary export name required')
        names.add(name)
        if type(address) is not int or type(length) is not int or length<=0 or not any(start<=address and address+length<=end for start,end in [(0,0x40000),(0x20000000,0x20380000)]):
            raise ValueError('Memory export must stay inside mapped G2 SRAM or ITCM')
    return exports

def memory_export_runtime(exports,policy='guest-stop'):
    if policy not in ('guest-stop','paused-after-observation'):raise ValueError('Unknown memory export policy')
    if not exports:return ''
    if policy=='guest-stop':
        code="    if not blackwall_paused_before_host or not m.IsPaused:raise ValueError('Memory export requires an existing guest stop')\n"
    else:
        code="    if not m.IsPaused:raise ValueError('Memory snapshot requires an already paused machine')\n"
        code+="    blackwall_snapshot_cpu=m['sysbus.cpu']\n    blackwall_snapshot_pc=int(blackwall_snapshot_cpu.PC.RawValue)\n    blackwall_snapshot_instructions=int(blackwall_snapshot_cpu.ExecutedInstructions)\n"
    code+="    import clr\n    clr.AddReference('System.Security.Cryptography')\n    from System.IO import File\n    from System.Security.Cryptography import SHA256\n    blackwall_memory_exports=[]\n"
    for item in exports:
        code+="    blackwall_memory_data=m.SystemBus.ReadBytes("+str(item['address'])+","+str(item['length'])+",True)\n"
        code+="    File.WriteAllBytes('/work-output/"+item['name']+"',blackwall_memory_data)\n"
        code+="    blackwall_memory_sha=SHA256.Create()\n    blackwall_memory_hash=''.join('{0:02x}'.format(int(x)) for x in blackwall_memory_sha.ComputeHash(blackwall_memory_data))\n    blackwall_memory_sha.Dispose()\n"
        code+="    blackwall_memory_exports.append(dict(name="+repr(item['name'])+",address="+str(item['address'])+",length="+str(item['length'])+",sha256=blackwall_memory_hash))\n"
    if policy=='paused-after-observation':
        code+="    blackwall_snapshot=dict(origin='guest-stop' if blackwall_paused_before_host else 'host-observation-limit',paused_before=True,paused_after=bool(m.IsPaused),pc_before=blackwall_snapshot_pc,pc_after=int(blackwall_snapshot_cpu.PC.RawValue),instructions_before=blackwall_snapshot_instructions,instructions_after=int(blackwall_snapshot_cpu.ExecutedInstructions))\n"
        code+="    if not blackwall_snapshot['paused_after'] or blackwall_snapshot['pc_before']!=blackwall_snapshot['pc_after'] or blackwall_snapshot['instructions_before']!=blackwall_snapshot['instructions_after']:raise ValueError('CPU changed during paused memory snapshot')\n"
        code+="    Console.WriteLine('BLACKWALL_MEMORY_SNAPSHOT '+json.dumps(blackwall_snapshot))\n"
    return code+"    Console.WriteLine('BLACKWALL_MEMORY_EXPORTS '+json.dumps(blackwall_memory_exports))\n"

def validate_memory_exports(folder,exports,native):
    if not isinstance(native,list) or len(native)!=len(exports):raise ValueError('Missing native memory exports')
    for item,record in zip(exports,native):
        path=local(folder/'exports',item['name'])
        if not path.is_file() or path.stat().st_size!=item['length'] or record!=dict(item,sha256=digest(path)):
            raise ValueError('Export bytes differ from native size/hash metadata')
    return native

def replace_memory_export_runtime(runtime,previous,exports,previous_policy='guest-stop',policy='guest-stop'):
    old=memory_export_runtime(previous,previous_policy)
    if old:
        if runtime.count(old)!=1:raise ValueError('Missing unique inherited memory exporter')
        runtime=runtime.replace(old,'')
    if 'BLACKWALL_MEMORY_EXPORTS ' in runtime:raise ValueError('Unknown inherited memory exporter')
    anchor="    Console.WriteLine('BLACKWALL_REPORT "
    if runtime.count(anchor)!=1:raise ValueError('Missing stopped report anchor')
    return runtime.replace(anchor,memory_export_runtime(exports,policy)+anchor)

def read_memory_export_records(log,runtime,exports,policy='guest-stop'):
    records=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_MEMORY_EXPORTS ')]
    block=memory_export_runtime(exports,policy)
    count=runtime.count(block) if block else 0
    # Historical captures inherited one exporter and injected the same block again.
    if count not in (1,2) or runtime.count('BLACKWALL_MEMORY_EXPORTS ')!=count or len(records)!=count or any(record!=records[0] for record in records):
        raise ValueError('Missing, ambiguous, or differing memory export records')
    return records[0]

def read_memory_snapshot(log,policy,observed):
    rows=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_MEMORY_SNAPSHOT ')]
    if policy=='guest-stop':
        if rows:raise ValueError('Unexpected paused memory snapshot metadata')
        return None
    if policy!='paused-after-observation' or len(rows)!=1:raise ValueError('Missing unique paused memory snapshot')
    snapshot=rows[0]
    fields={'origin','paused_before','paused_after','pc_before','pc_after','instructions_before','instructions_after'}
    if not isinstance(snapshot,dict) or set(snapshot)!=fields:raise ValueError('Invalid memory snapshot fields')
    if snapshot['paused_before'] is not True or snapshot['paused_after'] is not True:
        raise ValueError('Snapshot did not remain paused')
    for field in ['pc_before','pc_after','instructions_before','instructions_after']:
        if type(snapshot[field]) is not int or snapshot[field]<0:raise ValueError('Invalid snapshot CPU state')
    if type(observed.get('machine_paused_before_host')) is not bool:raise ValueError('Missing observed stop origin')
    origin='guest-stop' if observed['machine_paused_before_host'] else 'host-observation-limit'
    if (snapshot['origin']!=origin or snapshot['pc_before']!=snapshot['pc_after'] or snapshot['pc_after']!=observed['pc']
        or snapshot['instructions_before']!=snapshot['instructions_after'] or snapshot['instructions_after']!=observed['instructions']):
        raise ValueError('Snapshot CPU state or stop origin differs from report')
    return snapshot

def at(value,path):
    for key in path:value=value[key]
    return value

def same(left,right):
    return json.dumps(left,sort_keys=True,separators=(',',':'))==json.dumps(right,sort_keys=True,separators=(',',':'))

def validate_semantics(spec):
    required={'boundary','comparison','checks','allowed_differences','unresolved_differences'}
    if not isinstance(spec,dict) or set(spec)!=required:raise ValueError('Invalid semantic contract fields')
    b=spec['boundary'];kind=b.get('kind') if isinstance(b,dict) else None
    fields={'kind','pc','address','operation','width','value'} if kind=='strict-mmio' else {'kind'}
    if kind not in ('strict-mmio','bounded-capture','unsupported-system-control') or set(b)!=fields:raise ValueError('Invalid expected boundary')
    if kind=='strict-mmio':
        if any(type(b[k]) is not int or b[k]<0 for k in ['pc','address','width','value']) or not isinstance(b['operation'],str) or not re.fullmatch('[a-z][a-z0-9-]{0,63}',b['operation']) or b['width'] not in (1,2,4):raise ValueError('Invalid MMIO expectation')
    def path(p):return isinstance(p,list) and bool(p) and all(type(k) is str or type(k) is int and k>=0 for k in p)
    c=spec['comparison'];policy=c.get('policy') if isinstance(c,dict) else None
    if policy=='bounded-invariants':
        if set(c)!={'policy','paths'} or not isinstance(c['paths'],list) or not c['paths'] or not all(path(p) for p in c['paths']):raise ValueError('Invalid bounded invariant paths')
    elif policy in ('exact','prefix','subsequence'):
        if set(c)!={'policy','path'} or not path(c['path']):raise ValueError('Invalid comparison path')
    else:raise ValueError('Unknown comparison policy')
    if not isinstance(spec['checks'],list) or not spec['checks']:raise ValueError('Semantic checks are required')
    for check in spec['checks']:
        if not isinstance(check,dict) or set(check) not in ({'path','eq'},{'path','eq_source'}) or not path(check['path']):raise ValueError('Invalid semantic check')
        if 'eq_source' in check and not path(check['eq_source']):raise ValueError('Invalid source comparison path')
    for name in ['allowed_differences','unresolved_differences']:
        if not isinstance(spec[name],list) or not all(isinstance(v,str) and v.strip() for v in spec[name]):raise ValueError('Invalid difference notes')

def evaluate_semantics(result,prior,spec):
    validate_semantics(spec);checks=[]
    def check(name,value):checks.append(dict(name=name,passed=bool(value)))
    def equal_paths(name,current_path,source_path):
        try:check(name,same(at(result,current_path),at(prior,source_path)))
        except (KeyError,IndexError,TypeError):check(name,False)
    b=spec['boundary'];v=result['observed'];check('boundary-kind',result['boundary_kind']==b['kind'])
    if b['kind']=='strict-mmio':
        guards=[g for g in v['guards'] if g['accesses']]
        check('frontier-pc',same(v['pc'],b['pc']))
        check('frontier-single-access',len(guards)==1 and guards[0]['accesses']==1)
        for name in ['address','operation','width','value']:
            check('frontier-'+name,len(guards)==1 and same(guards[0].get(name),b[name]))
    obs=result['selected_observation'];check('events-complete',obs['dropped_events']==0 and obs['sequence']==len(obs['events']))
    c=spec['comparison'];policy=c['policy']
    if policy=='bounded-invariants':
        for p in c['paths']:equal_paths('invariant:'+str(p),p,p)
    elif policy=='exact':equal_paths('comparison:exact',c['path'],c['path'])
    else:
        try:
            current=at(result,c['path']);before=at(prior,c['path'])
            valid=isinstance(current,list) and isinstance(before,list)
            if valid and policy=='prefix':valid=same(current[:len(before)],before)
            elif valid:
                index=0
                for item in current:
                    if index<len(before) and same(item,before[index]):index+=1
                valid=index==len(before)
            check('comparison:'+policy,valid)
        except (KeyError,IndexError,TypeError):check('comparison:'+policy,False)
    for item in spec['checks']:
        name='check:'+str(item['path'])
        if 'eq_source' in item:equal_paths(name,item['path'],item['eq_source'])
        else:
            try:check(name,same(at(result,item['path']),item['eq']))
            except (KeyError,IndexError,TypeError):check(name,False)
    return dict(passed=all(c['passed'] for c in checks),checks=checks,
                allowed_differences=spec['allowed_differences'],unresolved_differences=spec['unresolved_differences'])

def semantic_spec(plan,case,control):
    if plan['schema']==1:
        if 'semantics' in plan:raise ValueError('Semantic contracts require plan schema 2')
        return None
    if plan['schema']!=2 or set(plan.get('semantics',{}))!=set(plan['cases']):raise ValueError('Missing case semantic contracts')
    for modes in plan['semantics'].values():
        if set(modes)!={'candidate','control'}:raise ValueError('Candidate and control contracts required')
        for spec in modes.values():validate_semantics(spec)
    return plan['semantics'][case]['control' if control else 'candidate']

def finish_capture(result,prior,spec):
    result['execution_passed']=True
    result['semantic_validation']=evaluate_semantics(result,prior,spec) if spec else dict(passed=None,status='legacy-capture-only')
    result['passed']=result['semantic_validation']['passed'] if spec else True
    return result

def source_acceptance(simulator,src,prior,plan,case):
    if prior.get('passed') is True:return None
    entry=plan.get('reviewed_sources',{}).get(case)
    if prior.get('execution_passed') is not True or not isinstance(entry,dict) or set(entry)!={'path','sha256'}:
        raise ValueError('Failed source requires an explicit reviewed audit')
    audit_path=local(simulator,entry['path'])
    if digest(audit_path)!=entry['sha256']:raise ValueError('Reviewed audit hash differs')
    audit=json.loads(audit_path.read_text())
    if (audit.get('passed') is not True or audit.get('execution_passed') is not True
        or audit.get('native_rerun') is not False or audit.get('case')!=case
        or audit.get('control')!=prior.get('control')
        or local(simulator,audit['capture'])!=src.resolve()):
        raise ValueError('Reviewed audit does not approve this capture')
    source=local(simulator,audit['source'])
    required_capture=set(FILES)|{'plan.json','runner-source.py','derived-inputs.json','report.json','renode.log'}
    captured_exports=memory_exports(json.loads((src/'plan.json').read_text()))
    required_capture.update('exports/'+item['name'] for item in captured_exports)
    if captured_exports:validate_memory_exports(src,captured_exports,prior.get('memory_exports'))
    required_source=set(FILES)|{'derived-inputs.json','report.json','renode.log'}
    for folder,pins,required in [(src,audit['capture_hashes'],required_capture),(source,audit['source_hashes'],required_source)]:
        if set(pins)!=required:raise ValueError('Incomplete reviewed source pins')
        for name,sha in pins.items():
            if digest(local(folder,name))!=sha:raise ValueError('Reviewed source asset differs: '+name)
    if not same(json.loads((src/'report.json').read_text()),prior):raise ValueError('Source report differs')
    reference=json.loads((source/'report.json').read_text())
    for folder,report in [(src,prior),(source,reference)]:
        log=(folder/'renode.log').read_text()
        observed,kind=observe(log,allow_bounded_capture=report.get('bounded_capture',False))
        rows=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_OBSERVATION ')]
        if not same(observed,report['observed']) or kind!=report['boundary_kind'] or len(rows)!=1 or not same(rows[0],report['selected_observation']):
            raise ValueError('Reviewed report differs from saved execution')
    evaluated=evaluate_semantics(prior,reference,audit['contract'])
    if not evaluated['passed'] or not same(evaluated,audit['semantic_validation']):raise ValueError('Reviewed contract no longer passes')
    return dict(path=entry['path'],sha256=entry['sha256'],capture=str(src.resolve()),original_passed=False)

def audit_existing(folder,output,plan,prior,spec,case,control,source):
    if spec is None:raise ValueError('Saved capture audit requires schema 2 semantics')
    frozen=json.loads((folder/'plan.json').read_text())
    stripped={k:v for k,v in plan.items() if k not in ('schema','semantics')}
    if stripped!={k:v for k,v in frozen.items() if k not in ('schema','semantics')}:raise ValueError('Audit may add a contract but cannot change the saved execution plan')
    manifest=json.loads((folder/'derived-inputs.json').read_text());validate_assets(folder,manifest['derived'])
    if digest(folder/'plan.json')!=manifest['plan_sha256'] or digest(folder/'runner-source.py')!=manifest['runner_sha256']:raise ValueError('Saved plan or runner changed')
    saved=json.loads((folder/'report.json').read_text())
    if saved['case']!=case or saved['control']!=control or manifest['control']!=control:raise ValueError('Saved case/control differs')
    registered=folder/'firmware-candidate.json'
    if registered.exists():
        _,record=load_candidate(registered,source,plan['cases'][case])
        if manifest.get('firmware_candidate')!=firmware_metadata(record,digest(registered)) or saved.get('firmware_candidate')!=manifest['firmware_candidate']:raise ValueError('Saved firmware registration differs')
    elif manifest.get('firmware_candidate') is not None or digest(folder/'main.bin')!=MAIN_LAYOUT[plan['cases'][case]][3]:raise ValueError('Saved original main changed')
    log=(folder/'renode.log').read_text();observed,kind=observe(log,allow_bounded_capture=plan.get('host_capture_seconds') is not None)
    for name,key in [('BLACKWALL_OBSERVATION','selected_observation'),('BLACKWALL_CANDIDATE_'+plan['id'],'diagnostics')]:
        rows=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith(name+' ')]
        if len(rows)!=1 or not same(rows[0],saved[key]):raise ValueError('Saved report differs from '+name)
    if not same(observed,saved['observed']) or kind!=saved['boundary_kind']:raise ValueError('Saved CPU/boundary differs from log')
    result=finish_capture(dict(saved),prior,spec)
    exports=memory_exports(plan)
    if exports:
        records=read_memory_export_records(log,(folder/'run.py').read_text(),exports,memory_export_policy(plan))
        if saved.get('memory_exports')!=validate_memory_exports(folder,exports,records):raise ValueError('Saved memory exports differ')
    snapshot=read_memory_snapshot(log,memory_export_policy(plan),observed)
    if snapshot!=saved.get('memory_snapshot'):raise ValueError('Saved memory snapshot differs')
    pins={name:digest(folder/name) for name in list(FILES)+['plan.json','runner-source.py','derived-inputs.json','report.json','renode.log']}
    if registered.exists():pins['firmware-candidate.json']=digest(registered)
    for item in exports:pins['exports/'+item['name']]=digest(folder/'exports'/item['name'])
    output.mkdir(parents=True,exist_ok=False)
    (output/'semantic-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    shutil.copyfile(__file__,output/'runner-source.py')
    dependencies={}
    for name in ['native_replay.py','pinned_main.py','revalidate_research_assets.py','run_renode_m55_probe.py','firmware_candidate.py']:
        shutil.copyfile(Path(__file__).parent/name,output/name);dependencies[name]=digest(output/name)
    audit=dict(case=case,control=control,execution_passed=True,semantic_validation=result['semantic_validation'],passed=result['passed'],
               capture=str(folder.resolve()),capture_hashes=pins,contract=spec,
               source=str(source.resolve()),source_hashes={name:digest(source/name) for name in list(FILES)+['report.json','derived-inputs.json','renode.log']},
               semantic_plan_sha256=digest(output/'semantic-plan.json'),audit_runner_sha256=digest(output/'runner-source.py'),
               audit_dependencies=dependencies,
               hardware_accessed=False,native_rerun=False,boot_verified=False,display_verified=False)
    (output/'report.json').write_text(json.dumps(audit,indent=2)+'\n')
    return audit

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('plan',type=Path);p.add_argument('output',type=Path);p.add_argument('--case',required=True);p.add_argument('--control',action='store_true');p.add_argument('--firmware-manifest',type=Path);p.add_argument('--audit-existing',action='store_true');p.add_argument('--audit-output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;root=Path(__file__).resolve().parents[1];plan=json.loads(a.plan.read_text())
    if a.firmware_manifest is not None and (a.control or a.audit_existing):raise ValueError('Firmware selection is separate from model-off or saved-audit modes')
    if type(plan['schema']) is not int or plan['schema'] not in (1,2) or plan['image_id']!=IMAGE or a.case not in plan['cases']:raise ValueError('Unreviewed plan/case/runtime')
    spec=semantic_spec(plan,a.case,a.control);exports=memory_exports(plan);policy=memory_export_policy(plan)
    if plan.get('execution_mode')=='until-guest-stop' and (spec is None or spec['boundary']['kind']=='bounded-capture'):
        raise ValueError('Guest-stop execution requires a guest stop semantic contract')
    if a.audit_existing!=(a.audit_output is not None):raise ValueError('Saved audit requires --audit-existing and a separate --audit-output')
    if not re.fullmatch('[a-z][a-z0-9-]{0,63}',plan['id']):raise ValueError('Invalid plan identifier')
    src=local(s,plan['source_root']+'/'+a.case);prior=json.loads((src/'report.json').read_text());base=json.loads((src/'derived-inputs.json').read_text())['derived'];validate_assets(src,base);before,source_kind=observe((src/'renode.log').read_text(),allow_bounded_capture=prior.get('bounded_capture',False))
    if before!=prior['observed'] or digest(src/'main.bin')!=MAIN_LAYOUT[plan['cases'][a.case]][3]:raise ValueError('Source provenance differs')
    accepted_source=source_acceptance(s,src,prior,plan,a.case)
    source_events=[json.loads(l.split(' ',1)[1]) for l in (src/'renode.log').read_text().splitlines() if l.startswith('BLACKWALL_OBSERVATION ')]
    if len(source_events)!=1 or not same(source_events[0],prior['selected_observation']):raise ValueError('Source event report differs from log')
    if a.audit_existing:
        answer=audit_existing(o,a.audit_output,plan,prior,spec,a.case,a.control,src)
        print(json.dumps(dict(case=a.case,execution_passed=True,semantic_passed=answer['passed'],native_rerun=False)))
        if not answer['passed']:raise SystemExit(1)
        return
    firmware_raw=firmware_record=firmware_info=None
    if a.firmware_manifest is not None:
        if not a.firmware_manifest.resolve().is_relative_to(s.resolve()):raise ValueError('Firmware registration must remain private')
        firmware_raw,firmware_record=load_candidate(a.firmware_manifest,src,plan['cases'][a.case])
        firmware_info=firmware_metadata(firmware_record,digest(a.firmware_manifest))
    model=(src/'strict.cs').read_bytes();components=[]
    for c in plan['components']:
        old=local(s,c['baseline']).read_bytes();new=local(root,c['candidate']).read_bytes()
        if hashlib.sha256(old).hexdigest()!=c['before_sha256'] or hashlib.sha256(new).hexdigest()!=c['after_sha256'] or model.count(old)!=1:raise ValueError('Unreviewed component replacement')
        model=model.replace(old,new);components.append(c)
    for c in plan.get('append_components',[]):
        addition=local(root,c['candidate']).read_bytes()
        if hashlib.sha256(addition).hexdigest()!=c['sha256'] or addition in model:raise ValueError('Unreviewed or duplicate appended component')
        model+=b'\n'+addition
    runtime=(src/'run.py').read_text()
    limit=plan.get('host_capture_seconds')
    if limit is not None:
        if type(limit) is not int or not 10<=limit<=300:raise ValueError('Invalid bounded observation plan')
        needle='    while not m.IsPaused:\n';replacement='    while not m.IsPaused and live_seconds<'+str(limit)+':\n'
        if runtime.count(needle)==1:runtime=runtime.replace(needle,replacement)
        elif runtime.count(replacement)!=1:raise ValueError('Unexpected existing observation limit')
    if not a.control:
        for e in plan['runtime_edits']:
            if runtime.count(e['before'])!=1:raise ValueError('Unexpected runtime edit anchor')
            runtime=runtime.replace(e['before'],e['after'])
    runtime=observation_runtime(runtime,plan)
    if firmware_raw is not None:runtime=candidate_runtime(runtime,MAIN_LAYOUT[plan['cases'][a.case]][1],len(firmware_raw))
    board=(src/'board.repl').read_text()
    if not a.control:
        for e in plan.get('board_edits',[]):
            if board.count(e['before'])!=1:raise ValueError('Unexpected board edit anchor')
            board=board.replace(e['before'],e['after'])
        board+=plan.get('board_append','')
    marker_name='BLACKWALL_CANDIDATE_'+plan['id']
    anchor="    Console.WriteLine('BLACKWALL_REPORT "
    if runtime.count(anchor)!=1:raise ValueError('Missing stopped report anchor')
    previous_plan=json.loads((src/'plan.json').read_text()) if (src/'plan.json').is_file() else {}
    previous_exports=memory_exports(previous_plan)
    runtime=replace_memory_export_runtime(runtime,previous_exports,exports,memory_export_policy(previous_plan),policy)
    runtime=runtime.replace(anchor,"    Console.WriteLine('"+marker_name+" '+json.dumps("+plan['diagnostics']+"))\n"+anchor);compile(runtime,'candidate-run.py','exec')
    o.mkdir(mode=0o700,parents=True)
    for f in FILES:shutil.copyfile(src/f,o/f)
    (o/'strict.cs').write_bytes(model);(o/'run.py').write_text(runtime);(o/'board.repl').write_text(board);shutil.copyfile(a.plan,o/'plan.json');shutil.copyfile(__file__,o/'runner-source.py')
    if firmware_raw is not None:
        (o/'main.bin').write_bytes(firmware_raw)
        (o/'firmware-candidate.json').write_bytes(a.firmware_manifest.read_bytes())
        if digest(o/'firmware-candidate.json')!=firmware_info['registration_sha256'] or digest(o/'main.bin')!=firmware_info['main_sha256']:raise ValueError('Firmware changed during capture preparation')
    derived={f:digest(o/f) for f in FILES}
    if firmware_info is not None:derived['firmware-candidate.json']=digest(o/'firmware-candidate.json')
    manifest=dict(schema=1,plan_sha256=digest(o/'plan.json'),runner_sha256=digest(o/'runner-source.py'),derived=derived,base=base,components=components,append_components=plan.get('append_components',[]),control=a.control,runtime_edits=[] if a.control else plan['runtime_edits'],board_edits=[] if a.control else plan.get('board_edits',[]),diagnostics_added_after_stop=True)
    if firmware_info is not None:manifest['firmware_candidate']=firmware_info
    if accepted_source is not None:manifest['reviewed_source_acceptance']=accepted_source
    (o/'derived-inputs.json').write_text(json.dumps(manifest,indent=2)+'\n')
    extra_mount=[]
    if exports:
        (o/'exports').mkdir(mode=0o700)
        extra_mount=['--mount',f'type=bind,source={o/"exports"},target=/work-output']
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly']+extra_mount+[IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=None,stream=plan.get('execution_mode')=='until-guest-stop' or policy=='paused-after-observation')
    validate_assets(o,derived);v,kind=observe(log,allow_bounded_capture=limit is not None)
    def marker(name):
        items=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(name+' ')]
        if len(items)!=1:raise ValueError('Missing '+name)
        return items[0]
    obs=marker('BLACKWALL_OBSERVATION');diagnostics=marker(marker_name);events=prior['selected_observation']['events'];prefix=obs['events'][:len(events)]==events
    result=dict(case=a.case,observed=v,boundary_kind=kind,bounded_capture=kind=='bounded-capture',selected_observation=obs,diagnostics=diagnostics,prior_prefix_equal=prefix,control=a.control,hardware_accessed=False,boot_verified=False,display_verified=False)
    if firmware_info is not None:result['firmware_candidate']=firmware_info
    if exports:result['memory_exports']=validate_memory_exports(o,exports,read_memory_export_records(log,runtime,exports,policy))
    snapshot=read_memory_snapshot(log,policy,v)
    if snapshot is not None:result['memory_snapshot']=snapshot
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    if obs['dropped_events'] or obs['sequence']!=len(obs['events']):raise ValueError('Event loss')
    if a.control:
        if source_kind=='bounded-capture':
            paths=plan.get('bounded_control_invariants')
            if not paths or kind!=source_kind or obs!=prior['selected_observation']:raise ValueError('Missing or changed bounded control contract')
            def at(value,path):
                for key in path:value=value[key]
                return value
            for path in paths:
                if at(result,path)!=at(prior,path):raise ValueError('Bounded control invariant changed: '+str(path))
            result['control_comparison']='bounded-invariants; CPU/instruction equality not claimed'
        elif v!=before or obs!=prior['selected_observation'] or kind!=source_kind:raise ValueError('Control changed CPU/instructions/events/boundary')
        else:result['control_comparison']='exact-CPU-instructions-events-boundary'
    result=finish_capture(result,prior,spec);(o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(case=a.case,passed=result['passed'],execution_passed=True,semantic_passed=result['semantic_validation']['passed'],boundary_kind=kind,pc=hex(v['pc']),prefix_equal=prefix,diagnostics=diagnostics)),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
