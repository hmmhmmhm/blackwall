#!/usr/bin/env python3
"""Run a pinned virtual G2 scenario or audit an existing run and create a private report."""
import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tools/run_original_boot_screen.py'


def read(path):
    return json.loads(path.read_text())


def load_scenario(path):
    spec = read(path)
    if not isinstance(spec, dict) or set(spec) != {'schema', 'name', 'base', 'require_facts'}:
        raise ValueError('Scenario requires exactly schema, name, base and require_facts')
    facts = spec['require_facts']
    if spec['schema'] != 1 or not isinstance(spec['name'], str) or not spec['name'].strip() or len(spec['name']) > 120:
        raise ValueError('Invalid scenario schema or name')
    if spec['base'] not in ('normal', 'unknown-boot-marker') or not isinstance(facts, list) or not facts:
        raise ValueError('Scenario needs a supported base and at least one fact')
    if any(not isinstance(f, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,79}', f) for f in facts) or len(set(facts)) != len(facts):
        raise ValueError('Invalid or duplicate fact name')
    return spec


def build(capture, audit, dest, custom=None):
    result = read(audit / 'report.json')
    if result.get('schema') != 2 or result.get('scenario') not in ('normal', 'unknown-boot-marker'):
        raise ValueError('Unsupported audit schema or scenario')
    observed = result['observed']
    exports = capture / 'exports'
    wire = read(exports / 'wire-activation.json') if (exports / 'wire-activation.json').exists() else {}
    replies = [dict(time_us=x['before']['ticks'] // 1000, direction='RX', data=' '.join(f'{v:02X}' for v in x['data']), channel='UART0', accepted=x['accepted']) for x in wire.get('replies', [])]
    requests = [dict(direction='TX', data=' '.join(f'{v:02X}' for v in x['data']), channel=f"UART0 / ch{x['channel']}", identifier=x['identifier']) for x in wire.get('requests', [])]
    points = [dict(name=x['label'], pc=x['pc'], sequence=x['sequence'], **({'time_us': x['ticks'] // 1000} if 'ticks' in x else {})) for x in observed.get('events', [])]
    timed_points = [x.get('time_us') for x in points]
    if any(x is not None for x in timed_points):
        if any(type(x) is not int or x < 0 for x in timed_points) or timed_points != sorted(timed_points) or timed_points[-1] > observed.get('virtual_ticks', 0) // 1000:
            raise ValueError('Invalid observer timestamp ordering')
    history = []
    manifest = exports/'observed-frames.json'
    if manifest.exists():
        integrity=['profile_pin','component_pins','component_contract','host_source_pins','no_forced_guest_state','assets_still_pinned','launcher_contract','execution_exit_zero','retained_artifact_pins','native_log_records_match']
        if not all(result.get('facts',{}).get(k) is True for k in integrity):
            raise ValueError('Frame history requires verified capture integrity')
        saved = read(manifest)
        if saved['dropped'] != 0: raise ValueError('Frame history overflow')
        if len(saved['frames']) != read(exports/'screen.json')['captures']: raise ValueError('Frame capture count differs')
        pins = read(capture/'artifacts.json')
        for i, frame in enumerate(saved['frames']):
            name=frame['file']
            if name != f'observed-frame-{i:02d}.bin': raise ValueError('Unexpected frame filename')
            path=exports/name; raw=path.read_bytes()
            if len(raw)!=576*288 or hashlib.sha256(raw).hexdigest()!=pins.get('exports/'+name): raise ValueError('Frame hash or dimensions mismatch')
            ticks=frame['ticks']
            if type(ticks) is not int or ticks<0 or ticks>observed.get('virtual_ticks',0): raise ValueError('Invalid frame timestamp')
            if history and ticks<history[-1]['ticks']: raise ValueError('Frame timestamps out of order')
            history.append(dict(ticks=ticks, raw=raw))
        if history and history[-1]['raw'] != (exports/'complete-screen.bin').read_bytes(): raise ValueError('Last observed frame differs from final verified frame')
    timed = []
    touch = wire.get('touch', {})
    if touch.get('accepted') and 'ticks' in touch.get('before', {}):
        timed.append(dict(time_us=touch['before']['ticks'] // 1000, text='[INPUT] Touch accepted'))
    cadence = wire.get('cadence', {})
    if cadence.get('before', {}).get('registers', [None]*16)[15] == 0x4456e8:
        timed.append(dict(time_us=cadence['before']['ticks'] // 1000, text='[UI] Dispatch observer checkpoint'))
    # UART timestamps exist only on the opt-in detailed observation profile.
    firmware_events=[]; uart_tx=[]; trace_quality=[]
    diagnostic=exports/'retry-diagnostic.json'
    if diagnostic.exists():
        diagnostics=read(diagnostic)
        for port in diagnostics.get('uarts',[]):
            raw=port.get('tx',[]); ticks=port.get('ticks',[]); module=port.get('module')
            if module==1 and ticks:
                if len(raw)!=len(ticks) or any(type(t) is not int or t<0 or t>observed.get('virtual_ticks',0) for t in ticks) or ticks!=sorted(ticks):
                    raise ValueError('Invalid UART1 timestamp capture')
                trace_quality.append(dict(source='UART1',captured=len(raw),dropped=port.get('dropped',0)))
                start=0
                for i,byte in enumerate(raw):
                    if byte!=10: continue
                    line=bytes(raw[start:i+1]).decode('utf-8','replace');start=i+1
                    line=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', line)
                    line=''.join(ch for ch in line if ch=='\t' or ord(ch)>=32).strip()
                    if line: firmware_events.append(dict(time_us=ticks[i]//1000,text=line[:512]))
                if start<len(raw):
                    line=bytes(raw[start:]).decode('utf-8','replace')
                    line=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', line)
                    line=''.join(ch for ch in line if ch=='\t' or ord(ch)>=32).strip()
                    if line: firmware_events.append(dict(time_us=ticks[-1]//1000,text=line[:512]+' [partial]'))
            if module==0:
                tx=port.get('transfers',[])
                tx_ticks=[x['ticks'] for x in tx]
                if any(type(t) is not int or t<0 or t>observed.get('virtual_ticks',0) for t in tx_ticks) or tx_ticks!=sorted(tx_ticks):
                    raise ValueError('Invalid UART0 transfer timestamps')
                uart_tx=[dict(time_us=x['ticks']//1000,data=' '.join(f'{v:02X}' for v in x['data'])) for x in tx]
                if tx:
                    dma_bytes=[v for item in tx for v in item['data']]
                    trace_quality.append(dict(source='UART0 DMA',captured=len(tx),raw_bytes=len(raw),dma_bytes=len(dma_bytes),matches_raw=dma_bytes==raw,dropped=port.get('dropped',0)))
    initial=wire.get('initial_observation')
    if initial:
        start=initial.get('start_ticks');stop=initial.get('stop_ticks');reason=initial.get('reason')
        if type(start) is not int or type(stop) is not int or not 0<=start<=stop<=observed.get('virtual_ticks',0) or reason not in ('halted','machine-paused','first-frame','host-limit','virtual-limit'):
            raise ValueError('Invalid initial observation record')
        if wire.get('touch',{}).get('accepted') and wire['touch']['before']['ticks']!=stop:
            raise ValueError('Initial pause and touch witness differ')
        if reason=='virtual-limit':
            metadata=read(capture/'manifest.json')['profile']
            target_us=metadata.get('experiment',{}).get('observation_window_us',metadata['budgets']['initial_virtual_ms']*1000)
            if stop-start<target_us*1000: raise ValueError('Initial window ended before its limit')
            timed.append(dict(time_us=stop//1000,text=f'[RUNNER] {target_us/1e6:g}s initial observation window reached; virtual input follows'))
    if uart_tx:
        captured={(entry['time_us'],entry['data']) for entry in uart_tx}
        for request in wire.get('requests',[]):
            if 'ticks' in request:
                pair=(request['ticks']//1000,' '.join(f'{v:02X}' for v in request['data']))
                if pair not in captured: raise ValueError('UART0 request missing from transfer trace')
    device_events=[]
    state_path=exports/'main-input-state.json'
    if state_path.exists():
        imu=read(state_path).get('imu',{})
        tick=imu.get('TriggeredAt')
        if type(tick) is int and tick>0 and imu.get('Triggers',0)>0:
            if tick>observed.get('virtual_ticks',0): raise ValueError('IMU trigger outside capture')
            device_events.append(dict(time_us=tick//1000,device='IMU',text='[IMU] Modeled service trigger (not sensor data)'))
    checks = list(result.get('semantic_validation', {}).get('checks', []))
    if custom is not None:
        if result['scenario'] != custom['base']:
            raise ValueError('Scenario base differs from capture')
        checks.extend(dict(name='custom: '+name, passed=result.get('facts', {}).get(name) is True) for name in custom['require_facts'])
    model = dict(scenario=custom['name'] if custom else result['scenario'], passed=result.get('passed') is True and all(c.get('passed') is True for c in checks),
        execution_passed=result.get('execution_passed') is True, boundary=result['boundary_kind'],
        virtual_us=observed.get('virtual_ticks', 0) // 1000, points=points, replies=replies, requests=requests, timed=timed,
        checks=checks, device_events=device_events, failure=wire.get('error'), firmware_events=firmware_events, uart_tx=uart_tx, trace_quality=trace_quality, identity=result.get('identity', {}),
        limitations=result.get('semantic_validation', {}).get('unresolved_differences', []),
        screen=(exports/'complete-screen.png').exists(), enhanced=(exports/'contrast-preview.png').exists(), screenshot='screen.png', frames=[dict(time_us=f['ticks']//1000,raw=f'frame-{i:02d}.png',enhanced=f'frame-{i:02d}-enhanced.png') for i,f in enumerate(history)])
    write_report(model, dest, exports/'complete-screen.png' if model['screen'] else None, exports/'contrast-preview.png' if model['enhanced'] else None)
    if history:
        peak=max(max(frame['raw']) for frame in history) or 1
        for i, frame in enumerate(history):
            save_frame(dest/f'frame-{i:02d}.png', frame['raw'])
            save_frame(dest/f'frame-{i:02d}-enhanced.png', bytes(v*255//peak for v in frame['raw']))
    return model


def save_frame(path, raw):
    def chunk(tag, data): return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    data=b''.join(b'\0'+raw[y*576:(y+1)*576] for y in range(288))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',576,288,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(data))+chunk(b'IEND',b''))


def isolate_observed_soc(source, dest):
    """Give the approximate FCC sample's AP510 package its own render material."""
    blob=source.read_bytes()
    magic,version,total=struct.unpack_from('<4sII',blob)
    if magic!=b'glTF' or version!=2 or total!=len(blob): raise ValueError('Unexpected board model')
    json_size,json_type=struct.unpack_from('<II',blob,12)
    if json_type!=0x4e4f534a: raise ValueError('Missing GLB JSON')
    model=json.loads(blob[20:20+json_size]); rest=blob[20+json_size:]
    for node_name,material_name in [('AP510BFA package','Blackwall observed SoC'),('U25643 package','Blackwall observed NOR'),('CY8C40 package','Blackwall observed Touch'),('Reverse upper middle package','Blackwall illustrative BLE'),('Reverse compact lower package','Blackwall illustrative IMU'),('Centre horizontal socket','Blackwall illustrative Display')]:
        nodes=[x for x in model['nodes'] if x.get('name')==node_name]
        if len(nodes)!=1: raise ValueError('Expected one '+node_name)
        primitives=model['meshes'][nodes[0]['mesh']]['primitives']
        if not primitives: raise ValueError('Empty component mesh')
        material=copy.deepcopy(model['materials'][primitives[0]['material']])
        material['name']=material_name
        material['emissiveFactor']=[0,0,0]
        primitives[0]['material']=len(model['materials']); model['materials'].append(material)
    encoded=json.dumps(model,separators=(',',':')).encode(); encoded+=b' '*((-len(encoded))%4)
    dest.write_bytes(struct.pack('<4sII',b'glTF',2,20+len(encoded)+len(rest))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+rest)


def write_report(model, dest, screen=None, enhanced=None):
    dest.mkdir(parents=True, exist_ok=False)
    template = ROOT / 'web/prototypes'
    for name in ('workbench.css', 'icons.svg'):
        shutil.copy2(template/name, dest/name)
    model_dir = dest/'board-model-bw590'
    model_dir.mkdir()
    for name in ('g2-temple-assembly.glb', 'g2-temple-board.glb'):
        isolate_observed_soc(template/'board-model-bw590'/name, model_dir/name)
    shutil.copy2(ROOT/'web/report/report.js', dest/'report.js')
    shutil.copy2(ROOT/'web/report/report.css', dest/'report.css')
    (dest/'index.html').write_text((ROOT/'web/report/report.html').read_text())
    if screen:
        shutil.copy2(screen, dest/'screen.png')
    if enhanced:
        shutil.copy2(enhanced, dest/'screen-enhanced.png')
    (dest/'report-data.js').write_text('window.BLACKWALL_REPORT = '+json.dumps(model, ensure_ascii=True).replace('<', '\\u003c')+';\n')


def host_failure(dest, scenario, stage, message):
    model = dict(scenario=scenario, passed=False, execution_passed=False, boundary='host-error',
        virtual_us=0, points=[], replies=[], requests=[], timed=[], device_events=[], firmware_events=[], uart_tx=[], trace_quality=[], failure=message, checks=[dict(name=stage+': '+message, passed=False)],
        identity={}, limitations=['No guest execution result was verified.'], screen=False, enhanced=False, frames=[], screenshot='screen.png')
    write_report(model, dest)
    print(json.dumps({'report': str(dest/'index.html'), 'passed': False, 'stage': stage}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=['normal', 'unknown-boot-marker'], default='normal')
    parser.add_argument('--scenario-file', type=Path, help='Custom JSON assertions')
    parser.add_argument('--profile', type=Path, help='Explicit pinned emulator profile')
    parser.add_argument('--capture', type=Path, help='Existing private capture to independently audit (no rerun)')
    parser.add_argument('--output', type=Path, required=True, help='New private output directory')
    parser.add_argument('--workspace', type=Path, required=True, help='Private run workspace')
    parser.add_argument('--boot-image', type=Path)
    parser.add_argument('--main-image', type=Path)
    args = parser.parse_args()
    try:
        custom = load_scenario(args.scenario_file) if args.scenario_file else None
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    if custom and args.capture:
        parser.error('--scenario-file requires a new run')
    if custom:
        args.scenario = custom['base']
    workspace = args.workspace.resolve()
    base = args.output.resolve()
    if base.exists() or not base.is_relative_to(workspace) or base.is_relative_to(ROOT):
        parser.error('Output must be a new directory inside the private Blackwall directory')
    base.mkdir(parents=True)
    capture = args.capture.resolve() if args.capture else base/'capture'
    if not args.capture:
        command = [sys.executable, '-B', str(RUNNER), '--scenario', args.scenario, '--private-root', str(workspace), '--output', str(capture)]
        if args.profile: command += ['--profile', str(args.profile)]
        for opt in ('boot_image', 'main_image'):
            if getattr(args, opt): command += ['--'+opt.replace('_','-'), str(getattr(args,opt))]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if completed.returncode and not (capture.parent/(capture.name+'-audit')/'report.json').exists():
            (base/'execution-error.log').write_text(completed.stdout + completed.stderr)
            host_failure(base/'report', args.scenario, 'execution', 'Runner failed; see private execution-error.log')
            return completed.returncode
    audit = base/'audit'
    completed = subprocess.run([sys.executable, '-B', str(RUNNER), '--audit-existing', str(capture), '--audit-output', str(audit)], cwd=ROOT)
    if not (audit/'report.json').exists():
        host_failure(base/'report', args.scenario, 'audit', 'Audit unavailable; inspect private audit output')
        return 1
    result = build(capture, audit, base/'report', custom)
    print(json.dumps({'report': str(base/'report/index.html'), 'passed': result['passed'], 'scenario': result['scenario']}))
    return 0 if result['passed'] and completed.returncode == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
