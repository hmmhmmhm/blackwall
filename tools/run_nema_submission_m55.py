"""Replay original submission with a passive sink or explicit diagnostic pixel model."""
import argparse, hashlib, json, struct
from pathlib import Path
from inspect_nema_submission import discover_submission
from pinned_main import load_pinned_main
from native_replay import IMAGE
from run_renode_m55_probe import execute
from run_recovery_m55_writer import private_write, is_git_output

ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()


def guard_control_matches(actual,contract):
    # This Renode hook reports the access after the passive sink records it.
    # Detection is not a pre-access veto; preserve this distinction in audits.
    return (actual['boundary']=='write-boundary' and actual['violations']==1
            and actual['fault_pc']==contract['reg_store'] and actual['fault_address']==0x400900ec
            and actual['fault_width']==4 and actual['writes']==[0x22000014]
            and actual['cursor']==4 and actual['submission_id']==7 and actual['list_id']==0xffffffff)


SCENARIOS=['nominal','clip','stride80','disabled','bad-shader','bad-source','intermediate-alpha','nonzero-destination','bad-length','bad-order']
POSITIVE=['nominal','clip','stride80']


def reference_input(work,scenario):
    data=bytearray(work)
    words=list(struct.unpack_from('<42I',data,0x4000))
    def put(register,value):words[words[::2].index(register)*2+1]=value
    if scenario=='clip':put(0x110,(20<<16)|13);put(0x114,(27<<16)|18)
    elif scenario=='stride80':
        put(4,0x09000050);data[0x9fe0:0xaa20]=b'\xa5'*0xa40;data[0xa000:0xaa00]=bytes(2560)
    elif scenario=='bad-shader':put(0x11c,0x141e8000)
    elif scenario=='bad-source':put(0x10,0x21008000)
    elif scenario=='intermediate-alpha':put(0x10,0x438000)
    elif scenario=='nonzero-destination':data[0xa000]=1
    elif scenario=='bad-length':struct.pack_into('<I',data,0x2014,40)
    elif scenario=='bad-order':words[0]=0x99
    elif scenario not in ['nominal','disabled']:raise ValueError('Unreviewed reference scenario')
    struct.pack_into('<42I',data,0x4000,*words)
    return bytes(data)


def run(simulator,captures,out,case,control,reference=False,scenario='nominal',live_draw=False,character=65,omit_letter=False,completion_irq=False,irq_disabled=False,kernel_context=False,deferred_completion=False,block_boundary_control=False):
    source=captures/'captures'/case;s=json.loads((source/'snapshot.json').read_text())
    filename={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[case]
    _,raw=load_pinned_main((simulator/'inputs/verified-01'/filename).read_bytes())
    if sha(raw)!=s['raw_sha256'] or discover_submission(raw)!=s['contract']:raise ValueError('Original submission source differs')
    for name,digest in s['image_hashes'].items():
        if sha((source/name).read_bytes())!=digest:raise ValueError('Submission fixture changed')
    out.mkdir(mode=0o700)
    original_work=(source/'work.bin').read_bytes();live=None
    if live_draw:
        from nema_live_draw import prepare
        live=prepare(simulator,case,raw,(source/'sram.bin').read_bytes(),original_work,character,omit_letter)
        work=live['work']
    else:work=reference_input(original_work,scenario) if reference else original_work
    sram=(source/'sram.bin').read_bytes();irq=None
    if completion_irq:
        from nema_native_irq import prepare
        sram,irq=prepare(simulator,case,raw,sram)
        private_write(out/'irq-profile.json',(json.dumps(irq,indent=2)+'\n').encode())
        private_write(out/'irq-helper-source.py',(ROOT/'tools/nema_native_irq.py').read_bytes())
    kernel=None;system_sram=None
    if kernel_context:
        from nema_kernel_context import prepare
        sram,system_sram,kernel=prepare(simulator,case,raw,sram,live,deferred_completion,block_boundary_control)
        private_write(out/'kernel-profile.json',(json.dumps(kernel,indent=2)+'\n').encode())
        private_write(out/'kernel-helper-source.py',(ROOT/'tools/nema_kernel_context.py').read_bytes())
        private_write(out/'system-sram.bin',system_sram)
    model='renode-nema-reference-gpu.cs' if reference else 'renode-nema-doorbell-latch.cs'
    for name,data in [('main.bin',raw),('sram.bin',sram),('work.bin',work),
                      ('snapshot.json',(source/'snapshot.json').read_bytes()),('fixture.cs',(ROOT/'tools/renode-arm-function-fixture.cs').read_bytes()),
                      ('latch.cs',(ROOT/'tools'/model).read_bytes()),('runner-source.py',Path(__file__).read_bytes())]:private_write(out/name,data)
    extent=2560 if reference and scenario=='stride80' else 2048
    expected_frame=work[0xa000:0xa000+extent]
    if reference:
        mutation=dict(scenario=scenario,baseline_work_sha256=sha(original_work),work_sha256=sha(work),
                      changed_offsets=[i for i,(x,y) in enumerate(zip(original_work,work)) if x!=y])
        private_write(out/'fixture-mutation.json',(json.dumps(mutation,indent=2)+'\n').encode())
        if live and not omit_letter:
            from render_nema_reference import cpu_bitmap
            pixels,bitmap=cpu_bitmap(raw,(source/'sram.bin').read_bytes(),live['snapshot']['registers']['R3'],character)
            if bitmap['height']!=16 or bitmap['width'] not in (11,13):raise ValueError('Unreviewed uppercase bitmap metrics')
            frame=bytearray(extent)
            for y in range(16):frame[(16+y)*64+10:(16+y)*64+10+bitmap['width']]=pixels[y*bitmap['width']:(y+1)*bitmap['width']]
            expected_frame=bytes(frame)
            private_write(out/'cpu-bitmap.bin',pixels)
            private_write(out/'cpu-bitmap.json',(json.dumps(bitmap,indent=2)+'\n').encode())
        elif scenario in POSITIVE and not live:
            from nema_pixel_reference import render_white_a4_reference
            def read(address,size):
                if not 0x438000<=address<=address+size<=0x438000+len(raw):raise ValueError('Reference source outside pinned ROM')
                return raw[address-0x438000:address-0x438000+size]
            expected_frame,_=render_white_a4_reference(list(struct.unpack_from('<42I',work,0x4000)),expected_frame,read)
        private_write(out/'expected-frame.bin',expected_frame)
        private_write(out/'pixel-reference-source.py',(ROOT/'tools/nema_pixel_reference.py').read_bytes())
    harness=None
    if live:
        from run_ambiq_glyph_m55 import make_batch_harness
        batch=dict(calls=live['calls'])
        if kernel:batch.update(stack_limits=kernel['stack_limits'],record_returns=True)
        harness=make_batch_harness(out,batch)
        private_write(out/'draw-snapshot.json',(json.dumps(live['snapshot'],indent=2)+'\n').encode())
        private_write(out/'itcm.bin',live['itcm'])
        info=dict(live['evidence'],harness=harness)
        private_write(out/'live-profile.json',(json.dumps(info,indent=2)+'\n').encode())
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
gpu: Miscellaneous.BlackwallNemaDoorbellLatch @ sysbus 0x40090000
fixture: Miscellaneous.BlackwallArmFunctionFixture @ sysbus 0x10001000
    cpu: cpu
    mainLength: {length}
    gpuDoorbellWritePc: {pc}
'''.format(length=len(raw),pc=0 if control else s['contract']['reg_store'])
    if reference:
        board=board.replace('gpu: Miscellaneous.BlackwallNemaDoorbellLatch @ sysbus 0x40090000\n',
                            'gpu: Miscellaneous.BlackwallNemaReferenceGpu @ sysbus 0x40090000\n    cpu: cpu\n    mainLength: '+str(len(raw))+'\n    enabled: '+str(scenario!='disabled').lower()+'\n')
    if live:
        board+='    harnessLength: '+str(harness['bytes'])+'\n    itcmRawReadPc: '+str(live['itcm_read_pc'])+'\nitcm: Memory.MappedMemory @ sysbus 0x0\n    size: 0x40000\n'
    if irq:
        board=board.replace('    systickFrequency: 1000000\n','    systickFrequency: 1000000\n    -> cpu@0\n')
        board=board.replace('    enabled: true\n','    enabled: true\n    completionIrq: true\n    IRQ -> nvic@28\n')
        if deferred_completion:board=board.replace('    completionIrq: true\n','    completionIrq: true\n    deferCompletionIrq: true\n')
    if kernel:board+='systemSram: Memory.MappedMemory @ sysbus 0x20080000\n    size: 0x300000\n'
    private_write(out/'board.repl',board.encode())
    setup='''import json,time
from System import Console
from System.IO import File
from Antmicro.Renode.Core import EmulationManager
m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];f=m['sysbus.fixture'];gpu=m['sysbus.gpu']
s=json.loads(File.ReadAllText('/work/snapshot.json'))
for n in range(13):f.SeedRegister(n,0x12340000+n if 4<=n<12 else 0)
for n,value in enumerate(s['args']):f.SeedRegister(n,value)
f.SeedRegister(13,0x2100ff00);f.SeedRegister(14,0x10000001)
cpu.FpuEnabled=True
for n,v in [(18,4),(19,0),(22,0),(25,0x1000000),(27,0xf00000),(28,0),(30,0),(31,0),(74,0)]:f.SeedRegister(n,v)
f.BeginCall();f.SeedRegister(15,s['entry']|1)
EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+5
while not f.Stopped and time.time()<deadline:time.sleep(0.001)
m.Pause()
r=dict(boundary=str(f.Boundary),violations=int(f.Violations),fault_pc=int(f.FaultPc),fault_address=int(f.FaultAddress),fault_width=int(f.FaultWidth),
       ring=[int(b.ReadDoubleWord(0x2100b000+4*i)) for i in range(64)],cursor=int(b.ReadDoubleWord(0x2100b410)),submission_id=int(b.ReadDoubleWord(0x2100b414)),
       list_id=int(b.ReadDoubleWord(0x2100201c)),writes=[int(gpu.GetWrite(i)) for i in range(int(gpu.WriteCount))],
       registers=[int(cpu.GetRegister(i).RawValue) for i in range(16)],cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)))
File.WriteAllBytes('/work-output/final-work.bin',b.ReadBytes(0x21000000,0x10000));File.WriteAllBytes('/work-output/final-sram.bin',b.ReadBytes(0x20000000,0x80000))
rejections=[]
for offset,value in [(0xe8,0x22000014),(0xec,0x23000014),(0xec,0x22000010)]:
    before=int(gpu.WriteCount)
    try:gpu.WriteDoubleWord(offset,value);rejections.append(False)
    except:rejections.append(int(gpu.WriteCount)==before)
try:gpu.ReadDoubleWord(0xec);rejections.append(False)
except:rejections.append(True)
r['latch_rejections']=rejections
Console.WriteLine('BLACKWALL_SUBMIT_M55 '+json.dumps(r))
'''
    if reference:
        setup=setup.replace('while not f.Stopped and time.time()<deadline:', 'while not f.Stopped and not gpu.Stopped and time.time()<deadline:')
        start=setup.index('rejections=[]\n');end=setup.index("Console.WriteLine('BLACKWALL_SUBMIT_M55 '")
        setup=setup[:start]+"r['reference_gpu']=dict(frames=int(gpu.FramesWritten),bytes=int(gpu.FrameBytesWritten),words=int(gpu.ConsumedWords),samples=int(gpu.Samples),queued_id=int(gpu.QueuedId),irq_request_observed=bool(gpu.IrqRequestObserved),stopped=bool(gpu.Stopped),fault=str(gpu.Fault),rejections=int(gpu.Rejections))\n"+setup[end:]
    if live:
        seed="d=json.loads(File.ReadAllText('/work/draw-snapshot.json'));r0=d['registers']\nfor n in range(13):f.SeedRegister(n,r0['R'+str(n)])\nf.SeedRegister(13,r0['SP']);f.SeedRegister(14,r0['LR']);f.SeedRegister(74,r0['FPSCR'])\nfor n,v in enumerate(d['float_registers']):f.SeedRegister(75+n,v)\nf.BeginCall();f.SeedRegister(15,0x2100e001)"
        setup=setup.replace("f.BeginCall();f.SeedRegister(15,s['entry']|1)",seed)
        anchor="File.WriteAllBytes('/work-output/final-work.bin'"
        details="info=json.loads(File.ReadAllText('/work/live-profile.json'))\nr['live_phases']=[dict(name=p['name'],marker=int(b.ReadDoubleWord(0x2100c000+64*i)),used_words=int(b.ReadDoubleWord(0x2100c004+64*i)),sp=int(b.ReadDoubleWord(0x2100c008+64*i)),saved=[int(b.ReadDoubleWord(0x2100c00c+64*i+4*j)) for j in range(8)]) for i,p in enumerate(info['phases'])]\nr['itcm_reads']=int(f.ItcmReads)\n"
        setup=setup.replace(anchor,details+anchor)
    if irq:
        from nema_native_irq import setup_text,observation_text
        setup=setup.replace('EmulationManager.Instance.CurrentEmulation.StartAll();',setup_text(irq,not irq_disabled)+'EmulationManager.Instance.CurrentEmulation.StartAll();')
        setup=setup.replace("Console.WriteLine('BLACKWALL_SUBMIT_M55 '",observation_text(irq)+"Console.WriteLine('BLACKWALL_SUBMIT_M55 '")
    if kernel:
        from nema_kernel_context import setup_text,observation_text
        setup=setup.replace('EmulationManager.Instance.CurrentEmulation.StartAll();',setup_text(kernel)+'EmulationManager.Instance.CurrentEmulation.StartAll();')
        setup=setup.replace("Console.WriteLine('BLACKWALL_SUBMIT_M55 '",observation_text(kernel)+"Console.WriteLine('BLACKWALL_SUBMIT_M55 '")
    private_write(out/'setup.py',setup.encode())
    resc='include @/work/fixture.cs\ninclude @/work/latch.cs\nmach create "nema-submit"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/main.bin 0x438000\nsysbus LoadBinary @/work/sram.bin 0x20000000\nsysbus LoadBinary @/work/work.bin 0x21000000\npython "exec(compile(open(\'/work/setup.py\').read(),\'/work/setup.py\',\'exec\'))"\n'
    if live:resc=resc.replace('\npython ','\nsysbus LoadBinary @/work/itcm.bin 0x0\npython ')
    if kernel:resc=resc.replace('\npython ','\nsysbus LoadBinary @/work/system-sram.bin 0x20080000\npython ')
    private_write(out/'probe.resc',resc.encode());result_dir=out/'result';result_dir.mkdir(mode=0o700)
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
                 '--mount',f'type=bind,source={out},target=/work,readonly','--mount',f'type=bind,source={result_dir},target=/work-output',IMAGE,
                 '--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode',timeout=None)
    rows=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_SUBMIT_M55 ')]
    if len(rows)!=1:raise ValueError('Missing native submission result; inspect saved log')
    actual=rows[0];expected=s['expected'];before=(out/'work.bin').read_bytes();after=(result_dir/'final-work.bin').read_bytes()
    checks=dict(no_arch_fault=actual['cfsr']==actual['hfsr']==0,
                sram_unchanged=(result_dir/'final-sram.bin').read_bytes()==(out/'sram.bin').read_bytes(),
                ring_canaries=after[0xafe0:0xb000]==after[0xb100:0xb120]==b'\xa5'*32)
    if kernel:
        from nema_kernel_context import checks as kernel_checks
        checks.pop('sram_unchanged')
        checks.update(kernel_checks(actual,sram,(result_dir/'final-sram.bin').read_bytes(),system_sram,(result_dir/'final-system-sram.bin').read_bytes(),kernel,irq))
    elif irq:
        from nema_native_irq import checks as irq_checks
        checks.pop('sram_unchanged')
        checks.update(irq_checks(actual,sram,(result_dir/'final-sram.bin').read_bytes(),irq,not irq_disabled))
    saved_expected=[live['snapshot']['registers']['R'+str(n)] for n in range(4,12)] if live else [0x12340000+n for n in range(4,12)]
    if live:
        used=10 if omit_letter else 42
        checks.update(no_preloaded_payload=before[0x4000:0x5000]==b'\xa5'*4096,
                      commands_generated=after[0x4000:0x4000+used*4]!=before[0x4000:0x4000+used*4],
                      list_closed=list(struct.unpack_from('<2I',after,0x4000+used*4))==[0x50000,0],
                      command_suffix_untouched=after[0x4000+(used+2)*4:0x5000]==b'\xa5'*(4096-(used+2)*4))
        counts=[0,6,10,10] if omit_letter else [0,6,10,42,42,42]
        if kernel:counts.append(42)
        completed=actual['live_phases'][:4] if omit_letter else actual['live_phases']
        if irq and actual['boundary']=='rtos-context-required':
            counts=counts[:5];completed=completed[:5]
        if block_boundary_control:
            counts=counts[:6];completed=completed[:6]
        expected_sp=kernel['psp'] if kernel else 0x2100ff00
        checks['original_calls_returned']=(len(completed)==len(counts) and [p['used_words'] for p in completed]==counts
                                           and all(p['marker']==i+1 and p['sp']==expected_sp and p['saved']==saved_expected for i,p in enumerate(completed)))
        checks['original_bitmap_itcm_read']=actual['itcm_reads']==(0 if omit_letter else 1)
    else:checks['commands_unchanged']=before[0x4000:0x40b0]==after[0x4000:0x40b0]
    if reference:
        g=actual['reference_gpu']
        checks.update(frame_matches=after[0xa000:0xa000+extent]==expected_frame,
                      surface_guards=before[0x9fe0:0xa000]==after[0x9fe0:0xa000] and before[0xa000+extent:0xa020+extent]==after[0xa000+extent:0xa020+extent])
        if scenario not in POSITIVE or omit_letter:
            reasons={'disabled':'Reference GPU profile is disabled','bad-shader':'Unsupported render profile','bad-source':'Source outside original ROM',
                     'intermediate-alpha':'Intermediate A4 alpha is unverified','nonzero-destination':'Destination must be zero',
                     'bad-length':'Unsupported ring list reference','bad-order':'Unsupported command order'}
            reason='Unsupported ring list reference' if omit_letter else reasons[scenario]
            checks['rejected_before_frame_write']=(g['stopped'] and g['fault']==reason and g['rejections']==1
                                                   and g['frames']==g['bytes']==g['words']==g['queued_id']==0 and not g['irq_request_observed'] and actual['writes']==[])
        else:
            checks['consumed_reference_profile']=(not g['stopped'] and g['fault']=='' and g['rejections']==0 and g['frames']==1
                                                  and g['bytes']==extent and g['words']==42 and g['queued_id']==8 and g['irq_request_observed'])
            if live and character==65 and not irq:
                baseline=(simulator/'nema-live-draw-passive-01'/case/'result/final-work.bin').read_bytes()
                normalized=bytearray(after);normalized[0xa000:0xa000+extent]=before[0xa000:0xa000+extent]
                checks['cpu_effects_match_live_passive_baseline']=bytes(normalized)==baseline
            elif not live:
                baseline=(simulator/'nema-submission-m55-01'/case/'result/final-work.bin').read_bytes()
                normalized=bytearray(after);normalized[0xa000:0xa000+extent]=before[0xa000:0xa000+extent]
                for offset,(original,modified) in enumerate(zip(original_work,work)):
                    if original!=modified:normalized[offset]=original
                checks['cpu_effects_match_passive_baseline']=bytes(normalized)==baseline
    else:
        checks['latch_rejections']=all(actual['latch_rejections'])
        checks['surface_unchanged']=before[0x9fe0:0xa820]==after[0x9fe0:0xa820]
    if control:
        checks['guard_detects_after_passive_write']=guard_control_matches(actual,s['contract'])
    elif not irq and (not reference or (scenario in POSITIVE and not omit_letter)):
        checks.update(returned=actual['boundary']=='return' and actual['violations']==0,
                      ring=actual['ring']==expected['ring'],cursor=actual['cursor']==expected['cursor'],submission_id=actual['submission_id']==expected['submission_id'],
                      list_id=actual['list_id']==expected['list_id'],doorbells=actual['writes']==[w[1] for w in expected['writes']],
                      stack=actual['registers'][13]==0x2100ff00,saved_registers=actual['registers'][4:12]==saved_expected)
    result=dict(passed=all(checks.values()),case=case,control=control,checks=checks,actual=actual,synthetic_ring=True,
                reference_gpu=reference,scenario=scenario,gpu_consumed=reference and actual['reference_gpu']['frames']>0,
                live_draw=live_draw,character=character if live_draw else None,omit_letter=omit_letter,kernel_context=kernel_context,deferred_completion=deferred_completion,block_boundary_control=block_boundary_control,
                hardware_gpu_validated=False,completion_injected=completion_irq,irq_disabled=irq_disabled,full_main_rendered=False,hardware_accessed=False,
                input_hashes={p.name:sha(p.read_bytes()) for p in out.iterdir() if p.is_file() and p.name not in ['renode.log']},
                final_work_sha256=sha(after),final_sram_sha256=sha((result_dir/'final-sram.bin').read_bytes()))
    private_write(out/'report.json',(json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(dict(case=case,passed=result['passed'],control=control,checks=checks)),flush=True)
    if not result['passed']:raise ValueError('Native submission comparison failed')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('captures',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--case',choices=['stock24','stock23','cfw'],action='append');p.add_argument('--guard-control',action='store_true')
    p.add_argument('--reference-gpu',action='store_true',help='Explicit binary white A4/black L8 diagnostic model, no completion/IRQ')
    p.add_argument('--reference-scenario',choices=SCENARIOS,default='nominal')
    p.add_argument('--live-draw',action='store_true',help='Generate commands with original functions in this same uninterrupted run')
    p.add_argument('--character',type=int,choices=[65,87],default=65)
    p.add_argument('--omit-letter',action='store_true',help='Explicit live-draw negative control, not a firmware patch')
    p.add_argument('--completion-irq',action='store_true',help='Explicit diagnostic IRQ28; stop at unsupported PendSV context')
    p.add_argument('--irq-disabled',action='store_true',help='Negative control: leave IRQ28 disabled in NVIC')
    p.add_argument('--kernel-context',action='store_true',help='Captured full RAM with an explicit PSP caller; run original PendSV and completed wait')
    p.add_argument('--deferred-completion',action='store_true',help='Diagnostic event: release GPU completion only after actual waiter enrollment')
    p.add_argument('--block-boundary-control',action='store_true',help='Stop at real waiter boundary without releasing completion')
    a=p.parse_args();out=a.output.resolve()
    if is_git_output(out) or out.exists():raise ValueError('New private output required')
    if a.guard_control and a.case!=['stock24']:raise ValueError('Default guard control uses stock24 only')
    if a.reference_gpu and a.guard_control:raise ValueError('Use the disabled device scenario for pre-effect rejection; CPU hook is post-access')
    if not a.reference_gpu and a.reference_scenario!='nominal':raise ValueError('Reference scenario requires explicit reference GPU')
    if a.live_draw and (a.reference_scenario!='nominal' or a.guard_control):raise ValueError('Live draw uses nominal inputs and separate omit-letter control')
    if a.completion_irq and (not a.reference_gpu or not a.live_draw or a.omit_letter):raise ValueError('IRQ requires nominal live reference GPU')
    if a.irq_disabled and not a.completion_irq:raise ValueError('Disabled IRQ control requires completion profile')
    if a.kernel_context and (not a.completion_irq or a.irq_disabled):raise ValueError('Kernel profile requires an enabled completion IRQ')
    if a.deferred_completion and not a.kernel_context:raise ValueError('Deferred completion requires captured kernel context')
    if a.block_boundary_control and not a.deferred_completion:raise ValueError('Block boundary control requires deferred completion')
    if (a.omit_letter or a.character!=65) and not a.live_draw:raise ValueError('Character/omit control requires live draw')
    if a.omit_letter and not a.reference_gpu:raise ValueError('Omit control tests device rejection')
    out.mkdir(mode=0o700);rows=[run(a.simulator,a.captures,out/case,case,a.guard_control,a.reference_gpu,a.reference_scenario,a.live_draw,a.character,a.omit_letter,a.completion_irq,a.irq_disabled,a.kernel_context,a.deferred_completion,a.block_boundary_control) for case in (a.case or ['stock24','stock23','cfw'])]
    private_write(out/'report.json',(json.dumps(dict(passed=True,cases=rows,gpu_consumed=any(r['gpu_consumed'] for r in rows),hardware_gpu_validated=False),indent=2)+'\n').encode())


if __name__=='__main__':main()
