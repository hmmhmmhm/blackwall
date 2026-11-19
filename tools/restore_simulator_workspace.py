"""Restore only hash-pinned private simulator assets into a fresh, non-Git root."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

RESERVED = {'blackwall-workspace.json', 'blackwall-workspace.lock.json'}


def restore(index, source, output):
    source, output = source.resolve(), output.resolve()
    if output.exists():
        raise ValueError('Output exists; preserve the current workspace')
    if any((parent / '.git').exists() for parent in [output, *output.parents]):
        raise ValueError('Private workspace must remain outside Git')
    if output.is_relative_to(source):
        raise ValueError('Workspace output must be outside its source')
    raw = index.read_bytes()
    lock = json.loads(raw)
    if (not isinstance(lock, dict) or set(lock) != {'schema', 'files'}
            or lock['schema'] != 'blackwall-simulator-workspace/1'
            or not isinstance(lock['files'], dict) or not lock['files']):
        raise ValueError('Unsupported workspace index')
    for name, item in lock['files'].items():
        relative = Path(name)
        path = source / relative
        if (relative.is_absolute() or '..' in relative.parts or not relative.parts
                or relative.as_posix() != name or relative.parts[0] in RESERVED
                or not path.resolve().is_relative_to(source)):
            raise ValueError('Workspace path escapes or is reserved: ' + name)
        if (not isinstance(item, dict) or set(item) != {'bytes', 'sha256'}
                or type(item['bytes']) is not int or item['bytes'] < 0
                or not isinstance(item['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
            raise ValueError('Invalid workspace asset metadata: ' + name)
        if not path.is_file():
            raise ValueError('Missing workspace asset: ' + name)
        data = path.read_bytes()
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Workspace asset hash differs: ' + name)
    # Validate the full input set before creating any output.
    output.mkdir(mode=0o700, parents=True)
    for name, item in lock['files'].items():
        destination = output / name
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(source / name, destination)
        destination.chmod(0o600)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Restored workspace asset hash differs: ' + name)
    (output / 'blackwall-workspace.lock.json').write_bytes(raw)
    report = dict(passed=True, schema=lock['schema'], index_sha256=hashlib.sha256(raw).hexdigest(),
                  files=len(lock['files']), bytes=sum(item['bytes'] for item in lock['files'].values()),
                  source=str(source), network_access=False, hardware_accessed=False)
    (output / 'blackwall-workspace.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('index', 'source', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        result = restore(args.index, args.source, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
