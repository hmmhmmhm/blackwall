"""Bound the original raw-bitmap early load and check data-word independence.

The load must still complete; this is not a proof that hardware permits an
access. Only req_raw_bitmap bit0=1 and a nonzero glyph ID are covered.
"""
import argparse,json,struct,hashlib
from pathlib import Path
from capstone.arm import ARM_REG_R9
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC
import unicorn.arm_const as arm
from inspect_ambiq_target import decode,BASE,WORK,SRAM,STOP
from font_wrapper_contract import discover_wrappers
from pinned_main import load_pinned_main


def sha(data):return hashlib.sha256(data).hexdigest()


def read_contract(raw,entry):
    prefix=decode(raw,entry,0x34)
    assert len(prefix)==20 and prefix[3].mnemonic=='ldr.w' and prefix[3].op_str=='sb, [r5, #0x10]' and not prefix[3].update_flags
    assert [(i.mnemonic,i.op_str) for i in prefix[13:19]]==[
        ('ldrb','r0, [r0, #0x14]'),('lsls','r0, r0, #0x1f'),('bpl','#'+hex(entry+0x34)),
        ('ldr.w','r0, [sl]'),('ldr','r1, [r6]'),('add','r0, r1')]
    assert prefix[5].op_str=='r1, [r0, #0x18]' and prefix[6].op_str=='r1, #0' and prefix[7].mnemonic=='bne' and prefix[7].operands[0].imm==entry+0x1a
    assert prefix[19].mnemonic=='b'
    epilogue=decode(raw,prefix[19].operands[0].imm,4)
    assert len(epilogue)==1 and epilogue[0].mnemonic=='pop.w' and ARM_REG_R9 in epilogue[0].regs_access()[1] and 'pc' in epilogue[0].op_str
    path=prefix[4:8]+prefix[10:]+epilogue
    assert all(ARM_REG_R9 not in i.regs_access()[0] and i.mnemonic not in ['bl','blx'] for i in path)
    return dict(entry=entry,read_pc=entry+8,loaded_register='sb',load_sets_flags=False,
        raw_flag_offset=20,raw_flag_mask=1,glyph_id_offset=24,requires_nonzero_glyph_id=True,
        loaded_word_read_before_return=False,saved_register_restored=True,access_must_complete=True,
        raw_path=[dict(pc=i.address,text=i.mnemonic+' '+i.op_str,bytes=i.bytes.hex()) for i in [prefix[3],*path]])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
    if any((v/'.git').exists() for v in [out,*out.parents]):raise ValueError('Private output required')
    out.mkdir(mode=0o700);results=[]
    source=json.loads((a.simulator/'ambiq-glyph-captures-01/report.json').read_text())
    for case,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        _,raw=load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes());wrappers=discover_wrappers(raw)
        lowdir=a.simulator/'builtin-font-memory-main-01'/case;low=(lowdir/'low-sram.bin').read_bytes();report=json.loads((lowdir/'report.json').read_text())
        assert len(low)==0x6000 and sha(low)==report['sram']['sha256'] and raw==(lowdir/'main.bin').read_bytes()
        font,fields=next((int(k,0),v) for k,v in report['fonts'].items() if v[6]);proof=read_contract(raw,fields[1]&~1)
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);size=(len(raw)+4095)&~4095
        u.mem_map(BASE,size);u.mem_write(BASE,raw);u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
        u.mem_map(SRAM,0x80000);u.mem_write(SRAM,low);u.mem_protect(SRAM,0x80000,UC_PROT_READ)
        u.mem_map(WORK,0x10000);u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        initial=u.context_save();descriptor,buffer=WORK+0x100,WORK+0x200
        def call(entry,args):
            for n in range(13):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),0x12340000+n)
            for reg,value in zip([arm.UC_ARM_REG_R0,arm.UC_ARM_REG_R1,arm.UC_ARM_REG_R2,arm.UC_ARM_REG_R3],args):u.reg_write(reg,value)
            u.reg_write(arm.UC_ARM_REG_SP,WORK+0xff00);u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
            u.emu_start(entry|1,STOP,count=100000)
            assert u.reg_read(arm.UC_ARM_REG_PC)==STOP and u.reg_read(arm.UC_ARM_REG_SP)==WORK+0xff00
            return [u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(13)]
        samples=[]
        for character in [65,87,103]:
            u.context_restore(initial);u.mem_write(WORK,bytes(0x10000))
            assert call(wrappers['descriptor'],[font,descriptor,character,0])[0]==1
            dsc=bytearray(u.mem_read(descriptor,32));dsc[20]|=1;assert int.from_bytes(dsc[24:28],'little')!=0
            expected=next(g for c in source['cases'] if c['case']==case for g in c['runtime']['glyphs'] if g['character']==character)
            outputs=[]
            for word in [0,0xffffffff,0xa5a5a5a5,0x12345678,0x80000000,1]:
                u.context_restore(initial);u.mem_write(WORK,bytes(0x10000));u.mem_write(descriptor,bytes(dsc));u.mem_write(buffer+16,struct.pack('<I',word))
                before=bytes(u.mem_read(WORK,0x10000));regs=call(wrappers['bitmap'],[descriptor,buffer]);after=bytes(u.mem_read(WORK,0x10000))
                assert regs[0]==int(expected['bitmap'],0)
                assert all(i>=0xfc00 and i<0xff00 for i,(x,y) in enumerate(zip(before,after)) if x!=y)
                outputs.append(dict(word=word,registers=regs,stack_sha256=sha(after[0xfc00:0xff00])))
            assert all(o['registers']==outputs[0]['registers'] and o['stack_sha256']==outputs[0]['stack_sha256'] for o in outputs)
            samples.append(dict(character=character,bitmap=expected['bitmap'],outputs=outputs))
        results.append(dict(case=case,raw_sha256=sha(raw),contract=proof,samples=samples))
    sources={}
    for name in ['inspect_glyph_itcm_read.py','inspect_ambiq_target.py','font_wrapper_contract.py','pinned_main.py','blackwall_package.py','revalidate_research_assets.py']:
        data=Path(__file__).with_name(name).read_bytes();(out/name).write_bytes(data);sources[name]=sha(data)
    (out/'report.json').write_text(json.dumps(dict(passed=True,cases=results,source_hashes=sources,bitmap_calls=54,descriptor_calls=9,
        null_address_mapped=False,hardware_accessed=False,full_main_rendered=False),indent=2)+'\n');(out/'report.json').chmod(0o600)
    print(json.dumps(dict(passed=True,bitmap_calls=54,descriptor_calls=9,null_address_mapped=False)))


if __name__=='__main__':main()
