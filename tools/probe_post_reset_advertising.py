"""Observe original HCI candidate packets without acknowledging unsupported commands."""
import argparse
import json
from pathlib import Path
from probe_controller_reset_generations import build as generation_build
from probe_controller_notification import SETUP as NOTIFY_SETUP,POST as NOTIFY_POST
from run_runtime_connection_m55 import sha,pin_capture
from run_renode_m55_probe import execute
from native_replay import IMAGE
from post_reset_advertising_model import compose

SETUP='''    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallHciEmissionObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallHciEmissionObserver
    emissiondiag=BlackwallHciEmissionObserver(m,cpu,peer,p['tcb_slot'])
'''
POST='''
try:
    emitted=dict(rows=[[int(x) for x in row] for row in emissiondiag.Rows],packets=[''.join('%02x'%int(x) for x in packet) for packet in emissiondiag.Packets],overflow=bool(emissiondiag.Overflow),invalid_pointer=bool(emissiondiag.InvalidPointer),hardware_accessed=False)
    File.WriteAllText('/work-output/hci-emission.json',json.dumps(emitted));Console.WriteLine('BLACKWALL_HCI_EMISSION '+json.dumps(emitted))
except Exception as error:Console.WriteLine('BLACKWALL_HCI_EMISSION_ERROR '+str(error))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--data-first',action='store_true');a=p.parse_args();generation_build(a.simulator,a.output,True)
    if a.data_first:
        p=a.output/'strict.cs';p.write_text(compose(p.read_text()))
        p=a.output/'board.repl';text=p.read_text();anchor='    controllerResetLimit: 1\n'
        if text.count(anchor)!=1:raise ValueError('Unknown qualified reset profile')
        p.write_text(text.replace(anchor,anchor+'    postResetAdvertisingDataFirst: true\n'))
        p=a.output/'connection-profile.json';v=json.loads(p.read_text());v.update(model_sha256=sha(a.output/'strict.cs'),post_reset_advertising_data_first=True);p.write_text(json.dumps(v,indent=2)+'\n')
    for n in ('renode-controller-notification-observer.cs','renode-hci-emission-observer.cs'):
        src=Path(__file__).with_name(n);(a.output/n).write_bytes(src.read_bytes())
        with (a.output/'activation.cs').open('ab') as f:f.write(b'\n'+src.read_bytes())
    p=a.output/'run.py';text=p.read_text();anchor='    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n'
    if text.count(anchor)!=1:raise ValueError('Unknown emission observation boundary')
    p.write_text(text.replace(anchor,NOTIFY_SETUP+SETUP+anchor)+NOTIFY_POST+POST)
    p=a.output/'connection-inputs.json';v=json.loads(p.read_text())
    for n in set(v)|{'renode-controller-notification-observer.cs','renode-hci-emission-observer.cs'}:v[n]=sha(a.output/n)
    p.write_text(json.dumps(v,indent=2)+'\n')
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=300)
    pin_capture(a.output);v=json.loads((a.output/'exports/hci-emission.json').read_text());print(json.dumps(dict(count=len(v['rows']),overflow=v['overflow'],packets=[p for row,p in zip(v['rows'],v['packets']) if row[6]==1 and int(p[:4],16)&0x20])))

if __name__=='__main__':main()
