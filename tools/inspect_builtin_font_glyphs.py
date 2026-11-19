"""Compare bounded ROM cmap decoding with original ARM glyph-descriptor callbacks."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11
from native_replay import digest, parse_log, validate_assets
from pinned_main import load_pinned_main

BASE = 0x438000
SRAM = 0x20000000
WORK = 0x21000000
STOP = 0x10000000
SAMPLES = [0, 9, 10, 32, 65, 0xE9, 0x3B1, 0x410, 0x4E2D, 0x65E5, 0xAC00, 0xD55C, 0x1F600, 0x10FFFF]
SAVED = [UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--bitmap-contract', action='store_true')
    p.add_argument('--wrapper-contract', action='store_true')
    a = p.parse_args()
    if a.bitmap_contract or a.wrapper_contract:
        if a.bitmap_contract and a.wrapper_contract:raise ValueError('Select one contract mode')
        bitmap_contract(a.simulator,a.output,wrappers=a.wrapper_contract)
        return
    a.output.mkdir(mode=0o700)
    checks, results = [], []
    def check(name, ok):
        if not ok:
            raise ValueError(name)
        checks.append(name)
    for key, filename in [('stock24', 'stock-2.4.0.24.bin'), ('stock23', 'stock-2.3.0.24.bin'), ('cfw', 'faceclaw-38-research-only.bin')]:
        directory = a.simulator/'builtin-font-memory-main-01'/key
        report = json.loads((directory/'report.json').read_text())
        validate_assets(directory, json.loads((directory/'derived-inputs.json').read_text())['derived'])
        check(key+'-native', report['passed'] and parse_log((directory/'renode.log').read_text()) == report['observed'])
        _, raw = load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes())
        check(key+'-original-main', raw == (directory/'main.bin').read_bytes())
        sram = (directory/'low-sram.bin').read_bytes()
        check(key+'-snapshot', report['sram'] == dict(base=SRAM, bytes=len(sram), sha256=digest(directory/'low-sram.bin')) and len(sram) == 0x6000)
        def rom(address, size):
            if size < 0 or not BASE <= address <= address+size <= BASE+len(raw):
                raise ValueError('Font reference outside pinned main ROM')
            return raw[address-BASE:address-BASE+size]
        u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        rom_size = (len(raw)+4095) & ~4095
        u.mem_map(BASE, rom_size)
        u.mem_write(BASE, raw)
        u.mem_protect(BASE, rom_size, UC_PROT_READ | UC_PROT_EXEC)
        u.mem_map(SRAM, len(sram))
        u.mem_map(WORK, 0x3000)
        u.mem_map(STOP, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
        for index, register in enumerate(SAVED):
            u.reg_write(register, 0x12340000+index)
        context = u.context_save()
        font_results = []
        for address_hex, font in report['fonts'].items():
            address = int(address_hex, 0)
            check(key+'-'+address_hex+'-snapshot-object', struct.pack('<9I', *font) == sram[address-SRAM:address-SRAM+36])
            if not font[6]:
                continue
            bitmap, glyphs, cmap_address, kern, scale, flags = struct.unpack('<4I2H', rom(font[6], 20))
            count, bpp = flags & 0x1FF, (flags >> 9) & 15
            check(key+'-'+address_hex+'-bounded-cmap-count', 0 < count <= 32)
            mapping, maps, probes = {}, [], set(SAMPLES)
            for i in range(count):
                start, length, first, unicode_list, glyph_offsets, list_length, kind = struct.unpack('<IHHIIHBx', rom(cmap_address+20*i, 20))
                check(key+'-'+address_hex+'-cmap'+str(i), length > 0 and kind in [0, 1, 2, 3] and start+length <= 0x110000)
                entries = {}
                if kind == 2:
                    entries = {start+j:first+j for j in range(length)}
                elif kind == 0:
                    offsets = rom(glyph_offsets, length)
                    entries = {start+j:first+offset for j, offset in enumerate(offsets) if offset or j == 0}
                else:
                    offsets = struct.unpack('<'+'H'*list_length, rom(unicode_list, 2*list_length))
                    check(key+'-'+address_hex+'-sparse'+str(i), list(offsets) == sorted(set(offsets)) and all(j < length for j in offsets))
                    glyph_ids = range(list_length) if kind == 3 else struct.unpack('<'+'H'*list_length, rom(glyph_offsets, 2*list_length))
                    entries = {start+j:first+g for j, g in zip(offsets, glyph_ids)}
                check(key+'-'+address_hex+'-nonoverlap'+str(i), not mapping.keys() & entries.keys())
                mapping.update(entries)
                maps.append(dict(start=start, length=length, type=kind, glyphs=len(entries)))
                probes.update([max(0, start-1), start, start+length-1, start+length])
                # Deterministic absent/in-range probes complement every declared glyph.
                probes.update(start+(j*(length-1)//31) for j in range(32))
            probes.update(mapping)
            rows = []
            for character in sorted(probes):
                u.context_restore(context)
                u.mem_write(SRAM, sram)
                u.mem_write(WORK, b'\0'*0x3000)
                for register, value in [(UC_ARM_REG_R0, address), (UC_ARM_REG_R1, WORK+0x1000), (UC_ARM_REG_R2, character), (UC_ARM_REG_R3, 0), (UC_ARM_REG_SP, WORK+0x2F00), (UC_ARM_REG_LR, STOP|1)]:
                    u.reg_write(register, value)
                try:
                    u.emu_start(font[0], STOP, count=20000)
                except UcError as e:
                    raise ValueError(key+' '+address_hex+' U+'+format(character, '04X')+' original callback fault') from e
                if u.reg_read(UC_ARM_REG_PC) != STOP or u.reg_read(UC_ARM_REG_SP) != WORK+0x2F00 or any(u.reg_read(r) != 0x12340000+i for i,r in enumerate(SAVED)):
                    raise ValueError('Original callback did not return with ABI preserved')
                expected = mapping.get(32 if character == 9 else character, 0)
                actual = u.reg_read(UC_ARM_REG_R0)
                output = bytes(u.mem_read(WORK+0x1000, 32))
                glyph = struct.unpack_from('<I', output, 24)[0]
                if actual != bool(expected) or (actual and glyph != expected):
                    raise ValueError('Original glyph result disagrees with ROM cmap: '+key+' '+address_hex+' '+hex(character))
                rows.append(dict(character=character, found=bool(actual), glyph_id=glyph if actual else None))
            font_results.append(dict(address=address_hex, descriptor=hex(font[6]), callback=hex(font[0]), bpp=bpp,
                                     maps=maps, declared_glyphs=len(mapping), callbacks=len(rows),
                                     ascii_supported=[c for c in range(32,127) if c in mapping],
                                     hangul_syllables=sum(0xAC00 <= c <= 0xD7A3 for c in mapping),
                                     cjk_ideographs=sum(0x3400 <= c <= 0x9FFF or 0x20000 <= c <= 0x323AF for c in mapping),
                                     sample_results=[r for r in rows if r['character'] in SAMPLES],
                                     declared_codepoints_sha256=hashlib.sha256(json.dumps(sorted(mapping)).encode()).hexdigest(),
                                     callback_results_sha256=hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()))
        check(key+'-five-nonempty-fonts', len(font_results) == 5)
        results.append(dict(case=key, fonts=font_results))
    baseline = [(f['declared_codepoints_sha256'], f['callback_results_sha256']) for f in results[0]['fonts']]
    for case in results:
        check(case['case']+'-same-original-glyph-support', [(f['declared_codepoints_sha256'], f['callback_results_sha256']) for f in case['fonts']] == baseline)
        ascii_union = set().union(*(set(f['ascii_supported']) for f in case['fonts']))
        check(case['case']+'-ascii-union', ascii_union == set(range(32,127)))
        check(case['case']+'-no-Hangul-syllables-or-CJK-ideographs', all(f['hangul_syllables'] == f['cjk_ideographs'] == 0 for f in case['fonts']))
    result = dict(passed=True, checks=checks, count=len(checks), cases=results,
                  callbacks=sum(f['callbacks'] for c in results for f in c['fonts']),
                  original_ARM_callbacks=True, synthetic_function_arguments=True,
                  opcode_replaced=False, MMIO_stubbed=False, hardware_accessed=False,
                  full_main_rendered=False,
                  scope='Every declared built-in cmap glyph plus deterministic absent/boundary/sample probes matched original ARM descriptor callbacks; no bitmap decode, font chain execution, external fonts or integrated display')
    (a.output/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, count=len(checks), callbacks=result['callbacks'], fonts=15)))


def bitmap_contract(simulator,output,wrappers=False):
    """Execute original bitmap callbacks with explicit caller-owned synthetic buffers."""
    from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
    import zlib
    output.mkdir(mode=0o700)
    checks=[];cases=[];sheet=bytearray(336*320);pins={}
    def check(name,value):
        if not value:raise ValueError(name)
        checks.append(name)
    def pin(path):
        pins[str(path.relative_to(simulator))]=digest(path)
    for case,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        lowdir=simulator/'builtin-font-memory-main-01'/case
        highdir=simulator/('font-draw-buffer-main-01' if case=='stock24' else 'font-draw-buffer-main-02')/case
        lowreport=json.loads((lowdir/'report.json').read_text());highreport=json.loads((highdir/'report.json').read_text())
        for folder in [lowdir,highdir]:
            validate_assets(folder,json.loads((folder/'derived-inputs.json').read_text())['derived'])
            for name in ['main.bin','strict.cs','report.json','renode.log','derived-inputs.json']:pin(folder/name)
        check(case+':native-cpu',parse_log((highdir/'renode.log').read_text())==highreport['observed']==lowreport['observed'])
        check(case+':native-events',highreport['selected_observation']==lowreport['selected_observation'])
        check(case+':native-semantic',highreport['passed'] and highreport['execution_passed'] and highreport['semantic_validation']['passed'])
        marker=[json.loads(l.split(' ',1)[1]) for l in (highdir/'renode.log').read_text().splitlines() if l.startswith('BLACKWALL_CANDIDATE_'+('font-draw-buffer-snapshot-v1' if case=='stock24' else 'font-draw-buffer-extra-v1')+' ')]
        check(case+':snapshot-log',marker==[highreport['diagnostics']])
        low=(lowdir/'low-sram.bin').read_bytes();pin(lowdir/'low-sram.bin')
        check(case+':low-snapshot',len(low)==0x6000 and digest(lowdir/'low-sram.bin')==lowreport['sram']['sha256'])
        hi=highreport['diagnostics'];high_base=0x20070000 if case=='stock24' else 0x20071450;high_words=1024 if case=='stock24' else 8
        check(case+':high-shape',hi['paused'] and hi['base']==high_base and len(hi['words'])==high_words)
        high=struct.pack('<'+'I'*high_words,*hi['words'])
        _,raw=load_pinned_main((simulator/'inputs/verified-01'/filename).read_bytes())
        check(case+':original-main',raw==(lowdir/'main.bin').read_bytes()==(highdir/'main.bin').read_bytes())
        if wrappers:
            from font_wrapper_contract import discover_wrappers,static_contract
            entries=discover_wrappers(raw);wrapper_static=static_contract(raw,entries)
        def rom(address,size):
            if not BASE<=address<=address+size<=BASE+len(raw):raise ValueError('ROM reference escapes main')
            return raw[address-BASE:address-BASE+size]
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);size=(len(raw)+4095)&~4095
        u.mem_map(BASE,size);u.mem_write(BASE,raw);u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
        u.mem_map(SRAM,0x80000);u.mem_map(WORK,0x10000);u.mem_map(STOP,4096,UC_PROT_READ|UC_PROT_EXEC)
        if wrappers:u.mem_protect(SRAM,0x80000,UC_PROT_READ)
        writes=[];executed=set();reads=[];memset_trace=[]
        def access(cpu,kind,address,size,value,unused):
            allowed=any(a<=address and address+size<=b for a,b in [(BASE,BASE+len(raw)),(SRAM,SRAM+len(low)),(high_base,high_base+len(high)),(WORK,WORK+0x10000)])
            if not allowed:raise ValueError('Read/write outside initialized snapshot or explicit caller buffer: '+hex(address))
            if kind==17:writes.append((address,size))
            else:reads.append((address,size))
        # This pinned Unicorn's write hook changes conditional STM behavior in original memset.
        # Wrappers use protected inputs and per-call final-memory diffs, not a harmful observer.
        u.hook_add(UC_HOOK_MEM_READ if wrappers else UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,access)
        def instruction(cpu,address,size,unused):
            executed.add(address)
            if wrappers and 0x43c0e4<=address<=0x43c148 and len(memset_trace)<60:
                memset_trace.append(dict(pc=hex(address),r0=hex(cpu.reg_read(UC_ARM_REG_R0)),r1=hex(cpu.reg_read(UC_ARM_REG_R1)),r2=hex(cpu.reg_read(UC_ARM_REG_R2))))
        u.hook_add(UC_HOOK_CODE,instruction)
        def fault(cpu,kind,address,size,value,unused):
            (output/'fault.json').write_text(json.dumps(dict(case=case,kind=kind,address=hex(address),size=size,value=value,pc=hex(cpu.reg_read(UC_ARM_REG_PC)),registers=[hex(cpu.reg_read(r)) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]],memset_trace=memset_trace),indent=2)+'\n')
            return False
        u.hook_add(UC_HOOK_MEM_INVALID,fault)
        def call(fn,args,allowed_writes=()):
            before=bytes(u.mem_read(WORK,0x10000)) if wrappers else None
            for reg,value in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(reg,value)
            for i,reg in enumerate(SAVED):u.reg_write(reg,0x12340000+i)
            u.reg_write(UC_ARM_REG_SP,WORK+0xff00);u.reg_write(UC_ARM_REG_LR,STOP|1)
            u.emu_start(fn,STOP,count=100000)
            if u.reg_read(UC_ARM_REG_PC)!=STOP or u.reg_read(UC_ARM_REG_SP)!=WORK+0xff00 or any(u.reg_read(reg)!=0x12340000+i for i,reg in enumerate(SAVED)):raise ValueError('Original callback ABI/return failure')
            if wrappers:
                after=bytes(u.mem_read(WORK,0x10000));allowed=[(WORK+0xfc00,WORK+0xff00),*allowed_writes]
                check(case+':wrapper-final-write-ownership',all(any(a<=WORK+i<b for a,b in allowed) for i,(x,y) in enumerate(zip(before,after)) if x!=y))
            return u.reg_read(UC_ARM_REG_R0)
        fonts=[]
        for index,(address_hex,font) in enumerate((a,f) for a,f in lowreport['fonts'].items() if f[6]):
            address=int(address_hex,0);check(case+':font-object:'+address_hex,struct.pack('<9I',*font)==low[address-SRAM:address-SRAM+36])
            bitmap,glyphs,cmap,kern,scale,flags=struct.unpack('<4I2H',rom(font[6],20))
            check(case+':format:'+address_hex,(flags>>14)==3 and (flags>>9)&15==4 and font[2]==0)
            md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
            ins=list(md.disasm(rom(font[1]&~1,0x2f4),font[1]&~1))
            stride_helper=next(i.operands[0].imm for i in ins if i.mnemonic=='bl')
            loader=next(i for i in md.disasm(rom(stride_helper,32),stride_helper) if i.mnemonic.startswith('ldr') and '[pc,' in i.op_str)
            handlers=struct.unpack('<I',rom(((loader.address+4)&~3)+loader.operands[1].mem.disp,4))[0]
            check(case+':handler-snapshot:'+address_hex,high_base<=handlers and handlers+24<=high_base+len(high))
            stride_callback=struct.unpack_from('<I',high,handlers-high_base+20)[0]
            check(case+':original-stride-callback:'+address_hex,BASE<=stride_callback<BASE+len(raw) and stride_callback&1)
            glyph_rows=[];reshape_rows=[]
            for column,character in enumerate([32,65,87,103,0x3b1,0x410,0x1f600]):
                u.mem_write(SRAM,low);u.mem_write(high_base,high);u.mem_write(WORK,b'\0'*0x10000)
                # The caller supplies resolved_font; the raw descriptor callback leaves this field alone.
                u.mem_write(WORK+0x1000,b'\xa5'*32 if wrappers else struct.pack('<I',address))
                found=call((entries['descriptor']|1) if wrappers else font[0],[address,WORK+0x1000,character,0],[(WORK+0x1000,WORK+0x1020)])
                check(case+':descriptor-bool:'+address_hex+':'+str(character),found in (0,1))
                if not found:
                    if wrappers:check(case+':missing-glyph-clears-font',bytes(u.mem_read(WORK+0x1000,4))==bytes(4))
                    continue
                descriptor=bytes(u.mem_read(WORK+0x1000,32));glyph_id=struct.unpack_from('<I',descriptor,24)[0]
                if wrappers:
                    check(case+':wrapper-resolves-font',struct.unpack_from('<I',descriptor)[0]==address)
                    check(case+':wrapper-clears-entry',descriptor[28:32]==bytes(4))
                offset,adv,unused,width,height,ofs_x,ofs_y=struct.unpack('<IHHHHhh',rom(glyphs+16*glyph_id,16))
                check(case+':bounded-glyph',0<=width<=48 and 0<=height<=64 and descriptor[20]&1==0)
                # The original format-3 loop advances an extra byte after every row, including even widths.
                packed_stride=width//2+1
                packed=rom(bitmap+offset,packed_stride*height)
                expected=bytes(((packed[y*packed_stride+x//2]>>(4 if x%2==0 else 0))&15)*17 for y in range(height) for x in range(width))
                if wrappers and width*height:
                    draw=WORK+0x1800;data=WORK+0x2000
                    # Glyph format and draw-buffer color format are different enums.
                    # The original letter caller's allocation uses color format 14.
                    header=struct.pack('<5I',14<<8,0,0,0x2000,data)
                    u.mem_write(draw,header);u.mem_write(WORK+0xff00,struct.pack('<I',0))
                    resized=call(entries['reshape']|1,[draw,0,width,height],[(draw,draw+12)])
                    current=bytes(u.mem_read(draw,20));w,h=struct.unpack_from('<HH',current,4);stride=struct.unpack_from('<H',current,8)[0]
                    check(case+':reshape-reuses-owned-buffer',resized==draw and (w,h)==(width,height) and current[12:20]==header[12:20] and stride>=width)
                    u.mem_write(draw+12,struct.pack('<I',0));before=bytes(u.mem_read(draw,20))
                    rejected=call(entries['reshape']|1,[draw,0,width,height])
                    check(case+':reshape-rejects-capacity',rejected==0 and bytes(u.mem_read(draw,20))==before)
                    reshape_rows.append(dict(character=character,width=width,height=height,stride=stride,capacity=0x2000,color_format=14,glyph_format=descriptor[14]))
                outputs=[]
                for data_address in [WORK+0x2000,WORK+0x5000]:
                    u.mem_write(data_address-32,b'\xa5'*(0x2000+64))
                    u.mem_write(WORK+0x1800,b'\0'*32);u.mem_write(WORK+0x1810,struct.pack('<I',data_address))
                    writes.clear();executed.clear();reads.clear()
                    result=call((entries['bitmap']|1) if wrappers else font[1],[WORK+0x1000,WORK+0x1800,0,0],[(data_address,data_address+width*height)])
                    pixel_bytes=bytes(u.mem_read(data_address,width*height))
                    check(case+':bitmap-result',result==(WORK+0x1800 if width*height else 0))
                    check(case+':original-pixel-match:'+address_hex+':'+str(character),pixel_bytes==expected)
                    check(case+':buffer-canaries',bytes(u.mem_read(data_address-32,32))==b'\xa5'*32 and bytes(u.mem_read(data_address+width*height,32))==b'\xa5'*32)
                    if not wrappers:check(case+':write-ownership',all(data_address<=a and a+n<=data_address+width*height or WORK+0xfc00<=a and a+n<=WORK+0xff00 for a,n in writes))
                    check(case+':descriptor-preserved',bytes(u.mem_read(WORK+0x1000,32))==descriptor)
                    check(case+':real-stride-call',not width*height or (stride_callback&~1) in executed)
                    if wrappers:
                        call(entries['release']|1,[WORK+0x1000,0,0,0])
                        check(case+':release-preserves-caller-data',bytes(u.mem_read(data_address,width*height))==pixel_bytes and bytes(u.mem_read(WORK+0x1000,32))==descriptor)
                    outputs.append(pixel_bytes)
                check(case+':caller-buffer-relocation',outputs[0]==outputs[1])
                if case=='stock24':
                    for y in range(height):
                        for x in range(width):sheet[(index*64+y)*336+column*48+x]=expected[y*width+x]
                glyph_rows.append(dict(character=character,glyph_id=glyph_id,width=width,height=height,bytes=len(expected),sha256=hashlib.sha256(outputs[0]).hexdigest()))
            fonts.append(dict(address=address_hex,descriptor_callback=hex(font[0]),bitmap_callback=hex(font[1]),release_callback=font[2],stride_handler=hex(handlers),stride_callback=hex(stride_callback),glyphs=glyph_rows,**({'reshape':reshape_rows} if wrappers else {})))
        prefix=None
        if wrappers:
            # Original letter caller with an explicit, already-owned reusable draw buffer.
            # Stop at the real backend entry; never replace it with a successful return.
            u.mem_write(SRAM,low);u.mem_write(high_base,high);u.mem_write(WORK,bytes(0x10000))
            task,context,point,draw,data=WORK+0x100,WORK+0x300,WORK+0x500,WORK+0x1800,WORK+0x5000
            selected=int(fonts[0]['address'],0)
            u.mem_write(task+0x38,struct.pack('<4i',0,0,575,287))
            u.mem_write(context+0x2c,struct.pack('<I',draw));u.mem_write(point,struct.pack('<2i',10,10))
            u.mem_write(draw,struct.pack('<5I',14<<8,0,0,0x2000,data));u.mem_write(data,b'\xa5'*0x2000)
            u.mem_write(WORK+0xff00,struct.pack('<2I',65,entries['ambiq_letter']|1))
            before=bytes(u.mem_read(WORK,0x10000));executed.clear()
            for reg,value in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],[task,context,point,selected]):u.reg_write(reg,value)
            for i,reg in enumerate(SAVED):u.reg_write(reg,0x12340000+i)
            u.reg_write(UC_ARM_REG_SP,WORK+0xff00);u.reg_write(UC_ARM_REG_LR,STOP|1)
            u.emu_start(entries['letter']|1,entries['ambiq_letter'],count=200000)
            check(case+':letter-reaches-real-backend',u.reg_read(UC_ARM_REG_PC)==entries['ambiq_letter'] and entries['descriptor'] in executed and entries['reshape'] in executed)
            check(case+':letter-backend-arguments',[u.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]]==[task,context,0,0])
            sp=u.reg_read(UC_ARM_REG_SP);area_ptr=struct.unpack('<I',u.mem_read(context+8,4))[0];glyph_ptr=struct.unpack('<I',u.mem_read(context+16,4))[0]
            glyph=bytes(u.mem_read(glyph_ptr,32));area=struct.unpack('<4i',u.mem_read(area_ptr,16))
            check(case+':borrowed-stack-descriptor-and-area',glyph_ptr==sp+12 and area_ptr==sp+44 and sp<WORK+0xff00)
            check(case+':letter-resolved-font',struct.unpack_from('<I',glyph)[0]==selected)
            check(case+':letter-reuses-buffer',struct.unpack('<I',u.mem_read(context+0x2c,4))[0]==draw and struct.unpack('<I',u.mem_read(draw+16,4))[0]==data)
            check(case+':letter-not-yet-rendered',bytes(u.mem_read(data,0x2000))==b'\xa5'*0x2000)
            after=bytes(u.mem_read(WORK,0x10000));allowed=[(context,context+0x30),(draw,draw+12),(WORK+0xfc00,WORK+0xff00)]
            check(case+':letter-final-write-ownership',all(any(a<=WORK+i<b for a,b in allowed) for i,(x,y) in enumerate(zip(before,after)) if x!=y))
            prefix=dict(entry=hex(entries['letter']),boundary=hex(entries['ambiq_letter']),glyph_descriptor=hex(glyph_ptr),area_pointer=hex(area_ptr),area=list(area),format=glyph[14],resolved_font=hex(selected),caller_buffer_reused=True,backend_executed=False,synthetic_task_and_clip=True)
        check(case+':five-fonts',len(fonts)==5);cases.append(dict(case=case,fonts=fonts,**({'wrapper_static':wrapper_static,'letter_prefix':prefix} if wrappers else {})))
    for case in cases[1:]:
        check(case['case']+':same-rendered-glyphs',[[g for g in f['glyphs']] for f in case['fonts']]==[[g for g in f['glyphs']] for f in cases[0]['fonts']])
    def chunk(kind,payload):return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',336,320,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+sheet[y*336:(y+1)*336] for y in range(320))))+chunk(b'IEND',b'')
    (output/'glyph-sheet.png').write_bytes(png)
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,source_hashes=pins,bitmap_calls=2*sum(len(f['glyphs']) for c in cases for f in c['fonts']),preview=dict(path='glyph-sheet.png',sha256=digest(output/'glyph-sheet.png'),columns=[32,65,87,103,0x3b1,0x410,0x1f600]),original_ARM_callbacks=True,synthetic_function_arguments=True,opcode_replaced=False,hardware_accessed=False,full_main_rendered=False,resolved_font_supplied_by_caller=not wrappers,scope='Original generic font wrappers with caller-owned buffers and static renderer caller ordering; no natural main render' if wrappers else 'Original descriptor and bitmap callbacks using original initialized stride dispatch, explicit resolved_font and caller-owned buffers; no natural renderer path or display submission')
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),bitmap_calls=result['bitmap_calls'])))


if __name__ == '__main__':
    main()
