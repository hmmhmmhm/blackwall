"""Known host prerequisites and actionable CLI errors; no downloads or devices."""
import importlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys

TOOLS = Path(__file__).resolve().parent
LLVM = {name: Path(path) for name, path in {
    'clang': '/opt/homebrew/opt/llvm@21/bin/clang',
    'lld': '/opt/homebrew/opt/lld@21/bin/ld.lld',
    'objcopy': '/opt/homebrew/opt/llvm@21/bin/llvm-objcopy'}.items()}


class ReadinessError(RuntimeError):
    pass


def python_packages():
    lock = json.loads((TOOLS / 'simulator-wheels.json').read_text())
    versions = {}
    for package in lock['packages']:
        name = package['name']
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            raise ReadinessError('Missing simulator Python package: ' + name
                + '\nUse the simulator venv or create one with tools/setup_simulator.py --wheels <pinned-wheel-directory> --output <new-private-venv>') from None
        if actual != package['version']:
            raise ReadinessError('Simulator Python version differs: ' + name + '=' + actual
                + '; expected ' + package['version'] + '. Use tools/setup_simulator.py with the pinned wheel set.')
        try:
            importlib.import_module(name)
        except (ImportError, OSError) as error:
            raise ReadinessError('Simulator Python package failed to load: ' + name + ': ' + str(error)
                + '\nRecreate the supported environment with tools/setup_simulator.py.') from error
        versions[name] = actual
    return versions


def native_tools(compiler=False):
    if not shutil.which('docker'):
        raise ReadinessError('Missing simulator executable: docker. See docs/architecture/renode-m55-probe.md.')
    if compiler:
        for name, path in LLVM.items():
            if not path.is_file():
                raise ReadinessError('Missing simulator executable: ' + str(path)
                    + '. The display caller needs LLVM/LLD 21; see docs/architecture/renode-m55-probe.md.')
    from native_replay import IMAGE
    result = subprocess.run(['docker', 'image', 'inspect', IMAGE], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ReadinessError('Pinned Renode image unavailable: ' + IMAGE + '\n' + result.stderr.strip()
            + '\nRestore the verified image; see docs/architecture/renode-m55-probe.md. No image was pulled.')
    entries = json.loads(result.stdout)
    if (len(entries) != 1 or entries[0]['Id'] != IMAGE
            or entries[0]['Architecture'] != 'arm64' or entries[0]['Os'] != 'linux'):
        raise ReadinessError('Pinned Renode image identity/platform differs')


def run_cli(main):
    try:
        return main()
    except ReadinessError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except FileNotFoundError as error:
        if error.filename is None:
            raise
        source = Path(error.filename).resolve().is_relative_to(TOOLS)
        guidance = ('Restore the matching project source checkout.' if source else
            'Restore verified private inputs with tools/restore_simulator_workspace.py.')
        print('Missing simulator asset: ' + str(error.filename) + '\n' + guidance
              + ' See docs/getting-started/fresh-simulator-workspace.md.', file=sys.stderr)
        raise SystemExit(2) from None
