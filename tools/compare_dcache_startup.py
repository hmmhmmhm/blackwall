"""Compare bounded stock/CFW cache startup on two engines; never connect to glasses."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from audit_assets import PINS
from emulate_codec_query import PROFILES
from firmware_runner import inspect_bundle
from simulator_scenarios import load_scenario

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['firmware_runner.py', 'simulator_registers.py', 'simulator_icache.py', 'simulator_dcache.py',
           'simulator_buck_start.py', 'simulator_vddf_tempco.py', 'simulator_mcu_clock.py', 'simulator_clocks.py',
           'simulator_scenarios.py', 'simulator-scenarios.json', 'run_renode_main_probe.py',
           'renode-system-control.cs', 'renode-memory-policy.cs', 'renode-strict-mmio.cs',
           'renode-reset-controller.cs', 'renode-watchdog.cs']


def normalized(data, native):
    if native:
        o = data['observed']
        events = [g for g in o['guards'] if g['accesses']]
        if len(events) != 1 or events[0]['accesses'] != 1 or o['memory_policy']['violations'] or o['system_control']['violations']:
            raise ValueError('Native did not stop at exactly one MMIO boundary')
        event = events[0]
        endpoint = (o['pc'], event['address'], event['width'], event['operation'],event['value'] if event['operation']=='write' else None)
        cache = o['coherent_dcache']
        if data['unmodeled_engine_messages']:
            raise ValueError('Unexpected native engine messages')
    else:
        event = data['access']
        endpoint = (int(data['final_pc'], 16), int(event['address'], 16), event['bytes'],
                    'read' if event['kind'].startswith('read') else 'write',
                    int(event['value'],16) if 'value' in event else None)
        cache = data['coherent_dcache']
    keys = ['enabled', 'geometry_reads', 'selector_reads', 'selector_writes', 'initialized_lines',
            'invalidate_set_way', 'clean_set_way', 'clean_invalidate_set_way', 'ccsidr']
    result=dict(endpoint=endpoint, cache={k: cache[k] for k in keys})
    source=o if native else data
    if source.get('buck_response') is not None:
        result['response']={k:source['buck_response'][k] for k in ('profile','phase','reads','transitions')}
    if source.get('vddf_tempco_storage') is not None:
        result['tempco']={k:source['vddf_tempco_storage'][k] for k in ('applied','original_word','reduced_trim')}
    if native and source.get('gpu_power_response') is not None:
        result['gpu_power']={k:source['gpu_power_response'][k] for k in ('profile','phase','request_word','status_word','enable_reads','status_reads','enable_writes','transitions')}
    if native and source.get('gpu_power_preparation') is not None:
        result['preparation']={k:source['gpu_power_preparation'][k] for k in ('steps_completed','complete','original_core_word','boost_delta')}
        result['preparation_fields']={a:source['hal_storage']['registers'][a] for a in ('0x40020080','0x40020088','0x40020380','0x40020344','0x4002034c','0x40020358','0x40020354')}
    if native and (source.get('mcu_clock_response') or {}).get('hfrc_force_control'):
        result['hfrc']={k:source['mcu_clock_response'][k] for k in ('hfrc_force_control','hfrc_forced')}
    if native and source.get('gfx_power_storage') is not None:
        result['gfx']={k:source['gfx_power_storage'][k] for k in ('selection','request','selection_reads','request_reads','selection_writes','request_writes')}
    if source.get('mcu_clock_response') is not None:
        result['clock']={k:source['mcu_clock_response'][k] for k in ('profile','phase','mode_word','force_writes','clock_reads','mode_reads','mode_writes','transitions','misc_word','hfrc2_enabled','hfrc2_ready')}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seed-native', type=Path)
    parser.add_argument('--seed-unicorn', type=Path)
    parser.add_argument('--reuse-native-from', type=Path, help='Reuse frozen native runs from an interrupted comparison')
    parser.add_argument('--buck-response', choices=('active','stuck-off'), help='Compare explicit response profile instead of single samples')
    parser.add_argument('--mcu-clock-response', choices=('nominal',), help='Compare clock state with explicitly different MPU/power boundaries')
    parser.add_argument('--gpu-power-response', choices=('active',), help='Native nominal GPU power response before first GPU register access')
    parser.add_argument('--gpu-power-preparation', action='store_true', help='Native ordered GPU power preparation before enable request')
    parser.add_argument('--hfrc-force-control', action='store_true', help='Native HFRC force control beyond GPU selection')
    parser.add_argument('--gfx-power-storage', action='store_true', help='Native-only legacy GPU selection storage beyond Python MPU boundary')
    args = parser.parse_args()
    if args.gpu_power_response and not args.gpu_power_preparation:
        raise ValueError('GPU response comparison requires preparation stage')
    if args.gpu_power_preparation and not args.hfrc_force_control:
        raise ValueError('GPU preparation comparison requires HFRC stage')
    if args.hfrc_force_control and not args.gfx_power_storage:
        raise ValueError('HFRC stage comparison requires GPU selection stage')
    if args.gfx_power_storage and not args.mcu_clock_response:
        raise ValueError('GFX comparison requires explicit MCU clock response')
    if args.mcu_clock_response and args.buck_response != 'active':
        raise ValueError('MCU clock comparison requires active buck response')
    args.output.mkdir(mode=0o700)
    sources = {name: hashlib.sha256((ROOT/'tools'/name).read_bytes()).hexdigest() for name in SOURCES}
    old_rows = (json.loads((args.reuse_native_from/'progress.json').read_text())['rows']
                if args.reuse_native_from else [])
    existing = {row['case']: row for row in old_rows if row.get('native_sha256')}
    # A failed comparison can still contain a valid frozen engine run. Verify its hash/source below.
    rows = []
    for key in ('stock_base', 'stock_current', 'cfw'):
        bundle = args.inputs / PROFILES[key]['file']
        if hashlib.sha256(bundle.read_bytes()).hexdigest() != PINS[key]:
            raise ValueError('Pinned input mismatch: ' + key)
        for power in ('lp', 'hp'):
            for buck in ((args.buck_response,) if args.buck_response else ('off', 'lp')):
                name = f'{key}-{power}-{buck}'
                seed = key == 'stock_current' and power == 'lp' and buck == (args.buck_response or 'off')
                scenario_name=(f'startup-zero-info1-rev-23-buck-response-{buck}-hypothesis' if args.buck_response
                               else f'startup-zero-info1-rev-23-buck-{buck}-coherent-dcache-hypothesis')
                if args.mcu_clock_response:
                    scenario_name=f'startup-zero-info1-rev-23-mcu-clock-{args.mcu_clock_response}-hypothesis'
                options, scenario = load_scenario(scenario_name)
                options['power_mode'] = power
                py_path = args.seed_unicorn if seed and args.seed_unicorn else args.output / (name+'.json')
                if seed and args.seed_unicorn:
                    python = json.loads(py_path.read_text())
                    if python['execution_scenario']['resolved_options'] != options:
                        raise ValueError('Seed Python options differ')
                else:
                    python = inspect_bundle(bundle, scenario['instructions'], timeout_us=scenario['timeout_us'], **options)
                    with py_path.open('x') as handle: json.dump(python, handle, indent=2)
                reuse = name in existing or (seed and args.seed_native is not None)
                native_path = (Path(existing[name]['native']) if name in existing else
                               args.seed_native if seed and args.seed_native else args.output / ('native-'+name) / 'report.json')
                if reuse:
                    combined = '\n'.join((ROOT/'tools'/n).read_text() for n in ('renode-strict-mmio.cs','renode-memory-policy.cs','renode-system-control.cs','renode-reset-controller.cs','renode-watchdog.cs'))
                    if (native_path.parent/'strict.cs').read_text() != combined:
                        raise ValueError('Seed native model source differs')
                    if name in existing and hashlib.sha256(native_path.read_bytes()).hexdigest() != existing[name]['native_sha256']:
                        raise ValueError('Existing native result changed')
                else:
                    cmd = [sys.executable, str(ROOT/'tools/run_renode_main_probe.py'), str(bundle), str(native_path.parent),
                           '--wall-run-seconds','15','--power-mode',power,'--reset-latch','2',
                           '--watchdog-model','--reset-controller','--startup-controls','--shadow-info1','mram',
                           '--info1-metadata-fixture','zero','--chip-revision-fixture','0x23','--spot-control-storage',
                           '--memory-startup-fixture','--hal-startup-storage','--mram-control-storage','--buck-override-storage',
                           '--buck-start-storage','--coreldo-reduction-storage','--memldo-setup-storage',
                           '--buck-status-fixture',buck,'--coherent-icache-model','--prefetch-control-storage','--coherent-dcache-model']
                    if args.buck_response:
                        index=cmd.index('--buck-status-fixture');del cmd[index:index+2]
                        cmd+=['--buck-response-model',buck,'--vddf-tempco-storage']
                    if args.mcu_clock_response:cmd+=['--mcu-clock-response',args.mcu_clock_response]
                    if args.gfx_power_storage:cmd+=['--gfx-power-storage']
                    if args.hfrc_force_control:cmd+=['--hfrc-force-control']
                    if args.gpu_power_preparation:cmd+=['--gpu-power-preparation']
                    if args.gpu_power_response:cmd+=['--gpu-power-response',args.gpu_power_response]
                    p = subprocess.run(cmd, text=True, capture_output=True, timeout=65)
                    (native_path.parent/'command.json').write_text(json.dumps(cmd, indent=2))
                    (native_path.parent/'stdout.log').write_text(p.stdout+p.stderr)
                    if p.returncode: raise ValueError('Native process failed: '+name)
                native = json.loads(native_path.read_text())
                selected = native['selected_hypotheses']
                mode_matches=(selected.get('buck_response_model')==buck and selected['vddf_tempco_storage'] if args.buck_response
                              else selected['buck_status_fixture']==buck and selected.get('buck_response_model') is None)
                if (selected['power_mode'] != power or not mode_matches
                    or not selected['coherent_dcache_model'] or not selected['prefetch_control_storage']
                    or selected.get('mcu_clock_response') != args.mcu_clock_response
                    or selected.get('gfx_power_storage',False) != args.gfx_power_storage
                    or selected.get('hfrc_force_control',False) != args.hfrc_force_control
                    or selected.get('gpu_power_preparation',False) != args.gpu_power_preparation
                    or selected.get('gpu_power_response') != args.gpu_power_response
                    or native['host_execution_window_seconds'] != 15):
                    raise ValueError('Native execution hypotheses differ')
                if python['bundle_sha256'] != PINS[key] or native['bundle_sha256'] != PINS[key]:
                    raise ValueError('Report input hash differs')
                a, b = normalized(python, False), normalized(native, True)
                boundary_ok=(a.get('response',{}).get('phase')==args.buck_response
                             and a.get('tempco',{}).get('applied')==(args.buck_response=='active')
                             if args.buck_response else a['endpoint'][1:] == (0x40021108, 4, 'read',None))
                comparison_a,comparison_b=dict(a),dict(b)
                if args.mcu_clock_response:
                    # Native M55 executes MPU disable, which the Python approximation cannot yet model.
                    # It then samples VRSTATUS once more before the next unmodeled power register.
                    boundary_ok=(a['endpoint'][1:]==(0xe000ed24,4,'read',None)
                                 and b['endpoint'][1:]==((0x400900f8,4,'write',0) if args.gpu_power_response else (0x40021004,4,'write',0x40000) if args.gpu_power_preparation else (0x40020080,4,'write',0x6d3d9) if args.hfrc_force_control else (0x40004044,4,'write',0xfbbfc1) if args.gfx_power_storage else (0x40021090,4,'read',None))
                                 and a['response']['phase']==b['response']['phase']=='active'
                                 and b['response']['reads']==a['response']['reads']+(3 if args.hfrc_force_control else 2 if args.gfx_power_storage else 1)
                                 and a['clock']['phase']=='acked' and a['clock']['mode_word']==22
                                 and a['clock']['transitions']==int(power=='lp')
                                 and a['clock']['force_writes']==2 and a['clock']['mode_writes']==1
                                 and b['cache']['geometry_reads']==a['cache']['geometry_reads']+1
                                 and b['cache']['selector_writes']==a['cache']['selector_writes']+1
                                 and a['cache']['clean_invalidate_set_way']==0
                                 and b['cache']['clean_invalidate_set_way']==2048)
                    if args.gfx_power_storage:
                        boundary_ok=boundary_ok and (b.get('gfx')==dict(selection=1,request=3,selection_reads=1,request_reads=1,selection_writes=1,request_writes=1)
                            and b['clock']['mode_reads']==a['clock']['mode_reads']+(4 if args.gpu_power_preparation else 2))
                        comparison_b.pop('gfx',None)
                        comparison_a['clock']=dict(a['clock']);comparison_b['clock']=dict(b['clock'])
                        comparison_a['clock'].pop('mode_reads');comparison_b['clock'].pop('mode_reads')
                    if args.hfrc_force_control:
                        boundary_ok=boundary_ok and (b.get('hfrc')==dict(hfrc_force_control=True,hfrc_forced=True)
                            and b['clock']['force_writes']==a['clock']['force_writes']+2
                            and b['clock']['clock_reads']==a['clock']['clock_reads']+1
                            and b['clock']['misc_word']==a['clock']['misc_word']|0x21)
                        comparison_b.pop('hfrc',None)
                        for field in ('force_writes','clock_reads','misc_word'):
                            comparison_a['clock'].pop(field);comparison_b['clock'].pop(field)
                    if args.gpu_power_preparation:
                        expected_fields={hex(address):dict(value=value,writes=writes,reads=reads) for address,value,writes,reads in (
                            (0x40020080,0x6d3cd,3,6),(0x40020088,0x207c0741,3,5),
                            (0x40020380,0x11000,10,10),(0x40020344,0xc003000,2,4),
                            (0x4002034c,0xa002800,2,4),(0x40020358,0xd00,1,2),(0x40020354,0x260000,1,2))}
                        boundary_ok=boundary_ok and (b.get('preparation')==dict(steps_completed=18,complete=True,original_core_word=0x6d3cd,boost_delta=12)
                            and b.get('preparation_fields')==expected_fields)
                        comparison_b.pop('preparation',None);comparison_b.pop('preparation_fields',None)
                    if args.gpu_power_response:
                        boundary_ok=boundary_ok and b.get('gpu_power')==dict(profile='active',phase='on',request_word=0x40000,status_word=0x40000,enable_reads=8,status_reads=8,enable_writes=1,transitions=2)
                        comparison_b.pop('gpu_power',None)
                    comparison_a.pop('endpoint');comparison_b.pop('endpoint')
                    comparison_a['cache']=dict(a['cache']);comparison_b['cache']=dict(b['cache'])
                    for field in ('geometry_reads','selector_writes','clean_invalidate_set_way'):
                        comparison_a['cache'].pop(field);comparison_b['cache'].pop(field)
                    comparison_a['response']=dict(a['response']);comparison_b['response']=dict(b['response'])
                    comparison_a['response'].pop('reads');comparison_b['response'].pop('reads')
                passed = (comparison_a == comparison_b and boundary_ok
                          and a['cache']['enabled'] and a['cache']['initialized_lines'] == 2048
                          and a['cache']['invalidate_set_way'] == a['cache']['clean_set_way'] == 2048)
                row = dict(case=name, passed=passed, normalized=a, native_normalized=b, native=str(native_path), unicorn=str(py_path),
                           native_sha256=hashlib.sha256(native_path.read_bytes()).hexdigest(),
                           unicorn_sha256=hashlib.sha256(py_path.read_bytes()).hexdigest(), native_reused=bool(reuse),
                           unicorn_reused=bool(seed and args.seed_unicorn))
                rows.append(row)
                (args.output/'progress.json').write_text(json.dumps(dict(rows=rows,sources=sources), indent=2))
                print(name, 'passed' if passed else 'FAILED', flush=True)
                if not passed: raise ValueError('Cache startup endpoints differ: '+name)
    if sources != {n:hashlib.sha256((ROOT/'tools'/n).read_bytes()).hexdigest() for n in SOURCES}:
        raise ValueError('Source changed during comparison')
    (args.output/'report.json').write_text(json.dumps(dict(passed=True, rows=rows, sources=sources,
        buck_response_profile=args.buck_response, mcu_clock_response=args.mcu_clock_response, gfx_power_storage=args.gfx_power_storage, hfrc_force_control=args.hfrc_force_control, gpu_power_preparation=args.gpu_power_preparation, gpu_power_response=args.gpu_power_response,
        comparison_scope=('native GPU request/status and preparation state; first GPU register write blocked; Python MPU boundary remains distinct' if args.gpu_power_response else 'native18-step power preparation and field/read/write states; explicit GPU-enable request boundary and Python MPU boundary differ' if args.gpu_power_preparation else 'native HFRC/GPU state, explicit trim-write boundary, additional MISC controls/reads; common cache/tempco state' if args.hfrc_force_control else 'clock/cache/tempco state plus native GPU selection; MPU/clock endpoints, one cache sweep, two buck reads and two MCU reads differ explicitly' if args.gfx_power_storage else 'clock/cache/tempco state; MPU/power endpoints, one cache clean-invalidate sweep and one buck read differ explicitly') if args.mcu_clock_response else 'bounded endpoint and state equality',
        hardware_validated=False, boot_verified=False, installable=False), indent=2)+'\n')


if __name__ == '__main__':
    main()
