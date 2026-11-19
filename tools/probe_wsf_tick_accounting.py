"""Repeat the bounded original loss case with explicit passive WSF accounting."""
import argparse
import json
from pathlib import Path

from probe_hci_response_loss import build
from run_runtime_connection_m55 import pin_capture,sha
from run_renode_m55_probe import execute
from native_replay import IMAGE

SETUP='''    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallWsfTickObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallWsfTickObserver
    tickdiag=BlackwallWsfTickObserver(m,cpu,c['timer'],c['timer_start_seconds'],0x4d7cb6,0x4d7ce8,0x20077660,0x20077b3c)
'''
POST='''
try:
    value=dict(start=[int(v) for v in tickdiag.Start],rows=[[int(v) for v in row] for row in tickdiag.Rows],overflow=bool(tickdiag.Overflow),os_tick_address=0x20077660,previous_tick_address=0x20077b3c,hardware_accessed=False)
    File.WriteAllText('/work-output/wsf-ticks.json',json.dumps(value));Console.WriteLine('BLACKWALL_WSF_TICKS '+json.dumps(value))
except Exception as error:Console.WriteLine('BLACKWALL_WSF_TICKS_ERROR '+str(error))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    build(a.simulator,a.output,False)
    path=Path(__file__).with_name('renode-wsf-tick-observer.cs');(a.output/path.name).write_bytes(path.read_bytes())
    with (a.output/'activation.cs').open('ab') as f:f.write(b'\n'+path.read_bytes())
    path=a.output/'run.py';text=path.read_text();anchor='    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n'
    if text.count(anchor)!=1:raise ValueError('Unknown observation boundary')
    path.write_text(text.replace(anchor,SETUP+anchor)+POST)
    inputs=json.loads((a.output/'connection-inputs.json').read_text())
    for n in set(inputs)|{'renode-wsf-tick-observer.cs'}:inputs[n]=sha(a.output/n)
    (a.output/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=210)
    pin_capture(a.output);v=json.loads((a.output/'exports/wsf-ticks.json').read_text());t=json.loads((a.output/'exports/hci-timeout.json').read_text())
    print(json.dumps(dict(rows=len(v['rows']),overflow=v['overflow'],start=v['start'],timeout_entered=t['timeout_entered'],observed_ns=t['timeout_entry_ticks']-t['timer_start_ticks'])))


if __name__=='__main__':main()
