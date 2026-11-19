"""Replay a fresh ARM main with only committed virtual NOR retained."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from kvtime_layout import discover

from native_replay import IMAGE
from run_renode_m55_probe import execute
from run_runtime_connection_m55 import pin_capture, inspect


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source, output, simulator, retained):
    if output.exists() or not output.resolve().is_relative_to(simulator.resolve()):
        raise ValueError('Use a new private output')
    pins = json.loads((source/'capture-files.json').read_text())['files']
    for name, expected in pins.items():
        path=source/name
        if not path.resolve().is_relative_to(source.resolve()) or digest(path)!=expected:
            raise ValueError('Source capture changed')
    profile=json.loads((source/'connection-profile.json').read_text())
    if profile['case'] not in ('stock24','stock23','cfw') or not profile.get('att_time'):
        raise ValueError('Use a reviewed original-three time scenario')
    layout=discover((source/'main.bin').read_bytes(),profile)
    old=(simulator/'kvtime-persistent-research-01/before-renode-mspi1-pio.cs').read_text()
    component=Path(__file__).with_name('renode-mspi1-pio.cs').read_text()
    model=(source/'strict.cs').read_text()
    if model.count(old)!=1:
        if model.count(component)==1:
            old=component
        else:
            raise ValueError('Source NOR component differs')
    runtime=(source/'run.py').read_text()
    start='    e.StartAll()\n'
    if runtime.count(start)!=1:raise ValueError('Unknown first CPU start')
    inputs=json.loads((source/'connection-inputs.json').read_text())
    if not set(inputs).issubset(pins):raise ValueError('Unpinned source input')
    output.mkdir(mode=0o700,parents=True);(output/'exports').mkdir()
    for name in inputs:
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        result=subprocess.run(['cp','-c',str(source/name),str(target)],capture_output=True)
        if result.returncode:shutil.copyfile(source/name,target)
    (output/'strict.cs').write_text(model.replace(old,component))
    profile['model_sha256']=digest(output/'strict.cs')
    (output/'connection-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    import_inputs=[]
    if retained:
        for name in ['kv-nv','littlefs']:
            source_image=source/('exports/nor-after-'+name+'.bin')
            if str(source_image.relative_to(source)) not in pins:raise ValueError('Missing committed source image')
            target=output/('retained-'+name+'.bin')
            result=subprocess.run(['cp','-c',str(source_image),str(target)],capture_output=True)
            if result.returncode:shutil.copyfile(source_image,target)
            import_inputs.append(target.name)
        load='''    from System.IO import File
    from System import Console
    if int(m['sysbus.cpu'].ExecutedInstructions)!=0:raise ValueError('Persistent import must precede ARM execution')
    fresh_before=m.SystemBus.ReadBytes(0x20000000,0x380000,True)
    kv_pio=m['sysbus.guard'].Mspi1Config.Pio
    for name,w in [('kv-nv',kv_pio.ArrayBacking),('littlefs',kv_pio.ArrayBacking.AdditionalWindow)]:
        w.LoadCommittedImage(File.ReadAllBytes('/work/retained-'+name+'.bin'))
    fresh_after=m.SystemBus.ReadBytes(0x20000000,0x380000,True)
    if bytearray(fresh_before)!=bytearray(fresh_after):raise ValueError('Persistent import changed volatile SRAM')
    File.WriteAllBytes('/work-output/fresh-sram-before-cpu.bin',fresh_after)
    Console.WriteLine('BLACKWALL_RETAINED_IMPORT '+json.dumps(dict(cpu_instructions=0,sram_unchanged=True,windows=2)))
'''
        runtime=runtime.replace(start,load+start)
        post="\ntry:\n    import clr,time,json\n"
        if runtime.count(post)!=1:raise ValueError('Unknown device runtime boundary')
        runtime=runtime.split(post)[0]+'''
try:
    import json
    from System import Console
    from System.IO import File
    m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];q=g.Mspi1Config.Pio;cpu=m['sysbus.cpu']
    File.WriteAllBytes('/work-output/restart-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    record=[int(x) for x in b.ReadBytes(0x2000690c,12,True)]
    state=[int(x) for x in b.ReadBytes(0x200076b4,8,True)]
    for name,w in [('kv-nv',q.ArrayBacking),('littlefs',q.ArrayBacking.AdditionalWindow)]:
        ok,data=w.TryRead(w.Start,w.Length)
        if not ok:raise ValueError('NOR readback failed')
        File.WriteAllBytes('/work-output/restart-nor-'+name+'.bin',data)
    r=dict(held=bool(activation_hold.Held),paused=bool(m.IsPaused),pc=int(cpu.PC.RawValue),record=record,state=state,programs=int(q.PageProgramCompletions),program_bytes=int(q.ProgramBytesCommitted),erases=int(q.SectorEraseCompletions),array_reads=int(q.ArrayReadTransfers),snapshot_loaded=bool(q.ArrayBacking.SnapshotLoaded) and bool(q.ArrayBacking.AdditionalWindow.SnapshotLoaded),rtc=dict(commits=int(g.Rtc.Commits),date=str(g.Rtc.VirtualDate)),memory_violations=int(memory_policy.Violations),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)))
    File.WriteAllText('/work-output/restart.json',json.dumps(r))
    Console.WriteLine('BLACKWALL_RUNTIME_KV_RESTART '+json.dumps(r))
except Exception as ex:
    print('BLACKWALL_KV_RESTART_ERROR '+str(ex))
'''
    runtime=runtime.replace('b.ReadBytes(0x2000690c,12,True)','b.ReadBytes('+str(layout['record'])+',12,True)')
    runtime=runtime.replace('b.ReadBytes(0x200076b4,8,True)','b.ReadBytes('+str(layout['state'])+',8,True)')
    (output/'run.py').write_text(runtime)
    metadata=dict(source_capture_sha256=digest(source/'capture-files.json'),retained=retained,
                  changed_component_before=hashlib.sha256(old.encode()).hexdigest(),
                  changed_component_after=hashlib.sha256(component.encode()).hexdigest(),
                  retained_inputs={name:digest(output/name) for name in import_inputs},
                  layout=layout,volatile_inputs_reused_from_initial_profile=True,previous_guest_sram_imported=False)
    (output/'restart-source.json').write_text(json.dumps(metadata,indent=2)+'\n')
    names=set(inputs)|set(import_inputs)|{'restart-source.json'}
    (output/'connection-inputs.json').write_text(json.dumps({name:digest(output/name) for name in sorted(names)},indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator',type=Path);parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--retained',action='store_true');args=parser.parse_args()
    build(args.source,args.output,args.simulator,args.retained)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128',
             '--cap-drop','ALL','--security-opt','no-new-privileges',
             '--mount',f'type=bind,source={args.output},target=/work,readonly',
             '--mount',f'type=bind,source={args.output}/exports,target=/work-output',IMAGE,
             '--disable-gui','--console','-p','-e','quit','/work/probe.resc'],args.output,'renode',timeout=180)
    pin_capture(args.output)
    if args.retained:
        result=json.loads((args.output/'exports/restart.json').read_text())
        profile=json.loads((args.output/'connection-profile.json').read_text())
        passed=result['held'] and result['paused'] and result['pc']==profile['getter'] and result['snapshot_loaded']
        print(json.dumps(dict(restart_reached_hold=passed,record=result['record'],rtc=result['rtc'])))
        if not passed:raise SystemExit(1)
    else:
        result=inspect(args.output);print(json.dumps(dict(passed=result['passed'],checks=len(result['checks']))))
        if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
