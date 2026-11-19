"""One original version: natural app -> device reset -> original app time action again."""
import argparse,json,shutil,subprocess
from pathlib import Path
from reset_restart_profiles import sha,read,RENODE_IMAGE as IMAGE
from run_renode_m55_probe import execute

def build(s,out,case,memory_policy=None,system_control=None):
    if out.exists() or not out.resolve().is_relative_to(s.resolve()) or shutil.disk_usage(s).free<1024**3:raise ValueError('Fresh private output and at least 1 GiB free required')
    from reset_restart_inputs import fixed_inputs
    values,meta=fixed_inputs(s,case)
    if memory_policy is not None:
        from reset_memory_policy_candidate import with_memory_policy
        values,meta=with_memory_policy(s,values,meta,memory_policy)
    if system_control is not None:
        from reset_memory_policy_candidate import with_system_control
        values,meta=with_system_control(s,values,meta,system_control)
    base=s/meta['original_input'];common=s/meta['reference']
    out.mkdir(mode=0o700,parents=True);(out/'exports').mkdir(mode=0o700)
    for n,data in values.items():
        source=next((x/n for x in (base,common) if (x/n).exists() and (x/n).read_bytes()==data),None)
        if source is None:(out/n).write_bytes(data)
        else:
            copied=subprocess.run(['cp','-c',str(source),str(out/n)],capture_output=True)
            if copied.returncode:shutil.copyfile(source,out/n)
    (out/'connection-inputs.json').write_text(json.dumps({n:sha(out/n) for n in sorted(values)},indent=2)+'\n')
    (out/'reset-restart-profile.json').write_text(json.dumps(meta,indent=2)+'\n')
    return meta

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--case',choices=('stock24','stock23','cfw'),required=True);p.add_argument('--prepare-only',action='store_true');p.add_argument('--memory-policy',type=Path);p.add_argument('--system-control',type=Path);a=p.parse_args();r=build(a.simulator,a.output,a.case,a.memory_policy,a.system_control)
    if a.prepare_only:print(json.dumps(r));return
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=300)
    value=read(a.output/'exports/restart-app.json')
    print(json.dumps(dict(case=a.case,stopped=value['stopped'],rtc=value['rtc'],pc=hex(value['pc']),guards=[x for x in value['guards'] if x['accesses']])))
    if not value['stopped'] or value['cfsr'] or value['hfsr'] or any(x['accesses'] for x in value['guards']):raise ValueError('Original restarted app did not return cleanly')
if __name__=='__main__':main()
