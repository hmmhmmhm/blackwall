"""Resume pinned original retention staging into the next strict hardware boundary."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from run_renode_m55_probe import execute
from native_replay import IMAGE

POST='''
try:
    if not reset_hold.Seen or not m.IsPaused or int(cpu.PC.RawValue)!=0x44df60 or int(g.CpuNormalSleep.CpdValue)!=0x22:raise ValueError('Need original qualified retention return')
    reset_hold.Detach()
    preparation_start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    reset_emulation.StartAll();preparation_deadline=time.time()+30
    while not m.IsPaused and time.time()<preparation_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-preparation_start<2000000000:time.sleep(0.002)
    m.Pause()
    preparation=reset_state()
    preparation.update(start_ticks=preparation_start,registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],cpd_value=int(g.CpuNormalSleep.CpdValue),retention_stages=int(g.CpuNormalSleep.RetentionStages),scr=int(b.ReadDoubleWord(0xe000ed10)),ccr=int(cpu.ConfigurationAndControlRegister),cpu_helper=dict(power_reads=int(g.CpuNormalSleep.PowerControlReads),cpd_reads=int(g.CpuNormalSleep.CpdReads),cpd_writes=int(g.CpuNormalSleep.CpdWrites),flushes=int(g.CpuNormalSleep.FlushReads)),guard_detail=[dict(name=x['name'],accesses=int(m['sysbus.'+x['name']].AccessCount),address=int(m['sysbus.'+x['name']].LastAddress),width=int(m['sysbus.'+x['name']].LastWidth),value=int(m['sysbus.'+x['name']].LastValue),operation=str(m['sysbus.'+x['name']].LastOperation)) for x in result['guards']],host_pc_or_register_seed=False,hardware_accessed=False)
    File.WriteAllBytes('/work-output/retention-preparation-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    File.WriteAllText('/work-output/retention-preparation.json',json.dumps(preparation));Console.WriteLine('BLACKWALL_RETENTION_PREPARATION '+json.dumps(preparation))
except Exception as error:Console.WriteLine('BLACKWALL_RETENTION_PREPARATION_ERROR '+str(error))
'''

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clone(a,b):
    v=subprocess.run(['cp','-c',str(a),str(b)],capture_output=True)
    if v.returncode:shutil.copyfile(a,b)

def build(s,out,idle_controls=False,inactive_audio=False,retention_flush=False,finish_sleep=False,restart_app=False):
    if restart_app and not finish_sleep:raise ValueError('App restart requires original sleep return')
    if finish_sleep and not retention_flush:raise ValueError('Sleep return requires retention flush profile')
    if retention_flush and not (idle_controls and inactive_audio):raise ValueError('Retention flush requires declared timer and audio profiles')
    if out.exists() or not out.resolve().is_relative_to(s.resolve()) or shutil.disk_usage(s).free<1024**3:raise ValueError('Use fresh private output with at least 1 GiB free')
    ref=s/'cpu-retention-staging-native-02';manifest=s/'cpu-retention-staging-research-01/manifest.json'
    if sha(manifest)!='e963eba901edde5f8dcedb6a78495c26d3f44d9436ed95971e7bacf34abaa547':raise ValueError('Changed retention acceptance pin')
    pins=json.loads(manifest.read_text())['files'];inputs=json.loads((ref/'connection-inputs.json').read_text())
    out.mkdir(mode=0o700,parents=True);(out/'exports').mkdir(mode=0o700)
    for n in set(inputs)|{'connection-inputs.json','retention-profile.json','reset-profile.json'}:
        pin=pins[str((ref/n).relative_to(s))]
        if sha(ref/n)!=pin['sha256'] or (ref/n).stat().st_size!=pin['bytes']:raise ValueError('Changed source input '+n)
        clone(ref/n,out/n)
    if idle_controls:
        from retention_preparation_models import compose_timer_controls
        p=out/'strict.cs';p.write_text(compose_timer_controls(p.read_text()))
        p=out/'board.repl';text=p.read_text();anchor='Miscellaneous.BlackwallTimer14 @ none\n'
        if text.count(anchor)!=1:raise ValueError('Unknown TIMER owner')
        p.write_text(text.replace(anchor,anchor+'    idleChannelControls: true\n'))
    if inactive_audio:
        from retention_preparation_models import compose_inactive_audio
        p=out/'strict.cs';p.write_text(compose_inactive_audio(p.read_text()))
        p=out/'board.repl';text=p.read_text();anchor='cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n'
        if text.count(anchor)!=1:raise ValueError('Unknown CPU power preparation owner')
        p.write_text(text.replace(anchor,anchor+'    inactiveAudioStatus: true\n'))
    if retention_flush:
        from retention_preparation_models import compose_retention_flush
        p=out/'strict.cs';p.write_text(compose_retention_flush(p.read_text()))
        p=out/'board.repl';text=p.read_text();anchor='cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n'
        p.write_text(text.replace(anchor,anchor+'    retentionFlush: true\n'))
        src=Path(__file__).with_name('renode-sleep-transition-observer.cs');clone(src,out/src.name)
        with (out/'activation.cs').open('ab') as f:f.write(b'\n'+src.read_bytes())
        inputs[src.name]=sha(out/src.name)
    post=POST
    if retention_flush:
        before="    reset_hold.Detach()\n"
        after="""    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallSleepTransitionObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallSleepTransitionObserver
    sleep_transition=BlackwallSleepTransitionObserver(m,cpu,m['sysbus.nvic'],int(b.ReadDoubleWord(0x4380c0))&~1)
    wfi_return=BlackwallResetEntryObserver(m,cpu,0x44e176)
    reset_hold.Detach()
"""
        post=post.replace(before,after).replace('preparation.update(', 'preparation.update(initial_masked_interrupt=bool(sleep_transition.InitialMaskedInterruptPresent),initial_nvic_irq=bool(sleep_transition.InitialIrq),masked_interrupt=bool(m[\'sysbus.nvic\'].MaskedInterruptPresent),timer_isr=int(sleep_transition.TimerIsr),retention_flushes=int(g.CpuNormalSleep.RetentionFlushes),wfi_return_seen=bool(wfi_return.Seen),sleep_events=[[int(x) for x in row] for row in sleep_transition.Events],sleep_overflow=bool(sleep_transition.Overflow),deep_sleep_level=bool(m[\'sysbus.nvic\'].InDeepSleep.IsSet),')
    if inactive_audio:post=post.replace('preparation.update(', 'preparation.update(audio_status_reads=int(g.CpuNormalSleep.AudioStatusReads),')
    if idle_controls:post=post.replace('preparation.update(', 'preparation.update(idle_control_reads=[int(x) for x in g.Timer14.IdleControlReads],selected_timer_controls=[int(g.Timer14.Timer0Control),int(g.Timer14.Timer7Control),int(g.Timer14.Control)],')
    if finish_sleep:
        post+='''
try:
    if not wfi_return.Seen or not m.IsPaused:raise ValueError('Need original WFI completion boundary')
    wfi_return.Detach()
    original_sleep_return=BlackwallResetEntryObserver(m,cpu,0x4765e2)
    sleep_return_start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);sleep_return_deadline=time.time()+20
    reset_emulation.StartAll()
    while not m.IsPaused and time.time()<sleep_return_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-sleep_return_start<1000000000:time.sleep(0.001)
    m.Pause();sleep_return=reset_state()
    sleep_return.update(return_seen=bool(original_sleep_return.Seen),cpd_value=int(g.CpuNormalSleep.CpdValue),scr=int(b.ReadDoubleWord(0xe000ed10)),masked_interrupt=bool(m['sysbus.nvic'].MaskedInterruptPresent),sleep_events=[[int(x) for x in row] for row in sleep_transition.Events],sleep_overflow=bool(sleep_transition.Overflow),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],guard_detail=[dict(name=x['name'],accesses=int(m['sysbus.'+x['name']].AccessCount),address=int(m['sysbus.'+x['name']].LastAddress),width=int(m['sysbus.'+x['name']].LastWidth),value=int(m['sysbus.'+x['name']].LastValue),operation=str(m['sysbus.'+x['name']].LastOperation)) for x in result['guards']])
    File.WriteAllBytes('/work-output/original-sleep-return-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    File.WriteAllText('/work-output/original-sleep-return.json',json.dumps(sleep_return));Console.WriteLine('BLACKWALL_ORIGINAL_SLEEP_RETURN '+json.dumps(sleep_return))
except Exception as error:Console.WriteLine('BLACKWALL_ORIGINAL_SLEEP_RETURN_ERROR '+str(error))
'''
    if restart_app:
        from retention_restart_app_scenario import POST as APP_POST
        post+=APP_POST
    p=out/'run.py';p.write_text(p.read_text()+post)
    for n in inputs:inputs[n]=sha(out/n)
    (out/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    (out/'preparation-source.json').write_text(json.dumps(dict(reference=str(ref.relative_to(s)),manifest_sha256=sha(manifest),model_unchanged=sha(out/'strict.cs')==sha(ref/'strict.cs'),main_unchanged=sha(out/'main.bin')==sha(ref/'main.bin'),only_execution_change='detach owned retention-return observation and resume',idle_controls=idle_controls,inactive_audio=inactive_audio,retention_flush=retention_flush,finish_sleep=finish_sleep,restart_app=restart_app,hardware_accessed=False),indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--prepare-only',action='store_true');p.add_argument('--idle-controls',action='store_true');p.add_argument('--inactive-audio',action='store_true');p.add_argument('--retention-flush',action='store_true');p.add_argument('--finish-sleep',action='store_true');p.add_argument('--restart-app',action='store_true');a=p.parse_args();build(a.simulator,a.output,a.idle_controls,a.inactive_audio,a.retention_flush,a.finish_sleep,a.restart_app)
    if a.prepare_only:return
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=240)
    r=json.loads((a.output/'exports/retention-preparation.json').read_text());print(json.dumps(dict(pc=hex(r['pc']),guards=[g for g in r['guard_detail'] if g['accesses']],cpd=r['cpd_value'])))
    if a.finish_sleep and not (a.output/'exports/original-sleep-return.json').exists():raise ValueError('Missing original sleep return capture')
    if a.restart_app and not (a.output/'exports/restart-app.json').exists():raise ValueError('Missing original app restart capture')
if __name__=='__main__':main()
