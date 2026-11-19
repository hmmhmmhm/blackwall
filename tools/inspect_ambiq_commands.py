"""Execute original command-list bind, texture binding, unbind and rewind in RAM.

Synthetic Nema state and preallocated descriptor, no GPU/MMIO mapping or hooks.
The original ARM performs all list/state updates. Never a main-boot proof.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11
from inspect_ambiq_target import BASE, WORK, STOP, SRAM, inspect, decode
from pinned_main import load_pinned_main

SIGNATURES = {
    'bind_circular': bytes.fromhex('f0b581b004000d4608bf4ff400502bd0'),
    'unbind': bytes.fromhex('30b4dff8b806'),
    'reserve': bytes.fromhex('70b5dff8a452'),
}
SAVED=[UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]


def discover(raw):
    _, target = inspect(raw)
    entries={'texture_binding':int(target['binding_entry'],0)}
    for name,signature in SIGNATURES.items():
        if raw.count(signature)!=1:raise ValueError('Missing or ambiguous command-list '+name)
        entries[name]=BASE+raw.index(signature)
    entries['rewind']=entries['bind_circular']-0x50
    assert raw[entries['rewind']-BASE:entries['rewind']-BASE+12]==bytes.fromhex('10b5040005d14ff40050bde8')
    # This exact original load follows the format/stride calculation and jump
    # table. Do not disassemble jump-table bytes as ARM instructions.
    load=decode(raw,entries['texture_binding']+0x138,4)[0]
    assert load.mnemonic=='ldr.w' and load.op_str.startswith('r7, [pc, #')
    literal=((load.address+4)&~3)+load.operands[1].mem.disp
    slot=struct.unpack_from('<I',raw,literal-BASE)[0]
    assert SRAM<=slot<SRAM+0x80000
    calls=[i for i in decode(raw,entries['texture_binding']+0x138,0x98) if i.mnemonic=='bl']
    assert any(i.operands[0].imm==entries['reserve'] for i in calls)
    return entries,slot


def execute(raw,entries,slot):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    size=(len(raw)+4095)&~4095
    u.mem_map(BASE,size);u.mem_write(BASE,raw);u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
    u.mem_map(SRAM,0x80000);u.mem_map(WORK,0x10000);u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
    state,cl,commands,pixels=WORK+0x1000,WORK+0x2000,WORK+0x4000,WORK+0x8000
    initial=u.context_save()
    def word(address):return struct.unpack('<I',u.mem_read(address,4))[0]
    def put(address,value):u.mem_write(address,struct.pack('<I',value))
    def reset():
        u.context_restore(initial);u.mem_write(WORK,bytes(0x10000));u.mem_write(SRAM,bytes(0x80000))
        put(slot,state)
        # A synthetic preallocated buffer object: size in bytes, unused handle,
        # virtual pointer, physical pointer; capacity is in 32-bit words.
        u.mem_write(cl,struct.pack('<4I',512,0,commands,commands));put(cl+0x10,128)
        put(cl+0x1c,0xffffffff);put(cl+0x34,0xffffffff);put(cl+0x38,0xffffffff)
        u.mem_write(commands,b'\xa5'*512);u.mem_write(pixels,b'\x7b'*4096)
    def call(entry,args=(),stack=()):
        for i,reg in enumerate(SAVED):u.reg_write(reg,0x12340000+i)
        for reg,value in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(reg,value)
        u.reg_write(UC_ARM_REG_SP,WORK+0xff00);u.reg_write(UC_ARM_REG_LR,STOP|1)
        u.mem_write(WORK+0xff00,struct.pack('<'+'I'*len(stack),*stack))
        before=bytes(u.mem_read(WORK,0x10000));sram_before=bytes(u.mem_read(SRAM,0x80000))
        u.emu_start(entry|1,STOP,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==STOP and u.reg_read(UC_ARM_REG_SP)==WORK+0xff00
        assert [u.reg_read(r) for r in SAVED]==[0x12340000+i for i in range(8)]
        assert bytes(u.mem_read(SRAM,0x80000))==sram_before
        after=bytes(u.mem_read(WORK,0x10000))
        allowed=[(0x1000,0x1100),(0x2000,0x2040),(0x4000,0x4200),(0xfe00,0xff00)]
        assert all(any(a<=i<b for a,b in allowed) for i,(x,y) in enumerate(zip(before,after)) if x!=y)
        assert bytes(u.mem_read(pixels,4096))==b'\x7b'*4096
        return u.reg_read(UC_ARM_REG_R0)
    results=[]
    for index,width,height,fmt,stride in [(0,64,32,9,128),(1,11,16,8,16),(0,64,32,9,256)]:
        reset();call(entries['bind_circular'],[cl,2])
        assert word(state+4)==cl and word(cl+0x14)==0 and word(cl+0x28)==2 and word(cl+0x2c)==64
        assert word(cl+0x18)&0x20
        call(entries['texture_binding'],[index,pixels,width,height],[fmt,stride,0])
        expected=[index*16,pixels,index*16+4,(fmt<<24)|stride,index*16+8,(height<<16)|width]
        emitted=list(struct.unpack('<6I',u.mem_read(commands,24)))
        assert emitted==expected and word(cl+0x14)==6
        cache=state+index*24
        assert [word(cache+o) for o in [0x38,0x3c,0x40,0x44,0x48,0x4c]]==[pixels,width,height,(fmt<<24)|stride,1,fmt]
        call(entries['texture_binding'],[index,pixels,width,height],[fmt,stride+16,0])
        appended=[index*16,pixels,index*16+4,(fmt<<24)|(stride+16),index*16+8,(height<<16)|width]
        assert word(cl+0x14)==12 and list(struct.unpack('<12I',u.mem_read(commands,48)))==expected+appended
        assert bytes(u.mem_read(commands+48,512-48))==b'\xa5'*(512-48)
        call(entries['unbind'])
        assert word(state+4)==0 and list(struct.unpack('<2I',u.mem_read(commands+48,8)))==[0x50000,0]
        assert word(cl+0x14)==12 and word(cl+0x18)&0x28==0
        call(entries['rewind'],[cl])
        assert word(cl+0x14)==0 and list(struct.unpack('<12I',u.mem_read(commands,48)))==expected+appended
        results.append(dict(texture_index=index,width=width,height=height,mapped_format=fmt,stride=stride,
            emitted_words=emitted,appended_words=appended,append_preserves_prefix=True,unbind_words=[0x50000,0],used_words_before_rewind=12,rewind_preserves_bytes=True,pixels_unchanged=True))
    # Absent list follows original sticky-error handling, not an observer stub.
    reset();call(entries['texture_binding'],[0,pixels,64,32],[9,128,0])
    assert word(state+0x20)==0x80 and word(state+4)==0 and bytes(u.mem_read(commands,512))==b'\xa5'*512
    # Misaligned physical pointer is rejected by original circular bind.
    reset();put(cl+12,commands+1);call(entries['bind_circular'],[cl,2])
    assert word(state+0x20)==0x4000 and word(state+4)==0
    return dict(cases=results,null_list_error=0x80,misaligned_buffer_error=0x4000,
        synthetic_preallocation_and_state=True,original_bind_activates_list=True,
        original_commands=True,mmio_mapped=False,hooks=False,gpu_executed=False,full_main_rendered=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    output=args.output.resolve()
    if any((v/'.git').exists() for v in [output,*output.parents]):raise ValueError('Private output required')
    output.mkdir(mode=0o700);results=[]
    for case,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        _,raw=load_pinned_main((args.simulator/'inputs/verified-01'/filename).read_bytes())
        entries,slot=discover(raw)
        results.append(dict(case=case,raw_sha256=hashlib.sha256(raw).hexdigest(),entries={k:hex(v) for k,v in entries.items()},
            global_slot=hex(slot),runtime=execute(raw,entries,slot)))
    assert all(r['runtime']==results[0]['runtime'] for r in results)
    sources={}
    for name in ['inspect_ambiq_commands.py','inspect_ambiq_target.py','font_wrapper_contract.py','pinned_main.py','blackwall_package.py','revalidate_research_assets.py']:
        data=Path(__file__).with_name(name).read_bytes();(output/name).write_bytes(data);sources[name]=hashlib.sha256(data).hexdigest()
    (output/'report.json').write_text(json.dumps(dict(passed=True,cases=results,source_hashes=sources),indent=2)+'\n');(output/'report.json').chmod(0o600)
    print(json.dumps(dict(passed=True,images=3,emission_calls=18,error_cases=6,original_arm_calls=51)))


if __name__=='__main__':main()
