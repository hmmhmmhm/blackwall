"""Build and execute an isolated M55/MVE/exception probe; no glasses or stock firmware access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

FIXTURES = Path(__file__).resolve().parents[1]/'tests/fixtures'


def execute(command, directory, name, timeout=45, stream=False):
    journal = None
    ownership = []
    if command[:2] == ['docker', 'run']:
        from native_process_recovery import create_job, finish_job, TOKEN_LABEL, DIRECTORY_LABEL
        journal, job = create_job(directory, name)
        ownership = ['--name', job['container'], '--label', TOKEN_LABEL + '=' + job['token'],
                     '--label', DIRECTORY_LABEL + '=' + job['directory']]
    console = '--console' in command
    interactive = ['--interactive'] if console and '--interactive' not in command and '-i' not in command else []
    actual_command = command[:2]+ownership+interactive+command[2:] if journal else command
    # Keep redirected console input open without sending bytes or triggering an EOF loop.
    console_read, console_write = os.pipe() if console else (None, None)
    try:
        if stream:
            with (directory/(name+'.log')).open('w') as log:
                result = subprocess.run(actual_command, stdin=console_read, stdout=log,
                                        stderr=subprocess.STDOUT, text=True, timeout=timeout)
        else:
            result = subprocess.run(actual_command, stdin=console_read, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b''
        stderr = error.stderr or b''
        if not stream:
            (directory/(name+'.log')).write_text(
                (stdout.decode(errors='replace') if isinstance(stdout,bytes) else stdout)+
                (stderr.decode(errors='replace') if isinstance(stderr,bytes) else stderr))
        raise
    finally:
        try:
            if journal:
                finish_job(journal)
        finally:
            if console_read is not None:
                os.close(console_read)
                os.close(console_write)
    output = (directory/(name+'.log')).read_text() if stream else result.stdout+result.stderr
    if not stream:
        (directory/(name+'.log')).write_text(output)
    if result.returncode:
        raise RuntimeError(f'{name} failed ({result.returncode}); inspect saved log')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--image', default='blackwall-renode:1.17.0-local')
    parser.add_argument('--clang', default='/opt/homebrew/opt/llvm@21/bin/clang')
    parser.add_argument('--lld', default='/opt/homebrew/opt/lld@21/bin/ld.lld')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Use a new output directory to preserve previous evidence')
    inspect = subprocess.run(['docker', 'image', 'inspect', args.image], capture_output=True,
                             text=True, check=True, timeout=15)
    image = json.loads(inspect.stdout)[0]
    if image['Architecture'] != 'arm64' or image['Os'] != 'linux':
        raise ValueError('This probe requires the reviewed Linux arm64 image')
    image_id = image['Id']
    output.mkdir(mode=0o700)
    for name in ('m55-exceptions-smoke.c', 'm55-exceptions-smoke.ld', 'm55-minimal.repl'):
        shutil.copy2(FIXTURES/name, output/name)
    compiler = [args.clang, '--target=arm-none-eabi', '-mcpu=cortex-m55', '-mthumb',
                '-mfloat-abi=hard', '-O1', '-ffreestanding', '-fno-builtin', '-nostdlib',
                '-fuse-ld='+args.lld, '-Wl,-T,'+str(output/'m55-exceptions-smoke.ld'),
                str(output/'m55-exceptions-smoke.c'), '-o', str(output/'smoke.elf')]
    execute(compiler, output, 'compiler')
    disassembly = execute([str(Path(args.clang).parent/'llvm-objdump'), '-d',
                           str(output/'smoke.elf')], output, 'disassembly')
    if 'vdup.32' not in disassembly or 'vadd.i32' not in disassembly:
        raise ValueError('Expected MVE instructions absent from compiled probe')
    version_command = ['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--pids-limit', '128',
                       '--cpus', '1', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', image_id]
    version = execute(version_command+['--version'], output, 'version')
    if 'Renode v1.17.0' not in version:
        raise ValueError('Unreviewed Renode version')
    cases = {}
    for cpu in ('cortex-m55', 'cortex-m4f'):
        platform = (output/'m55-minimal.repl').read_text().replace('"cortex-m55"', '"'+cpu+'"')
        (output/(cpu+'.repl')).write_text(platform)
        script = f'mach create "blackwall-{cpu}-probe"\nmachine LoadPlatformDescription @/work/{cpu}.repl\n'
        script += 'sysbus LoadELF @/work/smoke.elf\nemulation RunFor "00:00:00.010"\n'
        (output/(cpu+'-result.py')).write_text('from System import Console\n'
            'm = monitor.Machine\nfor i in range(16):\n'
            '    Console.WriteLine("0x{0:08X}".format(int(m.SystemBus.ReadDoubleWord(0x20000000+4*i))))\n')
        script += 'include @/work/'+cpu+'-result.py\nquit\n'
        (output/(cpu+'.resc')).write_text(script)
        command = version_command[:-1]+['--mount', f'type=bind,source={output},target=/work,readonly',
                                       image_id, '--disable-gui', '--hide-monitor', '-p', '/work/'+cpu+'.resc']
        log = execute(command, output, cpu)
        words = [int(value, 16) for value in re.findall(r'^0x([0-9a-fA-F]{8})\s*$', log, re.MULTILINE)]
        if len(words) != 16:
            raise ValueError(f'Missing or ambiguous mailbox in {cpu} output')
        if cpu == 'cortex-m55':
            passed = words == [0x600d, 11, 14, 16, 3, 15, 14, 0, 0x10000, 5, 0, 4, 44, 1, 1, 0]
        else:
            passed = words[:7] == [0]*7 and words[7] in (3, 6) and words[8:] == [0]*8
        cases[cpu] = {'mailbox': words, 'expected_behavior_observed': passed, 'command': command}
    report = {'scope': 'synthetic MVE, SVC, PendSV, NVIC IRQ0/IRQ28 pending-clear/delivery, SysTick and MPU enable/disable control only',
              'image_id': image_id, 'version': version.strip(), 'compiler_command': compiler,
              'elf_sha256': hashlib.sha256((output/'smoke.elf').read_bytes()).hexdigest(),
              'cases': cases, 'passed': all(c['expected_behavior_observed'] for c in cases.values()),
              'apollo510_peripherals_verified': False, 'stock_firmware_boot_verified': False,
              'hardware_validated': False, 'installable': False}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': report['passed'], 'mailboxes': {k:v['mailbox'] for k,v in cases.items()}}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
