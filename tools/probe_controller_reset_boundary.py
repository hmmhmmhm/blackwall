"""Record original post-timeout GPIO reset writes without changing the controller model."""
import argparse
import json
from pathlib import Path
from probe_hci_response_loss import build
from run_runtime_connection_m55 import pin_capture,sha
from run_renode_m55_probe import execute
from native_replay import IMAGE

SETUP='''    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallControllerResetObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallControllerResetObserver
    resetdiag=BlackwallControllerResetObserver(m,cpu,g.GpioOutput,g.Em9305Reset)
'''
POST='''
try:
    reset=g.Em9305Reset
    value=dict(rows=[[int(x) for x in row] for row in resetdiag.Rows],states=[str(x) for x in resetdiag.States],phases=[str(x) for x in resetdiag.Phases],overflow=bool(resetdiag.Overflow),
        final=dict(held=bool(reset.Held),released=bool(reset.Released),asserted_us=int(reset.AssertedAt),released_us=int(reset.ReleasedAt),last_us=int(reset.LastMicroseconds),minimum_us=int(reset.MinimumResetMicroseconds),busy_us=int(reset.BusyAfterMicroseconds),ready_us=int(reset.ReadyAfterMicroseconds),writes=int(reset.ResetWrites),phase=str(reset.Phase)),hardware_accessed=False)
    File.WriteAllText('/work-output/controller-reset.json',json.dumps(value));Console.WriteLine('BLACKWALL_CONTROLLER_RESET '+json.dumps(value))
except Exception as error:Console.WriteLine('BLACKWALL_CONTROLLER_RESET_ERROR '+str(error))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    build(a.simulator,a.output,False)
    src=Path(__file__).with_name('renode-controller-reset-observer.cs');(a.output/src.name).write_bytes(src.read_bytes())
    with (a.output/'activation.cs').open('ab') as f:f.write(b'\n'+src.read_bytes())
    run=a.output/'run.py';text=run.read_text();anchor='    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n'
    if text.count(anchor)!=1:raise ValueError('Unknown reset observation boundary')
    run.write_text(text.replace(anchor,SETUP+anchor)+POST)
    inputs=json.loads((a.output/'connection-inputs.json').read_text())
    for n in set(inputs)|{src.name}:inputs[n]=sha(a.output/n)
    (a.output/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=210)
    pin_capture(a.output);v=json.loads((a.output/'exports/controller-reset.json').read_text());print(json.dumps(v))

if __name__=='__main__':main()
