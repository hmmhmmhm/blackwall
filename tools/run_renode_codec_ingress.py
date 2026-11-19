"""Cross-check original codec state wrappers on isolated native M55 machines."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from audit_assets import PINS
from blackwall_package import parse_bundle
from emulate_codec_ingress import PROFILES, SRAM_SIZE
from emulate_codec_callers import PROFILES as CALLERS
from emulate_codec_flow import PROFILES as FLOWS
from emulate_codec_query import PROFILES as QUERIES
from run_renode_m55_probe import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--image', default='sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new evidence directory')
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.image], timeout=15))[0]
    if image['Architecture'] != 'arm64' or image['Os'] != 'linux':
        raise ValueError('Unexpected emulator image platform')
    args.output.mkdir(mode=0o700)
    helper = Path(__file__).with_name('renode-codec-ingress.cs')
    shutil.copy2(helper, args.output / 'probe.cs')
    (args.output / 'fill.bin').write_bytes(b'\xa5' * SRAM_SIZE)
    results = {}
    for key, p in PROFILES.items():
        bundle = (args.inputs / QUERIES[key]['file']).read_bytes()
        if hashlib.sha256(bundle).hexdigest() != PINS[key]:
            raise ValueError('Bundle hash mismatch: ' + key)
        raw = next(c for c in parse_bundle(bundle) if c.type_id == 0).payload[32:]
        (args.output / (key + '.bin')).write_bytes(raw)
        board = '''cpu: CPU.CortexM @ sysbus
    cpuType: "cortex-m55"
    nvic: nvic
    PerformanceInMips: 1
nvic: IRQControllers.NVIC @ sysbus 0xe000e000
    systickFrequency: 1000000
    -> cpu@0
main: Memory.MappedMemory @ sysbus 0x438000
    size: 0x3c0000
sram: Memory.MappedMemory @ sysbus 0x20000000
    size: 0x80000
'''
        (args.output / 'board.repl').write_text(board)
        rows = []
        for state in (0, 1, 2, 255):
            runtime = f'''import clr, time, json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
from Antmicro.Renode.Core import EmulationManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallCodecIngress').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallCodecIngress
m=monitor.Machine
cpu=m['sysbus.cpu']
Console.WriteLine('BLACKWALL_STAGE before-probe')
p=BlackwallCodecIngress(m,cpu,{len(raw)},{CALLERS[key]['state']},{FLOWS[key]['entry']},{CALLERS[key]['other']},{p['init']},{CALLERS[key]['state_bytes']})
Console.WriteLine('BLACKWALL_STAGE after-probe')
e=EmulationManager.Instance.CurrentEmulation
e.StartAll()
Console.WriteLine('BLACKWALL_STAGE started')
time.sleep(0.15)
e.PauseAll()
Console.WriteLine('BLACKWALL_STAGE paused')
guard=[int(m.SystemBus.ReadByte({p['init']}-4+i)) for i in range({CALLERS[key]['state_bytes']}+8)]
Console.WriteLine('BLACKWALL_CODEC '+json.dumps(dict(state={state},boundary=str(p.Boundary),pc=int(cpu.PC.RawValue),force=int(p.Force),writes=int(p.Writes),violations=int(p.Violations),guard=guard)))
'''
            name = key + '-' + str(state)
            (args.output / (name + '.py')).write_text(runtime)
            script = f'''include @/work/probe.cs
mach create "{name}"
machine LoadPlatformDescription @/work/board.repl
sysbus LoadBinary @/work/{key}.bin 0x438000
sysbus LoadBinary @/work/fill.bin 0x20000000
sysbus WriteByte {p['state_byte']} {state}
cpu VectorTableOffset 0x438000
include @/work/{name}.py
quit
'''
            (args.output / (name + '.resc')).write_text(script)
            command = ['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--pids-limit', '128',
                       '--cpus', '1', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                       '--mount', f'type=bind,source={args.output.resolve()},target=/work,readonly', image['Id'],
                       '--disable-gui', '--hide-monitor', '-p', '/work/' + name + '.resc']
            log = execute(command, args.output, name, timeout=45)
            rows.extend(json.loads(line.removeprefix('BLACKWALL_CODEC ')) for line in log.splitlines() if line.startswith('BLACKWALL_CODEC '))
        if len(rows) != 4:
            raise ValueError('Missing native result: ' + key)
        for row in rows:
            expected = 'codec-check-entry' if row['state'] == 2 else 'other-state-path'
            if (row['boundary'] != expected or row['violations'] or row['writes'] == 0
                or row['pc'] != (FLOWS[key]['entry'] if row['state'] == 2 else CALLERS[key]['other'])
                or (row['state'] == 2 and row['force'] != 0)
                or row['guard'] != [165]*4 + [0]*CALLERS[key]['state_bytes'] + [165]*4):
                raise ValueError('Native boundary/initialization mismatch: ' + key)
        results[key] = rows
    report = dict(scope='Original state wrapper, memset and getter; stop before codec/other-state execution',
                  image_id=image['Id'], results=results, bundle_sha256=PINS,
                  sources={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__), helper)},
                  passed=True, hardware_validated=False, installable=False, full_boot_verified=False,
                  limitations=['State bytes are fixtures; no normal-boot reachability proof',
                               'Parent preparation/selector and update body are outside this native probe'])
    (args.output / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('12 native M55 state-wrapper probes passed with original memset and write monitoring')


if __name__ == '__main__':
    main()
