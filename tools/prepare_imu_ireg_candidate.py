"""Select explicit SREG_CTRL indirect-read fixtures for original-reset replay."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def prepare_master(a,root):
    import re
    s=a.simulator
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root):raise ValueError('Fresh private master plan required')
    if any(x is not None for x in [a.fsync_config,a.int1_config2,a.edmp_configuration,a.power_configuration,a.auxiliary_configuration]) or a.sreg_control!=0 or a.missing_idle or a.missing_flush or a.edmp_idle_us!=1000 or a.fifo_flush_us!=1000:
        raise ValueError('Master stage reuses pinned auxiliary source; do not override bootstrap flags')
    if not re.fullmatch('[0-9a-fA-F]{10}',a.magnetometer_fixture) or not 1<=a.master_us<=1000000 or a.master_error<0 or a.master_error&~0x3c:
        raise ValueError('Explicit five-byte MAG/control fixture, bounded timing and error mask required')
    m=json.loads((s/'imu-aux-verification-01/manifest.json').read_text());assert m['passed']
    for n,pin in m['model_hashes'].items():
        if sha(root/'tools'/n)!=pin:raise ValueError('Changed inherited model '+n)
    baseline=s/'imu-i2cm-research-01/auxiliary-only.cs';observer=s/'imu-i2cm-research-01/observer-4096.cs'
    if sha(baseline)!=m['changed_model']['renode-imu-identity.cs']['after']:raise ValueError('Changed auxiliary baseline')
    contract=s/'imu-i2cm-source-01/report.json'
    if not json.loads(contract.read_text())['passed'] or (contract.parent/'inspector.py').read_bytes()!=(root/'tools/inspect_imu_i2cm.py').read_bytes():raise ValueError('Changed I2CM source contract')
    plan=json.loads((s/'imu-aux-main-01/stock23/plan.json').read_text())
    plan.update(id='imu-i2cm-mag-v1',source_root='imu-aux-main-01',append_components=[],components=[],board_append='',imu_master_contract_sha256=sha(contract))
    for name,old in [('renode-imu-identity.cs',baseline),('renode-execution-observer.cs',observer)]:
        plan['components'].append(dict(name=name,baseline=str(old.relative_to(s)),candidate='tools/'+name,before_sha256=sha(old),after_sha256=sha(root/'tools'/name)))
    before='    auxiliaryConfigurationHex: "a5b6d7"\n'
    plan['board_edits']=[dict(before=before,after=before+'    magnetometerFixtureHex: "'+a.magnetometer_fixture.lower()+'"\n    masterMicroseconds: '+str(a.master_us)+'\n    completeMaster: '+str(not a.missing_master).lower()+'\n    masterError: '+str(a.master_error)+'\n')]
    plan['runtime_edits']=[dict(before="observer=BlackwallExecutionObserver(m['sysbus.cpu'],4096)",after="observer=BlackwallExecutionObserver(m['sysbus.cpu'],16384)")]
    if a.missing_master:
        plan['runtime_edits'].append(dict(before='    while not m.IsPaused and live_seconds<120:\n        time.sleep(1.0)\n        live_seconds+=1\n',after='    while not m.IsPaused and live_seconds<120 and blackwall_imu_identity.Master.StatusPolls<3:\n        time.sleep(0.01)\n        live_seconds+=0.01\n'))
    obj='blackwall_imu_identity.Master';selected=obj+' is not None';fields=',imu_master_selected=('+selected+')'
    for field,prop,typ in [('fixture','FixtureHex','str'),('starts','Starts','int'),('completions','Completions','int'),('id_reads','IdentityReads','int'),('resets','SoftResets','int'),('polls','StatusPolls','int'),('done_reads','DoneReads','int'),('reads','Reads','int'),('writes','Writes','int'),('pending','Pending','bool'),('unlocked','Unlocked','bool'),('mode','Mode','int'),('history','History','str'),('error','Error','int')]:
        fields+=',imu_master_'+field+'=('+typ+'('+obj+'.'+prop+') if '+selected+' else None)'
    plan['diagnostics']=plan['diagnostics'][:-1]+fields+')';plan['reviewed_sources']={}
    for case in plan['cases']:
        audit=s/'imu-aux-saved-audit-01'/case/'report.json';plan['reviewed_sources'][case]=dict(path=str(audit.relative_to(s)),sha256=sha(audit))
        prior=json.loads((s/'imu-aux-main-01'/case/'report.json').read_text());g=next(x for x in prior['observed']['guards'] if x['accesses'])
        boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),
            checks=[dict(path=['diagnostics','imu_master_selected'],eq=True),dict(path=['diagnostics','imu_master_fixture'],eq=a.magnetometer_fixture.lower()),dict(path=['prior_prefix_equal'],eq=True)],
            allowed_differences=['Declared I2CM/MAG state machine, timed completion and polling flag; observer retains16384 events.'],unresolved_differences=['Provisional frontier; physical timing/IRQ/samples and full boot unverified.']),
            control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_master_selected'],eq=False)],allowed_differences=['Master disabled and default4096 observation preserve auxiliary source.'],unresolved_differences=['A20F setup write unsupported.']))
        if a.missing_master:plan['semantics'][case]['candidate']['checks'] += [dict(path=['diagnostics','imu_master_completions'],eq=0),dict(path=['diagnostics','imu_master_pending'],eq=True)]
        elif a.master_error==0 and a.magnetometer_fixture.lower()[:2]=='a0' and a.magnetometer_fixture.lower()[4:]=='000000' and a.master_us==1000:
            good_id=a.magnetometer_fixture.lower()[2:4]=='45'
            spec=plan['semantics'][case]['candidate'];spec['boundary']=dict(boundary,value=1)
            count=13 if good_id else 12
            spec['checks'] += [dict(path=['diagnostics','imu_master_'+k],eq=v) for k,v in [('starts',count),('completions',count),('id_reads',1),('resets',1),('done_reads',count),('reads',8 if good_id else 7),('writes',5),('pending',False),('unlocked',False),('mode',0)]]
            spec['checks'] += [dict(path=['diagnostics','imu_last_write'],eq='27'),dict(path=['diagnostics','imu_aux_int1'],eq=0x57 if good_id else 0x77)]
            spec['unresolved_differences']=['Next DMP_EXT_SEN_ODR_CFG register27 select unsupported; physical timing/IRQ/samples and full boot unverified.']
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared explicit master/MAG fixture',a.magnetometer_fixture)


def prepare_odr(a,root):
    import re
    s=a.simulator
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root):raise ValueError('Fresh private ODR plan required')
    if any(x is not None for x in [a.fsync_config,a.int1_config2,a.edmp_configuration,a.power_configuration,a.auxiliary_configuration,a.magnetometer_fixture]) or a.sreg_control!=0 or a.missing_idle or a.missing_flush or a.missing_master or a.master_error!=0 or a.master_us!=1000 or a.edmp_idle_us!=1000 or a.fifo_flush_us!=1000:
        raise ValueError('ODR stage reuses pinned completed MAG source; do not override bootstrap flags')
    if not re.fullmatch('[0-9a-fA-F]{16}',a.odr_fixture):raise ValueError('Eight explicit ODR/filter bytes required')
    m=json.loads((s/'imu-i2cm-verification-01/manifest.json').read_text());assert m['passed']
    for n,pin in m['model_hashes'].items():
        if sha(root/'tools'/n)!=pin:raise ValueError('Changed inherited model '+n)
    if sha(root/'tools/renode-execution-observer.cs')!=m['changed_model']['renode-execution-observer.cs']['after']:raise ValueError('Changed observer')
    baseline=s/'imu-odr-research-01/master-only.cs'
    if sha(baseline)!=m['changed_model']['renode-imu-identity.cs']['after']:raise ValueError('Changed master baseline')
    contract=s/'imu-odr-source-02/report.json'
    if not json.loads(contract.read_text())['passed'] or (contract.parent/'inspector.py').read_bytes()!=(root/'tools/inspect_imu_odr.py').read_bytes():raise ValueError('Changed ODR source contract')
    plan=json.loads((s/'imu-i2cm-main-02/stock23/plan.json').read_text())
    peer='tools/renode-imu-identity.cs'
    plan.update(id='imu-odr-fields-v1',source_root='imu-i2cm-main-02',components=[dict(name='imu-odr-fields',baseline=str(baseline.relative_to(s)),candidate=peer,before_sha256=sha(baseline),after_sha256=sha(root/peer))],append_components=[],runtime_edits=[],board_append='',imu_odr_contract_sha256=sha(contract))
    before='    masterError: 0\n';plan['board_edits']=[dict(before=before,after=before+'    odrConfigurationHex: "'+a.odr_fixture.lower()+'"\n')]
    obj='blackwall_imu_identity.Odr';selected=obj+' is not None';fields=',imu_odr_selected=('+selected+')'
    for field,prop,typ in [('fixture','FixtureHex','str'),('values','ValuesHex','str'),('history','History','str'),('reads','Reads','int'),('writes','Writes','int')]:fields+=',imu_odr_'+field+'=('+typ+'('+obj+'.'+prop+') if '+selected+' else None)'
    plan['diagnostics']=plan['diagnostics'][:-1]+fields+')';plan['reviewed_sources']={}
    for case in plan['cases']:
        audit=s/'imu-i2cm-saved-audit-02'/case/'report.json';plan['reviewed_sources'][case]=dict(path=str(audit.relative_to(s)),sha256=sha(audit))
        prior=json.loads((s/'imu-i2cm-main-02'/case/'report.json').read_text());g=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=[dict(path=['diagnostics','imu_odr_selected'],eq=True),dict(path=['diagnostics','imu_odr_fixture'],eq=a.odr_fixture.lower()),dict(path=['prior_prefix_equal'],eq=True)],allowed_differences=['Eight explicit ODR/filter/FSR register fixtures and source-bounded RMW fields.'],unresolved_differences=['Provisional next initialization frontier; physical sampling/clock/filter behavior unknown.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_odr_selected'],eq=False)],allowed_differences=['ODR model disabled preserves MAG bootstrap.'],unresolved_differences=['Register27 unsupported.']))
        initial=bytearray.fromhex(a.odr_fixture);initial[0]=(initial[0]&0xf8)|2;initial[1]=(initial[1]&0x80)|0x39;initial[3]|=0x10;initial[4]&=0xf0;initial[5]&=0xf8
        spec=plan['semantics'][case]['candidate'];spec['boundary']=dict(boundary,value=4)
        spec['checks'] += [dict(path=['diagnostics','imu_odr_'+k],eq=v) for k,v in [('values',initial.hex()),('reads',6),('writes',6)]]
        spec['checks'] += [dict(path=['diagnostics',k],eq=v) for k,v in [('imu_last_write','7ca24f00'),('imu_finishes',340),('imu_returned_bytes',149)]]
        spec['unresolved_differences']=['EDMP_PRGRM_IRQ0_0 A24F=00 write unsupported; gyro-disabled profile, physical sampling and FIFO initialization unverified.']
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared ODR/filter fixture',a.odr_fixture)



def prepare_service(a,root):
    import re
    s=a.simulator
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()):raise ValueError('Fresh private service plan required')
    if not re.fullmatch('[0-9a-fA-F]{10}',a.service_fixture) or not 1<=a.service_us<=1000000:raise ValueError('Explicit five-byte service fixture and bounded delay required')
    if any(x is not None for x in [a.odr_fixture,a.magnetometer_fixture,a.auxiliary_configuration,a.power_configuration,a.edmp_configuration,a.fsync_config,a.int1_config2]) or a.missing_idle or a.missing_flush or a.missing_master or a.master_error or a.master_us!=1000 or a.edmp_idle_us!=1000 or a.fifo_flush_us!=1000 or a.sreg_control!=0:raise ValueError('Service reuses pinned bootstrap')
    manifest=json.loads((s/'imu-odr-verification-01/manifest.json').read_text());assert manifest['passed']
    for n,pin in manifest['model_hashes'].items():assert sha(root/'tools'/n)==pin
    baseline=s/'imu-edmp-service-research-01/odr-only.cs';assert sha(baseline)==manifest['changed_model']['renode-imu-identity.cs']['after']
    contract=s/'imu-edmp-init-source-05/report.json';proof=json.loads((s/'imu-edmp-init-verification-01/manifest.json').read_text());assert proof['passed'] and sha(contract)==proof['files'][str(contract.relative_to(s))]
    plan=json.loads((s/'imu-odr-plan-01.json').read_text());peer='tools/renode-imu-identity.cs'
    plan.update(id='imu-edmp-service-v1',source_root='imu-odr-main-01',components=[dict(name='imu-edmp-service',baseline=str(baseline.relative_to(s)),candidate=peer,before_sha256=sha(baseline),after_sha256=sha(root/peer))],runtime_edits=[],append_components=[],board_append='',imu_edmp_service_contract_sha256=sha(contract))
    before='    odrConfigurationHex: "a5b6c7c8e9faab9c"\n'
    plan['board_edits']=[dict(before=before,after=before+'    edmpServiceFixtureHex: "'+a.service_fixture.lower()+'"\n    edmpServiceMicroseconds: '+str(a.service_us)+'\n    completeEdmpService: '+str(not a.missing_service).lower()+'\n')]
    obj='blackwall_imu_identity.Service';fields=',imu_service_selected=('+obj+' is not None)'
    for field,prop,typ in [('fixture','FixtureHex','str'),('program_writes','ProgramWrites','int'),('parameter_writes','ParameterWrites','int'),('starts','Starts','int'),('completions','Completions','int'),('decimation','DecimationCompletions','int'),('cleared_bytes','ClearedBytes','int'),('reads','Reads','int'),('writes','Writes','int'),('idle_reads','IdleReads','int'),('pending','Pending','bool')]:fields+=',imu_service_'+field+'=('+typ+'('+obj+'.'+prop+') if '+obj+' is not None else None)'
    plan['diagnostics']=plan['diagnostics'][:-1]+fields+')';plan['reviewed_sources']={}
    for case in plan['cases']:
        audit=s/'imu-odr-saved-audit-01'/case/'report.json';assert sha(audit)==manifest['files'][str(audit.relative_to(s))]
        plan['reviewed_sources'][case]=dict(path=str(audit.relative_to(s)),sha256=sha(audit))
        prior=json.loads((s/'imu-odr-main-01'/case/'report.json').read_text());g=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=[dict(path=['prior_prefix_equal'],eq=True),dict(path=['diagnostics','imu_service_selected'],eq=True)],allowed_differences=['Explicit EDMP host service model and virtual completion.'],unresolved_differences=['Provisional next main frontier; physical EDMP algorithm not executed.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_service_selected'],eq=False)],allowed_differences=['Disabled service keeps previous unsupported frontier.'],unresolved_differences=['EDMP initialization remains unsupported.']))
    a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared EDMP host service plan')



def prepare_patch(a,root):
    from inspect_imu_power import body
    from inspect_em9305_hci_framing import literal
    import hashlib
    s=a.simulator
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root):raise ValueError('Fresh private patch plan required')
    if any(x is not None for x in [a.service_fixture,a.odr_fixture,a.magnetometer_fixture,a.auxiliary_configuration,a.power_configuration,a.edmp_configuration,a.fsync_config,a.int1_config2]) or a.missing_service or a.service_us!=1000 or a.missing_idle or a.missing_flush or a.missing_master or a.master_error or a.master_us!=1000 or a.edmp_idle_us!=1000 or a.fifo_flush_us!=1000 or a.sreg_control!=0:raise ValueError('Patch reuses pinned service bootstrap')
    manifest=json.loads((s/'imu-edmp-service-verification-01/manifest.json').read_text());assert manifest['passed']
    for n,pin in manifest['model_hashes'].items():assert sha(root/'tools'/n)==pin
    baseline=s/'imu-patch-ram-research-01/service-only.cs';assert sha(baseline)==manifest['changed_model']['renode-imu-identity.cs']['after']
    proof=json.loads((s/'imu-edmp-patch-verification-01/manifest.json').read_text());contract=s/'imu-edmp-patch-source-02/report.json';assert proof['passed'] and sha(contract)==proof['files'][str(contract.relative_to(s))]
    row=json.loads(contract.read_text())['cases'][0];f=s/'imu-edmp-service-main-01/stock24';audit=json.loads((s/'imu-edmp-service-saved-audit-01/stock24/report.json').read_text())
    for n,pin in audit['capture_hashes'].items():assert sha(f/n)==pin
    raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();loads=[i for i in body(raw,row['entry']) if i.mnemonic in ['ldr','ldr.w'] and '[pc,' in i.op_str];payloads=[]
    for i,length,key in zip(loads[1:],[25,375],['dispatcher_sha256','feature_sha256']):
        ptr=literal(raw,i);assert 0x20000000<=ptr<=0x20380000-length;data=ram[ptr-0x20000000:ptr-0x20000000+length];assert hashlib.sha256(data).hexdigest()==row[key];payloads.append(data.hex())
    plan=json.loads((s/'imu-edmp-service-plan-01.json').read_text());peer='tools/renode-imu-identity.cs'
    plan.update(id='imu-patch-ram-v1',source_root='imu-edmp-service-main-01',components=[dict(name='imu-patch-ram',baseline=str(baseline.relative_to(s)),candidate=peer,before_sha256=sha(baseline),after_sha256=sha(root/peer))],runtime_edits=[],append_components=[],board_append='',imu_patch_contract_sha256=sha(contract))
    before='    completeEdmpService: true\n';plan['board_edits']=[dict(before=before,after=before+'    patchDispatcherHex: "'+payloads[0]+'"\n    patchFeatureHex: "'+payloads[1]+'"\n')]
    obj='blackwall_imu_identity.Patch';fields=',imu_patch_selected=('+obj+' is not None)'
    for field,prop,typ in [('read_bytes','ReadBytes','int'),('written_bytes','WrittenBytes','int'),('dispatcher_bytes','DispatcherBytes','int'),('key_bytes','KeyBytes','int'),('feature_bytes','FeatureBytes','int'),('loaded','Loaded','bool')]:fields+=',imu_patch_'+field+'=('+typ+'('+obj+'.'+prop+') if '+obj+' is not None else None)'
    plan['diagnostics']=plan['diagnostics'][:-1]+fields+')';plan['reviewed_sources']={}
    for case in plan['cases']:
        ap=s/'imu-edmp-service-saved-audit-01'/case/'report.json';assert sha(ap)==manifest['files'][str(ap.relative_to(s))];plan['reviewed_sources'][case]=dict(path=str(ap.relative_to(s)),sha256=sha(ap))
        prior=json.loads((s/'imu-edmp-service-main-01'/case/'report.json').read_text());g=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=[dict(path=['prior_prefix_equal'],eq=True),dict(path=['diagnostics','imu_patch_selected'],eq=True)],allowed_differences=['Original opaque payload bytes stored in existing virtual IMU RAM; no EDMP ISA execution.'],unresolved_differences=['Provisional next frontier; ROM and physical EDMP execution unverified.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_patch_selected'],eq=False)],allowed_differences=['Disabled patch keeps previous 0048 select frontier.'],unresolved_differences=['Patch read/write unsupported.']))
    a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared original patch payloads in private plan; no bytes printed')



def prepare_b2s(a,root):
    s=a.simulator
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root):raise ValueError('Fresh private B2S plan required')
    if a.patch_ram or any(x is not None for x in [a.service_fixture,a.odr_fixture,a.magnetometer_fixture,a.auxiliary_configuration,a.power_configuration,a.edmp_configuration,a.fsync_config,a.int1_config2]) or a.missing_service or a.service_us!=1000 or a.missing_idle or a.missing_flush or a.missing_master or a.master_error or a.master_us!=1000 or a.edmp_idle_us!=1000 or a.fifo_flush_us!=1000 or a.sreg_control!=0:raise ValueError('B2S reuses pinned patch bootstrap')
    manifest=json.loads((s/'imu-patch-ram-verification-02/manifest.json').read_text());assert manifest['passed']
    for n,pin in manifest['model_hashes'].items():assert sha(root/'tools'/n)==pin
    baseline=s/'imu-b2s-research-01/patch-only.cs';assert sha(baseline)==manifest['changed_model']['renode-imu-identity.cs']['after']
    contract=s/'imu-b2s-source-01/report.json';assert json.loads(contract.read_text())['passed'] and (contract.parent/'inspector.py').read_bytes()==(root/'tools/inspect_imu_b2s_parameters.py').read_bytes()
    plan=json.loads((s/'imu-patch-ram-plan-01.json').read_text());peer='tools/renode-imu-identity.cs'
    plan.update(id='imu-b2s-parameters-v1',source_root='imu-patch-ram-main-02',components=[dict(name='imu-b2s-parameters',baseline=str(baseline.relative_to(s)),candidate=peer,before_sha256=sha(baseline),after_sha256=sha(root/peer))],runtime_edits=[],append_components=[],board_append='',imu_b2s_contract_sha256=sha(contract))
    board=(s/'imu-patch-ram-main-02/stock24/board.repl').read_text();before=next(x for x in board.splitlines(True) if x.startswith('    patchFeatureHex:'))
    plan['board_edits']=[dict(before=before,after=before+'    b2sParameters: true\n')]
    obj='blackwall_imu_identity.Patch';plan['diagnostics']=plan['diagnostics'][:-1]+',imu_b2s_selected=('+obj+' is not None and bool('+obj+'.EnableParameters)),imu_b2s_parameter_bytes=(int('+obj+'.ParameterBytes) if '+obj+' is not None else None),imu_b2s_values=(str('+obj+'.ParameterHex) if '+obj+' is not None else None))'
    plan['reviewed_sources']={}
    for case in plan['cases']:
        ap=s/'imu-patch-ram-saved-audit-01'/case/'report.json';assert sha(ap)==manifest['files'][str(ap.relative_to(s))];plan['reviewed_sources'][case]=dict(path=str(ap.relative_to(s)),sha256=sha(ap))
        prior=json.loads((s/'imu-patch-ram-main-02'/case/'report.json').read_text());g=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=[dict(path=['prior_prefix_equal'],eq=True),dict(path=['diagnostics','imu_b2s_selected'],eq=True)],allowed_differences=['Twenty ordered bytes in eight source-bound B2S fields, other loaded bytes preserved.'],unresolved_differences=['Provisional next initialization frontier; B2S algorithm/physical behavior unverified.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_b2s_selected'],eq=False)],allowed_differences=['Disabled fields keep previous 1618=5e frontier.'],unresolved_differences=['Parameter modifications unsupported.']))
    a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared original B2S parameter field plan')



def prepare_wom(a,root):
    import re
    s=a.simulator
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root):raise ValueError('Fresh private WOM plan required')
    if not re.fullmatch('[0-9a-fA-F]{8}',a.wom_fixture):raise ValueError('Four explicit WOM bytes required')
    if a.b2s_parameters or a.patch_ram or any(x is not None for x in [a.service_fixture,a.odr_fixture,a.magnetometer_fixture,a.auxiliary_configuration,a.power_configuration,a.edmp_configuration,a.fsync_config,a.int1_config2]) or a.missing_service or a.service_us!=1000 or a.missing_idle or a.missing_flush or a.missing_master or a.master_error or a.master_us!=1000 or a.edmp_idle_us!=1000 or a.fifo_flush_us!=1000 or a.sreg_control!=0:raise ValueError('WOM reuses pinned B2S bootstrap')
    manifest=json.loads((s/'imu-b2s-verification-01/manifest.json').read_text());assert manifest['passed']
    for n,pin in manifest['model_hashes'].items():assert sha(root/'tools'/n)==pin
    baseline=s/'imu-wom-research-01/b2s-only.cs';assert sha(baseline)==manifest['changed_model']['renode-imu-identity.cs']['after']
    contract=s/'imu-wom-source-01/report.json';assert json.loads(contract.read_text())['passed'] and (contract.parent/'inspector.py').read_bytes()==(root/'tools/inspect_imu_wom.py').read_bytes()
    plan=json.loads((s/'imu-b2s-plan-01.json').read_text());peer='tools/renode-imu-identity.cs'
    plan.update(id='imu-wom-configuration-v1',source_root='imu-b2s-main-01',components=[dict(name='imu-wom-configuration',baseline=str(baseline.relative_to(s)),candidate=peer,before_sha256=sha(baseline),after_sha256=sha(root/peer))],runtime_edits=[],append_components=[],board_append='',imu_wom_contract_sha256=sha(contract))
    before='    b2sParameters: true\n';plan['board_edits']=[dict(before=before,after=before+'    womConfigurationHex: "'+a.wom_fixture.lower()+'"\n')]
    obj='blackwall_imu_identity.Wom';fields=',imu_wom_selected=('+obj+' is not None)'
    for field,prop,typ in [('fixture','FixtureHex','str'),('values','ValuesHex','str'),('threshold_writes','ThresholdWrites','int'),('control_reads','ControlReads','int'),('control_writes','ControlWrites','int')]:fields+=',imu_wom_'+field+'=('+typ+'('+obj+'.'+prop+') if '+obj+' is not None else None)'
    plan['diagnostics']=plan['diagnostics'][:-1]+fields+')';plan['reviewed_sources']={}
    for case in plan['cases']:
        ap=s/'imu-b2s-saved-audit-01'/case/'report.json';assert sha(ap)==manifest['files'][str(ap.relative_to(s))];plan['reviewed_sources'][case]=dict(path=str(ap.relative_to(s)),sha256=sha(ap))
        prior=json.loads((s/'imu-b2s-main-01'/case/'report.json').read_text());g=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=[dict(path=['prior_prefix_equal'],eq=True),dict(path=['diagnostics','imu_wom_selected'],eq=True)],allowed_differences=['Explicit WOM X/Y/Z threshold storage and source-bounded control fields.'],unresolved_differences=['Provisional next initialization frontier; physical WOM thresholds/events unverified.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_wom_selected'],eq=False)],allowed_differences=['Disabled WOM keeps a27e=02 frontier.'],unresolved_differences=['WOM configuration unsupported.']))
    a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared explicit WOM fixture',a.wom_fixture)



def prepare_powersave(a,root):
    import re
    s=a.simulator
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root):raise ValueError('Fresh private power-save plan required')
    if not re.fullmatch('[0-9a-fA-F]{8}',a.powersave_time):raise ValueError('Explicit four-byte unknown-ROM result fixture required')
    if a.wom_fixture is not None or a.b2s_parameters or a.patch_ram or any(x is not None for x in [a.service_fixture,a.odr_fixture,a.magnetometer_fixture,a.auxiliary_configuration,a.power_configuration,a.edmp_configuration,a.fsync_config,a.int1_config2]) or a.missing_service or a.service_us!=1000 or a.missing_idle or a.missing_flush or a.missing_master or a.master_error or a.master_us!=1000 or a.edmp_idle_us!=1000 or a.fifo_flush_us!=1000 or a.sreg_control!=0:raise ValueError('Power-save reuses pinned WOM bootstrap')
    manifest=json.loads((s/'imu-wom-verification-01/manifest.json').read_text());assert manifest['passed']
    for n,pin in manifest['model_hashes'].items():assert sha(root/'tools'/n)==pin
    baseline=s/'imu-powersave-research-01/wom-only.cs';assert sha(baseline)==manifest['changed_model']['renode-imu-identity.cs']['after']
    contract=s/'imu-powersave-source-02/report.json';assert json.loads(contract.read_text())['passed'] and (contract.parent/'inspector.py').read_bytes()==(root/'tools/inspect_imu_powersave.py').read_bytes()
    plan=json.loads((s/'imu-wom-plan-01.json').read_text());peer='tools/renode-imu-identity.cs'
    plan.update(id='imu-powersave-passthrough-v1',source_root='imu-wom-main-01',components=[dict(name='imu-powersave-passthrough',baseline=str(baseline.relative_to(s)),candidate=peer,before_sha256=sha(baseline),after_sha256=sha(root/peer))],runtime_edits=[],append_components=[],board_append='',imu_powersave_contract_sha256=sha(contract))
    before='    womConfigurationHex: "a5b6c7c3"\n';plan['board_edits']=[dict(before=before,after=before+'    powerSaveTimeHex: "'+a.powersave_time.lower()+'"\n')]
    obj='blackwall_imu_identity.PowerSave';fields=',imu_powersave_selected=('+obj+' is not None)'
    for field,prop,typ in [('fixture','FixtureHex','str'),('values','ValuesHex','str'),('profile_applications','ProfileApplications','int'),('read_bytes','ReadBytes','int'),('write_bytes','WriteBytes','int'),('control_reads','ControlReads','int'),('control_writes','ControlWrites','int'),('complete','Complete','bool')]:fields+=',imu_powersave_'+field+'=('+typ+'('+obj+'.'+prop+') if '+obj+' is not None else None)'
    plan['diagnostics']=plan['diagnostics'][:-1]+fields+')';plan['reviewed_sources']={}
    for case in plan['cases']:
        ap=s/'imu-wom-saved-audit-01'/case/'report.json';assert sha(ap)==manifest['files'][str(ap.relative_to(s))];plan['reviewed_sources'][case]=dict(path=str(ap.relative_to(s)),sha256=sha(ap))
        prior=json.loads((s/'imu-wom-main-01'/case/'report.json').read_text());g=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=[dict(path=['prior_prefix_equal'],eq=True),dict(path=['diagnostics','imu_powersave_selected'],eq=True)],allowed_differences=['Explicit unverified ROM-result time profile; original caller preserves time while clearing power-save bit.'],unresolved_differences=['Provisional next initialization frontier; physical ROM defaults and power effects unknown.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_powersave_selected'],eq=False)],allowed_differences=['Disabled profile preserves SRAM0040 select frontier.'],unresolved_differences=['Time profile not provided.']))
    a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared explicit unknown-ROM power-save time profile',a.powersave_time)


def prepare_gaf_clock(a,root,fixture,profile_path):
    import re
    if not a.gaf_configuration or not 0<=a.gaf_clock_variation_byte<=255:raise ValueError('Clock variation requires --gaf-configuration and explicit byte')
    s=a.simulator;peer='tools/renode-imu-identity.cs';value=a.gaf_clock_variation_byte
    source=s/'imu-clock-variation-source-01';manifest=json.loads((source/'manifest.json').read_text())
    if manifest['repository']!='tdk-invn-oss/motion.arduino.ICM45608' or manifest['commit']!='646f55a6ec119b59d9ebce47af660842b53e5506':raise ValueError('Pinned ICM45608 source revision required')
    for name in ['inv_imu_regmap_le.h','inv_imu_regmap_be.h']:
        entry=next(x for x in manifest['files'] if Path(x['path']).name==name);path=source/name
        if sha(path)!=entry['sha256'] or not re.search(r'#define SW_PLL1_TRIM +0xa2a2',path.read_text()) or not re.search(r'sw_pll1_trim +: 8;',path.read_text()):raise ValueError('Pinned 8-bit SW_PLL1_TRIM register required')
    plan=json.loads((s/'imu-gaf-storage-plan-04.json').read_text());baseline=source/'bias-only.cs'
    if sha(baseline)!=plan['components'][0]['after_sha256']:raise ValueError('Pinned bias-only model required')
    plan.update(id='imu-clock-variation-explicit-v1',source_root='imu-gaf-storage-main-02',components=[dict(name='imu-clock-variation-byte',baseline=str(baseline.relative_to(s)),candidate=peer,before_sha256=sha(baseline),after_sha256=sha(root/peer))],reviewed_sources={},clock_variation_byte=value,clock_variation_physical_verified=False,clock_source_manifest_sha256=sha(source/'manifest.json'))
    before='    gafConfiguration: true\n';plan['board_edits']=[dict(before=before,after=before+'    gafClockVariationByte: '+str(value)+'\n')]
    obj='blackwall_imu_identity.GafParameters';extra=''
    for field,prop in [('clock_fixture','ClockVariationByte'),('clock_reads','ClockReads'),('clock_selections','ClockSelections')]:extra+=',imu_gaf_'+field+'=int('+obj+'.'+prop+')'
    plan['diagnostics']=plan['diagnostics'][:-1]+extra+')'
    expected=''
    for f in json.loads(profile_path.read_text())['fields']:
        changed={0:1,1:value,4:20000,8:40000}.get(f['offset'])
        expected+=int(changed).to_bytes(f['length'],'little').hex() if changed is not None else f['bytes_le']
    for case in plan['cases']:
        prior=json.loads((s/'imu-gaf-storage-main-02'/case/'report.json').read_text())
        if not prior['passed']:raise ValueError('Passing bias source capture required')
        guard=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:guard[k] for k in ['address','operation','width','value']})
        checks=[dict(path=['prior_prefix_equal'],eq=True)]+[dict(path=['diagnostics','imu_gaf_'+k],eq=v) for k,v in [('clock_fixture',value),('clock_reads',1),('clock_selections',1),('written_bytes',225),('values',expected)]]+[dict(path=['diagnostics','imu_last_write'],eq='7c000402')]
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(boundary,width=4,value=4),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=checks,allowed_differences=['Explicit virtual SW_PLL1_TRIM byte, not a physical or reset default; original GAF setter stores fields and derived words.'],unresolved_differences=['First GAF on-demand service is unsupported; no fusion, complete startup or natural UI.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_gaf_clock_fixture'],eq=-1)],allowed_differences=['Unknown trim preserves bias-only read frontier.'],unresolved_differences=['Physical clock trim unknown.']))
    a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared explicit virtual SW_PLL1_TRIM byte',value)


def prepare_gaf_configuration(a,root,fixture,profile_path):
    s=a.simulator;peer='tools/renode-imu-identity.cs'
    verified=json.loads((s/'imu-gaf-parameters-verification-01/manifest.json').read_text())
    baseline=s/'imu-gaf-storage-research-01/getter-only.cs'
    if not verified['passed'] or sha(baseline)!=verified['source_hashes']['renode-imu-identity.cs']:raise ValueError('Verified getter-only baseline required')
    plan=json.loads((s/'imu-gaf-parameters-plan-02.json').read_text())
    if sha(profile_path)!=plan['gaf_profile_sha256']:raise ValueError('GAF profile pin mismatch')
    plan.update(id='imu-gaf-bias-configuration-v1',source_root='imu-gaf-parameters-main-01',components=[dict(name='imu-gaf-bias-storage',baseline=str(baseline.relative_to(s)),candidate=peer,before_sha256=sha(baseline),after_sha256=sha(root/peer))],runtime_edits=[],append_components=[],board_append='')
    before='    gafParametersHex: "'+fixture+'"\n'
    plan['board_edits']=[dict(before=before,after=before+'    gafConfiguration: true\n')]
    obj='blackwall_imu_identity.GafParameters';extra=''
    for field,prop,typ in [('enabled','ConfigurationEnabled','bool'),('written_bytes','WrittenBytes','int'),('write_transactions','WriteTransactions','int'),('history','History','str')]:extra+=',imu_gaf_'+field+'='+typ+'('+obj+'.'+prop+')'
    plan['diagnostics']=plan['diagnostics'][:-1]+extra+')';plan['reviewed_sources']={}
    for case in plan['cases']:
        source=s/'imu-gaf-parameters-main-01'/case/'report.json';prior=json.loads(source.read_text())
        audit=s/'imu-gaf-parameters-saved-audit-01'/case/'report.json'
        if not prior['execution_passed'] or not json.loads(audit.read_text())['passed'] or sha(audit)!=verified['native_audit_report_sha256'][case]:raise ValueError('Verified getter capture required')
        plan['reviewed_sources'][case]=dict(path=str(audit.relative_to(s)),sha256=sha(audit))
        guard=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:guard[k] for k in ['address','operation','width','value']})
        checks=[dict(path=['prior_prefix_equal'],eq=True)]+[dict(path=['diagnostics','imu_gaf_'+k],eq=v) for k,v in [('enabled',True),('complete',True),('read_bytes',153),('written_bytes',56),('values',fixture)]]+[dict(path=['diagnostics','imu_last_write'],eq='7ca2a2')]
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(boundary,width=4,value=3),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=checks,allowed_differences=['Original CPU magnetometer-bias writes stored in explicitly bounded SRAM.'],unresolved_differences=['Next A2A2 clock-variation register read is unknown and unsupported; GAF setter/services, fusion and natural UI incomplete.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_gaf_enabled'],eq=False)],allowed_differences=['Configuration disabled preserves getter-only frontier.'],unresolved_differences=['Storage disabled.']))
    a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared bounded GAF bias/configuration storage')


def prepare_gaf(a,root):
    s=a.simulator
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()):raise ValueError('Fresh private GAF plan required')
    if any(x is not None for x in [a.powersave_time,a.wom_fixture,a.service_fixture,a.odr_fixture,a.magnetometer_fixture,a.auxiliary_configuration,a.power_configuration,a.edmp_configuration,a.fsync_config,a.int1_config2]) or a.b2s_parameters or a.patch_ram or a.missing_service or a.missing_idle or a.missing_flush or a.missing_master or a.master_error or a.service_us!=1000 or a.master_us!=1000 or a.edmp_idle_us!=1000 or a.fifo_flush_us!=1000 or a.sreg_control!=0:
        raise ValueError('GAF profile reuses pinned power-save bootstrap')
    import re
    contract=s/'imu-parameter-full-setter-01/verification-report.json';verified=json.loads(contract.read_text())
    profile_path=root/'docs/data/imu-gaf-default-profile.json'
    profile_pins=[pin for name,pin in verified['source_files'].items() if Path(name).name=='imu-gaf-default-profile.json']
    if not verified['passed'] or len(profile_pins)!=1 or sha(profile_path)!=profile_pins[0]:raise ValueError('GAF default profile differs from verified source input')
    profile=json.loads(profile_path.read_text());fields=profile['fields']
    if profile['profile_kind']!='explicit-source-derived-virtual-input' or profile['physical_g2_defaults_verified'] or len(fields)!=41 or sum(x['length'] for x in fields)!=153:raise ValueError('Explicit source-derived GAF input required')
    fixture=''.join(x['bytes_le'] for x in fields)
    if not re.fullmatch('[0-9a-f]{306}',fixture):raise ValueError('153 GAF input bytes required')
    if a.gaf_clock_variation_byte is not None:
        prepare_gaf_clock(a,root,fixture,profile_path)
        return
    if a.gaf_configuration:
        prepare_gaf_configuration(a,root,fixture,profile_path)
        return
    manifest=json.loads((s/'imu-powersave-verification-01/manifest.json').read_text());assert manifest['passed']
    baseline=s/'imu-gaf-parameters-research-01/powersave-only.cs';assert sha(baseline)==manifest['changed_model']['renode-imu-identity.cs']['after']
    plan=json.loads((s/'imu-powersave-plan-01.json').read_text());peer='tools/renode-imu-identity.cs'
    plan.update(id='imu-gaf-default-getter-v1',source_root='imu-powersave-main-01',components=[dict(name='imu-gaf-default-getter',baseline=str(baseline.relative_to(s)),candidate=peer,before_sha256=sha(baseline),after_sha256=sha(root/peer))],runtime_edits=[],append_components=[],board_append='',gaf_source_contract_sha256=sha(contract),gaf_profile_sha256=sha(profile_path),gaf_profile=profile['profile'],gaf_parameters_hex=fixture)
    before='    powerSaveTimeHex: "78563412"\n';plan['board_edits']=[dict(before=before,after=before+'    gafParametersHex: "'+fixture+'"\n')]
    obj='blackwall_imu_identity.GafParameters';selected=obj+' is not None';extra=',imu_gaf_selected=('+selected+')'
    for field,prop,typ in [('fixture','FixtureHex','str'),('values','ValuesHex','str'),('profile_applications','ProfileApplications','int'),('fields_started','FieldsStarted','int'),('read_bytes','ReadBytes','int'),('read_remaining','ReadRemaining','int'),('complete','Complete','bool')]:extra+=',imu_gaf_'+field+'=('+typ+'('+obj+'.'+prop+') if '+selected+' else None)'
    plan['diagnostics']=plan['diagnostics'][:-1]+extra+')';plan['reviewed_sources']={}
    for case in plan['cases']:
        ap=s/'imu-powersave-saved-audit-01'/case/'report.json';assert sha(ap)==manifest['files'][str(ap.relative_to(s))];plan['reviewed_sources'][case]=dict(path=str(ap.relative_to(s)),sha256=sha(ap))
        prior=json.loads((s/'imu-powersave-main-01'/case/'report.json').read_text());g=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(boundary,width=4,value=4),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=[dict(path=['prior_prefix_equal'],eq=True),dict(path=['diagnostics','imu_gaf_selected'],eq=True)]+[dict(path=['diagnostics','imu_gaf_'+k],eq=v) for k,v in [('fixture',fixture),('values',fixture),('profile_applications',1),('fields_started',41),('read_bytes',153),('read_remaining',0),('complete',True)]]+[dict(path=['diagnostics','imu_last_write'],eq='7c077400')],allowed_differences=['Explicit TDK-source-derived virtual GAF parameters and ordered original getter reads; physical ROM/algorithm version unverified.'],unresolved_differences=['Next original magnetometer-bias SRAM0774 write is unsupported; GAF services, sensor fusion and natural UI incomplete.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_gaf_selected'],eq=False)],allowed_differences=['GAF input absent preserves power-save frontier.'],unresolved_differences=['Physical ROM defaults unverified.']))
    a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared explicit GAF source profile',profile['profile'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--sreg-control', type=lambda x: int(x, 0), default=0)
    p.add_argument('--fsync-config', type=lambda x: int(x, 0))
    p.add_argument('--int1-config2', type=lambda x: int(x, 0))
    p.add_argument('--edmp-configuration')
    p.add_argument('--edmp-idle-us', type=int, default=1000)
    p.add_argument('--missing-idle', action='store_true')
    p.add_argument('--power-configuration')
    p.add_argument('--fifo-flush-us', type=int, default=1000)
    p.add_argument('--missing-flush', action='store_true')
    p.add_argument('--auxiliary-configuration')
    p.add_argument('--magnetometer-fixture')
    p.add_argument('--master-us',type=int,default=1000)
    p.add_argument('--missing-master',action='store_true')
    p.add_argument('--master-error',type=lambda x:int(x,0),default=0)
    p.add_argument('--odr-fixture')
    p.add_argument('--gaf-defaults',action='store_true')
    p.add_argument('--gaf-configuration',action='store_true')
    p.add_argument('--gaf-clock-variation-byte',type=lambda x:int(x,0))
    p.add_argument('--powersave-time')
    p.add_argument('--wom-fixture')
    p.add_argument('--b2s-parameters',action='store_true')
    p.add_argument('--patch-ram',action='store_true')
    p.add_argument('--service-fixture')
    p.add_argument('--service-us',type=int,default=1000)
    p.add_argument('--missing-service',action='store_true')
    a = p.parse_args()
    s, root = a.simulator, Path(__file__).resolve().parents[1]
    if a.gaf_defaults or a.gaf_configuration or a.gaf_clock_variation_byte is not None:
        prepare_gaf(a,root)
        return
    if a.powersave_time is not None:
        prepare_powersave(a,root)
        return
    if a.wom_fixture is not None:
        prepare_wom(a,root)
        return
    if a.b2s_parameters:
        prepare_b2s(a,root)
        return
    if a.patch_ram:
        prepare_patch(a,root)
        return
    if a.service_fixture is not None:
        prepare_service(a,root)
        return
    if a.service_us!=1000 or a.missing_service:raise ValueError("Service timing needs fixture")
    if a.odr_fixture is not None:
        prepare_odr(a,root)
        return
    if a.magnetometer_fixture is not None:
        prepare_master(a,root)
        return
    if a.master_us!=1000 or a.missing_master or a.master_error!=0:raise ValueError('Master options require explicit fixture')
    tags = a.fsync_config is not None
    pins = a.int1_config2 is not None
    edmp = a.edmp_configuration is not None
    power = a.power_configuration is not None
    auxiliary = a.auxiliary_configuration is not None
    if a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root) or not 0 <= a.sreg_control <= 255 or tags and not 0 <= a.fsync_config <= 255:
        raise ValueError('Fresh private plan and explicit byte required')
    if pins and (not tags or not 0 <= a.int1_config2 <= 255):
        raise ValueError('Explicit INT1 byte requires FSYNC fixture')
    if edmp:
        import re
        if not pins or not re.fullmatch('[0-9a-fA-F]{4}', a.edmp_configuration) or not 1 <= a.edmp_idle_us <= 1000000:
            raise ValueError('EDMP requires pin fixture, two hex bytes and bounded idle delay')
    elif a.edmp_idle_us != 1000 or a.missing_idle:
        raise ValueError('EDMP timing requires explicit configuration')
    if power:
        if not edmp or a.missing_idle or not re.fullmatch('[0-9a-fA-F]{12}', a.power_configuration) or int(a.power_configuration[2:4],16) & 0x80 or not 1 <= a.fifo_flush_us <= 1000000:
            raise ValueError('Power requires completing EDMP, six hex bytes, initially idle FIFO and bounded flush delay')
    elif a.fifo_flush_us != 1000 or a.missing_flush:
        raise ValueError('FIFO timing requires explicit power configuration')
    if auxiliary and (not power or a.missing_flush or not re.fullmatch('[0-9a-fA-F]{6}',a.auxiliary_configuration) or
                      (a.sreg_control,a.fsync_config,a.int1_config2,a.edmp_configuration,a.edmp_idle_us,a.power_configuration,a.fifo_flush_us)!=(0,0,166,'ffff',1000,'af2500000000',1000)):
        raise ValueError('Auxiliary setup requires pinned completed power profile and three hex bytes')
    verification = 'imu-power-verification-01' if auxiliary else 'imu-edmp-verification-01' if power else 'imu-configuration-verification-01' if edmp else 'imu-tags-verification-01' if pins else 'imu-ireg-verification-01' if tags else 'imu-reset-model-verification-01'
    manifest = json.loads((s / verification / 'manifest.json').read_text())
    source = s / 'imu-ireg-source-01/report.json'
    if not manifest['passed'] or not json.loads(source.read_text())['passed'] or (s / 'imu-ireg-source-01/inspector.py').read_bytes() != (root / 'tools/inspect_imu_ireg.py').read_bytes():
        raise ValueError('Changed indirect source contract')
    for n, value in manifest['model_hashes'].items():
        if sha(root / 'tools' / n) != value:
            raise ValueError('Changed inherited model ' + n)
    baseline = s / ('imu-aux-research-01/power-only.cs' if auxiliary else 'imu-power-research-01/edmp-only.cs' if power else 'imu-edmp-research-01/configuration-only.cs' if edmp else 'imu-configuration-research-01/tags-only.cs' if pins else 'imu-tags-research-01/ireg-only.cs' if tags else 'imu-ireg-research-01/reset-only.cs')
    if sha(baseline) != manifest['changed_model']['renode-imu-identity.cs']['after']:
        raise ValueError('Changed reset-only baseline')
    peer = 'tools/renode-imu-identity.cs'
    source_root = 'imu-power-main-01' if auxiliary else 'imu-edmp-main-02' if power else 'imu-configuration-main-01' if edmp else 'imu-tags-main-01' if pins else 'imu-ireg-main-01' if tags else 'imu-reset-main-02'
    audit_root = 'imu-power-saved-audit-01' if auxiliary else 'imu-edmp-saved-audit-01' if power else 'imu-configuration-saved-audit-01' if edmp else 'imu-tags-saved-audit-01' if pins else 'imu-ireg-saved-audit-01' if tags else 'imu-reset-model-saved-audit-01'
    plan = json.loads((s / source_root / 'stock23/plan.json').read_text())
    plan.update(id='imu-auxiliary-setup-v1' if auxiliary else 'imu-power-fifo-v1' if power else 'imu-edmp-quiesce-v1' if edmp else 'imu-int1-configuration-v1' if pins else 'imu-fifo-fsync-v1' if tags else 'imu-ireg-endian-v1', source_root=source_root,
                components=[dict(name='imu-indirect-endianness', baseline=str(baseline.relative_to(s)), candidate=peer, before_sha256=sha(baseline), after_sha256=sha(root / peer))],
                append_components=[], runtime_edits=[], board_append='', imu_ireg_contract_sha256=sha(source))
    if auxiliary:
        contract = s/'imu-aux-source-02/report.json'
        if not json.loads(contract.read_text())['passed'] or (contract.parent/'inspector.py').read_bytes()!=(root/'tools/inspect_imu_auxiliary.py').read_bytes():
            raise ValueError('Changed auxiliary setup/identity contract')
        plan['imu_aux_contract_sha256']=sha(contract)
        before='    powerConfigurationHex: "af2500000000"\n    fifoFlushMicroseconds: 1000\n    completeFifoFlush: true\n'
        after=before+'    auxiliaryConfigurationHex: "'+a.auxiliary_configuration.lower()+'"\n'
    elif power:
        contract = s / 'imu-power-source-02/report.json'
        if not json.loads(contract.read_text())['passed'] or (contract.parent / 'inspector.py').read_bytes() != (root / 'tools/inspect_imu_power.py').read_bytes():
            raise ValueError('Changed power/FIFO/status source contract')
        plan['imu_power_contract_sha256'] = sha(contract)
        before = '    sregControl: 0\n    fsyncConfig: 0\n    int1Config2: 166\n    edmpConfigurationHex: "ffff"\n    edmpIdleMicroseconds: 1000\n    completeEdmpIdle: true\n'
        after = '    sregControl: ' + str(a.sreg_control) + '\n    fsyncConfig: ' + str(a.fsync_config) + '\n    int1Config2: ' + str(a.int1_config2) + '\n'
        after += '    edmpConfigurationHex: "' + a.edmp_configuration.lower() + '"\n    edmpIdleMicroseconds: ' + str(a.edmp_idle_us) + '\n    completeEdmpIdle: true\n'
        after += '    powerConfigurationHex: "' + a.power_configuration.lower() + '"\n    fifoFlushMicroseconds: ' + str(a.fifo_flush_us) + '\n    completeFifoFlush: ' + str(not a.missing_flush).lower() + '\n'
    elif edmp:
        contract = s / 'imu-edmp-source-02/report.json'
        if not json.loads(contract.read_text())['passed'] or (contract.parent / 'inspector.py').read_bytes() != (root / 'tools/inspect_imu_edmp.py').read_bytes():
            raise ValueError('Changed EDMP source contract')
        plan['imu_edmp_contract_sha256'] = sha(contract)
        before = '    sregControl: 0\n    fsyncConfig: 0\n    int1Config2: 166\n'
        after = '    sregControl: ' + str(a.sreg_control) + '\n    fsyncConfig: ' + str(a.fsync_config) + '\n    int1Config2: ' + str(a.int1_config2) + '\n'
        after += '    edmpConfigurationHex: "' + a.edmp_configuration.lower() + '"\n    edmpIdleMicroseconds: ' + str(a.edmp_idle_us) + '\n    completeEdmpIdle: ' + str(not a.missing_idle).lower() + '\n'
    elif pins:
        contract = s / 'imu-configuration-source-01/report.json'
        if not json.loads(contract.read_text())['passed'] or (contract.parent / 'inspector.py').read_bytes() != (root / 'tools/inspect_imu_configuration.py').read_bytes():
            raise ValueError('Changed INT1 configuration source contract')
        plan['imu_configuration_contract_sha256'] = sha(contract)
        before = '    sregControl: 0\n    fsyncConfig: 0\n'
        after = '    sregControl: ' + str(a.sreg_control) + '\n    fsyncConfig: ' + str(a.fsync_config) + '\n    int1Config2: ' + str(a.int1_config2) + '\n'
    elif tags:
        contract = s / 'imu-tags-source-01/report.json'
        if not json.loads(contract.read_text())['passed'] or (contract.parent / 'inspector.py').read_bytes() != (root / 'tools/inspect_imu_tags.py').read_bytes():
            raise ValueError('Changed FIFO/FSYNC source contract')
        plan['imu_tags_contract_sha256'] = sha(contract)
        before = '    sregControl: 0\n'
        after = '    sregControl: ' + str(a.sreg_control) + '\n    fsyncConfig: ' + str(a.fsync_config) + '\n'
    else:
        before = '    completeReset: true\n'
        after = before + '    sregControl: ' + str(a.sreg_control) + '\n'
    plan['board_edits'] = [dict(before=before, after=after)]
    obj = 'blackwall_imu_identity'
    selected = 'int(' + obj + '.SregControl)>=0'
    if auxiliary:
        selected=obj+'.Auxiliary is not None'
        fields=',imu_aux_selected=('+selected+')'
        for field,prop,typ in [('fixture','ConfigurationHex','str'),('pad','PadValue','int'),('pad_reads','PadReads','int'),('pad_writes','PadWrites','int'),('int0','Interrupt0','int'),('int1','Interrupt1','int'),('int_reads','InterruptReads','int'),('int_writes','InterruptWrites','int')]:
            fields+=',imu_aux_'+field+'=('+typ+'('+obj+'.Auxiliary.'+prop+') if '+selected+' else None)'
    elif power:
        selected = obj + '.Configuration is not None'
        fields = ',imu_power_selected=(' + selected + ')'
        for field, prop, typ in [('fixture','ConfigurationHex','str'), ('value','PowerValue','int'), ('reads','PowerReads','int'), ('writes','PowerWrites','int'), ('fifo_value','FifoValue','int'), ('fifo_reads','FifoReads','int'), ('fifo_writes','FifoWrites','int'), ('flush_requests','FlushRequests','int'), ('flush_completions','FlushCompletions','int'), ('flush_pending','FlushPending','bool'), ('flush_done','FlushDone','bool'), ('status0_reads','Status0Reads','int'), ('status_apex_reads','StatusApexReads','int')]:
            fields += ',imu_power_' + field + '=(' + typ + '(' + obj + '.Configuration.' + prop + ') if ' + selected + ' else None)'
    elif edmp:
        selected = obj + '.Edmp is not None'
        fields = ',imu_edmp_selected=(' + selected + ')'
        for field, prop, typ in [('initial0','Initial0','int'), ('initial1','Initial1','int'), ('enable0','Enable0','int'), ('enable1','Enable1','int'), ('reads0','Reads0','int'), ('reads1','Reads1','int'), ('writes','Writes','int'), ('idle_reads','IdleReads','int'), ('requests','DisableRequests','int'), ('completions','IdleCompletions','int'), ('idle','Idle','bool'), ('pending','Pending','bool'), ('complete_idle','CompleteIdle','bool')]:
            fields += ',imu_edmp_' + field + '=(' + typ + '(' + obj + '.Edmp.' + prop + ') if ' + selected + ' else None)'
    elif pins:
        selected = 'int(' + obj + '.InitialInt1Config2)>=0'
        fields = ',imu_pin_selected=(' + selected + ')'
        for field, prop in [('fixture', 'InitialInt1Config2'), ('value', 'Int1Config2Value'), ('reads', 'Int1Reads'), ('writes', 'Int1Writes')]:
            fields += ',imu_pin_' + field + '=(int(' + obj + '.' + prop + ') if ' + selected + ' else None)'
    elif tags:
        selected = 'int(' + obj + '.FsyncConfig)>=0'
        fields = ',imu_fsync_selected=(' + selected + '),imu_fsync_fixture=(int(' + obj + '.FsyncConfig) if ' + selected + ' else None),imu_fsync_reads=(int(' + obj + '.FsyncReads) if ' + selected + ' else None)'
    else:
        fields = ',imu_ireg_selected=(' + selected + ')'
        for field, prop, typ in [('control', 'SregControl', 'int'), ('address', 'IregAddress', 'int'), ('pending', 'IregPending', 'bool'), ('ready', 'IregReady', 'bool'), ('starts', 'IregStarts', 'int'), ('completions', 'IregCompletions', 'int'), ('reads', 'IregReads', 'int')]:
            fields += ',imu_ireg_' + field + '=(' + typ + '(' + obj + '.' + prop + ') if ' + selected + ' else None)'
    plan['diagnostics'] = plan['diagnostics'][:-1] + fields + ')'
    if edmp and a.missing_idle:
        plan['runtime_edits'] = [dict(before='    while not m.IsPaused and live_seconds<120:\n        time.sleep(1.0)\n        live_seconds+=1\n',
            after='    while not m.IsPaused and live_seconds<120 and blackwall_imu_identity.Edmp.IdleReads<2:\n        time.sleep(0.01)\n        live_seconds+=0.01\n')]
    if power and a.missing_flush:
        plan['runtime_edits'] = [dict(before='    while not m.IsPaused and live_seconds<120:\n        time.sleep(1.0)\n        live_seconds+=1\n',
            after='    while not m.IsPaused and live_seconds<120 and blackwall_imu_identity.Configuration.FifoReads<3:\n        time.sleep(0.01)\n        live_seconds+=0.01\n')]
    plan['reviewed_sources'] = {}
    for case in plan['cases']:
        audit = s / audit_root / case / 'report.json'
        plan['reviewed_sources'][case] = dict(path=str(audit.relative_to(s)), sha256=sha(audit))
        prior = json.loads((s / source_root / case / 'report.json').read_text())
        guard = next(x for x in prior['observed']['guards'] if x['accesses'])
        boundary = dict(kind='strict-mmio', pc=prior['observed']['pc'], **{k: guard[k] for k in ['address', 'operation', 'width', 'value']})
        plan['semantics'][case] = dict(
            candidate=dict(boundary=dict(kind='bounded-capture'), comparison=dict(policy='bounded-invariants', paths=[['observed', 'memory_policy', 'violations'], ['observed', 'system_control', 'violations']]),
                           checks=[dict(path=['diagnostics', 'imu_ireg_' + k], eq=v) for k, v in [('selected', True), ('control', a.sreg_control), ('reads', 1)]],
                           allowed_differences=['Explicit single-byte SREG_CTRL fixture and virtual4us access only.'],
                           unresolved_differences=['Provisional frontier, physical timing/defaults and sensor samples unknown.']),
            control=dict(boundary=boundary, comparison=dict(policy='exact', path=['observed']),
                         checks=[dict(path=['selected_observation'], eq_source=['selected_observation']), dict(path=['diagnostics', 'imu_ireg_selected'], eq=False)],
                         allowed_differences=['IREG disabled preserves reset-only execution.'], unresolved_differences=['Indirect address-select remains unsupported.']))
        spec = plan['semantics'][case]['candidate']
        if auxiliary:
            initial=bytes.fromhex(a.auxiliary_configuration)
            expected=[('selected',True),('fixture',a.auxiliary_configuration.lower()),('pad',(initial[0]&0xf3)|0x14),('int0',initial[1]),('int1',(initial[2]&0x7f)|0x20),('pad_reads',1),('pad_writes',1),('int_reads',1),('int_writes',1)]
            spec['checks']=[dict(path=['diagnostics','imu_aux_'+k],eq=v) for k,v in expected]
            spec['checks'].append(dict(path=['prior_prefix_equal'],eq=True))
            spec['allowed_differences']=['Explicit auxiliary pad/INT1 fixtures; original pad RMW and interrupt packing.']
            spec['boundary']=dict(boundary,operation='peer-write',value=4)
            spec['checks'] += [dict(path=['diagnostics',k],eq=v) for k,v in [('imu_last_write','7ca20f1e'),('imu_finishes',72),('imu_returned_bytes',29)]]
            spec['unresolved_differences']=['A20F=1E first I2C-master setup write unsupported; secondary response, interrupt generation and ODR execution unverified.']
            plan['semantics'][case]['control']['checks'][-1]=dict(path=['diagnostics','imu_aux_selected'],eq=False)
            plan['semantics'][case]['control']['allowed_differences']=['Auxiliary model disabled preserves power/FIFO execution.']
            plan['semantics'][case]['control']['unresolved_differences']=['Pad30 select unsupported.']
            continue
        if power:
            expected = [('selected',True), ('fixture',a.power_configuration.lower()), ('value',int(a.power_configuration[:2],16)&0xf0), ('reads',2), ('writes',2), ('fifo_writes',1), ('flush_requests',1), ('flush_completions',int(not a.missing_flush)), ('flush_done',not a.missing_flush)]
            if not a.missing_flush:
                expected += [('fifo_value',int(a.power_configuration[2:4],16)), ('status0_reads',1), ('status_apex_reads',1)]
            else:
                expected += [('fifo_value',int(a.power_configuration[2:4],16)|0x80), ('status0_reads',0), ('status_apex_reads',0)]
            spec['checks'] = [dict(path=['diagnostics','imu_power_' + k],eq=v) for k,v in expected]
            spec['checks'].append(dict(path=['prior_prefix_equal'],eq=True))
            spec['allowed_differences'] = ['Explicit power/FIFO/status fixtures; original mode RMW, virtual FIFO flush and status decoding.']
            spec['unresolved_differences'] = ['IOC pad scenario30 query unsupported; native ODR execution, physical flush timing and interrupt event lifecycle unknown.']
            if not a.missing_flush:
                spec['boundary'] = dict(boundary, operation='peer-write', value=1)
                spec['checks'].append(dict(path=['diagnostics','imu_last_write'],eq='30'))
            plan['semantics'][case]['control']['checks'][-1] = dict(path=['diagnostics','imu_power_selected'],eq=False)
            plan['semantics'][case]['control']['allowed_differences'] = ['Power/FIFO disabled preserves EDMP execution.']
            plan['semantics'][case]['control']['unresolved_differences'] = ['Power register10 query remains unsupported.']
            continue
        if edmp:
            spec['checks'] = [dict(path=['diagnostics', 'imu_edmp_' + k], eq=v) for k,v in [('selected', True), ('initial0', int(a.edmp_configuration[:2],16)), ('initial1', int(a.edmp_configuration[2:],16)), ('complete_idle', not a.missing_idle)]]
            spec['checks'].append(dict(path=['prior_prefix_equal'], eq=True))
            spec['allowed_differences'] = ['Explicit EDMP bank, clear-only source masks and virtual idle timer; original ARM controls polling.']
            spec['unresolved_differences'] = ['Hardware timing, opaque legacy bits, sensor sampling and full boot unknown.']
            if not a.missing_idle:
                en0, en1 = int(a.edmp_configuration[:2],16), int(a.edmp_configuration[2:],16)
                writes = 5 + int(not (en0 & 8)) + 1
                spec['boundary'] = dict(boundary, operation='peer-write', value=1)
                expected = [('enable0',en0 & 0xf2), ('enable1',en1 & 0x8f), ('writes',writes), ('idle',True), ('pending',False), ('requests',int(bool(en1 & 0x40))), ('completions',int(bool(en1 & 0x40)))]
                spec['checks'] += [dict(path=['diagnostics','imu_edmp_' + k],eq=v) for k,v in expected]
                spec['checks'].append(dict(path=['diagnostics','imu_last_write'],eq='10'))
            else:
                spec['checks'] += [dict(path=['diagnostics','imu_edmp_idle'],eq=False), dict(path=['diagnostics','imu_edmp_completions'],eq=0)]
            plan['semantics'][case]['control']['checks'][-1] = dict(path=['diagnostics','imu_edmp_selected'], eq=False)
            plan['semantics'][case]['control']['allowed_differences'] = ['EDMP disabled preserves INT1 configuration execution.']
            plan['semantics'][case]['control']['unresolved_differences'] = ['EDMP register select remains unsupported.']
            continue
        if pins:
            spec['checks'] += [dict(path=['diagnostics', 'imu_pin_' + k], eq=v) for k, v in [('selected', True), ('fixture', a.int1_config2), ('reads', 1), ('writes', 1), ('value', (a.int1_config2 & 0xf8) | 1)]]
            spec['checks'].append(dict(path=['prior_prefix_equal'], eq=True))
            spec['boundary'] = dict(boundary, operation='peer-write', value=1)
            spec['checks'] += [dict(path=['diagnostics', k], eq=v) for k, v in [('imu_last_write', '2a'), ('imu_finishes', 19), ('imu_returned_bytes', 7)]]
            spec['allowed_differences'] = ['Explicit INT1 pin configuration byte, source-backed low-three-bit RMW only.']
            spec['unresolved_differences'] = ['Next EDMP_APEX_EN1 select unsupported; interrupt generation/power/ODR and full boot unknown.']
            plan['semantics'][case]['control']['checks'][-1] = dict(path=['diagnostics', 'imu_pin_selected'], eq=False)
            plan['semantics'][case]['control']['allowed_differences'] = ['INT1 model disabled preserves FSYNC execution.']
            plan['semantics'][case]['control']['unresolved_differences'] = ['INT1_CONFIG2 select remains unsupported.']
            continue
        if tags:
            spec['checks'] += [dict(path=['diagnostics', 'imu_fsync_' + k], eq=v) for k, v in [('selected', True), ('fixture', a.fsync_config), ('reads', 1)]]
            spec['boundary'] = dict(boundary, operation='peer-write', value=1)
            spec['checks'] += [dict(path=['diagnostics', k], eq=v) for k, v in [('imu_last_write', '18'), ('imu_finishes', 16), ('imu_returned_bytes', 6)]]
            spec['checks'].append(dict(path=['prior_prefix_equal'], eq=True))
            spec['allowed_differences'] = ['Explicit FSYNC_CONFIG0 query fixture; original FIFO and tag initialization.']
            spec['unresolved_differences'] = ['Next INT1_CONFIG2 select unsupported; sensor interrupt configuration and acquisition unverified.']
            plan['semantics'][case]['control']['checks'][-1] = dict(path=['diagnostics', 'imu_fsync_selected'], eq=False)
            plan['semantics'][case]['control']['allowed_differences'] = ['FSYNC fixture disabled preserves IREG execution.']
            plan['semantics'][case]['control']['unresolved_differences'] = ['FSYNC_CONFIG0 select remains unsupported.']
            continue
        spec['boundary'] = dict(boundary, operation='peer-write', value=1)
        spec['checks'] += [dict(path=['diagnostics', k], eq=v) for k, v in [('imu_last_write', '24'), ('imu_finishes', 14), ('imu_returned_bytes', 5), ('imu_ireg_starts', 1), ('imu_ireg_completions', 1), ('imu_ireg_pending', False), ('imu_ireg_ready', False)]]
        spec['unresolved_differences'] = ['Next direct register24 select unsupported; physical defaults/timing/sensor sample behavior remain unknown.']
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan, indent=2) + '\n')
    print('Prepared declared SREG_CTRL/FSYNC fixtures', hex(a.sreg_control), hex(a.fsync_config) if tags else 'FSYNC disabled')


if __name__ == '__main__':
    main()
