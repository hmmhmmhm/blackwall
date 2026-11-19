"""Verify MRS/MSR stack register roundtrips on the pinned M55, without G2 code."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from native_replay import IMAGE
from run_renode_m55_probe import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise ValueError('Preserve prior probe outputs')
    out.mkdir(parents=True, mode=0o700)
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures'
    for name in ['m55-stack-limits.c', 'm55-exceptions-smoke.ld', 'm55-minimal.repl']:
        shutil.copyfile(fixtures / name, out / name)
    shutil.copyfile(__file__, out / 'runner-source.py')
    clang = Path('/opt/homebrew/opt/llvm@21/bin/clang')
    execute([str(clang), '--target=arm-none-eabi', '-mcpu=cortex-m55', '-mthumb',
             '-O1', '-ffreestanding', '-fno-builtin', '-nostdlib',
             '-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld',
             '-Wl,-T,' + str(out / 'm55-exceptions-smoke.ld'),
             str(out / 'm55-stack-limits.c'), '-o', str(out / 'probe.elf')], out, 'compiler')
    execute([str(clang.parent / 'llvm-objdump'), '-d', str(out / 'probe.elf')], out, 'disassembly')
    (out / 'query.py').write_text("import json\nfrom System import Console\nm=monitor.Machine\nConsole.WriteLine('STACK_LIMIT_MAIL '+json.dumps([int(m.SystemBus.ReadDoubleWord(0x20000000+4*i)) for i in range(16)]))\n")
    (out / 'probe.resc').write_text('mach create "stack-limit-probe"\nmachine LoadPlatformDescription @/work/m55-minimal.repl\nsysbus LoadELF @/work/probe.elf\nemulation RunFor "00:00:00.001"\ninclude @/work/query.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m',
                   '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL',
                   '--security-opt', 'no-new-privileges', '--mount',
                   f'type=bind,source={out},target=/work,readonly', IMAGE,
                   '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], out, 'renode', timeout=None)
    rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines()
            if line.startswith('STACK_LIMIT_MAIL ')]
    if len(rows) != 1:
        raise ValueError('Missing unique native mailbox')
    words = rows[0]
    checks = dict(completed=words[0] == 0x600d, no_fault=words[15] == 0,
                  psplim_roundtrip=words[5] == 0x20002000,
                  msplim_roundtrip=words[6] == 0x20001000,
                  psp_roundtrip=words[7] == 0x20008000,
                  psplim_restored=words[8] == words[1],
                  msplim_restored=words[9] == words[2],
                  psp_restored=words[10] == words[3])
    report = dict(passed=all(checks.values()), checks=checks, mailbox=words,
                  image_id=IMAGE, hardware_accessed=False, g2_firmware_executed=False,
                  files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()})
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['checks']))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
