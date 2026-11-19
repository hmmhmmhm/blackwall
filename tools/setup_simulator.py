"""Create a new offline simulator venv from pinned local wheels. No device APIs."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
LOCK = Path(__file__).with_name('simulator-wheels.json')


def validate(wheels, output):
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Simulator environment must be outside the repository')
    if output.exists():
        raise ValueError('Output exists; preserve the current environment')
    lock_bytes = LOCK.read_bytes()
    lock = json.loads(lock_bytes)
    if platform.system().lower()+'-'+platform.machine().lower() != lock['platform'] or list(sys.version_info[:2]) != lock['python']:
        raise ValueError('This wheel set requires macOS arm64 and Python 3.14')
    for package in lock['packages']:
        path = wheels/package['wheel']
        if not path.is_file():
            raise ValueError('Missing pinned wheel: '+str(path)+'; prepare the local files listed in tools/simulator-wheels.json')
        if hashlib.sha256(path.read_bytes()).hexdigest() != package['sha256']:
            raise ValueError('Wheel SHA256 mismatch: '+package['name'])
    return output, lock, hashlib.sha256(lock_bytes).hexdigest()


def setup(wheels, output):
    output, lock, lock_hash = validate(wheels, output)
    venv.EnvBuilder(with_pip=True).create(output)
    requirements = output/'simulator-requirements.lock'
    requirements.write_text(''.join(f"{p['name']}=={p['version']} --hash=sha256:{p['sha256']}\n" for p in lock['packages']))
    python = output/'bin/python'
    with (output/'install.log').open('x') as log:
        subprocess.run([str(python), '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check',
                        'install', '--no-index', '--find-links', str(wheels.resolve()),
                        '--only-binary=:all:', '--require-hashes', '-r', str(requirements)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    smoke = '''import json,sys,importlib.metadata
import unicorn,capstone
from unicorn import arm_const
cpu=unicorn.Uc(unicorn.UC_ARCH_ARM,unicorn.UC_MODE_THUMB|unicorn.UC_MODE_MCLASS)
cpu.ctl_set_cpu_model(arm_const.UC_CPU_ARM_CORTEX_M4)
print(json.dumps({"python":sys.version,"packages":{n:importlib.metadata.version(n) for n in ("unicorn","capstone")},"module_paths":{"unicorn":unicorn.__file__,"capstone":capstone.__file__}}))
'''
    installed = json.loads(subprocess.check_output([str(python), '-I', '-c', smoke], text=True))
    if installed['packages'] != {p['name']:p['version'] for p in lock['packages']}:
        raise ValueError('Installed versions differ from wheel lock')
    if not all(Path(path).resolve().is_relative_to(output) for path in installed['module_paths'].values()):
        raise ValueError('Simulator modules were loaded outside the new environment')
    report = dict(schema='blackwall-simulator-environment/1', lock_sha256=lock_hash,
                  installed=installed, wheel_directory=str(wheels.resolve()), network_install=False,
                  device_access=False, simulator_complete=False)
    with (output/'blackwall-environment.json').open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheels', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = setup(args.wheels, args.output)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Simulator setup failed: {error}\n')
    print(json.dumps(report['installed']))


if __name__ == '__main__':
    main()
