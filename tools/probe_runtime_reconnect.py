"""Original stock24 main: close, exact optional advertising replay, second connection."""
import argparse
import json
from pathlib import Path

from probe_frozen_peer_disconnect import build as close_build
from run_runtime_connection_m55 import pin_capture,sha
from runtime_reconnect_model import compose
from native_replay import IMAGE
from run_renode_m55_probe import execute

POST='''
try:
    from System import Action,Console
    from System.IO import File
    from Antmicro.Renode.Core import EmulationManager
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallRuntimeConnectionObserver
    m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];g=m['sysbus.guard'];peer=g.Em9305Reset.HciPeer
    def state():
        return dict(pc=int(cpu.PC.RawValue),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),guards=[dict(name=v['name'],accesses=int(m['sysbus.'+v['name']].AccessCount),address=int(m['sysbus.'+v['name']].LastAddress)) for v in result['guards']],cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),peer=dict(commands=int(peer.CommandsAccepted),replies=int(peer.Replies),state=str(peer.State),runtime_events=int(peer.RuntimeEventsConsumed),pending=bool(peer.RuntimeEventPending),readvertising_commands=int(peer.ReadvertisingCommands),readvertising_replies=int(peer.ReadvertisingReplies),accepted=str(peer.ReadvertisingAccepted)),gaf=gaf_snapshot(),rtc=dict(commits=int(g.Rtc.Commits),date=str(g.Rtc.VirtualDate),pending=bool(g.Rtc.WritePending),error=str(g.Rtc.LastError)))
    def clean(v):return not any(g['accesses'] for g in v['guards']) and v['cfsr']==v['hfsr']==v['memory_violations']==0
    if not m.IsPaused or not close.Stopped or not clean(state()):raise ValueError('Need clean original close boundary')
    completed=[]
    def rearmed():
        completed.append(int(m.ElapsedVirtualTime.TimeElapsed.Ticks));m.Pause()
    callback=Action(rearmed);peer.ReadvertisingCompleted+=callback
    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45
    while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<2000000000:time.sleep(0.001)
    m.Pause();rearm=state();iom=m['sysbus.iom6'];rearm.update(start_ticks=start,completed=completed,registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],iom6=dict(address=int(iom.LastAddress),value=int(iom.LastValue),operation=str(iom.LastOperation)))
    File.WriteAllBytes('/work-output/readvertising-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    File.WriteAllText('/work-output/readvertising.json',json.dumps(rearm));Console.WriteLine('BLACKWALL_READVERTISING '+json.dumps(rearm))
    reconnect=dict(executed=False,reason='advertising did not complete cleanly')
    if completed and clean(rearm):
        diag2=BlackwallRuntimeConnectionObserver(m,cpu,p['gpio']['isr'],p['opened'],p['finished'],p['tcb_slot'])
        accepted=bool(peer.TryQueueRuntimeReconnection())
        inp=dict(accepted=accepted,pc=int(cpu.PC.RawValue),irq=bool(q.IRQ.IsSet),pending=bool(q.Pending117))
        if not accepted:raise ValueError('Readvertising completion lost reconnect preconditions')
        EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45
        while not diag2.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-rearm['ticks']<2000000000:time.sleep(0.001)
        m.Pause();reconnect=state();reconnect.update(executed=True,input=inp,stopped=bool(diag2.Stopped),entry=[int(v) for v in diag2.Entry],exit=[int(v) for v in diag2.Exit],calls=int(diag2.OpenCalls),irq_entries=int(diag2.IrqEntries),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],gpio=dict(irq=bool(q.IRQ.IsSet),pending=bool(q.Pending117),edges=int(q.RisingEdges)))
        File.WriteAllBytes('/work-output/reconnect-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    File.WriteAllText('/work-output/reconnect.json',json.dumps(reconnect));Console.WriteLine('BLACKWALL_RECONNECT '+json.dumps(reconnect))
except Exception as error:Console.WriteLine('BLACKWALL_RECONNECT_ERROR '+str(error))
'''


def build(s,out,delay):
    close_build(s,out,delay,19)
    model=compose((out/'strict.cs').read_text());(out/'strict.cs').write_text(model)
    p=json.loads((out/'connection-profile.json').read_text());p.update(model_sha256=sha(out/'strict.cs'),runtime_readvertise=True)
    (out/'connection-profile.json').write_text(json.dumps(p,indent=2)+'\n')
    board=(out/'board.repl').read_text();anchor='    runtimeDisconnectEventHex:'
    if board.count(anchor)!=1:raise ValueError('Unknown explicit disconnect profile')
    (out/'board.repl').write_text(board.replace(anchor,'    runtimeReadvertise: true\n'+anchor))
    (out/'run.py').write_text((out/'run.py').read_text()+POST)
    inputs=json.loads((out/'connection-inputs.json').read_text())
    for n in inputs:inputs[n]=sha(out/n)
    (out/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--delay-ms',type=int,choices=(0,1000),default=0);a=p.parse_args()
    build(a.simulator,a.output,a.delay_ms)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=180)
    pin_capture(a.output)
    a1=json.loads((a.output/'exports/readvertising.json').read_text());a2=json.loads((a.output/'exports/reconnect.json').read_text())
    print(json.dumps(dict(readvertising=a1['peer'],reconnection_executed=a2['executed'],reconnection_stopped=a2.get('stopped',False),pc=a2.get('pc'),guards=[g for g in a1['guards'] if g['accesses']])))
    if not a1['completed'] or not a2.get('stopped'):raise SystemExit(1)


if __name__=='__main__':main()
