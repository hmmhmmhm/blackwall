"""Original builtin glyph -> raw bitmap -> Ambiq helper -> RAM draw commands.

Explicit synthetic draw/Nema state. Also preserves the full generic-letter
fixture's null-buffer fault; the successful helper fixture does not replace it.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import unicorn.arm_const as arm_registers

from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_CPU_ARM_CORTEX_M7, UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from inspect_ambiq_commands import discover, SAVED, BASE, WORK, STOP, SRAM
from font_wrapper_contract import discover_wrappers
from inspect_ambiq_target import decode
from pinned_main import load_pinned_main


def sha(data):return hashlib.sha256(data).hexdigest()


def inspect_case(raw, low, high_base, high, fonts, captures=None):
    entries,slot=discover(raw);wrappers=discover_wrappers(raw)
    signature=bytes.fromhex('2de9f8438cb0884616001c00')
    assert raw.count(signature)==1
    helper=BASE+raw.index(signature)
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
    u.reg_write(UC_ARM_REG_C1_C0_2,0xf00000);u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
    size=(len(raw)+4095)&~4095
    u.mem_map(BASE,size);u.mem_write(BASE,raw);u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
    u.mem_map(SRAM,0x80000);u.mem_map(WORK,0x10000);u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
    state,cl,commands,pixels=WORK+0x1000,WORK+0x2000,WORK+0x4000,WORK+0x8000
    task,context,point,layer,unit,draw,descriptor,rect=WORK+0x100,WORK+0x300,WORK+0x500,WORK+0x600,WORK+0x800,WORK+0x1800,WORK+0x700,WORK+0x900
    font,font_words=next((int(k,0),v) for k,v in fonts.items() if v[6])
    assert low[font-SRAM:font-SRAM+36]==struct.pack('<9I',*font_words)
    initial=u.context_save()
    def word(address):return struct.unpack('<I',u.mem_read(address,4))[0]
    def put(address,value):u.mem_write(address,struct.pack('<I',value))
    def reset():
        u.context_restore(initial);u.mem_write(WORK,bytes(0x10000))
        u.mem_write(SRAM,bytes(0x80000));u.mem_write(SRAM,low);u.mem_write(high_base,high);put(slot,state)
        u.mem_write(cl,struct.pack('<4I',4096,0,commands,commands));put(cl+0x10,1024)
        put(cl+0x1c,0xffffffff);put(cl+0x34,0xffffffff);put(cl+0x38,0xffffffff)
        u.mem_write(commands,b'\xa5'*4096);u.mem_write(pixels,b'\x7b'*4096)
        u.mem_write(draw,struct.pack('<5I',14<<8,0,0,4096,pixels))
        # The initialized snapshots are immutable to the guest. Host reset writes
        # are permitted by Unicorn's host API despite guest page protection.
        u.mem_protect(SRAM,0x80000,UC_PROT_READ)
    def call(entry,args=(),stack=(),until=STOP,may_fault=False,capture=None):
        for i,reg in enumerate(SAVED):u.reg_write(reg,0x12340000+i)
        for reg,value in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(reg,value)
        u.reg_write(UC_ARM_REG_SP,WORK+0xff00);u.reg_write(UC_ARM_REG_LR,STOP|1)
        u.mem_write(WORK+0xff00,struct.pack('<'+'I'*len(stack),*stack))
        before=bytes(u.mem_read(WORK,0x10000));sram_before=bytes(u.mem_read(SRAM,0x80000))
        if capture is not None and captures is not None:
            directory=captures/capture;directory.mkdir(mode=0o700,parents=True)
            images={'sram.bin':sram_before,'work.bin':before}
            for filename,data in images.items():(directory/filename).write_bytes(data)
            names=['R'+str(i) for i in range(13)]+['SP','LR','XPSR','FPSCR']
            snapshot=dict(entry=entry,registers={name:u.reg_read(getattr(arm_registers,'UC_ARM_REG_'+name)) for name in names},
                float_registers=[u.reg_read(getattr(arm_registers,'UC_ARM_REG_S'+str(i))) for i in range(32)],
                image_hashes={name:sha(data) for name,data in images.items()},raw_sha256=sha(raw),
                profile='Synthetic function entry, original prepared SRAM/WORK, M7 FPU input state')
            (directory/'snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
        error=None
        try:u.emu_start(entry|1,until,count=200000)
        except UcError as exc:
            if not may_fault:raise
            error=dict(message=str(exc),errno=exc.errno,pc=hex(u.reg_read(UC_ARM_REG_PC)),r0=hex(u.reg_read(UC_ARM_REG_R0)),r1=hex(u.reg_read(UC_ARM_REG_R1)))
        assert bytes(u.mem_read(SRAM,0x80000))==sram_before
        after=bytes(u.mem_read(WORK,0x10000))
        allowed=[(0x100,0x940),(0x1000,0x1100),(0x1800,0x181c),(0x2000,0x2040),(0x4000,0x5000),(0xfc00,0xff00)]
        assert all(any(a<=i<b for a,b in allowed) for i,(x,y) in enumerate(zip(before,after)) if x!=y)
        assert bytes(u.mem_read(pixels,4096))==b'\x7b'*4096
        if error:return error
        assert u.reg_read(UC_ARM_REG_PC)==until
        if until==STOP:
            assert u.reg_read(UC_ARM_REG_SP)==WORK+0xff00
            assert [u.reg_read(r) for r in SAVED]==[0x12340000+i for i in range(8)]
        return u.reg_read(UC_ARM_REG_R0)
    glyphs=[]
    for character in [65,87,103]:
        reset();call(entries['bind_circular'],[cl,2])
        assert call(wrappers['descriptor'],[font,descriptor,character,0])==1
        dsc=bytes(u.mem_read(descriptor,32));width,height=struct.unpack_from('<HH',dsc,6)
        assert width>0 and height>0 and dsc[14]==20
        u.mem_write(descriptor+20,bytes([dsc[20]|1]))
        # Actual callback loads draw-buffer+16 even in its req_raw_bitmap path.
        bitmap=call(wrappers['bitmap'],[descriptor,draw])
        glyph_id=struct.unpack_from('<I',dsc,24)[0]
        bitmap_base,glyph_table=struct.unpack_from('<2I',raw,font_words[6]-BASE)
        offset=struct.unpack_from('<I',raw,glyph_table+glyph_id*16-BASE)[0]
        assert bitmap==bitmap_base+offset
        packed_stride=width//2+1;extent=packed_stride*height
        assert BASE<=bitmap<bitmap+extent<=BASE+len(raw)
        area=[10,16,10+width-1,16+height-1];u.mem_write(rect,struct.pack('<4i',*area))
        call(helper,[unit,bitmap,width,height],[rect,20,0xffffffff,1,1],capture='glyph-'+str(character))
        used=word(cl+0x14)
        if not 0<used<128:raise ValueError('Unexpected helper command count: '+str(used))
        words=list(struct.unpack('<'+'I'*used,u.mem_read(commands,used*4)))
        pairs=list(zip(words[::2],words[1::2]));mapping=dict(pairs)
        padded_width=width+(2 if width%2==0 else 0)
        expected={0x10:bitmap,0x14:(0x34<<24)|packed_stride,0x18:(height<<16)|padded_width,
            0x1c:0xffffffff,0x174:struct.unpack('<I',struct.pack('<f',-16.0))[0],
            0x168:struct.unpack('<I',struct.pack('<f',-10.0))[0],0x160:0x3f800000,0x164:0,
            0x16c:0,0x170:0x3f800000,0x104:(16<<16)|10,
            0x108:((16+height)<<16)|(10+width),0xff000100:2}
        assert all(mapping[k]==v for k,v in expected.items())
        # Firmware versions emit different blend prefixes. Keep their exact
        # ordered words; an unordered map would hide repeated command keys.
        prefix=([(0x118,0),(0xc4,0),(0xc8,0x080c0003),(0xcc,0x0a012007),
                 (0xc8,0x004e0002),(0xcc,0x804b1286),(0x11c,0x141e8000)]
                if helper==0x5761c0 else [(0x1d0,0x504),(0x118,0),(0x11c,0x141f801f)])
        order=[0x1c,0x10,0x14,0x18,0x174,0x168,0x160,0x164,0x16c,0x170,0x104,0x108,0xff000100]
        assert pairs==prefix+[(key,expected[key]) for key in order]
        byte_count=used*4
        assert bytes(u.mem_read(commands+byte_count,4096-byte_count))==b'\xa5'*(4096-byte_count)
        assert word(state+0x20)==0
        call(entries['unbind']);assert list(struct.unpack('<2I',u.mem_read(commands+byte_count,8)))==[0x50000,0]
        glyphs.append(dict(character=character,glyph_id=glyph_id,width=width,height=height,bitmap=hex(bitmap),
            bitmap_sha256=sha(raw[bitmap-BASE:bitmap-BASE+extent]),packed_stride=packed_stride,
            area=area,words=words,used_words=used,original_bitmap_and_helper=True,pixels_unchanged=True))
    # Preserve the broader caller's actual failure without substituting the
    # successful direct helper fixture above.
    reset();call(entries['bind_circular'],[cl,2])
    u.mem_write(task+0x38,struct.pack('<4i',0,0,575,287));put(task+0x48,layer);put(task+0x4c,unit)
    put(layer,draw);put(context+0x2c,draw);put(context+0x14,0xffffffff)
    u.mem_write(point,struct.pack('<2i',10,10))
    fault=call(wrappers['letter'],[task,context,point,font],[65,wrappers['ambiq_letter']|1],may_fault=True,capture='full-letter')
    assert isinstance(fault,dict) and fault['pc']==hex((font_words[1]&~1)+8) and fault['errno']==6
    # At this exact original instruction R5 is the null draw-buffer; its +16
    # load precedes the later req_raw_bitmap check. Do not map address zero.
    assert u.reg_read(SAVED[1])==0 and word(cl+0x14)==0
    instruction=decode(raw,int(fault['pc'],0),4)[0]
    assert instruction.mnemonic=='ldr.w' and instruction.op_str=='sb, [r5, #0x10]'
    fault['instruction']=instruction.mnemonic+' '+instruction.op_str
    fault['null_draw_buffer']=True;fault['used_words']=0;fault['main_boot_or_hardware_bug_proven']=False
    return dict(helper=hex(helper),glyphs=glyphs,full_letter_fixture=fault,
        cpu_profile='Unicorn Cortex-M7 with CP10/11 and FPEXC enabled; not Renode M55',
        synthetic_draw_and_nema_state=True,hooks=False,mmio_mapped=False,gpu_executed=False,full_main_rendered=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--capture',action='store_true',help='Export pre-call RAM/register inputs for independent engine replay')
    a=p.parse_args()
    output=a.output.resolve()
    if any((v/'.git').exists() for v in [output,*output.parents]):raise ValueError('Private output required')
    output.mkdir(mode=0o700);results=[];assets={}
    baseline_path=a.simulator/'font-wrapper-contract-07/report.json'
    baseline=json.loads(baseline_path.read_text());assert baseline['passed'] and not baseline['full_main_rendered']
    assets[str(baseline_path.relative_to(a.simulator))]=sha(baseline_path.read_bytes())
    for case,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        bundle=a.simulator/'inputs/verified-01'/filename;_,raw=load_pinned_main(bundle.read_bytes())
        directory=a.simulator/'builtin-font-memory-main-01'/case
        low=(directory/'low-sram.bin').read_bytes();report=json.loads((directory/'report.json').read_text())
        assert len(low)==0x6000 and sha(low)==report['sram']['sha256'] and raw==(directory/'main.bin').read_bytes()
        highfile=a.simulator/('font-draw-buffer-main-01' if case=='stock24' else 'font-draw-buffer-main-02')/case/'report.json'
        hi=json.loads(highfile.read_text())['diagnostics'];high=struct.pack('<'+'I'*len(hi['words']),*hi['words'])
        assert hi['paused'] and hi['base']==(0x20070000 if case=='stock24' else 0x20071450)
        for path in [bundle,directory/'low-sram.bin',directory/'report.json',highfile]:
            relative=str(path.relative_to(a.simulator));digest=sha(path.read_bytes());assets[relative]=digest
            if path!=bundle:assert baseline['source_hashes'][relative]==digest
        captures=output/'captures'/case if a.capture else None
        results.append(dict(case=case,raw_sha256=sha(raw),runtime=inspect_case(raw,low,hi['base'],high,report['fonts'],captures)))
    for result in results[1:]:
        assert [{k:g[k] for k in ['character','glyph_id','width','height','packed_stride','bitmap_sha256']} for g in result['runtime']['glyphs']]==[{k:g[k] for k in ['character','glyph_id','width','height','packed_stride','bitmap_sha256']} for g in results[0]['runtime']['glyphs']]
    assert results[1]['runtime']==results[2]['runtime']
    sources={}
    for name in ['inspect_ambiq_glyph_commands.py','inspect_ambiq_commands.py','inspect_ambiq_target.py','font_wrapper_contract.py','pinned_main.py','blackwall_package.py','revalidate_research_assets.py']:
        data=Path(__file__).with_name(name).read_bytes();(output/name).write_bytes(data);sources[name]=sha(data)
    (output/'report.json').write_text(json.dumps(dict(passed=True,cases=results,source_hashes=sources,asset_hashes=assets,
        full_letter_succeeded=False),indent=2)+'\n');(output/'report.json').chmod(0o600)
    print(json.dumps(dict(passed=True,original_glyph_helper_cases=9,full_letter_faults_preserved=3,full_letter_succeeded=False)))


if __name__=='__main__':main()
