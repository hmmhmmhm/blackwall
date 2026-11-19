"""Interleaved original stock24 fixed500ms runs, changing only the memory policy."""
import argparse,hashlib,json,shutil,subprocess,time
from pathlib import Path
from reset_restart_profiles import RENODE_IMAGE
from run_renode_m55_probe import execute
from verify_observer_suspension import validate

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--pairs',type=int,default=1);a=p.parse_args();s=a.simulator;o=a.output
 if not 1<=a.pairs<=5 or o.exists() or not o.resolve().is_relative_to(s.resolve()) or shutil.disk_usage(s).free<1024**3:raise ValueError('Fresh private output, 1 GiB free and 1..5 pairs required')
 ref=s/'observer-suspension-native-02/scoped';validate(ref)
 old=(s/'reset-memory-protection-research-01/baseline-memory-policy.cs').read_bytes();model=(ref/'strict.cs').read_bytes()
 if hashlib.sha256(old).hexdigest()!='330182ef865a41085daf853a2e5a8678049db8dd4fe2314fb3fe851939880d29' or model.count(old)!=1:raise ValueError('Changed original policy source')
 r=s/'main-read-routing-research-01';policies={n:(r/(n+'-memory-policy.cs')).read_bytes() for n in ('baseline','candidate')}
 if hashlib.sha256(policies['baseline']).hexdigest()!='29daafce028464c94a217260df7cc0016617b8be3c158498b4dced63b6837c5e' or hashlib.sha256(policies['candidate']).hexdigest()!='312cdbff50e8cca28fb5b3bf8e698eceb50096f3f91427796f205218b3a4d4f4':raise ValueError('Changed comparison policies')
 o.mkdir(mode=0o700,parents=True);rows=[]
 for pair in range(1,a.pairs+1):
  for mode in ('baseline','candidate'):
   cap=o/(str(pair).zfill(2)+'-'+mode);cap.mkdir();(cap/'exports').mkdir();inputs=json.loads((ref/'connection-inputs.json').read_text());started=time.monotonic()
   for n in inputs:
    src=ref/n;dst=cap/n
    if subprocess.run(['cp','-c',str(src),str(dst)],capture_output=True).returncode:shutil.copyfile(src,dst)
   (cap/'strict.cs').write_bytes(model.replace(old,policies[mode],1))
   profile=json.loads((cap/'connection-profile.json').read_text());profile['model_sha256']=sha(cap/'strict.cs');(cap/'connection-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
   metadata=dict(mode=mode,policy_sha256=hashlib.sha256(policies[mode]).hexdigest(),reference=str(ref.relative_to(s)),reference_manifest_sha256=sha(ref/'capture-files.json'),requested_ms=500,profiler_enabled=False)
   (cap/'read-routing-profile.json').write_text(json.dumps(metadata,indent=2)+'\n')
   for n in set(inputs)|{'read-routing-profile.json'}:inputs[n]=sha(cap/n)
   (cap/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
   execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={cap},target=/work,readonly','--mount',f'type=bind,source={cap}/exports,target=/work-output',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],cap,'renode',timeout=180)
   f=json.loads((cap/'exports/frozen-core.json').read_text());b=json.loads((cap/'exports/fixed-boundary.json').read_text());connection=json.loads((cap/'exports/connection.json').read_text())
   if not connection['att']['stopped'] or f['cfsr'] or f['hfsr'] or f['memory_violations'] or any(g['accesses'] for g in f['guards']) or f['busy_reads']<100 or f['completed_calculations'] or b['end_ticks']-b['start_ticks']!=500000000:raise ValueError('Work did not finish cleanly')
   row=dict(pair=pair,mode=mode,phase_wall_seconds=b['wall_seconds'],total_wall_seconds=time.monotonic()-started,busy_reads=f['busy_reads'],instructions=b['instructions'],capture=cap.name);rows.append(row)
   pins={str(x.relative_to(cap)):sha(x) for x in cap.rglob('*') if x.is_file() and x.name!='capture-files.json'};(cap/'capture-files.json').write_text(json.dumps(dict(files=pins),indent=2)+'\n')
   (o/'runs.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
if __name__=='__main__':main()
