"""Run original pending/clear boot paths with a bounded functional16byte ROM model."""
import argparse,json,shutil,hashlib
from pathlib import Path
from run_boot_validation import derive,classify
from run_original_boot_screen import PRIVATE,validate_runtime
from run_stock_main_mram_probe import class_source
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
FAULTS=('success','rom-error','interrupt-0','interrupt-1','stuck')


def sha(data):return hashlib.sha256(data).hexdigest()


def namespace(source,name):
    at=source.index('public sealed class '+name);start=source.rfind('namespace Antmicro.',0,at);end=source.find('\nnamespace Antmicro.',at)
    return source[start:] if end<0 else source[start:end]


def run(output,fault='success',initial_path=None):
    if fault not in FAULTS:raise ValueError('Reviewed metadata fault required')
    output=Path(output).resolve()
    initial=bytes.fromhex('55555555'+'a5'*12) if initial_path is None else Path(initial_path).resolve().read_bytes()
    if len(initial)!=16 or initial_path is not None and not Path(initial_path).resolve().is_relative_to(PRIVATE):raise ValueError('Exact private16byte persistent state required')
    command=derive('pending-rom-stuck' if fault=='stuck' else 'pending-rom-ready',output)
    strict=(output/'strict.cs').read_text()
    for cls,name in [('BlackwallMemoryPolicy','renode-memory-policy.cs'),('BlackwallOtaMarkerRead','renode-ota-marker-read.cs'),('BlackwallResetController','renode-reset-controller.cs')]:
        strict=strict.replace(namespace(strict,cls),(ROOT/'tools'/name).read_text())
    fixture=namespace(strict,'BlackwallG2StartupFixture');updated=fixture
    for sig,body in [('public override uint ReadDoubleWord(long offset)','if(PendingMramControl!=null && address>=0x40014000 && address<0x40014028)return PendingMramControl.ReadDoubleWord((long)(address-0x40014000));'),('public override void WriteDoubleWord(long offset, uint value)','if(PendingMramControl!=null && address>=0x40014000 && address<0x40014028){PendingMramControl.WriteDoubleWord((long)(address-0x40014000),value);return;}')]:
        prefix=sig+'\n        {\n            var address = baseAddress + (ulong)offset;'
        if updated.count(prefix)!=1:raise ValueError('Unique shared control owner required')
        updated=updated.replace(prefix,prefix+'\n            '+body)
    updated=updated.replace('public BlackwallMemoryStartup MemoryStartup { get; }','public BlackwallRecoveryMramControl PendingMramControl { get; set; }\n        public BlackwallMemoryStartup MemoryStartup { get; }')
    strict=strict.replace(fixture,updated)
    control=class_source((ROOT/'tools/renode-recovery-writer-fixture.cs').read_text(),'BlackwallRecoveryMramControl').replace('{','{\nusing Antmicro.Renode.Peripherals.CPU;\nusing Antmicro.Renode.Peripherals.Bus;',1)
    strict+='\n'+control+(ROOT/'tools/renode-pending-metadata-program.cs').read_text()
    (output/'strict.cs').write_text(strict)
    (output/'board.repl').write_text((output/'board.repl').read_text()+'\nrom_model: Memory.MappedMemory @ sysbus 0x0200f000\n    size: 0x1000\n')
    (output/'initial-metadata.bin').write_bytes(initial);(output/'rom-trap.bin').write_bytes(bytes.fromhex('00be'))
    (output/'probe.resc').write_text((output/'probe.resc').read_text().replace('include @/work/run.py','sysbus LoadBinary @/work/rom-trap.bin 0x0200ff20\ninclude @/work/run.py'))
    source=(output/'run.py').read_text().replace('m=monitor.Machine;', 'from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallPendingRomProgram,BlackwallRecoveryMramControl\nm=monitor.Machine;')
    setup=f'''pending=BlackwallPendingRomProgram(m,cpu,m['sysbus.guard'].MemoryStartup,m['sysbus.guard_mram_tail'].OtaMarker,File.ReadAllBytes('/work/initial-metadata.bin'),'{fault}')
m['sysbus.guard'].PendingMramControl=BlackwallRecoveryMramControl()
m['sysbus.rstgen'].BindPendingPor(cpu)
policy.BindFunctionalRomEntry(pending.CheckEntry)
policy.Attach()'''
    source=source.replace('policy.Attach()',setup)
    source+='''File.WriteAllBytes('/work-output/metadata-after.bin',pending.State.Bytes)
r=m['sysbus.rstgen']
File.WriteAllText('/work-output/pending-result.json',json.dumps(dict(block_instructions=int(pending.BlockInstructions),entries=int(pending.Entries),calls=int(pending.Calls),status=int(pending.Status),key=int(pending.Key),operation=int(pending.Operation),source=int(pending.Source),offset=int(pending.Offset),words=int(pending.Words),primask=int(pending.Primask),programmed_words=int(pending.ProgrammedWords),violation=bool(pending.Violation),unready=bool(pending.Unready),interrupted=bool(pending.Interrupted),por_requested=bool(r.PendingPorRequested),por_pc=int(r.PendingPorPc),por_primask=int(r.PendingPorPrimask),control_writes=int(m['sysbus.guard'].PendingMramControl.Writes),hardware_accessed=False,rom_functional_model=True,physical_por_executed=False)))
'''
    validate_runtime(source);(output/'run.py').write_text(source);shutil.copy2(__file__,output/'experiment-source.py')
    manifest=json.loads((output/'manifest.json').read_text());manifest.update(fault=fault,initial_metadata_sha256=sha(initial),initial_metadata_source=None if initial_path is None else str(Path(initial_path).resolve()),functional_rom=True,rom_instruction_is_backend_trap_not_original=True,persistent_state_scope='7fe000..7fe010, synthetic initial adjacent12bytes A5 unless explicit prior-state input')
    manifest['components'].update({n:sha((output/n).read_bytes()) for n in ('strict.cs','board.repl','run.py','probe.resc','experiment-source.py','initial-metadata.bin','rom-trap.bin')})
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    log=execute(command,output,'native',timeout=220,stream=True)
    raw=json.loads((output/'exports/result.json').read_text());result=json.loads((output/'exports/pending-result.json').read_text());after=(output/'exports/metadata-after.bin').read_bytes()
    points={p['label']:p['hits'] for p in raw['points']};raw.update(main=points['main-reset'],handoff=points['stock-handoff'])
    classification='software-por-request' if result['por_requested'] else 'interrupted-program' if result['interrupted'] else 'unready-rom-boundary' if result['unready'] else classify(raw)
    result.update(classification=classification,cpu=raw,metadata_after_sha256=sha(after),images_unchanged=sha((output/'exports/guest-boot.bin').read_bytes())==manifest['boot']['sha256'] and sha((output/'exports/guest-main.bin').read_bytes())==manifest['main']['fixture_sha256'])
    cleanup=[]
    for n in ('main-fixture.bin','exports/guest-boot.bin','exports/guest-main.bin'):
        path=output/n;data=path.read_bytes();cleanup.append(dict(name=n,bytes=len(data),sha256=sha(data)));path.unlink()
    result['cleanup']=cleanup;(output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(classification=classification,rom_calls=result['calls'],programmed_words=result['programmed_words'],por=result['por_requested'],pc=hex(raw['pc']),policy=raw['policy'],guards=[g for g in raw['guards'] if g['accesses']],after=after.hex())),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--fault',choices=FAULTS,default='success');p.add_argument('--initial',type=Path);a=p.parse_args();run(a.output,a.fault,a.initial)
