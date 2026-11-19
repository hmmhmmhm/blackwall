#!/usr/bin/env python3
"""Derive a profile exporting existing IMU service timestamp fields."""
import hashlib
import json
from pathlib import Path

PRIVATE=Path.home()/'Library/Application Support/Blackwall'
BASE=PRIVATE/'simulator/detailed-boot-observer-bw601'
DEST=PRIVATE/'simulator/imu-observation-bw604'

def main():
    profile=json.loads((BASE/'profile.json').read_text())
    source=(BASE/'run.py').read_bytes()
    if hashlib.sha256(source).hexdigest()!=profile['components']['run.py']['sha256']:raise ValueError('Pinned runtime differs')
    runtime=source.decode()
    old="['Phase','CompletedServices','Pending','Requests','Triggers','CompletedCalculations','LastReject']"
    new="['Phase','CompletedServices','Pending','Requests','Triggers','CompletedCalculations','LastReject','RequestedAt','TriggeredAt']"
    if runtime.count(old)!=1:raise ValueError('IMU export anchor differs')
    runtime=runtime.replace(old,new,1)
    DEST.mkdir(parents=True,exist_ok=False)
    path=DEST/'run.py';path.write_text(runtime)
    profile['components']['run.py']={'origin':'private','path':str(path.relative_to(PRIVATE)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (DEST/'profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n')
    print(DEST/'profile.json')
if __name__=='__main__':main()
