#!/usr/bin/env python3
"""Create an isolated 12-second observation-window research profile."""
import hashlib
import json
from pathlib import Path

PRIVATE=Path.home()/'Library/Application Support/Blackwall'
BASE=PRIVATE/'simulator/detailed-boot-observer-bw601'
DEST=PRIVATE/'simulator/short-boot-observer-bw600'

def main():
    profile=json.loads((BASE/'profile.json').read_text())
    for name in ('strict.cs','run.py'):
        path=BASE/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=profile['components'][name]['sha256']:
            raise ValueError('Detailed profile source hash differs')
    runtime=(BASE/'run.py').read_text()
    old='TimeElapsed.Ticks)-start<20000000000'
    if runtime.count(old)!=1:raise ValueError('Unique observation threshold not found')
    runtime=runtime.replace(old,'TimeElapsed.Ticks)-start<12000000000',1)
    DEST.mkdir(parents=True,exist_ok=False)
    path=DEST/'run.py';path.write_text(runtime)
    profile['components']['run.py']={'origin':'private','path':str(path.relative_to(PRIVATE)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    profile['experiment']={'observation_window_us':12000000,'basis':'research only; explicit input window; not physical boot timing'}
    (DEST/'profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n')
    print(DEST/'profile.json')
if __name__=='__main__':main()
