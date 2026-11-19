"""Pinned original ATT run followed by an external NVIC SYSRESETREQ input, without PC seeding."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from run_renode_m55_probe import execute
from native_replay import IMAGE

POST='''
try:
    from Antmicro.Renode.Time import TimeInterval
    from System.Security.Cryptography import SHA256
    from System import BitConverter
    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallResetEntryObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallResetEntryObserver
    def digest(data):return str(BitConverter.ToString(SHA256.Create().ComputeHash(data))).replace('-','').lower()
    def reset_nor():
        window=g.Mspi1Config.Pio.ArrayBacking;ok,data=window.TryRead(window.Start,window.Length)
        if not ok:raise ValueError('Missing NOR backing')
        return digest(data)
    def reset_state():
        return dict(nor_kv_sha256=reset_nor(),pio_busy=bool(g.Mspi1Config.Pio.Busy),pio_program_busy=bool(g.Mspi1Config.Pio.ProgramBusy),pio_erase_busy=bool(g.Mspi1Config.Pio.EraseBusy),pc=int(cpu.PC.RawValue),sp=int(cpu.GetRegister(13).RawValue),vtor=int(cpu.VectorTableOffset),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),paused=bool(m.IsPaused),halted=bool(cpu.IsHalted),nvic_reset_count=int(m['sysbus.nvic'].ResetCompletions),basepri=int(m['sysbus.nvic'].BASEPRI_NS),sram_sha256=digest(b.ReadBytes(0x20000000,0x380000,True)),itcm_sha256=digest(b.ReadBytes(0,0x40000,True)),rtc=dict(date=str(g.Rtc.VirtualDate),commits=int(g.Rtc.Commits),pending=bool(g.Rtc.WritePending)),guards=[dict(name=x['name'],accesses=int(m['sysbus.'+x['name']].AccessCount),address=int(m['sysbus.'+x['name']].LastAddress)) for x in result['guards']],memory=dict(violations=int(memory_policy.Violations),operation=str(memory_policy.LastOperation),address=int(memory_policy.LastAddress),written=int(memory_policy.WrittenBytes)),system_control=dict(violations=int(system_control.Violations),icache=bool(system_control.ICacheEnabled)),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),peer=dict(state=str(peer.State),commands=int(peer.CommandsAccepted),events=int(peer.RuntimeEventsConsumed)))
    before=reset_state()
    File.WriteAllBytes('/work-output/system-reset-before-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    if not app.Stopped or not m.IsPaused or any(x['accesses'] for x in before['guards']) or before['cfsr'] or before['hfsr'] or before['memory']['violations']:raise ValueError('Need clean original ATT application return')
    reset_entry=int(b.ReadDoubleWord(0x438004))&~1
    reset_observer=BlackwallResetEntryObserver(m,cpu,reset_entry)
    reset_emulation=EmulationManager.Instance.CurrentEmulation
    reset_emulation.PauseAll()
    b.WriteDoubleWord(0xe000ed0c,0x05fa0004)
    reset_emulation.StartAll();reset_deadline=time.time()+10
    while not reset_observer.Seen and time.time()<reset_deadline:time.sleep(0.001)
    m.Pause()
    entry=reset_state()
    File.WriteAllBytes('/work-output/system-reset-entry-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    reset_observer.Detach()
    File.WriteAllText('/work-output/system-reset-entry.json',json.dumps(dict(before=before,entry=entry,entry_seen=bool(reset_observer.Seen),expected_entry=reset_entry,expected_sp=int(b.ReadDoubleWord(0x438000)),request=dict(address=0xe000ed0c,value=0x05fa0004,origin='external virtual NVIC device input'),host_pc_or_register_seed=False,original_firmware_executed=True,hardware_accessed=False)))
    Console.WriteLine('BLACKWALL_ORIGINAL_RESET_ENTRY '+json.dumps(dict(seen=bool(reset_observer.Seen),pc=entry['pc'],resets=entry['nvic_reset_count'])))
    if not reset_observer.Seen:raise ValueError('No original reset entry')
    reset_start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);reset_deadline=time.time()+15
    reset_emulation.StartAll()
    while not m.IsPaused and time.time()<reset_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-reset_start<20000000:time.sleep(0.001)
    m.Pause()
    after=reset_state();File.WriteAllText('/work-output/system-reset-after.json',json.dumps(after));File.WriteAllBytes('/work-output/system-reset-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    Console.WriteLine('BLACKWALL_ORIGINAL_RESET_AFTER '+json.dumps(after))
    reset_hold=BlackwallUiActivationHold(m,cpu,p['getter'])
    reset_start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);reset_deadline=time.time()+85
    reset_emulation.StartAll()
    while not m.IsPaused and time.time()<reset_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-reset_start<10000000000:time.sleep(0.005)
    m.Pause();later=reset_state();later['held']=bool(reset_hold.Held)
    File.WriteAllText('/work-output/system-reset-later.json',json.dumps(later));File.WriteAllBytes('/work-output/system-reset-later-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    Console.WriteLine('BLACKWALL_ORIGINAL_RESET_LATER '+json.dumps(later))
except Exception as error:Console.WriteLine('BLACKWALL_ORIGINAL_SYSTEM_RESET_ERROR '+str(error))
'''

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def build(s,out,case):
    if case!='stock24':raise ValueError('Original reset integration currently requires the audited stock24 profile')
    ref=s/'runtime-att-acceptance-native-01'/case
    manifest=s/'runtime-att-research-01/manifest.json'
    expected='a139c04c4c277f183d9ef9a8f7ab612bd3cc59cc5ed2beb6cfc9cbe7cca6fa3c'
    if sha(manifest)!=expected:raise ValueError('Changed E13 evidence manifest')
    pins=json.loads(manifest.read_text())['files']
    if sha(ref/'capture-files.json')!=pins[str((ref/'capture-files.json').relative_to(s))]:raise ValueError('Changed reference capture')
    capture=json.loads((ref/'capture-files.json').read_text())['files']
    inputs=json.loads((ref/'connection-inputs.json').read_text())
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'exports').mkdir(mode=0o700)
    for n in set(inputs)|{'connection-inputs.json'}:
        if sha(ref/n)!=capture[n]:raise ValueError('Changed input '+n)
        shutil.copyfile(ref/n,out/n)
    for n in ('renode-reset-aware-nvic.cs','renode-reset-entry-observer.cs'):
        shutil.copyfile(Path(__file__).with_name(n),out/n)
        with (out/'activation.cs').open('ab') as f:f.write(b'\n'+(out/n).read_bytes())
    p=out/'board.repl';text=p.read_text();anchor='    PerformanceInMips: 10\n'
    if text.count(anchor)!=1 or text.count('nvic: IRQControllers.NVIC @')!=1:raise ValueError('Unknown original board')
    text=text.replace(anchor,anchor+'    InitVectorTableOffset: 0x438000\n').replace('nvic: IRQControllers.NVIC @','nvic: Miscellaneous.BlackwallResetAwareNVIC @');p.write_text(text)
    p=out/'run.py';p.write_text(p.read_text()+POST)
    for n in set(inputs)|{'renode-reset-aware-nvic.cs','renode-reset-entry-observer.cs'}:inputs[n]=sha(out/n)
    (out/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    (out/'reset-profile.json').write_text(json.dumps(dict(case=case,reference=str(ref.relative_to(s)),reference_manifest_sha256=expected,main_sha256=sha(out/'main.bin'),request='external SYSRESETREQ',existing_reset_domain='unmodified peripheral Reset methods; RAM and NOR backing retained; RTC source resets to year2000; diagnostic helpers not registered for reset',e06_complete=False),indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--case',choices=('stock24',),default='stock24');p.add_argument('--prepare-only',action='store_true');a=p.parse_args();build(a.simulator,a.output,a.case)
    if a.prepare_only:return
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=240)
    for n in ('system-reset-entry.json','system-reset-after.json','system-reset-later.json'):
        if not (a.output/'exports'/n).exists():raise ValueError('Missing native reset capture '+n)
        print(n,True)
    from verify_original_system_reset import verify
    report=verify(a.output,a.output/'reset-audit')
    print(json.dumps(dict(passed=report['passed'],checks=len(report['checks']),e06_complete=False)))

if __name__=='__main__':main()
