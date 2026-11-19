"""Run original main's formatter on a non-FF sector, optionally holding erase.

Only virtual NOR is touched. Completed bytes, never old SRAM, may be retained.
"""
import argparse
import json
from pathlib import Path
import subprocess

from inspect_nor_error_propagation import body
from native_replay import IMAGE
from probe_runtime_kv_restart import build as build_model, digest
from run_renode_m55_probe import execute
from run_runtime_connection_m55 import pin_capture
from runtime_event_models import integrate_gaf
from verify_kv_persistence_cycle import validate_capture


def build(s,source,out,fault,observe,retained):
    if fault and retained:raise ValueError('Retained restart must use normal erase completion')
    build_model(source,out,s,False)
    profile=json.loads((out/'connection-profile.json').read_text())
    report_path=s/'nor-erase-propagation-01/report.json'
    manifest=json.loads((s/'nor-erase-propagation-research-01/manifest.json').read_text())
    if digest(report_path)!=manifest['files']['nor-erase-propagation-01/report.json']['sha256']:
        raise ValueError('Changed erase source contract')
    contract=next(c for c in json.loads(report_path.read_text())['cases'] if c['case']==profile['case'])
    if contract['original_main_sha256']!=digest(out/'main.bin'):raise ValueError('Different original main')
    c=contract['chain'];raw=(out/'main.bin').read_bytes()
    sites=[body(raw,c[k],n)[-1].address for k,n in [('poll',0x60),('nor',0x110),('adapter',0x150),('part',0x50),('fdb',0x30)]]
    model,gaf=integrate_gaf(s,(out/'strict.cs').read_text());(out/'strict.cs').write_text(model)
    (out/'gaf-profile.json').write_text(json.dumps(gaf,indent=2)+'\n')
    board=(out/'board.repl').read_text();anchor='    profile: "icm45608-reset-lifecycle"\n'
    if board.count(anchor)!=1 or board.count('    completeSectorErase: true\n')!=1:raise ValueError('Unknown board')
    board=board.replace(anchor,anchor+'    gafParametersHex: "'+gaf['parameters_hex']+'"\n    gafConfiguration: true\n    gafClockVariationByte: '+str(gaf['clock_variation_byte'])+'\n')
    if fault:board=board.replace('    completeSectorErase: true\n','    completeSectorErase: false\n')
    (out/'board.repl').write_text(board)
    profile.update(gaf_profile=gaf,gaf_profile_sha256=digest(out/'gaf-profile.json'),model_sha256=digest(out/'strict.cs'))
    (out/'connection-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    images=[]
    if retained:
        validate_capture(retained)
        for name in ('kv-nv','littlefs'):
            target=out/('initial-'+name+'.bin');old=retained/('exports/nor-after-'+name+'.bin')
            subprocess.run(['cp','-c',str(old),str(target)],check=True);images.append(target.name)
    else:
        (out/'initial-kv-nv.bin').write_bytes(bytes(range(256))*16+b'\xff'*(0x40000-4096));images.append('initial-kv-nv.bin')
    code=Path(__file__).with_name('renode-nor-error-observer.cs').read_bytes()
    (out/'erase-observer.cs').write_bytes(code)
    with (out/'activation.cs').open('ab') as f:f.write(b'\n'+code)
    runtime=(out/'run.py').read_text()
    boundary='\ntry:\n    import clr,time,json\n'
    if runtime.count(boundary)!=1 or runtime.count('    e.StartAll()\n')!=1:raise ValueError('Unknown boot runtime')
    runtime=runtime.split(boundary)[0]
    setup='''    from System.IO import File
    from System import Console,Array,UInt32
    eq=m['sysbus.guard'].Mspi1Config.Pio;ecpu=m['sysbus.cpu']
    if int(ecpu.ExecutedInstructions)!=0:raise ValueError('NOR import after CPU start')
    volatile_before=m.SystemBus.ReadBytes(0x20000000,0x380000,True)
    eq.ArrayBacking.LoadCommittedImage(File.ReadAllBytes('/work/initial-kv-nv.bin'))
    if RETAINED:eq.ArrayBacking.AdditionalWindow.LoadCommittedImage(File.ReadAllBytes('/work/initial-littlefs.bin'))
    volatile_after=m.SystemBus.ReadBytes(0x20000000,0x380000,True)
    if bytearray(volatile_before)!=bytearray(volatile_after):raise ValueError('NOR import changed SRAM')
    File.WriteAllBytes('/work-output/fresh-sram-before-cpu.bin',volatile_after)
    def erase_snapshot(phase):
        for name,w in [('kv-nv',eq.ArrayBacking),('littlefs',eq.ArrayBacking.AdditionalWindow)]:
            ok,data=w.TryRead(w.Start,w.Length)
            if not ok:raise ValueError('Missing NOR backing')
            File.WriteAllBytes('/work-output/nor-'+phase+'-'+name+'.bin',data)
    erase_snapshot('before')
    erase_observer=None
    if OBSERVE:
        clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallNorErrorObserver').Assembly)
        from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallNorErrorObserver
        erase_observer=BlackwallNorErrorObserver(m,ecpu,eq,SLOT,Array[UInt32](SITES),True)
    Console.WriteLine('BLACKWALL_ERASE_IMPORT '+json.dumps(dict(cpu_instructions=0,sram_unchanged=True,retained=RETAINED)))
'''.replace('RETAINED',repr(bool(retained))).replace('OBSERVE',repr(observe)).replace('SLOT',str(profile['tcb_slot'])).replace('SITES',repr(sites))
    post='''
try:
    from System import Console
    from System.IO import File
    b=m.SystemBus;g=m['sysbus.guard'];cpu=m['sysbus.cpu'];q=g.Mspi1Config.Pio
    erase_snapshot('after')
    File.WriteAllBytes('/work-output/erase-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    guards=[dict(name=name,accesses=int(m['sysbus.'+name].AccessCount),address=int(m['sysbus.'+name].LastAddress)) for name in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail')]
    result=dict(pc=int(cpu.PC.RawValue),held=bool(activation_hold.Held),paused=bool(m.IsPaused),erase_starts=int(q.SectorEraseStarts),erase_completions=int(q.SectorEraseCompletions),erase_busy=bool(q.EraseBusy),last_erase=int(q.LastEraseAddress),program_starts=int(q.PageProgramStarts),program_completions=int(q.PageProgramCompletions),program_bytes=int(q.ProgramBytesCommitted),rows=[] if erase_observer is None else [[int(v) for v in row] for row in erase_observer.Rows],observer_completed=False if erase_observer is None else bool(erase_observer.Completed),overflow=False if erase_observer is None else bool(erase_observer.Overflow),guards=guards,cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations))
    File.WriteAllText('/work-output/erase.json',json.dumps(result))
    Console.WriteLine('BLACKWALL_BOOT_ERASE '+json.dumps(result))
except Exception as error:
    Console.WriteLine('BLACKWALL_BOOT_ERASE_ERROR '+str(error))
'''
    (out/'run.py').write_text(runtime.replace('    e.StartAll()\n',setup+'    e.StartAll()\n')+post)
    meta=dict(source_capture_sha256=digest(source/'capture-files.json'),fault=fault,observe=observe,
        pattern='retained NOR' if retained else '4096-byte ramp at KV start; all other bytes FF',
        retained_source_sha256=digest(retained/'capture-files.json') if retained else None,
        initial_images={name:digest(out/name) for name in images},previous_guest_sram_imported=False,
        erase_contract_sha256=digest(report_path),return_sites=sites)
    (out/'erase-source.json').write_text(json.dumps(meta,indent=2)+'\n')
    inputs=json.loads((out/'connection-inputs.json').read_text())
    for name in set(inputs)|set(images)|{'gaf-profile.json','erase-source.json','erase-observer.cs'}:inputs[name]=digest(out/name)
    (out/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--fault',action='store_true');p.add_argument('--observe',action='store_true');p.add_argument('--retained',type=Path);a=p.parse_args()
    build(a.simulator,a.source,a.output,a.fault,a.observe,a.retained)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,
        '--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=180)
    pin_capture(a.output);r=json.loads((a.output/'exports/erase.json').read_text())
    print(json.dumps(dict(pc=hex(r['pc']),held=r['held'],erase_starts=r['erase_starts'],erase_completions=r['erase_completions'],rows=len(r['rows']))))
    if not r['held']:raise SystemExit(1)


if __name__=='__main__':main()
