"""Replay saved GPU bytes and optionally run isolated original ARM emitters.

The C# replay has no guest CPU. Source probes use auxiliary Unicorn M7;
neither executes the live main/RTOS or accesses physical hardware.
"""
import argparse, hashlib, json, shutil, struct
from pathlib import Path
from inspect_nema_submission import discover_submission
from run_renode_m55_probe import execute
from native_replay import IMAGE

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def original_shape_commands(raw,args,rounded=True,operation=None):
    """Run the unmodified ARM emitter/bind/reserve in explicit synthetic RAM; no hooks."""
    from inspect_ambiq_commands import discover,BASE,WORK,STOP,SRAM
    from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC
    import unicorn.arm_const as arm
    entries,slot=discover(raw)
    signatures=dict(aa='4ff0000c08b14ff0806c09b14cf0007c',quad='f0b5074681b00e4615461c46')
    signature=bytes.fromhex(signatures[operation] if operation else ('2de9f04f904687b008ebd872109e5210' if rounded else 'f0b5164681b004460d461f46012ea8bf'))
    assert raw.count(signature)==1
    entry=BASE+raw.index(signature);u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
    size=(len(raw)+4095)&~4095;u.mem_map(BASE,size);u.mem_write(BASE,raw);u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
    u.mem_map(SRAM,0x80000);u.mem_map(WORK,0x10000);u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
    state,cl,commands=WORK+0x1000,WORK+0x2000,WORK+0x4000
    u.mem_write(slot,struct.pack('<I',state));u.mem_write(cl,struct.pack('<5I',4096,0,commands,commands,1024))
    u.mem_write(cl+0x1c,struct.pack('<I',0xffffffff))
    def call(pc,values):
        for i,v in enumerate(values[:4]):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(i)),v&0xffffffff)
        u.reg_write(arm.UC_ARM_REG_SP,WORK+0xff00);u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
        if len(values)>4:u.mem_write(WORK+0xff00,struct.pack('<'+'I'*(len(values)-4),*[v&0xffffffff for v in values[4:]]))
        u.emu_start(pc|1,STOP,count=100000)
        assert u.reg_read(arm.UC_ARM_REG_PC)==STOP and u.reg_read(arm.UC_ARM_REG_SP)==WORK+0xff00
    call(entries['bind_circular'],[cl,2])
    if operation=='quad':
        aa=bytes.fromhex(signatures['aa']);assert raw.count(aa)==1
        call(BASE+raw.index(aa),[0,1,0,1])
    call(entry,args)
    length=struct.unpack('<I',u.mem_read(cl+0x14,4))[0]
    assert length<=1024
    return dict(entry=entry,args=args,words=list(struct.unpack('<'+'I'*length,u.mem_read(commands,4*length))),original_arm=True,
        aa_flags=struct.unpack('<I',u.mem_read(state+0x1c,4))[0],return_value=u.reg_read(arm.UC_ARM_REG_R0),
        synthetic_state=True,cpu="Unicorn Cortex-M7 auxiliary",hooks=False,mmio_mapped=False,gpu_executed=False)

def original_packing_commands(raw,sram,source,destination,width,height):
    """Run the original two-pass list producer, not a GPU or natural-main run.

    Native SRAM supplies library flags; a separate synthetic list/state and
    declared clip supply the caller contract. No instruction or memory hooks.
    """
    from inspect_ambiq_commands import discover,BASE,WORK,STOP,SRAM,SAVED
    from inspect_ambiq_target import decode
    from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC
    import unicorn.arm_const as arm
    if len(sram)!=0x380000 or not 0<width<=1024 or not 0<height<=1024:
        raise ValueError('Full native SRAM and bounded dimensions required')
    for address,extent in [(source,width*height),(destination,((width+1)//2)*height)]:
        if not SRAM<=address or address+extent>SRAM+len(sram):
            raise ValueError('Packing surface outside native SRAM')
    signature=bytes.fromhex('2de9f04712f001068eb0')
    if raw.count(signature)!=1:raise ValueError('Ambiguous original packing producer')
    entry=BASE+raw.index(signature);entries,slot=discover(raw)
    calls=[i.operands[0].imm for i in decode(raw,entry+0x28,0x10) if i.mnemonic=='bl']
    if len(calls)!=1:raise ValueError('Ambiguous original clip call')
    clip=calls[0]
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
    u.reg_write(arm.UC_ARM_REG_C1_C0_2,0xf00000);u.reg_write(arm.UC_ARM_REG_FPEXC,0x40000000)
    size=(len(raw)+4095)&~4095;u.mem_map(BASE,size);u.mem_write(BASE,raw)
    u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
    u.mem_map(SRAM,len(sram));u.mem_write(SRAM,sram)
    u.mem_map(WORK,0x10000);u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
    state,cl,commands=WORK+0x1000,WORK+0x2000,WORK+0x4000
    put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
    put(slot,state);u.mem_write(cl,struct.pack('<5I',4096,0,commands,commands,1024))
    for off in (0x1c,0x34,0x38):put(cl+off,0xffffffff)
    put(state+0x2c,width);put(state+0x30,height)
    def call(pc,args):
        for j,reg in enumerate(SAVED):u.reg_write(reg,0x12340000+j)
        for j,v in enumerate(args[:4]):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(j)),v&0xffffffff)
        u.reg_write(arm.UC_ARM_REG_SP,WORK+0xff00);u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
        if len(args)>4:u.mem_write(WORK+0xff00,struct.pack('<'+'I'*(len(args)-4),*args[4:]))
        u.emu_start(pc|1,STOP,count=200000)
        if u.reg_read(arm.UC_ARM_REG_PC)!=STOP or u.reg_read(arm.UC_ARM_REG_SP)!=WORK+0xff00:
            raise ValueError('Original packing call did not return normally')
        if [u.reg_read(reg) for reg in SAVED]!=[0x12340000+j for j in range(len(SAVED))]:
            raise ValueError('Original packing call changed saved registers')
    source_before=bytes(u.mem_read(source,width*height))
    destination_before=bytes(u.mem_read(destination,((width+1)//2)*height))
    call(entries['bind_circular'],[cl,2])
    call(entries['texture_binding'],[0,destination,width,height,0x35,(width+1)//2,0])
    call(clip,[0,0,width,height])
    call(entry,[source,destination,width,height])
    length=struct.unpack('<I',u.mem_read(cl+0x14,4))[0]
    if length>1024:raise ValueError('Original packing list exceeds allocation')
    if bytes(u.mem_read(source,width*height))!=source_before or bytes(u.mem_read(destination,((width+1)//2)*height))!=destination_before:
        raise ValueError('CPU producer unexpectedly wrote pixel memory')
    return dict(entry=entry,clip_entry=clip,words=list(struct.unpack('<'+'I'*length,u.mem_read(commands,length*4))),
        original_arm=True,cpu='Unicorn Cortex-M7 auxiliary',synthetic_list_and_clip=True,
        full_native_sram_sha256=hashlib.sha256(sram).hexdigest(),raw_sha256=hashlib.sha256(raw).hexdigest(),
        hooks=False,mmio_mapped=False,gpu_executed=False,live_main_cpu_executed=False,pixel_memory_unchanged=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--shape-streams',action='store_true');p.add_argument('--quad-coverage',action='store_true');a=p.parse_args()
    if a.quad_coverage:a.shape_streams=True
    o=a.output.resolve()
    if o.exists() or any((v/'.git').exists() for v in [o,*o.parents]):raise ValueError('New private output required')
    o.mkdir(mode=0o700);fixtures=o/'fixtures';fixtures.mkdir();sources=[]
    for case,suffix in [('stock24','stock24-04'),('stock23','stock23-01'),('cfw','cfw-01')]:
        capture=a.simulator/('gpu-runtime-native-'+suffix);ex=capture/'exports'
        trace=json.loads((ex/'content-trace.json').read_text());raw=(capture/'main.bin').read_bytes()
        ram=(ex/'content-after-sram.bin').read_bytes();contract=discover_submission(raw)
        word=lambda address:struct.unpack_from('<I',ram,address-0x20000000)[0]
        start=word(contract['ring_table']+8);size=word(contract['ring_table']+16)
        # Both the buffer object and native footer table carry the configured byte size.
        bo=word(contract['ring_table']);assert size==word(bo)
        if 'ring_bytes' in trace['gpu_runtime']:assert size==trace['gpu_runtime']['ring_bytes']
        guards=[x for x in trace['guards'] if x['accesses']]
        assert len(guards)==1 and guards[0]['address']==0x400900ec
        bell=guards[0]['value'];list_address=word((bell&~7)-12)
        assert (bell&~7)-start==92*4 and word((bell&~7)-16)==0xf0 and word((bell&~7)-4)==24
        f=fixtures/case;f.mkdir();(f/'sram.bin').write_bytes(ram)
        (f/'config.txt').write_text('\n'.join(map(str,[start,size,bell,list_address]))+'\n')
        sources.append(dict(case=case,main_sha256=sha(capture/'main.bin'),trace_sha256=sha(ex/'content-trace.json'),
            sram_sha256=sha(ex/'content-after-sram.bin'),ring_base=start,ring_bytes=size,doorbell=bell,list_address=list_address))
        if a.shape_streams:
            native=a.simulator/('gpu-ring-native-'+dict(stock24='stock24-04',stock23='stock23-01',cfw='cfw-01')[case]);nx=native/'exports'
            t=json.loads((nx/'content-trace.json').read_text());memory=(nx/'content-after-sram.bin').read_bytes()
            assert (native/'main.bin').read_bytes()==raw
            bell=t['registers'][1];h=struct.unpack_from('<4I',memory,(bell&~7)-16-0x20000000)
            assert h[0]==0xf0 and h[2:]==(0x200f4,108)
            shape=struct.unpack_from('<108I',memory,h[1]-0x20000000)
            emitted=original_shape_commands(raw,[1,1,638,478,7])
            assert emitted['words']==list(shape[18:]),'Original rounded emitter differs from native stream'
            controls=[original_shape_commands(raw,values,rounded=False) for values in [[-3,2,10,4],[1,2,0,4],[1,2,3,0]]]
            assert controls[0]['words']==[0x104,0x0002fffd,0x108,0x00060007,0xff000100,2]
            assert controls[1]['words']==controls[2]['words']==[]
            (f/'sram-second.bin').write_bytes(memory)
            (f/'config-second.txt').write_text('\n'.join(map(str,[t['gpu_runtime']['ring_base'],t['gpu_runtime']['ring_bytes'],bell,h[1]]))+'\n')
            (f/'shape-source.json').write_text(json.dumps(dict(passed=True,rounded=emitted,controls=controls,native_sha256=sha(nx/'content-after-sram.bin')),indent=2)+'\n')
        if a.quad_coverage:
            native=a.simulator/('gpu-shape-native-'+dict(stock24='stock24-01',stock23='stock23-01',cfw='cfw-02')[case]);nx=native/'exports'
            t=json.loads((nx/'content-trace.json').read_text());memory=(nx/'content-after-sram.bin').read_bytes()
            assert (native/'main.bin').read_bytes()==raw
            bell=t['registers'][1];h=struct.unpack_from('<4I',memory,(bell&~7)-16-0x20000000);assert h[0]==0xf0 and h[2:]==(0x200f4,252)
            stream=struct.unpack_from('<252I',memory,h[1]-0x20000000);offset=stream.index(0x120)
            quad_words=stream[offset:offset+18];points=list(quad_words[1:16:2])
            emitted=original_shape_commands(raw,points,operation='quad');assert emitted['words']==list(quad_words) and emitted['aa_flags']==0x2800000
            flags=[]
            for bits in range(16):
                values=[(bits>>i)&1 for i in range(4)];result=original_shape_commands(raw,values,operation='aa')
                assert result['aa_flags']==sum(v<<(26-i) for i,v in enumerate(values))
                flags.append(result)
            (f/'sram-quad.bin').write_bytes(memory)
            (f/'config-quad.txt').write_text('\n'.join(map(str,[t['gpu_runtime']['ring_base'],t['gpu_runtime']['ring_bytes'],bell,h[1]]))+'\n')
            (f/'quad-source.json').write_text(json.dumps(dict(passed=True,quad=emitted,aa_matrix=flags,msaa_samples_verified=False),indent=2)+'\n')
    shutil.copyfile(ROOT/'tests/nema-ring-consumer-tests.cs',o/'Tests.cs')
    model=ROOT/'tools/nema-ring-consumer.cs'
    if model.exists():shutil.copyfile(model,o/'Consumer.cs')
    (o/'probe.resc').write_text('include @/work/Consumer.cs\ninclude @/work/Tests.cs\ninclude @/work/tests.py\nquit\n')
    (o/'tests.py').write_text('from System import Array,String,Object\nfrom Antmicro.Renode.Utilities import TypeManager\nt=TypeManager.Instance.GetTypeByName("Antmicro.Renode.Peripherals.Miscellaneous.RingConsumerTests")\nt.GetMethod("Main").Invoke(None,Array[Object]([Array[String](["/work/fixtures"])]))\n')
    (o/'inputs.json').write_text(json.dumps(sources,indent=2)+'\n');shutil.copyfile(__file__,o/'verifier.py')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--mount','type=bind,source='+str(o)+',target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'consumer',timeout=90)
    rows=[int(l.split()[-1]) for l in log.splitlines() if l.startswith('BLACKWALL_RING_TESTS ')]
    assert len(rows)==1
    result=dict(passed=True,checks=rows[0],native_saved_images=3,sources=sources,model_sha256=sha(model),
        shape_streams=a.shape_streams,test_harness_sha256=sha(o/'Tests.cs'),verifier_sha256=sha(o/'verifier.py'),
        quad_coverage=a.quad_coverage,quad_source_reports={case:sha(fixtures/case/'quad-source.json') for case in ['stock24','stock23','cfw']} if a.quad_coverage else {},
        shape_source_reports={case:sha(fixtures/case/'shape-source.json') for case in ['stock24','stock23','cfw']} if a.shape_streams else {},
        cpu_executed=a.shape_streams,auxiliary_original_arm_execution=a.shape_streams,gpu_replay_cpu_executed=False,
        live_main_cpu_executed=False,live_submission_completed=False,natural_main_complete=False,hardware_accessed=False)
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='sources'}))
if __name__=='__main__':main()
