"""Keep optional Docker resource sampling separate from native job lifecycle."""
import json
import subprocess
import time


def sample_resources(container):
    row = dict(at=time.time(), container=container, stats=[])
    try:
        result = subprocess.run(
            ['docker', 'stats', '--no-stream', '--format', '{{json .}}', container],
            capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return dict(row, exit_code=124, error='resource-sample-timeout')
    except OSError as error:
        return dict(row, exit_code=127, error=type(error).__name__)
    if result.returncode:
        return dict(row, exit_code=result.returncode, error='resource-sample-command-failed')
    try:
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        if not rows or any(not isinstance(item, dict) or item.get('Name') != container for item in rows):
            raise ValueError('Unexpected resource sample owner')
    except (ValueError, TypeError):
        return dict(row, exit_code=65, error='invalid-resource-sample')
    return dict(row, exit_code=0, stats=rows)
