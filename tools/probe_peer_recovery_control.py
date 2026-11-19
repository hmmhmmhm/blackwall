"""Replay fixed inputs with only the three phase-stop hooks, for observer comparison."""
import argparse
import json
from pathlib import Path
import re
import shutil
from run_runtime_connection_m55 import sha,pin_capture
from verify_kv_persistence_cycle import validate_capture
from run_renode_m55_probe import execute
from native_replay import IMAGE

def minimal_observer(source):
    source,count=re.subn(r'            cpu.AddHook\((?:start|entry|send),\(c,a\)=>\{.*?\n            \}\);\n','',source,flags=re.S)
    if count!=3:raise ValueError('Unknown detailed hook blocks')
    old='if(!Entered || Returned)return;Returned=true;'
    if source.count(old)!=1:raise ValueError('Unknown callback return stop')
    source=source.replace(old,'if(Returned)return;Returned=true;')
    source,count=re.subn(r'        public void WatchCall\(CortexM cpu,uint address\)\n        \{.*?\n        \}\n        public bool Started', '        public void WatchCall(CortexM cpu,uint address) { }\n        public bool Started',source,flags=re.S)
    if count!=1 or source.count('cpu.AddHook(')!=3:raise ValueError('Unknown minimal stop observer')
    return source

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--case',choices=('stock23','cfw'),required=True);a=p.parse_args();s=a.simulator;ref=s/'peer-recovery-version-native-01'/a.case;validate_capture(ref)
    pins=json.loads((s/'peer-recovery-version-research-01/fixed-inputs.json').read_text())[a.case]
    a.output.mkdir(mode=0o700,parents=True,exist_ok=False);(a.output/'exports').mkdir(mode=0o700)
    for n,digest in pins.items():
        if sha(ref/n)!=digest:raise ValueError('Changed original recovery input')
        shutil.copyfile(ref/n,a.output/n)
    p=a.output/'renode-peer-recovery-observer.cs';p.write_text(minimal_observer(p.read_text()))
    (a.output/'observer-control.json').write_text(json.dumps(dict(case=a.case,detailed_reference=str(ref.relative_to(s)),reference_capture_sha256=sha(ref/'capture-files.json'),remaining_hooks=['timeout-return','healthy-stop','credit-return'],removed=['timer-start-detail','timeout-entry-detail','sender-buffers','six-callsite-details'],model_changes=False,firmware_changes=False,control_only=True),indent=2)+'\n')
    p=a.output/'connection-inputs.json';v=json.loads(p.read_text())
    for n in set(v)|{'observer-control.json'}:v[n]=sha(a.output/n)
    p.write_text(json.dumps(v,indent=2)+'\n')
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=360)
    pin_capture(a.output);v=json.loads((a.output/'exports/recovery-diagnostic.json').read_text());print(json.dumps(dict(case=a.case,control_only=True,phase_count=len(v['phases']),phases=[dict(name=x['name'],pc=hex(x['state']['pc'])) for x in v['phases']])))

if __name__=='__main__':main()
