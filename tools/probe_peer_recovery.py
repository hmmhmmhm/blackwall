"""Version-pinned original main: delayed close, lost completion, timeout, reset and reconnect."""
import argparse
import hashlib
import json
from pathlib import Path
from run_runtime_connection_m55 import build as runtime_build,sha,pin_capture
from probe_gaf_frozen_core import compose_frozen,scoped_observer_component
from runtime_reconnect_model import compose as reconnect_model
from iom_shared_power_model import compose as power_model,board_profile
from hci_response_loss_model import compose as loss_model
from controller_reset_generation_model import compose as generation_model
from post_reset_advertising_model import compose as advertising_model
from runtime_event_models import imu_span
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from run_renode_m55_probe import execute
from native_replay import IMAGE

SUSPEND='''    if not app.Stopped or not m.IsPaused or any(v['accesses'] for v in result['guards']) or result['cfsr'] or result['hfsr'] or result['memory_violations']:
        raise ValueError('Recovery requires clean original ATT return')
    for label in p['suspended_startup_observer_labels']:
        if not observer.SuspendPoint(label):raise ValueError('Diagnostic point not owned or already suspended')
'''
POST='''
try:
    import clr,time,json
    from System import Console
    from System.IO import File
    from Antmicro.Renode.Core import EmulationManager
    from Antmicro.Renode.Utilities import TypeManager
    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallPeerRecoveryObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallPeerRecoveryObserver,BlackwallRuntimeConnectionObserver
    m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];g=m['sysbus.guard'];peer=g.Em9305Reset.HciPeer
    p=json.load(open('/work/connection-profile.json'));c=json.load(open('/work/recovery-contract.json'))
    def guards():return [dict(name=v['name'],accesses=int(m['sysbus.'+v['name']].AccessCount),address=int(m['sysbus.'+v['name']].LastAddress)) for v in result['guards']]
    def state():
        return dict(ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pc=int(cpu.PC.RawValue),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],credit=int(b.ReadByte(c['credit'])),opcode=int(b.ReadWord(c['opcode'])),timer=[int(x) for x in b.ReadBytes(c['timer'],16,True)],guards=guards(),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),generation=int(peer.ControllerGeneration),history=str(peer.ControllerGenerationHistory),rejection=str(peer.ResetGenerationRejection),peer=dict(state=str(peer.State),commands=int(peer.CommandsAccepted),replies=int(peer.Replies),events=int(peer.RuntimeEventsConsumed),pending=bool(peer.RuntimeEventPending),advertising_commands=int(peer.AdvertisingCommandsAccepted),advertising_replies=int(peer.AdvertisingRepliesConsumed),readvertising_commands=int(peer.ReadvertisingCommands),readvertising_replies=int(peer.ReadvertisingReplies),dropped=int(peer.ReadvertisingRepliesDropped)),gpio=dict(irq=bool(q.IRQ.IsSet),pending=bool(q.Pending117),edges=int(q.RisingEdges)),gaf=gaf_snapshot(),rtc=dict(commits=int(g.Rtc.Commits),date=str(g.Rtc.VirtualDate),pending=bool(g.Rtc.WritePending),error=str(g.Rtc.LastError)),hardware_accessed=False)
    def clean(v):return not any(x['accesses'] for x in v['guards']) and v['cfsr']==v['hfsr']==v['memory_violations']==0
    def resume(virtual_ns,host_seconds):
        start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);deadline=time.time()+host_seconds
        EmulationManager.Instance.CurrentEmulation.StartAll()
        while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<virtual_ns:time.sleep(0.001)
        m.Pause()
    phases=[]
    def save(name):
        v=state();phases.append(dict(name=name,state=dict(v)));File.WriteAllBytes('/work-output/'+name+'-sram.bin',b.ReadBytes(0x20000000,0x380000,True));File.WriteAllText('/work-output/'+name+'.json',json.dumps(v));Console.WriteLine('BLACKWALL_RECOVERY_PHASE '+json.dumps(dict(name=name,state=v)));return v
    if not m.IsPaused or not close.Stopped or not clean(state()):raise ValueError('Need clean original delayed close')
    diag=BlackwallPeerRecoveryObserver(m,cpu,c['timer'],c['opcode'],c['credit'],c['timer_start_seconds'],c['timer_callback'],c['timer_callback_return'],c['healthy_stop_pc'],c['ready_return'],p['tcb_slot'],c['send'],peer)
    for pc in c['callback_sites']:diag.WatchCall(cpu,pc)
    resume(18000000000,105);returned=save('timeout-return')
    if not diag.Returned or not clean(returned):raise ValueError('Original timeout did not reach callback return cleanly')
    resume(3000000000,45);healthy=save('healthy-stop')
    if not diag.Healthy or not clean(healthy):raise ValueError('Post-reset initialization did not complete cleanly')
    resume(100000000,20);credit=save('credit-return')
    if not diag.CreditReturned or credit['credit']!=1 or not clean(credit):raise ValueError('Original credit did not restore')
    resume(100000000,20);settled=save('settled')
    if not clean(settled) or settled['peer']['state']!='Complete' or settled['peer']['events']!=0 or settled['credit']!=1:raise ValueError('No clean reconnect baseline')
    connection=BlackwallRuntimeConnectionObserver(m,cpu,p['gpio']['isr'],p['opened'],p['finished'],p['tcb_slot'])
    accepted=bool(peer.TryQueueRuntimeConnection());input=dict(accepted=accepted,ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pc=int(cpu.PC.RawValue),irq=bool(q.IRQ.IsSet),pending=bool(q.Pending117))
    if not accepted:raise ValueError('New generation connection rejected')
    resume(2000000000,30);connected=save('reconnected');connected.update(input=input,stopped=bool(connection.Stopped),entry=[int(x) for x in connection.Entry],exit=[int(x) for x in connection.Exit],calls=int(connection.OpenCalls),irq_entries=int(connection.IrqEntries))
    File.WriteAllText('/work-output/reconnection.json',json.dumps(connected));Console.WriteLine('BLACKWALL_VERSION_RECONNECTION '+json.dumps(connected))
except Exception as error:Console.WriteLine('BLACKWALL_VERSION_RECOVERY_ERROR '+str(error))
try:
    diagnostic=dict(started=bool(diag.Started),seconds=int(diag.Seconds),started_at=int(diag.StartedAt),entered=bool(diag.Entered),entered_at=int(diag.EnteredAt),entry=[int(x) for x in diag.Entry],message=[int(x) for x in diag.Message],returned=bool(diag.Returned),returned_at=int(diag.ReturnedAt),returned_context=[int(x) for x in diag.Return],healthy=bool(diag.Healthy),healthy_at=int(diag.HealthyAt),credit_returned=bool(diag.CreditReturned),credit_at=int(diag.CreditAt),calls=[[int(x) for x in row] for row in diag.Calls],packets=[''.join('%02x'%int(x) for x in packet) for packet in diag.Packets],packet_generations=[int(x) for x in diag.PacketGenerations],invalid_pointer=bool(diag.InvalidPointer),overflow=bool(diag.Overflow),phases=phases,hardware_accessed=False)
    File.WriteAllText('/work-output/recovery-diagnostic.json',json.dumps(diagnostic));Console.WriteLine('BLACKWALL_VERSION_RECOVERY_DIAGNOSTIC '+json.dumps(diagnostic))
except Exception as error:Console.WriteLine('BLACKWALL_VERSION_DIAGNOSTIC_ERROR '+str(error))
'''

def contract(s,raw,case):
    src=s/'hci-response-loss-research-01/original-contract.json';pins=json.loads((s/'hci-response-loss-research-01/manifest.json').read_text())['files'];pin=pins[str(src.relative_to(s))]
    if sha(src)!=pin['sha256']:raise ValueError('Changed original timeout source')
    c=next(x for x in json.loads(src.read_text())['cases'] if x['case']==case)
    if hashlib.sha256(raw).hexdigest()!=c['main_sha256']:raise ValueError('Different original main')
    for row in c['callback_code']:
        code=bytes.fromhex(row['bytes']);offset=row['pc']-0x438000
        if raw[offset:offset+len(code)]!=code:raise ValueError('Changed timeout code')
    ready=decode(raw,c['ready'],0x30);first=next(i for i in ready if i.mnemonic=='bl');ret=next(i for i in ready if i.mnemonic=='pop' and i.op_str=='{r4, pc}')
    base=next(i for i in ready if i.mnemonic.startswith('ldr') and i.op_str.startswith('r4, [pc,'))
    store=next(i for i in ready if i.mnemonic.startswith('strb'))
    if literal(raw,base)!=c['timer'] or store.op_str!='r0, [r4, #'+hex(c['credit']-c['timer'])+']':raise ValueError('Unverified credit ABI')
    return dict(c,healthy_stop_pc=first.address+first.size,timer_stop=first.operands[0].imm,ready_return=ret.address,callback_sites=[r['pc'] for r in c['callback_code'] if r['asm'].startswith('bl #')],ready_code=[dict(pc=i.address,asm=i.mnemonic+' '+i.op_str,bytes=bytes(i.bytes).hex()) for i in ready if i.address<=ret.address])

def build(s,out,case):
    p=runtime_build(s,out,case,att_time=True,disconnect_reason=19,disconnect_delay_ms=1000,gaf_profile=True,gaf_on_demand_control=True)
    model=scoped_observer_component(compose_frozen((out/'strict.cs').read_text()))
    model=advertising_model(generation_model(loss_model(power_model(reconnect_model(model)))));(out/'strict.cs').write_text(model)
    board=board_profile((out/'board.repl').read_text());anchor='    runtimeDisconnectEventHex:'
    if board.count(anchor)!=1:raise ValueError('Unknown recovery board boundary')
    board=board.replace(anchor,'    runtimeReadvertise: true\n    runtimeDropFirstReadvertisingReply: true\n    controllerResetLimit: 1\n    postResetAdvertisingDataFirst: true\n'+anchor);(out/'board.repl').write_text(board)
    a,b=imu_span(model);gaf=json.loads((out/'gaf-profile.json').read_text());gaf.update(candidate_sha256=hashlib.sha256(model[a:b].encode()).hexdigest(),control_fragment_sha256=sha(Path(__file__).with_name('renode-gaf-frozen-core.cs')),on_demand_fault='frozen-core',calculation_supported=False,retained_ram_source='prior modeled clear and explicit host writes; no EDMP execution');(out/'gaf-profile.json').write_text(json.dumps(gaf,indent=2)+'\n')
    p.update(gaf_profile=gaf,gaf_profile_sha256=sha(out/'gaf-profile.json'),model_sha256=sha(out/'strict.cs'),suspended_startup_observer_labels=['iom7-address','iom7-fifo','iom7-command'],combined_fault_scenario='EDMP-frozen-core plus lost HCI completion',controller_reset_limit=1,post_reset_advertising_data_first=True)
    (out/'connection-profile.json').write_text(json.dumps(p,indent=2)+'\n');c=contract(s,(out/'main.bin').read_bytes(),case);(out/'recovery-contract.json').write_text(json.dumps(c,indent=2)+'\n')
    src=Path(__file__).with_name('renode-peer-recovery-observer.cs');(out/src.name).write_bytes(src.read_bytes())
    with (out/'activation.cs').open('ab') as f:f.write(b'\n'+src.read_bytes())
    path=out/'run.py';text=path.read_text();anchor="    if p.get('disconnect_reason') is not None:\n"
    if text.count(anchor)!=1:raise ValueError('Unknown original close setup')
    path.write_text(text.replace(anchor,SUSPEND+anchor)+POST)
    inputs=json.loads((out/'connection-inputs.json').read_text())
    for n in set(inputs)|{src.name,'recovery-contract.json'}:inputs[n]=sha(out/n)
    (out/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--case',choices=('stock24','stock23','cfw'),required=True);p.add_argument('--prepare-only',action='store_true');a=p.parse_args();build(a.simulator,a.output,a.case)
    if a.prepare_only:print(json.dumps(dict(prepared=True,case=a.case)));return
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=360)
    pin_capture(a.output);v=json.loads((a.output/'exports/recovery-diagnostic.json').read_text());print(json.dumps(dict(case=a.case,timeout=v['entered'],returned=v['returned'],healthy=v['healthy'],credit=v['credit_returned'],phases=[dict(name=x['name'],pc=hex(x['state']['pc']),guards=[g for g in x['state']['guards'] if g['accesses']]) for x in v['phases']])))

if __name__=='__main__':main()
