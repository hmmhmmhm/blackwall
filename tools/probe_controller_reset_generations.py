"""Run original timeout recovery with explicitly bounded controller reset generations."""
import argparse
import json
from pathlib import Path
from controller_reset_generation_model import compose
from probe_hci_response_loss import build as loss_build
from probe_controller_reset_boundary import SETUP,POST
from run_runtime_connection_m55 import pin_capture,sha
from run_renode_m55_probe import execute
from native_replay import IMAGE

GENERATION_POST='''
try:
    generation=dict(limit=int(peer.ControllerResetLimit),generation=int(peer.ControllerGeneration),history=str(peer.ControllerGenerationHistory),rejection=str(peer.ResetGenerationRejection),hardware_accessed=False)
    File.WriteAllText('/work-output/controller-generation.json',json.dumps(generation));Console.WriteLine('BLACKWALL_CONTROLLER_GENERATION '+json.dumps(generation))
except Exception as error:Console.WriteLine('BLACKWALL_CONTROLLER_GENERATION_ERROR '+str(error))
'''

def build(s,out,enabled):
    loss_build(s,out,False)
    p=out/'strict.cs';p.write_text(compose(p.read_text()))
    p=out/'board.repl';text=p.read_text();anchor='    runtimeReadvertise: true\n'
    if text.count(anchor)!=1:raise ValueError('Unknown controller profile')
    p.write_text(text.replace(anchor,anchor+'    controllerResetLimit: '+('1' if enabled else '0')+'\n'))
    src=Path(__file__).with_name('renode-controller-reset-observer.cs');(out/src.name).write_bytes(src.read_bytes())
    with (out/'activation.cs').open('ab') as f:f.write(b'\n'+src.read_bytes())
    p=out/'run.py';text=p.read_text();anchor='    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n'
    if text.count(anchor)!=1:raise ValueError('Unknown timeout observation boundary')
    text=text.replace(anchor,SETUP+anchor)
    if text.count('deadline=time.time()+75')!=1 or text.count('<11500000000')!=1:raise ValueError('Unknown bounded run budget')
    p.write_text(text.replace('deadline=time.time()+75','deadline=time.time()+105').replace('<11500000000','<18000000000')+POST+GENERATION_POST)
    p=out/'connection-profile.json';value=json.loads(p.read_text());value.update(model_sha256=sha(out/'strict.cs'),controller_reset_limit=1 if enabled else 0);p.write_text(json.dumps(value,indent=2)+'\n')
    p=out/'connection-inputs.json';value=json.loads(p.read_text())
    for n in set(value)|{src.name}:value[n]=sha(out/n)
    p.write_text(json.dumps(value,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--disabled',action='store_true');a=p.parse_args();build(a.simulator,a.output,not a.disabled)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=250)
    pin_capture(a.output);h=json.loads((a.output/'exports/hci-timeout.json').read_text());g=json.loads((a.output/'exports/controller-generation.json').read_text())
    print(json.dumps(dict(generation=g['generation'],rejection=g['rejection'],timeout_returned=h['timeout_returned'],peer=h['peer'],pc=hex(h['pc']),guards=[x for x in h['guards'] if x['accesses']])))

if __name__=='__main__':main()
