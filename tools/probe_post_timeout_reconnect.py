"""Resume pinned original healthy-stop into credit restoration and a new virtual connection."""
import argparse
import json
from pathlib import Path
import shutil
from run_runtime_connection_m55 import sha,pin_capture
from verify_kv_persistence_cycle import validate_capture
from run_renode_m55_probe import execute
from native_replay import IMAGE

POST='''
try:
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallRuntimeConnectionObserver
    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallHciCreditObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallHciCreditObserver
    def recovery_state():
        return dict(ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pc=int(cpu.PC.RawValue),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],credit=int(b.ReadByte(c['credit'])),opcode=int(b.ReadWord(c['opcode'])),timer=[int(x) for x in b.ReadBytes(c['timer'],16,True)],guards=guard_state(),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),generation=int(peer.ControllerGeneration),rejection=str(peer.ResetGenerationRejection),peer=dict(state=str(peer.State),commands=int(peer.CommandsAccepted),replies=int(peer.Replies),events=int(peer.RuntimeEventsConsumed),pending=bool(peer.RuntimeEventPending)),gpio=dict(irq=bool(q.IRQ.IsSet),pending=bool(q.Pending117),edges=int(q.RisingEdges)),gaf=gaf_snapshot(),rtc=dict(commits=int(g.Rtc.Commits),date=str(g.Rtc.VirtualDate),pending=bool(g.Rtc.WritePending),error=str(g.Rtc.LastError)),hardware_accessed=False)
    def clean(v):return not any(x['accesses'] for x in v['guards']) and v['cfsr']==v['hfsr']==v['memory_violations']==0
    initial=recovery_state()
    if not m.IsPaused or not diag.HealthyStop or initial['pc']!=c['healthy_stop_pc'] or initial['credit']!=0 or not clean(initial):raise ValueError('Need clean original healthy stop with credit zero')
    creditdiag=BlackwallHciCreditObserver(m,cpu,c['timer'],p['tcb_slot'])
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+20
    while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-initial['ticks']<100000000:time.sleep(0.001)
    m.Pause();credit=recovery_state();credit.update(before=int(creditdiag.Before),after=int(creditdiag.After),stopped=bool(creditdiag.Stopped),start_ticks=int(creditdiag.Started),finish_ticks=int(creditdiag.Finished),context=[int(x) for x in creditdiag.Context],observed_timer=[int(x) for x in creditdiag.Timer])
    File.WriteAllBytes('/work-output/credit-restored-sram.bin',b.ReadBytes(0x20000000,0x380000,True));File.WriteAllText('/work-output/credit-restored.json',json.dumps(credit));Console.WriteLine('BLACKWALL_CREDIT_RESTORED '+json.dumps(credit))
    if not credit['stopped'] or credit['credit']!=1 or not clean(credit):raise ValueError('Original credit restoration did not complete cleanly')
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+20
    while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-credit['ticks']<100000000:time.sleep(0.001)
    m.Pause();settled=recovery_state()
    File.WriteAllBytes('/work-output/recovery-settled-sram.bin',b.ReadBytes(0x20000000,0x380000,True));File.WriteAllText('/work-output/recovery-settled.json',json.dumps(settled));Console.WriteLine('BLACKWALL_RECOVERY_SETTLED '+json.dumps(settled))
    if not clean(settled) or settled['credit']!=1 or settled['peer']['events']!=0 or settled['peer']['state']!='Complete':raise ValueError('Recovery did not settle cleanly')
    reconnectdiag=BlackwallRuntimeConnectionObserver(m,cpu,p['gpio']['isr'],p['opened'],p['finished'],p['tcb_slot'])
    accepted=bool(peer.TryQueueRuntimeConnection());input=dict(accepted=accepted,ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pc=int(cpu.PC.RawValue),irq=bool(q.IRQ.IsSet),pending=bool(q.Pending117))
    if not accepted:raise ValueError('New generation connection preconditions rejected')
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+30
    while not m.IsPaused and not reconnectdiag.Stopped and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-input['ticks']<2000000000:time.sleep(0.001)
    m.Pause();connected=recovery_state();connected.update(input=input,stopped=bool(reconnectdiag.Stopped),entry=[int(x) for x in reconnectdiag.Entry],exit=[int(x) for x in reconnectdiag.Exit],calls=int(reconnectdiag.OpenCalls),irq_entries=int(reconnectdiag.IrqEntries))
    File.WriteAllBytes('/work-output/recovery-reconnect-sram.bin',b.ReadBytes(0x20000000,0x380000,True));File.WriteAllText('/work-output/recovery-reconnect.json',json.dumps(connected));Console.WriteLine('BLACKWALL_RECOVERY_RECONNECT '+json.dumps(connected))
except Exception as error:Console.WriteLine('BLACKWALL_RECOVERY_RECONNECT_ERROR '+str(error))
'''

def build(s,out):
    ref=s/'post-reset-advertising-native-02';validate_capture(ref);pins=json.loads((s/'post-reset-advertising-research-01/manifest.json').read_text())['files']
    if out.exists():raise ValueError('Preserve existing run')
    out.mkdir(mode=0o700,parents=True);(out/'exports').mkdir(mode=0o700)
    inputs=json.loads((ref/'connection-inputs.json').read_text())
    for n in set(inputs)|{'connection-inputs.json'}:
        pin=pins[str((ref/n).relative_to(s))]
        if sha(ref/n)!=pin['sha256'] or (ref/n).stat().st_size!=pin['bytes']:raise ValueError('Changed fixed recovery input')
        shutil.copyfile(ref/n,out/n)
    src=Path(__file__).with_name('renode-hci-credit-observer.cs');(out/src.name).write_bytes(src.read_bytes())
    with (out/'activation.cs').open('ab') as f:f.write(b'\n'+src.read_bytes())
    p=out/'run.py';p.write_text(p.read_text()+POST)
    for n in set(inputs)|{src.name}:inputs[n]=sha(out/n)
    (out/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build(a.simulator,a.output)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=360)
    pin_capture(a.output);v=json.loads((a.output/'exports/recovery-reconnect.json').read_text());print(json.dumps(dict(stopped=v['stopped'],pc=hex(v['pc']),credit=v['credit'],peer=v['peer'],guards=[x for x in v['guards'] if x['accesses']])))

if __name__=='__main__':main()
