"""Observe the original unshortened HCI timer after one simulated missing completion."""
import argparse
import json
from pathlib import Path

from probe_frozen_peer_disconnect import build as close_build
from runtime_reconnect_model import compose as reconnect_model
from iom_shared_power_model import compose as power_model,board_profile
from hci_response_loss_model import compose as loss_model
from run_runtime_connection_m55 import sha,pin_capture
from run_renode_m55_probe import execute
from native_replay import IMAGE
from inspect_ambiq_target import decode

POST='''
try:
    import clr,time,json
    from System import Action,Console
    from System.IO import File
    from Antmicro.Renode.Core import EmulationManager
    from Antmicro.Renode.Utilities import TypeManager
    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallHciTimeoutObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallHciTimeoutObserver
    m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];g=m['sysbus.guard'];peer=g.Em9305Reset.HciPeer
    c=json.load(open('/work/hci-timeout-contract.json'));p=json.load(open('/work/connection-profile.json'))
    def guard_state():return [dict(name=v['name'],accesses=int(m['sysbus.'+v['name']].AccessCount),address=int(m['sysbus.'+v['name']].LastAddress)) for v in result['guards']]
    if not m.IsPaused or not close.Stopped or any(v['accesses'] for v in guard_state()):raise ValueError('Need clean original close return')
    diag=BlackwallHciTimeoutObserver(m,cpu,c['timer'],c['timer_start_seconds'],c['timer_callback'],c['timer_callback_return'],p['tcb_slot'])
    diag.WatchHealthyStop(m,cpu,c['healthy_stop_pc'],c['timer'])
    for row in c['callback_code']:
        if row['asm'].startswith('bl #'):diag.WatchCall(cpu,row['pc'])
    lost=[];healthy=[]
    def on_lost():
        lost.append(dict(ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),opcode=int(b.ReadWord(c['opcode'])),credit=int(b.ReadByte(c['credit'])),timer=[int(v) for v in b.ReadBytes(c['timer'],16,True)]))
    def on_healthy():
        healthy.append(int(m.ElapsedVirtualTime.TimeElapsed.Ticks))
    peer.ReadvertisingReplyDropped+=Action(on_lost);peer.ReadvertisingCompleted+=Action(on_healthy)
    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+75
    while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<11500000000:time.sleep(0.005)
    m.Pause()
    v=dict(start_ticks=start,end_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pc=int(cpu.PC.RawValue),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],timer_starts=int(diag.Starts),timer_seconds=int(diag.StartSeconds),timer_start_ticks=int(diag.StartTicks),timeout_entered=bool(diag.Entered),timeout_entry_ticks=int(diag.EntryTicks),timeout_entry=[int(x) for x in diag.Entry],timeout_message=[int(x) for x in diag.EntryMessage],timeout_returned=bool(diag.Returned),timeout_return_ticks=int(diag.ReturnTicks),timeout_exit=[int(x) for x in diag.Exit],calls=[[int(x) for x in row] for row in diag.Calls],overflow=bool(diag.Overflow),lost=lost,healthy=healthy,guards=guard_state(),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),peer=dict(state=str(peer.State),commands=int(peer.CommandsAccepted),replies=int(peer.Replies),events=int(peer.RuntimeEventsConsumed),pending=bool(peer.RuntimeEventPending),readvertising_commands=int(peer.ReadvertisingCommands),readvertising_replies=int(peer.ReadvertisingReplies),dropped=int(peer.ReadvertisingRepliesDropped),accepted=str(peer.ReadvertisingAccepted)),final_credit=int(b.ReadByte(c['credit'])),final_opcode=int(b.ReadWord(c['opcode'])),final_timer=[int(x) for x in b.ReadBytes(c['timer'],16,True)],gaf=gaf_snapshot(),hardware_accessed=False,normal_initialization_verified=False)
    v.update(healthy_timer_stop=bool(diag.HealthyStop),healthy_timer_stop_ticks=int(diag.HealthyStopTicks),healthy_timer=[int(x) for x in diag.HealthyTimer])
    File.WriteAllBytes('/work-output/hci-timeout-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    File.WriteAllText('/work-output/hci-timeout.json',json.dumps(v));Console.WriteLine('BLACKWALL_HCI_RESPONSE_LOSS '+json.dumps(v))
except Exception as error:Console.WriteLine('BLACKWALL_HCI_RESPONSE_LOSS_ERROR '+str(error))
'''


def build(s,out,control):
    close_build(s,out,1000,19)
    contract=next(x for x in json.loads((s/'hci-response-loss-research-01/original-contract.json').read_text())['cases'] if x['case']=='stock24')
    if contract['main_sha256']!=sha(out/'main.bin') or contract['seconds']!=10:raise ValueError('Unverified original timer contract')
    raw=(out/'main.bin').read_bytes()
    first_call=next(i for i in decode(raw,contract['ready'],0x20) if i.mnemonic=='bl')
    contract['healthy_stop_pc']=first_call.address+first_call.size
    contract['timer_stop']=first_call.operands[0].imm
    for v in contract['callback_code']:
        data=bytes.fromhex(v['bytes']);offset=v['pc']-0x438000
        if raw[offset:offset+len(data)]!=data:raise ValueError('Changed original timeout callback')
    (out/'hci-timeout-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    model=loss_model(power_model(reconnect_model((out/'strict.cs').read_text())));(out/'strict.cs').write_text(model)
    board=board_profile((out/'board.repl').read_text()).replace('    runtimeDisconnectEventHex:','    runtimeReadvertise: true\n    runtimeDropFirstReadvertisingReply: '+str(not control).lower()+'\n    runtimeDisconnectEventHex:')
    (out/'board.repl').write_text(board)
    path=Path(__file__).with_name('renode-hci-timeout-observer.cs');(out/path.name).write_bytes(path.read_bytes())
    with (out/'activation.cs').open('ab') as f:f.write(b'\n'+path.read_bytes())
    p=json.loads((out/'connection-profile.json').read_text());p.update(model_sha256=sha(out/'strict.cs'),runtime_readvertise=True,iom_shared_gate=True,hci_response_loss=not control)
    (out/'connection-profile.json').write_text(json.dumps(p,indent=2)+'\n')
    (out/'run.py').write_text((out/'run.py').read_text()+POST)
    inputs=json.loads((out/'connection-inputs.json').read_text())
    for n in set(inputs)|{'hci-timeout-contract.json',path.name}:inputs[n]=sha(out/n)
    (out/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--control',action='store_true');a=p.parse_args()
    build(a.simulator,a.output,a.control)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=210)
    pin_capture(a.output);v=json.loads((a.output/'exports/hci-timeout.json').read_text())
    print(json.dumps({k:v[k] for k in ('timeout_entered','timeout_returned','timer_seconds','timer_starts','peer','guards','pc')}))


if __name__=='__main__':main()
