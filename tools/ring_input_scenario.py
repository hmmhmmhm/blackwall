"""Known-ABI ring wake scenario using original main and peripheral-only inputs."""
import hashlib
import json
from pathlib import Path
import struct

TOOLS = Path(__file__).resolve().parent
BASE = 0x438000
SRAM = 0x20000000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_profile(case):
    data = json.loads((TOOLS/'ring-input-profiles.json').read_text())
    if data['schema'] != 1 or data['scenario'] != 'ring-wake' or case not in data['profiles']:
        raise ValueError('Unsupported ring scenario profile')
    return data['profiles'][case]


def validate_anchors(raw, profile):
    for anchor in profile['anchors']:
        offset = anchor['address']-BASE
        if (offset < 0 or offset+16 > len(raw)
                or hashlib.sha256(raw[offset:offset+16]).hexdigest() != anchor['sha256']):
            raise ValueError('Unsupported ring observer ABI at '+hex(anchor['address']))


def build(simulator, output, case, firmware_manifest=None, firmware_baseline=None):
    from run_runtime_connection_m55 import build as runtime_build
    from iom_shared_power_model import compose, board_profile
    from ring_wake_runtime import RUNTIME
    from sync_peer_roundtrip import frame
    profile = source_profile(case)
    runtime_build(simulator, output, case, gaf_profile=True,
                  firmware_manifest=firmware_manifest, firmware_baseline=firmware_baseline)
    raw = (output/'main.bin').read_bytes()
    baseline = (output/'firmware-baseline/main.bin').read_bytes() if firmware_manifest else raw
    if hashlib.sha256(baseline).hexdigest() != profile['ring']['raw_sha256']:
        raise ValueError('Ring baseline differs from source-checked image')
    validate_anchors(raw, profile)
    model = (output/'strict.cs').read_text()
    (output/'ring-base-model.cs').write_text(model)
    current = (TOOLS/'renode-strict-mmio.cs').read_text()
    begin = '    public sealed class BlackwallUartAdapter : IPeripheral\n'
    end = '\n    public sealed class BlackwallAdcPower\n'
    if model.count(begin) != 1 or current.count(begin) != 1 or model.count(end) != 1 or current.count(end) != 1:
        raise ValueError('Unknown UART component boundary')
    previous = begin+model.split(begin)[1].split(end)[0]
    replacement = begin+current.split(begin)[1].split(end)[0]
    model = compose(model.replace(previous, replacement))
    (output/'strict.cs').write_text(model)
    board = (output/'board.repl').read_text()
    anchor = 'uart0_adapter: Miscellaneous.BlackwallUartAdapter\n    module: 0\n'
    if board.count(anchor) != 1:
        raise ValueError('Unknown UART0 board attachment')
    board = board.replace(anchor, anchor+'    receiveFifo: true\n    receiveTimeout: true\n')
    (output/'board.repl').write_text(board_profile(board))
    for name in ['renode-touch-input-observer.cs', 'renode-ring-wake-observer.cs']:
        payload = (TOOLS/name).read_bytes()
        (output/name).write_bytes(payload)
        with (output/'activation.cs').open('ab') as stream:
            stream.write(b'\n'+payload)
    connection = json.loads((output/'connection-profile.json').read_text())
    connection['model_sha256'] = sha(output/'strict.cs')
    (output/'connection-profile.json').write_text(json.dumps(connection, indent=2)+'\n')
    ring = profile['ring']
    report = bytes.fromhex('00096100020aa7e8030000')
    wire = frame(0x9010, 1, struct.pack('<4H', 0x901, 0x90, 0, 11)+report)
    selected = dict(connection, schema=1, scenario='ring-wake', recipe_version=1,
                    ring_receiver=ring['receiver'], ring_caller=ring['receiver_caller'],
                    slider=ring['slider'], ring_relay=ring['relay_callback'],
                    ring_enqueue=ring['queue_wrapper'], last_tick=ring['last_ring_tick'],
                    hook=ring.get('hook'), fallback=ring.get('fallback'),
                    wake=profile['wake'], flow=profile['flow'],
                    report_hex=report.hex(), wire_hex=wire.hex(),
                    baseline_sha256=ring['raw_sha256'], raw_sha256=sha(output/'main.bin'),
                    shared_iom_gate=True, gaf_calculation_supported=False)
    (output/'ring-profile.json').write_text(json.dumps(selected, indent=2)+'\n')
    (output/'ring-source-profile.json').write_text(json.dumps(profile, indent=2)+'\n')
    (output/'ring_wake_runtime.py').write_bytes((TOOLS/'ring_wake_runtime.py').read_bytes())
    (output/'ring_input_scenario.py').write_bytes(Path(__file__).read_bytes())
    runtime = (output/'run.py').read_text()
    anchor = '\ntry:\n    import clr,time,json\n'
    if runtime.count(anchor) != 1:
        raise ValueError('Unknown original-main observation boundary')
    (output/'run.py').write_text(runtime.split(anchor)[0]+'\n'+RUNTIME)
    inputs = json.loads((output/'connection-inputs.json').read_text())
    names = set(inputs) | {'ring-base-model.cs', 'ring-profile.json', 'ring-source-profile.json',
                          'ring_wake_runtime.py', 'ring_input_scenario.py',
                          'renode-touch-input-observer.cs', 'renode-ring-wake-observer.cs'}
    (output/'connection-inputs.json').write_text(json.dumps(
        {name: sha(output/name) for name in sorted(names)}, indent=2)+'\n')
    return selected


def inspect(output, destination):
    from sync_peer_roundtrip import frame
    from inspect_imu_ui_dependency import linked_graph
    import runtime_firmware_candidate
    for name, expected in json.loads((output/'capture-files.json').read_text())['files'].items():
        path = (output/name).resolve()
        if not path.is_relative_to(output.resolve()) or sha(path) != expected:
            raise ValueError('Ring capture changed: '+name)
    p = json.loads((output/'ring-profile.json').read_text())
    if p.get('schema') != 1 or p.get('recipe_version') != 1 or p.get('scenario') != 'ring-wake':
        raise ValueError('Unsupported saved ring scenario')
    connection = json.loads((output/'connection-profile.json').read_text())
    if 'firmware_candidate' in connection:
        candidate = runtime_firmware_candidate.inspect(output, connection)
    else:
        runtime_firmware_candidate.check_original(output, connection)
        candidate = {}
    profile = json.loads((output/'ring-source-profile.json').read_text())
    validate_anchors((output/'main.bin').read_bytes(), profile)
    log = (output/'renode.log').read_text()
    errors = [line for line in log.splitlines() if line.startswith('BLACKWALL_RING_RUNTIME_ERROR ')]
    data_path = output/'exports/ring.json'
    x = json.loads(data_path.read_text()) if data_path.exists() else {}
    console = [json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_RING_RUNTIME ')]
    checks = dict(capture_export=bool(x), runtime_error_absent=not errors,
                  main_identity=sha(output/'main.bin') == p['raw_sha256'],
                  model_identity=sha(output/'strict.cs') == p['model_sha256'],
                  console_export_match=len(console) == 1 and console[0] == x, **candidate)
    semantic = {}
    if x:
        rows = x['rows']; a = x.get('app_stage', {}); r = x.get('request_stage'); d = x.get('display_reply')
        checks['ring_caller'] = x['ring_stage']['stopped'] and x['ring_stage']['pc'] == p['ring_caller']
        checks['ring_report'] = bytes(x['actual_report']).hex() == p['report_hex']
        checks['fault_free'] = x['cfsr'] == x['hfsr'] == x['memory_violations'] == 0 and not x['overflow'] and len(x['guards']) == 17 and all(v['accesses'] == 0 for v in x['guards'])
        checks['uart54_read_empty'] = x['read']-x['before']['read'] == 54 and x['pending'] == 0
        requests = a.get('requests', [])
        checks['actual108_request'] = len(requests) == 1
        if len(requests) == 1:
            wire = bytes(requests[0]); identifier, size, channel = struct.unpack('>HHH', wire[1:7]); body = wire[9:9+size]
            checks['actual108_wire'] = wire == frame(identifier, channel, body) and channel == 1 and body == struct.pack('<4H', 0x901, 0x108, 0, 12)+struct.pack('<3I', 4, 1, 0)
            checks['ack_correlated'] = bytes(a['ack']) == frame(identifier, 0, b'\x0a')
        callbacks = [v for v in rows if v[0] == 30]
        checks['app_callback'] = len(callbacks) == 1
        if len(callbacks) == 1:
            cb = callbacks[0]
            returns = [v for v in rows if v[0] == 35 and v[8] == cb[8] and v[-1] > cb[-1]]
            checks['app_callback_return'] = len(returns) == 1 and returns[0][2] == 0 and cb[6] == returns[0][6] and cb[9]&511 == returns[0][9]&511 == 0
        helpers = [v for v in rows if v[0] == 31]
        checks['source_role_code'] = len(helpers) == 1 and helpers[0][2:4] == [4, 1]
        app_ram = (output/'exports/app-wake-sram.bin').read_bytes()
        role = app_ram[p['flow']['role_slot']-SRAM]
        tick = struct.unpack_from('<I', app_ram, p['flow']['tick_slot']-SRAM)[0]
        checks['app_state'] = role == 4 and len(helpers) == 1 and tick == helpers[0][4]
        checks['idle_wake'] = a.get('stopped') and a.get('pc') == p['wake']['wake_gate']
        checks['app1_request'] = bool(r and r['stopped'] and r['matches'] == 1 and r['packet'] == [2, 1, 1, 0, 0, 0, 0, 0])
        checks['display_reply'] = bool(r and d and bytes(d['bytes']) == frame(struct.unpack_from('<H', bytes(r['descriptor']))[0], 0, b'\x02'))
        checks['display_wire'] = bool(r and any(bytes(v['data']) == frame(struct.unpack_from('<H', bytes(r['descriptor']))[0], 2, bytes(r['packet'])) for v in x['uart_dma']))
        checks['ui_callback_entry'] = bool(d and d.get('ui_dispatch') and d.get('callback', {}).get('stopped') and d['callback']['pc'] == p['wake']['ui']['callback'])
        checks['timeout_irq'] = bool(x['timeout_trace'] and not x['timeout_trace']['overflow'] and any(v[1]&0x40 and v[2] == 12 and v[3] == 1 and v[7]&511 == 31 for v in x['timeout_trace']['rows']))
        for name, before, after in [('ring', x['before'], x['injected']), ('ack', a.get('before'), a.get('after')), ('display', d.get('before') if d else None, d.get('after') if d else None)]:
            checks[name+'_input_cpu_time'] = bool(before and after and after['accepted'] and before['registers'] == after['registers'] and before['ticks'] == after['ticks'])
        for name, before, after in [('ring','before-input-sram.bin','after-input-sram.bin'), ('ack','before-ack-sram.bin','after-ack-sram.bin'), ('display','before-display-reply-sram.bin','after-display-reply-sram.bin')]:
            b = output/'exports'/before; c = output/'exports'/after
            checks[name+'_input_sram'] = b.exists() and c.exists() and b.read_bytes() == c.read_bytes()
        if checks['ui_callback_entry']:
            ram = (output/'exports/ring-sram.bin').read_bytes()
            graph = linked_graph(ram, d['callback']['entry'][4])
            checks['original_ui_task'] = graph['current']['name'] == 'ui_task'
        semantic = dict(role=role, code=helpers[0][3] if len(helpers) == 1 else None,
                        ui_callback_entry=checks['ui_callback_entry'], ring_report=p['report_hex'])
    passed = all(checks.values())
    result = dict(schema=2, scenario='ring-wake', case=p['case'], passed=passed,
                  execution_passed=bool(x and not errors and checks.get('fault_free')),
                  checks=checks, semantic=semantic, observed=x, errors=errors,
                  api_caller=False, natural_main_complete=False, full_ui_verified=False,
                  pixels_verified=False, gaf_calculation_supported=False,
                  physical_hardware_access=False, firmware_candidate=p.get('firmware_candidate'))
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    (destination/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
