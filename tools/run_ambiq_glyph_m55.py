"""Replay frozen glyph helper inputs in Renode M55, without device or GPU access."""
import argparse
import hashlib
import json
from pathlib import Path

from native_replay import IMAGE
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from run_recovery_m55_writer import private_write, is_git_output

ROOT=Path(__file__).resolve().parents[1]


def sha(data):return hashlib.sha256(data).hexdigest()


def make_batch_harness(output,batch):
    # This caller contains no drawing logic: only AAPCS arguments, BLX to the
    # original entries, and completion records after each original return.
    assembly=['.syntax unified','.cpu cortex-m55','.thumb','.section .text','.global batch_entry','.thumb_func','batch_entry:']
    limits=batch.get('stack_limits')
    if limits:
        for reg in ['psplim','msplim','psp','control']:
            if reg not in limits:continue
            assembly += [f'ldr r12, =0x{limits[reg]:x}',f'msr {reg}, r12']
        assembly += ['isb']
        assembly += ['ldr r0, =0x2100c3f0']
        for index,reg in enumerate(['psp','msp','control','psplim','msplim']):
            assembly += [f'mrs r12, {reg}',f'str r12, [r0, #{index*4}]']
        assembly += ['mov r12, sp','str r12, [r0, #20]']
    for index,phase in enumerate(batch['calls']):
        for n,value in enumerate(phase['stack']):assembly += [f'ldr r12, =0x{value:x}',f'str r12, [sp, #{4*n}]']
        for n,value in enumerate(phase['args']):assembly += [f'ldr r{n}, =0x{value:x}']
        assembly += [f'ldr r12, =0x{phase["entry"]|1:x}','blx r12',f'ldr r12, =0x{0x2100c000+index*64:x}']
        if batch.get('record_returns'):assembly += ['str r0, [r12, #44]']
        assembly += [f'movs r0, #{index+1}','str r0, [r12]',
            'ldr r0, =0x21002014','ldr r0, [r0]','str r0, [r12, #4]','mov r0, sp','str r0, [r12, #8]']
        assembly += [f'str r{n}, [r12, #{12+4*(n-4)}]' for n in range(4,12)]
        assembly += [f'b phase_{index}_end','.balign 4','.ltorg',f'phase_{index}_end:']
    assembly += ['ldr r12, =0x10000001','bx r12','.balign 4','.ltorg']
    private_write(output/'harness.s',('\n'.join(assembly)+'\n').encode())
    clang='/opt/homebrew/opt/llvm@21/bin/clang';lld='/opt/homebrew/opt/lld@21/bin/ld.lld';objcopy='/opt/homebrew/opt/llvm@21/bin/llvm-objcopy'
    command=[clang,'--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-mfloat-abi=hard','-nostdlib','-fuse-ld='+lld,'-Wl,-Ttext=0x2100e000','-Wl,-e,batch_entry',str(output/'harness.s'),'-o',str(output/'harness.elf')]
    execute(command,output,'harness-compiler')
    execute([objcopy,'-O','binary',str(output/'harness.elf'),str(output/'harness.bin')],output,'harness-objcopy')
    disassembly=execute(['/opt/homebrew/opt/llvm@21/bin/llvm-objdump','-d',str(output/'harness.elf')],output,'harness-disassembly')
    import re
    count=len(batch['calls'])
    if count not in (5,6,7) or len(re.findall(r'\bblx\s+r12',disassembly))!=count:raise ValueError('Expected bounded original calls in ARM caller')
    code=(output/'harness.bin').read_bytes()
    if not 0<len(code)<=0x1000:raise ValueError('Unexpected ARM test caller size')
    work=bytearray((output/'work.bin').read_bytes());source_work_sha256=sha(work)
    work[0xe000:0xe000+len(code)]=code;(output/'work.bin').write_bytes(work)
    profile=dict(address=0x2100e000,bytes=len(code),sha256=sha(code),marker_address=0x2100c000,compiler_command=command,
        source_work_sha256=source_work_sha256,work_sha256=sha(work),assembly_sha256=sha((output/'harness.s').read_bytes()))
    private_write(output/'harness-profile.json',(json.dumps(profile,indent=2)+'\n').encode())
    return profile


def run_case(simulator,captures,output,case,kind,memory_guard=True,canonical_itcm=False,itcm_word=None):
    folder=captures/'captures'/case/kind
    manifest=json.loads((folder/'snapshot.json').read_text())
    expected_report=json.loads((captures/'report.json').read_text())
    expected=next(c['runtime'] for c in expected_report['cases'] if c['case']==case)
    for name,digest in manifest['image_hashes'].items():
        if sha((folder/name).read_bytes())!=digest:raise ValueError('Capture image changed')
    filename={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[case]
    _,raw=load_pinned_main((simulator/'inputs/verified-01'/filename).read_bytes())
    if sha(raw)!=manifest['raw_sha256']:raise ValueError('Capture main mismatch')
    batch=manifest.get('batch')
    if batch:
        from prepare_nema_state_captures import validate_region
        validate_region(simulator,case,raw,manifest,(folder/'sram.bin').read_bytes())
        from prepare_draw_command_batch import batch_calls
        if kind!='full-letter' or not canonical_itcm:raise ValueError('Prepared command batch requires canonical full-letter mode')
        surface=batch['surface']
        if surface!={'address':0x2100a000,'width':64,'height':32,'stride':surface['stride'],'format':9,'extent':surface['stride']*32} or surface['stride'] not in [64,80]:raise ValueError('Unreviewed batch surface')
        phases=batch_calls(raw,manifest,surface['stride'])
        source_work=(folder/'work.bin').read_bytes()
        import struct
        phases[3]['stack']=list(struct.unpack_from('<2I',source_work,manifest['registers']['SP']-0x21000000))
        if phases!=batch['calls']:raise ValueError('Original batch entries/arguments differ')
    itcm_profile=None
    if itcm_word is not None and (not canonical_itcm or not 0<=itcm_word<=0xffffffff):raise ValueError('Bounded ITCM word hypothesis requires canonical mode')
    if canonical_itcm:
        if kind!='full-letter' or not memory_guard:raise ValueError('Canonical ITCM is a guarded full-letter fixture only')
        from native_replay import validate_assets,parse_log
        source=simulator/'em9305-reset-main-01'/case
        source_report=json.loads((source/'report.json').read_text())
        validate_assets(source,json.loads((source/'derived-inputs.json').read_text())['derived'])
        if not source_report['passed'] or parse_log((source/'renode.log').read_text())!=source_report['observed'] or (source/'main.bin').read_bytes()!=raw:raise ValueError('Unverified canonical memory source')
        itcm=bytearray((source/'itcm-fill.bin').read_bytes());prefix=bytes(source_report['observed']['itcm_prefix'])
        if len(itcm)!=0x40000 or len(prefix)!=256:raise ValueError('Unexpected canonical ITCM extent')
        itcm[:len(prefix)]=prefix
        from inspect_glyph_itcm_read import read_contract
        proof=read_contract(raw,int(expected['full_letter_fixture']['pc'],0)-8)
        source_word=int.from_bytes(itcm[16:20],'little')
        if itcm_word is not None:itcm[16:20]=itcm_word.to_bytes(4,'little')
        itcm_profile=dict(source=str(source.relative_to(simulator)),report_sha256=sha((source/'report.json').read_bytes()),
            fill_sha256=sha((source/'itcm-fill.bin').read_bytes()),image_sha256=sha(itcm),prefix_sha256=sha(prefix),
            raw_read_pc=proof['read_pc'],word=int.from_bytes(itcm[16:20],'little'),source_word=source_word,
            word_hypothesis=itcm_word is not None,read_contract=proof,hardware_value_verified=False)
    output.mkdir(mode=0o700)
    for name,data in [('main.bin',raw),('sram.bin',(folder/'sram.bin').read_bytes()),('work.bin',(folder/'work.bin').read_bytes()),
                      ('snapshot.json',(folder/'snapshot.json').read_bytes()),('fixture.cs',(ROOT/'tools/renode-arm-function-fixture.cs').read_bytes()),
                      ('runner-source.py',Path(__file__).read_bytes())]:private_write(output/name,data)
    if canonical_itcm:private_write(output/'itcm.bin',bytes(itcm))
    harness=make_batch_harness(output,batch) if batch else None
    board='''cpu: CPU.CortexM @ sysbus
    cpuType: "cortex-m55"
    nvic: nvic
    PerformanceInMips: 10
nvic: IRQControllers.NVIC @ sysbus 0xe000e000
    systickFrequency: 1000000
main: Memory.MappedMemory @ sysbus 0x438000
    size: 0x400000
sram: Memory.MappedMemory @ sysbus 0x20000000
    size: 0x80000
work: Memory.MappedMemory @ sysbus 0x21000000
    size: 0x10000
stop: Memory.MappedMemory @ sysbus 0x10000000
    size: 0x1000
fixture: Miscellaneous.BlackwallArmFunctionFixture @ sysbus 0x10001000
    cpu: cpu
    mainLength: {length}
    memoryGuard: {guard}
    itcmRawReadPc: {itcm_pc}
    harnessLength: {harness_bytes}
'''.format(length=len(raw),guard=str(memory_guard).lower(),itcm_pc=itcm_profile['raw_read_pc'] if canonical_itcm else 0,harness_bytes=harness['bytes'] if harness else 0)
    if canonical_itcm:board+='itcm: Memory.MappedMemory @ sysbus 0x0\n    size: 0x40000\n'
    private_write(output/'board.repl',board.encode())
    setup='''import json,time
from System import Console
from System.IO import File
from Antmicro.Renode.Core import EmulationManager
m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];fixture=m['sysbus.fixture']
s=json.loads(File.ReadAllText('/work/snapshot.json'));r=s['registers']
cpu.FpuEnabled=True
for n in range(13):fixture.SeedRegister(n,r['R'+str(n)])
fixture.SeedRegister(13,r['SP']);fixture.SeedRegister(14,r['LR'])
for n,v in [(18,4),(19,0),(22,0),(25,r['XPSR']),(27,0xf00000),(28,0),(30,0),(31,0),(74,r['FPSCR'])]:fixture.SeedRegister(n,v)
for n in range(32):fixture.SeedRegister(75+n,s['float_registers'][n])
phase_results=[]
phases=[dict(name='batch-caller' if 'batch' in s else 'entry',entry=0x2100e000 if 'batch' in s else s['entry'],args=[r['R'+str(n)] for n in range(4)],stack=[])]
for phase in phases:
    fixture.BeginCall()
    for n in range(13):fixture.SeedRegister(n,r['R'+str(n)])
    for n,value in enumerate(phase['args']):fixture.SeedRegister(n,value)
    fixture.SeedRegister(13,r['SP']);fixture.SeedRegister(14,r['LR'])
    for n,value in enumerate(phase['stack']):b.WriteDoubleWord(r['SP']+4*n,value)
    fixture.SeedRegister(15,phase['entry']|1)
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+5
    while not fixture.Stopped and time.time()<deadline:time.sleep(0.001)
    m.Pause()
    phase_results.append(dict(name=phase['name'],boundary=str(fixture.Boundary),used_words=int(b.ReadDoubleWord(0x21002014)),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)]))
    if str(fixture.Boundary)!='return':break
if 'batch' in s:
    phase_results=[]
    for n,phase in enumerate(s['batch']['calls']):
        marker=0x2100c000+n*64
        phase_results.append(dict(name=phase['name'],boundary='return' if int(b.ReadDoubleWord(marker))==n+1 else 'not-reached',used_words=int(b.ReadDoubleWord(marker+4)),stack=int(b.ReadDoubleWord(marker+8)),saved_registers=[int(b.ReadDoubleWord(marker+12+4*i)) for i in range(8)]))
regs=dict((str(n),int(cpu.GetRegister(n).RawValue)) for n in range(16))
used=int(b.ReadDoubleWord(0x21002014))
answer=dict(boundary=str(fixture.Boundary),violations=int(fixture.Violations),fault_pc=int(fixture.FaultPc),fault_address=int(fixture.FaultAddress),fault_width=int(fixture.FaultWidth),blocks=int(fixture.Blocks),writes=int(fixture.Writes),registers=regs,used_words=used,words=[int(b.ReadDoubleWord(0x21004000+4*n)) for n in range(min(used,1024))],cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),itcm_reads=int(fixture.ItcmReads),itcm_read_word=int(fixture.ItcmReadWord))
answer['phases']=phase_results
answer['terminator']=[int(b.ReadDoubleWord(0x21004000+used*4+4*n)) for n in range(2)]
answer['active_list']=int(b.ReadDoubleWord(0x21001004))
answer['cpu_halted']=bool(cpu.IsHalted)
File.WriteAllBytes('/work-output/final-sram.bin',b.ReadBytes(0x20000000,0x80000))
File.WriteAllBytes('/work-output/final-work.bin',b.ReadBytes(0x21000000,0x10000))
Console.WriteLine('BLACKWALL_GLYPH_M55 '+json.dumps(answer))
'''
    private_write(output/'setup.py',setup.encode())
    resc='include @/work/fixture.cs\nmach create "glyph-function"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/main.bin 0x438000\nsysbus LoadBinary @/work/sram.bin 0x20000000\nsysbus LoadBinary @/work/work.bin 0x21000000\n'
    if canonical_itcm:resc+='sysbus LoadBinary @/work/itcm.bin 0x0\n'
    private_write(output/'probe.resc',(resc+'include @/work/setup.py\nquit\n').encode())
    # Inputs are immutable in the container; only final host-side memory copies
    # are written through this output mount. No device/network mounts exist.
    result_folder=output/'result';result_folder.mkdir(mode=0o700)
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--mount',f'type=bind,source={output},target=/work,readonly','--mount',f'type=bind,source={result_folder},target=/work-output',
        IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],output,'renode',timeout=45)
    rows=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_GLYPH_M55 ')]
    if len(rows)!=1:raise ValueError('Missing M55 result; inspect saved log')
    actual=rows[0];glyph=kind!='full-letter'
    initial_work=(output/'work.bin').read_bytes();final_work=(result_folder/'final-work.bin').read_bytes()
    final_sram=(result_folder/'final-sram.bin').read_bytes()
    checks=dict(sram_immutable=sha(final_sram)==manifest['image_hashes']['sram.bin'],
        pixels_immutable=final_work[0x8000:0x9000]==initial_work[0x8000:0x9000],
        no_architectural_fault=actual['cfsr']==actual['hfsr']==0)
    if glyph or canonical_itcm:
        want=next(g for g in expected['glyphs'] if g['character']==(65 if canonical_itcm else int(kind.split('-')[1])))
        checks.update(returned=actual['boundary']=='return' and actual['violations']==0,
            command_words=actual['words']==(batch['words'] if batch else want['words']) and actual['used_words']==(len(batch['words']) if batch else want['used_words']),
            registers=all(actual['registers'][str(i)]==manifest['registers']['R'+str(i)] for i in range(4,12)),
            stack=actual['registers']['13']==manifest['registers']['SP'],
            outside_stack_matches_input=all(a==b or batch and 0xc000<=i<0xc140 or canonical_itcm and (0x300<=i<0x330 or 0x1800<=i<0x180c) or 0x800<=i<0x900 or 0x1000<=i<0x1100 or 0x2000<=i<0x2040 or 0x4000<=i<0x5000 or 0xfc00<=i<0xff00 for i,(a,b) in enumerate(zip(initial_work,final_work))))
        if canonical_itcm:checks['canonical_itcm_read']=actual['itcm_reads']==1 and actual['itcm_read_word']==itcm_profile['word']
        if batch:
            checks['batch_phases']=[dict(name=p['name'],used_words=p['used_words']) for p in actual['phases']]==batch['phase_results'] and all(p['boundary']=='return' and p['stack']==manifest['registers']['SP'] and p['saved_registers']==[manifest['registers']['R'+str(n)] for n in range(4,12)] for p in actual['phases'])
            checks['batch_closed']=actual['active_list']==0 and actual['terminator']==batch['terminator']
            address=surface['address']-0x21000000;extent=surface['extent']
            checks['surface_unchanged']=final_work[address-32:address+extent+32]==initial_work[address-32:address+extent+32]
    else:
        checks.update(strict_null_boundary=actual['boundary']=='read-boundary' and actual['violations']==1
            and actual['fault_pc']==int(expected['full_letter_fixture']['pc'],0) and actual['fault_address']==0x10
            and actual['fault_width']==4 and actual['registers']['5']==0,commands_absent=actual['used_words']==0)
    # Renode reports this missing bus read before the memory observer aborts.
    # Do not call it a hardware HardFault or let the returned bus value drive
    # subsequent guest instructions.
    bad=[line for line in log.splitlines() if ('[ERROR]' in line or 'There was an error' in line or '[WARNING]' in line and 'Translation cache size' not in line)]
    allowed_abort=not glyph and not canonical_itcm and actual['boundary']=='read-boundary'
    allowed_messages=['glyph-function: This machine has aborted. Emulation cannot continue until this machine is removed.',
        'sysbus: [cpu: 0x{:X}] ReadDoubleWord from non existing peripheral at 0x10.'.format(actual['fault_pc'])]
    checks['runtime_diagnostics']=not bad or allowed_abort and all(any(message in line for message in allowed_messages) for line in bad)
    report=dict(passed=all(checks.values()),case=case,kind=kind,memory_guard=memory_guard,checks=checks,actual=actual,
        snapshot_sha256=sha((folder/'snapshot.json').read_bytes()),input_hashes={name:sha((output/name).read_bytes()) for name in ['main.bin','sram.bin','work.bin','fixture.cs','runner-source.py','board.repl','setup.py','probe.resc']},
        expected_report_sha256=sha((captures/'report.json').read_bytes()),
        itcm_profile=itcm_profile,
        command_batch=bool(batch),
        harness=harness,
        final_hashes={'sram':sha(final_sram),'work':sha(final_work)},image=IMAGE,synthetic_function_entry=True,full_main_rendered=False,hardware_accessed=False)
    if harness:
        report['input_hashes'].update({name:sha((output/name).read_bytes()) for name in ['harness.s','harness.elf','harness.bin','harness-profile.json','harness-compiler.log','harness-objcopy.log','harness-disassembly.log']})
    private_write(output/'report.json',(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(dict(case=case,kind=kind,passed=report['passed'],checks=checks)),flush=True)
    if not report['passed']:raise ValueError('M55 comparison failed; inspect frozen result')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('captures',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--case',choices=['stock24','stock23','cfw'],action='append');p.add_argument('--kind',choices=['glyph-65','glyph-87','glyph-103','full-letter'])
    p.add_argument('--without-memory-guard',action='store_true')
    p.add_argument('--canonical-itcm',action='store_true',help='Guarded full-letter replay with pinned main ITCM fill/prefix')
    p.add_argument('--itcm-word',type=lambda value:int(value,0),help='Explicit counterfactual word for the unused-load comparison')
    a=p.parse_args();output=a.output.resolve()
    if is_git_output(output):raise ValueError('Private output required')
    if a.without_memory_guard and (not a.case or len(a.case)!=1 or not a.kind or a.kind=='full-letter'):raise ValueError('Observer control is a single returning helper only')
    if a.canonical_itcm and (a.kind!='full-letter' or a.without_memory_guard):raise ValueError('Canonical ITCM requires guarded full-letter mode')
    if a.itcm_word is not None and not a.canonical_itcm:raise ValueError('ITCM word hypothesis requires canonical mode')
    if output.exists():raise ValueError('Preserve prior results: use a new output directory')
    output.mkdir(mode=0o700);reports=[]
    for case in (a.case if a.case else ['stock24','stock23','cfw']):
        for kind in ([a.kind] if a.kind else ['glyph-65','glyph-87','glyph-103','full-letter']):
            reports.append(run_case(a.simulator,a.captures,output/(case+'-'+kind),case,kind,not a.without_memory_guard,a.canonical_itcm,a.itcm_word))
    private_write(output/'report.json',(json.dumps(dict(passed=True,cases=reports,full_main_rendered=False),indent=2)+'\n').encode())


if __name__=='__main__':main()
