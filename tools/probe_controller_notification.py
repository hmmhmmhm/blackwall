"""Continue original timeout return into WSF notification and asynchronous startup."""
import argparse
import json
from pathlib import Path
from probe_controller_reset_generations import build as generation_build
from run_runtime_connection_m55 import sha,pin_capture
from run_renode_m55_probe import execute
from native_replay import IMAGE

SETUP='''    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallControllerNotificationObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallControllerNotificationObserver
    notifydiag=BlackwallControllerNotificationObserver(m,cpu,p['tcb_slot'])
'''
POST='''
try:
    def notification():
        return dict(rows=[[int(x) for x in row] for row in notifydiag.Rows],message=int(notifydiag.Message),sent=bool(notifydiag.Sent),callback_returned=bool(notifydiag.CallbackReturned),handler_entered=bool(notifydiag.HandlerEntered),dispatched=bool(notifydiag.Dispatched),leaf_entered=bool(notifydiag.LeafEntered),handler_return_instruction=bool(notifydiag.HandlerReturnInstruction),handler_returned=bool(notifydiag.HandlerReturned),message_freed=bool(notifydiag.MessageFreed),overflow=bool(notifydiag.Overflow))
    before=notification()
    File.WriteAllText('/work-output/notification-before.json',json.dumps(before));Console.WriteLine('BLACKWALL_NOTIFICATION_BEFORE '+json.dumps(before))
    if not m.IsPaused or not diag.Returned or any(x['accesses'] for x in guard_state()):raise ValueError('Need clean original timeout return instruction')
    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45
    while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<3000000000:time.sleep(0.005)
    m.Pause()
    value=dict(start_ticks=start,end_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pc=int(cpu.PC.RawValue),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],notification=notification(),guards=guard_state(),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),generation=int(peer.ControllerGeneration),history=str(peer.ControllerGenerationHistory),rejection=str(peer.ResetGenerationRejection),peer=dict(state=str(peer.State),commands=int(peer.CommandsAccepted),replies=int(peer.Replies),events=int(peer.RuntimeEventsConsumed),pending=bool(peer.RuntimeEventPending),reset_command=str(peer.ApplicationResetCommandHex),advertising_commands=int(peer.AdvertisingCommandsAccepted),advertising_replies=int(peer.AdvertisingRepliesConsumed)),gaf=gaf_snapshot(),hardware_accessed=False)
    File.WriteAllBytes('/work-output/notification-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    File.WriteAllText('/work-output/notification-after.json',json.dumps(value));Console.WriteLine('BLACKWALL_NOTIFICATION_AFTER '+json.dumps(value))
except Exception as error:Console.WriteLine('BLACKWALL_NOTIFICATION_ERROR '+str(error))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();generation_build(a.simulator,a.output,True)
    src=Path(__file__).with_name('renode-controller-notification-observer.cs');(a.output/src.name).write_bytes(src.read_bytes())
    with (a.output/'activation.cs').open('ab') as f:f.write(b'\n'+src.read_bytes())
    p=a.output/'run.py';text=p.read_text();anchor='    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n'
    if text.count(anchor)!=1:raise ValueError('Unknown notification observation boundary')
    p.write_text(text.replace(anchor,SETUP+anchor)+POST)
    p=a.output/'connection-inputs.json';v=json.loads(p.read_text())
    for n in set(v)|{src.name}:v[n]=sha(a.output/n)
    p.write_text(json.dumps(v,indent=2)+'\n')
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=300)
    pin_capture(a.output);v=json.loads((a.output/'exports/notification-after.json').read_text());print(json.dumps(dict(notification=v['notification'],peer=v['peer'],pc=hex(v['pc']),guards=[x for x in v['guards'] if x['accesses']])))

if __name__=='__main__':main()
