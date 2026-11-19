"""Run the original delayed reconnect with explicit IOM shared lifecycle on or off."""
import argparse
import json
from pathlib import Path

from probe_runtime_reconnect import build
from iom_shared_power_model import compose,board_profile
from run_runtime_connection_m55 import sha,pin_capture
from run_renode_m55_probe import execute
from native_replay import IMAGE

POST='''
try:
    from System import Console
    from System.IO import File
    g=monitor.Machine['sysbus.guard'];powers=[]
    for pair in g.IomPowers:
        v=pair.Value;i=monitor.Machine['sysbus.iom'+str(pair.Key)]
        powers.append(dict(module=int(pair.Key),selected=bool(v.SharedIomGate),phase=str(v.Phase),request=int(v.RequestWord),status=int(v.StatusWord),requests=int(v.Requests),responses=int(v.Responses),off_requests=int(v.OffRequests),power_cycles=int(v.PowerCycles),device_power_downs=int(i.PowerDowns)))
    value=dict(powers=powers,physical_retention_verified=False,hardware_accessed=False)
    File.WriteAllText('/work-output/iom-shared-power.json',json.dumps(value));Console.WriteLine('BLACKWALL_IOM_SHARED_POWER '+json.dumps(value))
except Exception as error:Console.WriteLine('BLACKWALL_IOM_SHARED_POWER_ERROR '+str(error))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--disabled',action='store_true');a=p.parse_args()
    build(a.simulator,a.output,1000)
    path=a.output/'strict.cs';path.write_text(compose(path.read_text()))
    if not a.disabled:
        path=a.output/'board.repl';path.write_text(board_profile(path.read_text()))
    profile=json.loads((a.output/'connection-profile.json').read_text());profile.update(model_sha256=sha(a.output/'strict.cs'),iom_shared_gate=not a.disabled)
    (a.output/'connection-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    (a.output/'run.py').write_text((a.output/'run.py').read_text()+POST)
    inputs=json.loads((a.output/'connection-inputs.json').read_text())
    for n in inputs:inputs[n]=sha(a.output/n)
    (a.output/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=180)
    pin_capture(a.output)
    a1=json.loads((a.output/'exports/readvertising.json').read_text());a2=json.loads((a.output/'exports/reconnect.json').read_text())
    print(json.dumps(dict(selected=not a.disabled,rearm=a1['peer'],reconnect=a2.get('stopped',False),guards=[g for g in a1['guards'] if g['accesses']])))


if __name__=='__main__':main()
