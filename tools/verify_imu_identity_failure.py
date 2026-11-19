"""Verify saved original-main identity faults and an independent-register correction."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from inspect_nema_irq_contract import discover_irq
from inspect_ambiq_target import decode
from inspect_imu_ui_dependency import linked_graph
from native_replay import digest


def verify(simulator, root):
    before = (simulator / 'imu-identity-failure-research-01/model-before.cs').read_text()
    after = (root / 'tools/renode-imu-identity.cs').read_text()
    assert after == before.replace('InitialInt1Config2>=0 && FsyncReads>0 && data!=null',
                                   'InitialInt1Config2>=0 && !ResetPending && data!=null')
    bindings = json.loads((simulator / 'iom4-command-source-04/report.json').read_text())['cases']
    results = []
    for case in ['stock24', 'stock23', 'cfw']:
        folder = simulator / 'imu-identity-failure-main-02' / case
        source = simulator / 'imu-clock-variation-main-01' / case
        report = json.loads((folder / 'report.json').read_text())
        assert report['execution_passed']
        audit = json.loads((simulator / 'imu-identity-failure-audit-01' / ('failure-' + case) / 'report.json').read_text())
        assert audit['passed'] and audit['native_rerun'] is False
        for name, expected in audit['capture_hashes'].items():
            path = (folder / name).resolve()
            assert path.is_relative_to(folder.resolve()) and digest(path) == expected
        raw = (folder / 'main.bin').read_bytes()
        assert raw == (source / 'main.bin').read_bytes()
        strict = (folder / 'strict.cs').read_text()
        assert strict.count(after) == 1 and strict.replace(after, before) == (source / 'strict.cs').read_text()
        assert (folder / 'board.repl').read_text().replace('    identityByte: 0\n', '    identityByte: 129\n') == (source / 'board.repl').read_text()
        diag = report['diagnostics']
        assert diag['imu_identity_byte'] == 0 and diag['imu_reads'] == 1
        assert diag['identity_driver_return_hits'] == 1 and diag['identity_driver_return_status'] == [0xffffffff]
        assert diag['identity_reset_entry_hits'] == diag['imu_reset_requests'] == 0
        assert diag['identity_sensor_return_hits'] == diag['identity_wrapper_return_hits'] == 0
        assert diag['imu_pin_reads'] == diag['imu_pin_writes'] == 1
        assert diag['imu_fsync_reads'] == diag['imu_ireg_reads'] == 0
        assert diag['imu_edmp_writes'] == 6 and diag['imu_edmp_requests'] == 1
        assert diag['imu_service_starts'] == diag['imu_gaf_written_bytes'] == 0
        assert diag['imu_last_write'] == '7ca297'
        binding = next(x for x in bindings if x['case'] == case)
        event = next(x for x in report['selected_observation']['events'] if x['label'] == 'identity-driver-return')
        assert event['pc'] == binding['identity_samples'][0]['execution']['stop'] and event['r0'] == 0xffffffff
        ram = (folder / 'exports/sram-full.bin').read_bytes()
        slot = discover_irq(raw)['current_tcb_slot']
        current = struct.unpack_from('<I', ram, slot - 0x20000000)[0]
        graph = linked_graph(ram, current)
        assert graph['current']['name'] == 'sensor_hub' and len(graph['tasks']) == 29
        results.append(dict(case=case, task='sensor_hub', tasks=29, identity_status=0xffffffff,
                            pin_access_before_fsync_verified=True, next_packet='7ca297',
                            sensor_initializer_return_reached=False, wrapper_return_reached=False))
    nominal = simulator / 'imu-identity-nominal-main-01/stock24'
    source = simulator / 'imu-clock-variation-main-01/stock24'
    positive = json.loads((nominal / 'report.json').read_text())
    old = json.loads((source / 'report.json').read_text())
    assert positive['passed'] and positive['observed'] == old['observed']
    assert (nominal / 'exports/sram-full.bin').read_bytes() == (source / 'exports/sram-full.bin').read_bytes()
    assert positive['diagnostics']['identity_driver_return_status'] == [0]
    assert positive['diagnostics']['identity_reset_entry_hits'] == positive['diagnostics']['imu_reset_requests'] == 1
    assert positive['diagnostics']['imu_gaf_written_bytes'] == 225
    assert positive['diagnostics']['imu_last_write'] == '7c000402'
    clean = lambda events: [{k: v for k, v in event.items() if k != 'sequence'} for event in events if not event['label'].startswith('identity-')]
    assert clean(positive['selected_observation']['events']) == clean(old['selected_observation']['events'])
    return dict(passed=True, fault_cases=results, nominal_cpu_report_exact=True, nominal_full_sram_exact=True,
                nominal_legacy_event_projection_exact=True, observer_universally_neutral=False,
                normal_startup_verified=False, hardware_accessed=False)


def verify_initial(simulator, root):
    before=(simulator/'imu-initial-indirect-research-01/model-before.cs').read_text()
    after=(root/'tools/renode-imu-identity.cs').read_text()
    bindings=json.loads((simulator/'imu-gaf-parameters-verification-01/manifest.json').read_text())['cases']
    setters=json.loads((simulator/'imu-parameter-full-setter-01/report.json').read_text())['cases']
    result=[]
    for case in ['stock24','stock23','cfw']:
        folder=simulator/'imu-initial-ireg-main-01'/case;source=simulator/'imu-identity-failure-main-02'/case
        report=json.loads((folder/'report.json').read_text());assert report['execution_passed']
        audit=json.loads((simulator/'imu-initial-ireg-audit-01'/case/'report.json').read_text());assert audit['passed'] and audit['native_rerun'] is False
        for name,pin in audit['capture_hashes'].items():
            path=(folder/name).resolve();assert path.is_relative_to(folder.resolve()) and digest(path)==pin
        raw=(folder/'main.bin').read_bytes();assert raw==(source/'main.bin').read_bytes()
        strict=(folder/'strict.cs').read_text();assert strict.count(after)==1 and strict.replace(after,before)==(source/'strict.cs').read_text()
        expected_board=(source/'board.repl').read_text().replace('    gafClockVariationByte: 133\n','    gafClockVariationByte: 133\n    initialIregReady: true\n')
        assert (folder/'board.repl').read_text()==expected_board
        d=report['diagnostics'];assert d['imu_initial_ireg_ready'] and d['imu_identity_byte']==0
        assert d['identity_driver_return_status']==[0xffffffff]
        assert d['imu_reset_requests']==d['imu_reset_completions']==d['imu_reset_drive_restores']==d['imu_reset_interface_restores']==0
        assert d['imu_gaf_written_bytes']==225 and d['imu_last_write']=='7c000402'
        assert d['identity_sensor_return_hits']==d['identity_wrapper_return_hits']==0
        ram=(folder/'exports/sram-full.bin').read_bytes();word=lambda a:struct.unpack_from('<I',ram,a-0x20000000)[0]
        graph=linked_graph(ram,word(discover_irq(raw)['current_tcb_slot']));assert graph['current']['name']=='sensor_hub' and len(graph['tasks'])==29
        bound=next(x for x in bindings if x['case']==case);assert hashlib.sha256(raw).hexdigest()==bound['source_hash']
        root_sp=bound['root_sp'];setter=next(x['entry'] for x in setters if x['case']==case)
        prologue=decode(raw,setter,6);assert prologue[0].op_str=='{r3, r4, r5, r6, r7, r8, sb, lr}' and prologue[1].op_str=='sp, #0x18'
        root_return=word(root_sp+0x154);assert root_return==bound['root_lr']
        call=decode(raw,(word(root_sp-4)&~1)-4,4)[0];assert call.mnemonic=='bl' and call.operands[0].imm==setter
        setter_sp=root_sp-0x38;helper=0x55405c if case=='stock24' else 0x520204
        call=decode(raw,(word(setter_sp-4)&~1)-4,4)[0];assert call.mnemonic=='bl' and call.operands[0].imm==helper
        assert word(setter_sp-16)==2
        current_sp=report['observed']['register_context']['r13'];stack=graph['current']['stack_base'];depth=word(graph['current']['tcb']+84)
        assert stack<=current_sp<setter_sp-16<root_sp<root_sp+0x158<=stack+depth*4
        local_status=word(root_sp-28);assert local_status==0
        result.append(dict(case=case,task='sensor_hub',tasks=29,initial_driver_status=0xffffffff,configuration_caller_local_r4=local_status,root_sp=root_sp,root_return=root_return,active_setter_frame_bound=True,service_request=2,reset_requests=0,written_bytes=225))
    positive=json.loads((simulator/'imu-initial-ireg-nominal-01/report.json').read_text());old=json.loads((simulator/'imu-identity-nominal-main-01/stock24/report.json').read_text())
    assert positive['execution_passed'] and positive['observed']==old['observed'] and positive['selected_observation']==old['selected_observation']
    assert positive['diagnostics']['identity_driver_return_status']==[0] and positive['diagnostics']['imu_reset_requests']==1
    assert (simulator/'imu-initial-ireg-nominal-01/exports/sram-full.bin').read_bytes()==(simulator/'imu-identity-nominal-main-01/stock24/exports/sram-full.bin').read_bytes()
    off=json.loads((simulator/'imu-initial-ireg-off-01/report.json').read_text());old=json.loads((simulator/'imu-identity-failure-main-02/stock24/report.json').read_text())
    assert off['passed'] and off['observed']==old['observed'] and off['selected_observation']==old['selected_observation']
    assert not off['diagnostics']['imu_initial_ireg_ready'] and off['diagnostics']['imu_last_write']=='7ca297'
    return dict(passed=True,cases=result,nominal_cpu_events_full_sram_exact=True,disabled_cpu_events_exact=True,physical_power_on_readiness_verified=False,whole_initializer_status_verified=False,full_startup_verified=False,hardware_accessed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--initial-ireg', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output')
    answer = (verify_initial if args.initial_ireg else verify)(args.simulator, Path(__file__).resolve().parents[1])
    args.output.write_text(json.dumps(answer, indent=2) + '\n')
    print('Verified identity faults3 and nominal control; startup/UI remain unproven')
