"""Recover only a journaled, owned Docker job after its local worker has stopped."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import uuid

TOKEN_LABEL = 'io.blackwall.run-token'
DIRECTORY_LABEL = 'io.blackwall.run-directory'
PREFIX = 'blackwall-m55-probe-'


class RecoveryError(RuntimeError):
    pass


def write_job(path, job):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(job, indent=2) + '\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def create_job(directory, name):
    directory = directory.resolve()
    if Path(name).name != name:
        raise RecoveryError('Job name must remain inside its output directory')
    token = uuid.uuid4().hex
    path = directory / (name + '.process.json')
    if path.exists():
        path = directory / (name + '.process-' + token + '.json')
    job = dict(schema=1, directory=str(directory), token=token, container=PREFIX + token,
               owner_pid=os.getpid(), owner_host=platform.node(), status='prepared')
    write_job(path, job)
    return path, job


def validate_job(path, job):
    required = {'schema', 'directory', 'token', 'container', 'owner_pid', 'owner_host', 'status'}
    if (not isinstance(job, dict) or not required <= set(job)
            or set(job) - required - {'container_id', 'last_error'}
            or type(job['schema']) is not int or job['schema'] != 1
            or not isinstance(job['token'], str) or not re.fullmatch('[0-9a-f]{32}', job['token'])
            or job['container'] != PREFIX + job['token']
            or type(job['owner_pid']) is not int or job['owner_pid'] <= 0
            or job['status'] not in ('prepared', 'removed', 'cleanup-failed')):
        raise RecoveryError('Unsupported native process journal')
    if job['owner_host'] != platform.node():
        raise RecoveryError('Journal belongs to another host')
    if job['directory'] != str(path.resolve().parent):
        raise RecoveryError('Journal directory differs from its recorded owner')


def owner_is_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def docker(arguments):
    return subprocess.run(['docker', *arguments], capture_output=True, text=True, timeout=15)


def absent(result):
    return result.returncode != 0 and any(message in result.stderr
        for message in ('No such container', 'No such object'))


def cleanup(path, require_dead_owner):
    path = Path(path)
    job = json.loads(path.read_text())
    validate_job(path, job)
    if require_dead_owner and job['status'] != 'removed' and owner_is_alive(job['owner_pid']):
        raise RecoveryError('Owner process is still running; stop its job before recovery')
    try:
        inspected = docker(['container', 'inspect', job['container']])
        already_absent = absent(inspected)
        if not already_absent:
            if inspected.returncode:
                raise RecoveryError('Could not inspect task container: ' + inspected.stderr)
            entries = json.loads(inspected.stdout)
            if not isinstance(entries, list) or len(entries) != 1:
                raise RecoveryError('Ambiguous task container identity')
            entry = entries[0]
            labels = entry.get('Config', {}).get('Labels') or {}
            identity = entry.get('Id', '')
            if (entry.get('Name') != '/' + job['container']
                    or labels.get(TOKEN_LABEL) != job['token']
                    or labels.get(DIRECTORY_LABEL) != job['directory']
                    or not re.fullmatch('[0-9a-f]{64}', identity)):
                raise RecoveryError('Container ownership differs; refusing removal')
            if require_dead_owner and owner_is_alive(job['owner_pid']):
                raise RecoveryError('Owner process is still running; refusing removal')
            # The inspected immutable ID prevents removal of a reused name.
            removed = docker(['rm', '--force', identity])
            if removed.returncode and not absent(removed):
                raise RecoveryError('Could not remove task container: ' + removed.stderr)
            job['container_id'] = identity
        if job['status'] != 'removed':
            job['status'] = 'removed'
            job.pop('last_error', None)
            write_job(path, job)
        return dict(removed=True, already_absent=already_absent, container=job['container'])
    except (RecoveryError, OSError, ValueError, subprocess.SubprocessError) as error:
        job.update(status='cleanup-failed', last_error=str(error))
        write_job(path, job)
        raise


def finish_job(path):
    return cleanup(path, require_dead_owner=False)


def recover(path):
    return cleanup(path, require_dead_owner=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('journal', type=Path)
    args = parser.parse_args()
    try:
        result = recover(args.journal)
    except (RecoveryError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
