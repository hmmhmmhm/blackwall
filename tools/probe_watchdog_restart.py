"""Continue original stock main after its actual watchdog reset, without CPU seeding."""
import argparse,json,hashlib
from pathlib import Path
from probe_watchdog_reset_entry import build as entry_build
from reset_restart_profiles import RENODE_IMAGE,profile,pin,read,PREPARATION_PIN
from run_renode_m55_probe import execute

POST='''
try:
    if not reset_entry_observer.Seen or not m.IsPaused:raise ValueError('Need actual original watchdog reset entry')
    reset_entry_observer.Detach()
    restart_hold=BlackwallUiActivationHold(m,cpu,p['getter'])
    restart_start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);restart_deadline=time.time()+100
    EmulationManager.Instance.CurrentEmulation.StartAll()
    while not m.IsPaused and time.time()<restart_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-restart_start<15000000000:time.sleep(0.005)
    m.Pause()
    restart=dict(held=bool(restart_hold.Held),pc=int(cpu.PC.RawValue),sp=int(cpu.GetRegister(13).RawValue),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),start_ticks=restart_start,deliveries=int(reset_gate.WatchdogResetDeliveries),nvic_resets=int(m['sysbus.nvic'].ResetCompletions),virtual_boot_status=int(reset_gate.VirtualBootStatus),wdt_configuration=int(watchdog.Configuration),wdt_restarts=int(watchdog.Restarts),peer=dict(state=str(peer.State),commands=int(peer.CommandsAccepted),runtime_events=int(peer.RuntimeEventsConsumed)),cpu_power=dict(cpd=int(g.CpuNormalSleep.CpdValue)),guards=[dict(name=x['name'],accesses=int(m['sysbus.'+x['name']].AccessCount),address=int(m['sysbus.'+x['name']].LastAddress),width=int(m['sysbus.'+x['name']].LastWidth),value=int(m['sysbus.'+x['name']].LastValue),operation=str(m['sysbus.'+x['name']].LastOperation)) for x in result['guards']],memory_violations=int(memory_policy.Violations),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),rtc=dict(date=str(g.Rtc.VirtualDate),commits=int(g.Rtc.Commits)),host_pc_register_seed=False,hardware_accessed=False)
    File.WriteAllBytes('/work-output/watchdog-restart-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    File.WriteAllText('/work-output/watchdog-restart.json',json.dumps(restart));Console.WriteLine('BLACKWALL_WATCHDOG_RESTART '+json.dumps(restart))
except Exception as error:Console.WriteLine('BLACKWALL_WATCHDOG_RESTART_ERROR '+str(error))
'''

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(s,o,retention=False,restart_app=False,completed_entry_pause=True):
 if restart_app and not retention:raise ValueError('App restart requires verified retention profile')
 meta=entry_build(s,o)
 if completed_entry_pause:
  from reset_entry_pause_contract import completed_pause
  source=Path(__file__).with_name('renode-reset-entry-observer.cs').read_text();activation=(o/'activation.cs').read_text()
  if activation.count(source)!=1:raise ValueError('Expected one owned reset-entry observer')
  (o/'activation.cs').write_text(activation.replace(source,completed_pause(source),1))
  runtime=(o/'run.py').read_text();old='    while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start_ticks<300000*int(TimeInterval.TicksPerMillisecond):'
  if runtime.count(old)!=1:raise ValueError('Unknown reset entry wait condition')
  runtime=runtime.replace(old,old.replace('not m.IsPaused','not reset_entry_observer.Seen and not m.IsAborted'),1)
  old="    stop_reason='natural-timeout-caller'"
  if runtime.count(old)!=1:raise ValueError('Unknown entry completion boundary')
  runtime=runtime.replace(old,"    if not reset_entry_observer.Seen:raise ValueError('Reset entry pause did not complete')\n"+old,1)
  (o/'run.py').write_text(runtime);meta['completed_entry_pause']=True

 if retention:
  manifest=s/'cpu-retention-preparation-research-01/manifest.json';common=s/'cpu-retention-preparation-native-06'
  if sha(manifest)!=PREPARATION_PIN:raise ValueError('Changed retention profile acceptance')
  pin(s,read(manifest),common/'strict.cs');known=(common/'strict.cs').read_text();model=(o/'strict.cs').read_text();parts=[]
  for start,end in [('    public sealed class BlackwallCpuNormalSleep : IPeripheral','    public class BlackwallPeripheralPower'),('    public sealed class BlackwallTimer14 : IBlackwallTimer14','\n    }\n}')]:
   def region(text):
    a=text.index(start);b=text.index(end,a);return text[a:b] if end.startswith('    public') else text[a:b+len('\n    }')]
   old=region(model);new=region(known)
   if model.count(old)!=1 or old==new:raise ValueError('Unknown distinct retention component')
   model=model.replace(old,new,1);parts.append(dict(component=start.strip(),sha256=hashlib.sha256(new.encode()).hexdigest()))
  (o/'strict.cs').write_text(model);p=profile(s,'stock24',(o/'main.bin').read_bytes());board=(o/'board.repl').read_text()
  for old,new in [('cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n','cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n    retentionFlush: true\n    inactiveAudioStatus: true\n    retentionStorePc: '+hex(p['retention_store'])+'\n    retentionReturnPc: '+hex(p['retention_return'])+'\n'),('Miscellaneous.BlackwallTimer14 @ none\n','Miscellaneous.BlackwallTimer14 @ none\n    idleChannelControls: true\n')]:
   if board.count(old)!=1:raise ValueError('Unknown retention board contract')
   board=board.replace(old,new,1)
  (o/'board.repl').write_text(board);meta['retention']=dict(manifest=PREPARATION_PIN,components=parts)
 with (o/'run.py').open('a') as f:f.write(POST)
 if restart_app:
  pin(s,read(manifest),common/'run.py')
  from retention_restart_app_scenario import POST as accepted_app_post
  if not (common/'run.py').read_text().endswith(accepted_app_post):raise ValueError('Changed pinned app scenario')
  offset=accepted_app_post.index('    new_connection=BlackwallRuntimeConnectionObserver')
  helper="""
try:
    if not restart_hold.Held or not m.IsPaused or any(x['accesses'] for x in restart['guards']) or restart['cfsr'] or restart['hfsr'] or restart['memory_violations']:raise ValueError('Original services did not restart cleanly')
    reset_emulation=EmulationManager.Instance.CurrentEmulation
    def reset_state():
        return dict(pc=int(cpu.PC.RawValue),sp=int(cpu.GetRegister(13).RawValue),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),nvic_reset_count=int(m['sysbus.nvic'].ResetCompletions),watchdog_deliveries=int(reset_gate.WatchdogResetDeliveries),virtual_boot_status=int(reset_gate.VirtualBootStatus),guards=[dict(name=x['name'],accesses=int(m['sysbus.'+x['name']].AccessCount),address=int(m['sysbus.'+x['name']].LastAddress)) for x in result['guards']],cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory=dict(violations=int(memory_policy.Violations)),rtc=dict(date=str(g.Rtc.VirtualDate),commits=int(g.Rtc.Commits),pending=bool(g.Rtc.WritePending)),peer=dict(state=str(peer.State),commands=int(peer.CommandsAccepted),events=int(peer.RuntimeEventsConsumed)),host_pc_register_seed=False,original_firmware_executed=True,hardware_accessed=False)
"""
  with (o/'run.py').open('a') as f:f.write(helper+accepted_app_post[offset:])
  meta['restart_app']=True
  compile((o/'run.py').read_text(),'generated-run.py','exec')
 meta['watchdog_restart']=True;(o/'watchdog-restart-profile.json').write_text(json.dumps(meta,indent=2)+'\n')
 inputs=read(o/'connection-inputs.json');inputs['watchdog-restart-profile.json']=''
 for n in inputs:inputs[n]=sha(o/n)
 (o/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');return meta
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--retention',action='store_true');p.add_argument('--restart-app',action='store_true');a=p.parse_args();build(a.simulator,a.output,a.retention,a.restart_app)
 execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=1600,stream=True)
 r=read(a.output/'exports/watchdog-restart.json');print(json.dumps(dict(held=r['held'],pc=hex(r['pc']),guards=[g for g in r['guards'] if g['accesses']],peer=r['peer'])),flush=True)
