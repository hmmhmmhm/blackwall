"""Inspect original Ambiq draw-target ownership and run bounded ARM preflight.

No hardware access. Synthetic arguments and global unit pointer; stop before
locking/emission or logging. This is not full-main or GPU execution.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R8, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from font_wrapper_contract import BASE, discover_wrappers
from pinned_main import load_pinned_main

SIGNATURES = {
    'dispatch': bytes.fromhex('2de9f8418bb00400a56c2e68'),
    'target': bytes.fromhex('2de9f8418bb004000d001700'),
    'target_format': bytes.fromhex('c0b206281ad00b281cd00c281cd00d28'),
}
WORK, STOP, SRAM = 0x21000000, 0x10000000, 0x20000000


def discover(raw):
    entries = discover_wrappers(raw)
    for name, signature in SIGNATURES.items():
        if raw.count(signature) != 1:
            raise ValueError('Missing or ambiguous Ambiq '+name)
        entries[name] = BASE+raw.index(signature)
    return entries


def decode(raw, address, length):
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    decoder.detail = True
    return list(decoder.disasm(raw[address-BASE:address-BASE+length], address))


def inspect(raw):
    entries = discover(raw)
    dispatch = decode(raw, entries['dispatch'], 0x1c8)
    target = decode(raw, entries['target'], 0x206)
    calls = [i for i in target if i.mnemonic == 'bl']
    getter, zero, intersect = calls[:3]
    format_call = next(i for i in calls if i.operands[0].imm == entries['target_format'])
    getter_body = decode(raw, getter.operands[0].imm, 6)
    assert [i.mnemonic for i in getter_body] == ['ldr', 'ldr', 'bx']
    literal = ((getter_body[0].address+4)&~3)+getter_body[0].operands[1].mem.disp
    global_slot = struct.unpack_from('<I', raw, literal-BASE)[0]
    assert SRAM <= global_slot < SRAM+0x80000
    lock = calls[calls.index(format_call)+2]
    # Target preflight has two failure logs followed by a unit-lock call.
    logger = calls[3].operands[0].imm
    assert calls[calls.index(format_call)+1].operands[0].imm == logger
    ordered = [(i.mnemonic, i.op_str) for i in dispatch]
    assert ordered[:6] == [('push.w', '{r3, r4, r5, r6, r7, r8, lr}'), ('sub', 'sp, #0x2c'), ('movs', 'r4, r0'), ('ldr', 'r5, [r4, #0x48]'), ('ldr', 'r6, [r5]'), ('ldr', 'r0, [r4, #0x4c]')]
    target_sites = [i.address for i in dispatch if i.mnemonic == 'bl' and i.operands[0].imm == entries['target']]
    iterator = decode(raw, entries['ambiq_letter']-0x21e, 0x14)
    label_entry = iterator[0].address
    assert any(i.mnemonic == 'bl' and i.operands[0].imm == label_entry for i in dispatch)
    # Find the shared post-draw call following the last type branch instead of
    # interpreting literal pools or guessing Nema symbols.
    post = next(j for j, i in enumerate(dispatch) if i.mnemonic == 'movs' and i.op_str == 'r0, #1' and j > len(dispatch)-12)
    submit_call = dispatch[post+1]
    assert submit_call.mnemonic == 'bl'
    binding = next(j for j, i in enumerate(target) if i.mnemonic == 'movs' and i.op_str == 'r0, #0' and j+1<len(target) and target[j+1].mnemonic=='str' and target[j+1].op_str=='r0, [sp, #8]')
    bind_body = target[binding:binding+13]
    assert [(i.mnemonic,i.op_str) for i in bind_body[:-1]] == [
        ('movs','r0, #0'),('str','r0, [sp, #8]'),('ldr','r0, [r4, #8]'),('uxth','r0, r0'),
        ('str','r0, [sp, #4]'),('str','r5, [sp]'),('ldr','r3, [r4, #4]'),('lsrs','r3, r3, #0x10'),
        ('ldr','r2, [r4, #4]'),('uxth','r2, r2'),('mov','r1, r8'),('movs','r0, #0')]
    assert bind_body[-1].mnemonic=='bl'
    def rows(instructions):
        return [dict(pc=hex(i.address), instruction=i.mnemonic+' '+i.op_str, bytes=i.bytes.hex()) for i in instructions]
    assert len(target_sites) == 1
    return entries, dict(entries={k:hex(v) for k,v in entries.items()}, global_slot=hex(global_slot),
        getter=hex(getter.operands[0].imm), preflight_boundary=hex(lock.operands[0].imm), logger_boundary=hex(logger),
        target_call=hex(target_sites[0]), label_entry=hex(label_entry), post_draw_call=hex(submit_call.operands[0].imm),
        binding_call=hex(bind_body[-1].address), binding_entry=hex(bind_body[-1].operands[0].imm),
        binding_arguments=['0','data-pointer','width-u16','height-u16','mapped-format','stride-u16','0'],
        dispatch=rows(dispatch), target=rows(target))


def runtime(raw, entries, contract):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    size = (len(raw)+4095)&~4095
    u.mem_map(BASE, size); u.mem_write(BASE, raw)
    u.mem_protect(BASE, size, UC_PROT_READ | UC_PROT_EXEC)
    u.mem_map(SRAM, 0x80000); u.mem_map(WORK, 0x10000)
    u.mem_map(STOP, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
    initial = u.context_save()
    mapped = []
    for cf in range(256):
        u.context_restore(initial)
        u.reg_write(UC_ARM_REG_R0, cf); u.reg_write(UC_ARM_REG_SP, WORK+0xff00); u.reg_write(UC_ARM_REG_LR, STOP|1)
        u.emu_start(entries['target_format']|1, STOP, count=1000)
        assert u.reg_read(UC_ARM_REG_PC) == STOP
        mapped.append(u.reg_read(UC_ARM_REG_R0))
    results = []
    # Distinguish a target color enum from the glyph enum and exercise clip /
    # minimum-area rejection without substituting logger/lock return values.
    cases = [('color14',14,0,64,32,None,'lock',9), ('format20-normal',20,0,64,32,None,'logger',None),
             ('format20-special',20,1,64,32,None,'lock',4), ('one-pixel',14,0,1,1,None,'return',None),
             ('outside-clip',14,0,64,32,(100,100,110,110),'return',None),
             ('clipped',14,0,64,32,(-2,-3,10,11),'lock',9)]
    for name,cf,flag,width,height,clip,expected,fmt in cases:
        u.context_restore(initial); u.mem_write(WORK, bytes(0x10000))
        buf, unit, area, data = WORK+0x100, WORK+0x400, WORK+0x700, WORK+0x1000
        u.mem_write(int(contract['global_slot'],0), struct.pack('<I',unit))
        u.mem_write(buf, struct.pack('<7I', cf<<8, width|(height<<16), 128, 8192, data, 0, 0))
        if clip: u.mem_write(area,struct.pack('<4i',*clip))
        for reg,val in [(UC_ARM_REG_R0,buf),(UC_ARM_REG_R1,area if clip else 0),(UC_ARM_REG_R2,flag),
                        (UC_ARM_REG_SP,WORK+0xff00),(UC_ARM_REG_LR,STOP|1)]:u.reg_write(reg,val)
        # Logger and lock are distinct emu_until boundaries. A tiny code observer
        # is unnecessary: run to expected boundary, never fake their returns.
        boundary = STOP if expected == 'return' else int(contract[expected+'_boundary' if expected=='logger' else 'preflight_boundary'],0)
        before = bytes(u.mem_read(WORK,0x10000))
        sram_before = bytes(u.mem_read(SRAM,0x80000))
        u.emu_start(entries['target']|1, boundary, count=20000)
        assert u.reg_read(UC_ARM_REG_PC) == boundary, name
        assert bytes(u.mem_read(SRAM,0x80000)) == sram_before, name
        assert bytes(u.mem_read(buf,28)) == before[0x100:0x11c], name
        after = bytes(u.mem_read(WORK,0x10000))
        assert all(i >= 0xfe00 for i,(a,b) in enumerate(zip(before,after)) if a != b), name
        if expected == 'return': assert u.reg_read(UC_ARM_REG_R0) == 0
        if expected == 'lock':
            assert [u.reg_read(r) for r in [UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R8]] == [buf,fmt,unit,data]
        sp = u.reg_read(UC_ARM_REG_SP)
        if expected == 'lock':
            expected_area = (0,0,width-1,height-1) if clip is None else (max(0,clip[0]),max(0,clip[1]),min(width-1,clip[2]),min(height-1,clip[3]))
            assert struct.unpack('<4i',u.mem_read(sp+12,16)) == expected_area, name
        results.append(dict(name=name,color_format=cf,special_flag=flag,width=width,height=height,
            clip=clip,boundary=hex(boundary),outcome=expected,target_format=fmt,
            clipped_area=list(struct.unpack('<4i',u.mem_read(sp+12,16))) if expected=='lock' else None,
            pixels_unchanged=True))
    return dict(format_results=mapped,preflight=results,synthetic_global_and_arguments=True,
        memory_write_hook=False,lock_or_emission_executed=False,full_main_rendered=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    # Keep original-code disassembly out of every Git/worktree.
    output=args.output.resolve()
    if any((p/'.git').exists() for p in [output,*output.parents]):raise ValueError('Private output required')
    output.mkdir(mode=0o700)
    cases=[]
    for case,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        _,raw=load_pinned_main((args.simulator/'inputs/verified-01'/filename).read_bytes())
        entries,contract=inspect(raw)
        cases.append(dict(case=case,raw_sha256=hashlib.sha256(raw).hexdigest(),static=contract,runtime=runtime(raw,entries,contract)))
    def normalized(result):
        return dict(format_results=result['format_results'],preflight=[{k:v for k,v in r.items() if k!='boundary'} for r in result['preflight']])
    assert all(normalized(c['runtime'])==normalized(cases[0]['runtime']) for c in cases)
    report=dict(passed=True,cases=cases,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='Original function preflight with synthetic global pointer and arguments; static downstream candidates only')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'report.json').chmod(0o600)
    for name in ['inspect_ambiq_target.py','font_wrapper_contract.py','pinned_main.py','revalidate_research_assets.py','blackwall_package.py']:
        (output/name).write_bytes(Path(__file__).with_name(name).read_bytes())
    print(json.dumps(dict(passed=True,cases=len(cases),format_calls=768,preflight_cases=18)))


if __name__=='__main__':main()
