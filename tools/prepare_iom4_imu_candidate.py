"""Attach the source-bounded identity peer to original-reset native candidates."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def prepare_initial_indirect(a,root):
    s=a.simulator;case=a.case
    baseline=s/'imu-initial-indirect-research-01/model-before.cs'
    proof=json.loads((s/'imu-identity-failure-research-01/manifest.json').read_text())
    if not proof['passed'] or sha(baseline)!=proof['frozen_sources']['tools/renode-imu-identity.cs']:raise ValueError('Pinned identity-failure model required')
    plan=json.loads((s/('imu-identity-failure-'+case+'-plan-03.json')).read_text())
    peer='tools/renode-imu-identity.cs'
    plan.update(id='imu-initial-indirect-'+format(a.identity_byte,'02x')+'-v1',source_root='imu-identity-failure-main-02',components=[dict(name='explicit-initial-indirect-state',baseline=str(baseline.relative_to(s)),candidate=peer,before_sha256=sha(baseline),after_sha256=sha(root/peer))],runtime_edits=[],append_components=[],board_append='',initial_ireg_ready_physical_verified=False)
    before='    gafClockVariationByte: 133\n';plan['board_edits']=[dict(before=before,after=before+'    initialIregReady: true\n')]
    if a.identity_byte!=0:plan['board_edits'].append(dict(before='    identityByte: 0\n',after='    identityByte: '+str(a.identity_byte)+'\n'))
    audit=s/'imu-identity-failure-audit-01'/('failure-'+case)/'report.json'
    if sha(audit)!=proof['files'][str(audit.relative_to(s))] or not json.loads(audit.read_text())['passed']:raise ValueError('Verified failure capture required')
    plan['reviewed_sources']={case:dict(path=str(audit.relative_to(s)),sha256=sha(audit))}
    plan['diagnostics']=plan['diagnostics'][:-1]+',imu_initial_ireg_ready=bool(blackwall_imu_identity.InitialIregReady))'
    prior=json.loads((s/'imu-identity-failure-main-02'/case/'report.json').read_text());g=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
    checks=[dict(path=['diagnostics','imu_initial_ireg_ready'],eq=True),dict(path=['diagnostics','imu_identity_byte'],eq=a.identity_byte),dict(path=['diagnostics','identity_driver_return_status'],eq=[0 if a.identity_byte==129 else 0xffffffff])]
    if a.identity_byte!=129:checks.append(dict(path=['diagnostics','imu_reset_requests'],eq=0))
    checks += [dict(path=['diagnostics',k],eq=v) for k,v in [('imu_gaf_written_bytes',225),('imu_last_write','7c000402')]]
    plan['semantics']={case:dict(candidate=dict(boundary=dict(boundary,width=4,value=4),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=checks,allowed_differences=['Explicit hypothetical initial indirect readiness; existing response fixtures and timer remain selected. Original CPU error path is not patched.'],unresolved_differences=['First GAF service remains unsupported; physical power-on readiness, final error propagation, normal startup and UI unknown.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','imu_initial_ireg_ready'],eq=False)],allowed_differences=['Default unknown initial indirect state retains failed-ID frontier.'],unresolved_differences=['Not physical I2C NACK or full device failure recovery.']))}
    a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared explicit initial indirect readiness',case,hex(a.identity_byte))


def prepare_startup_probe(a,root):
    s=a.simulator
    proof=json.loads((s/'imu-clock-variation-source-01/verification-manifest.json').read_text())
    baseline=s/'imu-identity-failure-research-01/model-before.cs'
    if not proof['passed'] or sha(baseline)!=proof['frozen_sources']['tools/renode-imu-identity.cs']:raise ValueError('Pinned IMU baseline required')
    contract=s/'iom4-command-source-04/report.json';old=json.loads((s/'iom4-command-verification-01/manifest.json').read_text())
    if sha(contract)!=old['files'][str(contract.relative_to(s))]:raise ValueError('Pinned identity branch contract required')
    identities=json.loads(contract.read_text())
    plan=json.loads((s/'imu-clock-variation-plan-01.json').read_text())
    plan.update(id='imu-identity-startup-'+format(a.identity_byte,'02x')+'-v1',source_root='imu-clock-variation-main-01',components=[],append_components=[],runtime_edits=[],board_edits=[],board_append='',reviewed_sources={})
    plan['components']=[dict(name='independent-int1-configuration',baseline=str(baseline.relative_to(s)),candidate='tools/renode-imu-identity.cs',before_sha256=sha(baseline),after_sha256=sha(root/'tools/renode-imu-identity.cs'))]
    if a.identity_byte!=129:plan['board_edits']=[dict(before='    identityByte: 129\n',after='    identityByte: '+str(a.identity_byte)+'\n')]
    # Addresses differ across firmware, so make the selected case explicit.
    plan['cases']={a.case:plan['cases'][a.case]}
    case=a.case;original=next(x for x in identities['cases'] if x['case']==case)
    points=[('identity-driver-return',original['identity_samples'][0]['execution']['stop']),('identity-reset-entry',original['reset_entry']),('identity-sensor-return',0x4c3246 if case=='stock24' else 0x4b7b8a),('identity-wrapper-return',0x4c61fc if case=='stock24' else 0x4bab40)]
    prior=json.loads((s/'imu-clock-variation-main-01'/case/'report.json').read_text())
    if not prior['passed'] or any(p['address'] in [address for _,address in points] for p in prior['selected_observation']['points']):raise ValueError('Unique points and successful baseline required')
    before='    e.StartAll()\n';after=''.join("    observer.AddPoint("+repr(label)+","+str(address)+")\n" for label,address in points)+before
    plan['runtime_edits']=[dict(before=before,after=after)]
    extra=''
    for label,_ in points:
        field=label.replace('-','_')
        extra+=','+field+"_hits=next((int(p.Hits) for p in observer.Points if str(p.Label)=="+repr(label)+"),0)"
        extra+=','+field+"_status=[int(e.R0) for e in observer.Events if str(e.Label)=="+repr(label)+"]"
    plan['diagnostics']=plan['diagnostics'][:-1]+extra+')'
    guard=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:guard[k] for k in ['address','operation','width','value']})
    checks=[dict(path=['diagnostics','imu_identity_byte'],eq=a.identity_byte),dict(path=['diagnostics','identity_driver_return_status'],eq=[0 if a.identity_byte==129 else 0xffffffff]),dict(path=['diagnostics','identity_reset_entry_hits'],eq=1 if a.identity_byte==129 else 0)]
    if a.identity_byte!=129:checks += [dict(path=['diagnostics',k],eq=v) for k,v in [('imu_reset_requests',0),('imu_last_write','7ca297'),('imu_pin_reads',1),('imu_pin_writes',1)]]
    plan['semantics']={case:dict(candidate=dict(boundary=boundary if a.identity_byte==129 else dict(boundary,width=4,value=3),comparison=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']]),checks=checks,allowed_differences=['Explicit identity fault or nominal fixture plus four declared PC observations; no firmware/branch/return/TCB changes.'],unresolved_differences=['Failed identity returns -1, continues INT1/EDMP setup and stops at unreset IPREG_MISC select; observer neutrality and normal startup/UI not claimed.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation'])],allowed_differences=['Probe disabled retains original model and observation recipe.'],unresolved_differences=['Original GAF service frontier.']))}
    a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared current startup identity probe',case,hex(a.identity_byte))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--identity-byte', type=lambda x: int(x, 0), default=0x81)
    p.add_argument('--current-startup',action='store_true')
    p.add_argument('--initial-ireg-ready',action='store_true')
    p.add_argument('--case',choices=['stock24','stock23','cfw'],default='stock24')
    a = p.parse_args()
    s, root = a.simulator, Path(__file__).resolve().parents[1]
    if not 0 <= a.identity_byte <= 255 or a.output.exists() or not a.output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(root):
        raise ValueError('Fresh private output and byte fixture required')
    if a.initial_ireg_ready:
        if not a.current_startup:raise ValueError('Initial indirect state requires current startup profile')
        prepare_initial_indirect(a,root)
        return
    if a.current_startup:
        prepare_startup_probe(a,root)
        return
    manifest = json.loads((s / 'iom4-command-verification-01/manifest.json').read_text())
    contract = s / 'iom4-command-source-04/report.json'
    if not manifest['passed'] or sha(contract) != manifest['files'][str(contract.relative_to(s))]:
        raise ValueError('Changed original IOM4 contract')
    for name, value in manifest['model_hashes'].items():
        if sha(root / 'tools' / name) != value:
            raise ValueError('Changed inherited model ' + name)
    peer = 'tools/renode-imu-identity.cs'
    plan = json.loads((s / 'mspi0-rx-main-01/stock24/plan.json').read_text())
    plan.update(id='iom4-imu-identity-v1', source_root='mspi0-rx-main-01', components=[],
                append_components=[dict(candidate=peer, sha256=sha(root / peer))], board_edits=[], runtime_edits=[],
                board_append='\nimu_identity: Miscellaneous.BlackwallImuIdentity @ iom4 0x69\n    owner: iom4\n    profile: "icm45608-whoami-only"\n    identityByte: ' + str(a.identity_byte) + '\n',
                iom4_contract_sha256=sha(contract))
    plan['runtime_edits'] = [dict(before='    m=monitor.Machine\n', after="    m=monitor.Machine\n    blackwall_imu_identity=m['sysbus.iom4.imu_identity']\n"),
                             dict(before='peer_attached=(int(w.Module)==7)', after='peer_attached=(int(w.Module) in (4,7))')]
    selected = "('blackwall_imu_identity' in globals())"
    obj = 'blackwall_imu_identity'
    fields = ',imu_selected=' + selected
    for field, prop, typ in [('identity_byte', 'IdentityByte', 'int'), ('pointer', 'Pointer', 'int'), ('pointer_writes', 'PointerWrites', 'int'), ('reads', 'IdentityReads', 'int'), ('returned_bytes', 'ReturnedBytes', 'int'), ('finishes', 'Finishes', 'int'), ('read_attempts', 'ReadAttempts', 'int'), ('write_attempts', 'WriteAttempts', 'int'), ('last_write', 'LastWriteHex', 'str'), ('last_read_count', 'LastReadCount', 'int')]:
        fields += ',imu_' + field + '=(' + typ + '(' + obj + '.' + prop + ') if ' + selected + ' else None)'
    plan['diagnostics'] = plan['diagnostics'][:-1] + fields + ')'
    plan['reviewed_sources'] = {}
    for case in plan['cases']:
        prior = json.loads((s / 'mspi0-rx-main-01' / case / 'report.json').read_text())
        audit = s / 'mspi0-rx-saved-audit-01' / case / 'report.json'
        plan['reviewed_sources'][case] = dict(path=str(audit.relative_to(s)), sha256=sha(audit))
        guard = next(x for x in prior['observed']['guards'] if x['accesses'])
        boundary = dict(kind='strict-mmio', pc=prior['observed']['pc'], **{k: guard[k] for k in ['address', 'operation', 'width', 'value']})
        plan['semantics'][case] = dict(
            candidate=dict(boundary=dict(kind='bounded-capture'), comparison=dict(policy='bounded-invariants', paths=[['observed', 'memory_policy', 'violations'], ['observed', 'system_control', 'violations']]),
                           checks=[dict(path=['diagnostics', 'imu_selected'], eq=True), dict(path=['diagnostics', 'imu_identity_byte'], eq=a.identity_byte)],
                           allowed_differences=['Explicit IMU identity fixture through inherited I2C peer; original firmware unchanged.'],
                           unresolved_differences=['Provisional next frontier, no IMU reset/config/sample model or full boot proof.']),
            control=dict(boundary=boundary, comparison=dict(policy='exact', path=['observed']),
                         checks=[dict(path=['selected_observation'], eq_source=['selected_observation']), dict(path=['diagnostics', 'imu_selected'], eq=False)],
                         allowed_differences=['Unregistered peer preserves original IOM4 frontier.'], unresolved_differences=['IMU remains absent.']))
        if a.identity_byte == 0x81:
            spec = plan['semantics'][case]['candidate']
            spec['boundary'] = dict(boundary, operation='peer-write', value=1)
            spec['checks'] += [dict(path=['diagnostics', 'imu_' + k], eq=v) for k, v in [('reads', 1), ('returned_bytes', 1), ('pointer_writes', 1), ('finishes', 2), ('last_write', '2d')]]
            spec['unresolved_differences'] = ['First unmodeled register-select 2d before reset; no sensor reset or full boot proof.']
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan, indent=2) + '\n')
    print('Prepared original-reset IOM4 identity fixture', hex(a.identity_byte))


if __name__ == '__main__':
    main()
