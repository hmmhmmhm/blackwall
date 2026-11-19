"""Pin the MCU info source/layout and compare its memory tables with original ARM literals."""
import argparse,hashlib,json,struct
from pathlib import Path
import xml.etree.ElementTree as ET
import capstone
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute

PINS={'am_hal_mcuctrl.c':'3a75caa326f613bf3aaeba99b1354a9824249b2ed6d139ba2b72010e8eba9500','am_hal_mcuctrl.h':'6504a1af04209e0c111e704a63f0628537a0c59ed8750806784e049fc21fc7f8','am_reg_jedec.h':'e9672ca3a653d80a10c08d7b62986281b6d93f460b66df45a55aa9180159301a'}
REGS={'CHIPPN':0,'CHIPID0':4,'CHIPID1':8,'CHIPREV':12,'VENDORID':16,'SKU':20}
MRAM=(1024,2048,3072,4096)
RAM=(128,256,1024,128,256,2048,256,512,2048,256,512,3072)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
    if o.exists():raise ValueError('Use a fresh evidence directory')
    texts={}
    for name,digest in PINS.items():
        b=(s/'chip-identity-research-01'/name).read_bytes()
        if hashlib.sha256(b).hexdigest()!=digest:raise ValueError('Source pin differs: '+name)
        texts[name]=b.decode()
    h=(s/'upstream/hal-ambiq-61b293a/apollo510.h').read_bytes();svd=(s/'apollo-dfp-research-01/apollo510.svd').read_bytes()
    assert hashlib.sha256(h).hexdigest()=='b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797'
    assert hashlib.sha256(svd).hexdigest()=='a2390c3366450eaccc9d4531d26dc9d68488ec42de5795ee50ab45a266f28276'
    root=ET.fromstring(svd);m=next(x for x in root.findall('./peripherals/peripheral') if x.findtext('name')=='MCUCTRL')
    definitions={}
    for r in m.findall('./registers/register'):
        name=r.findtext('name')
        if name in REGS:
            assert int(r.findtext('addressOffset'),0)==REGS[name]
            definitions[name]=dict(address=hex(0x40020000+REGS[name]),reset=int(r.findtext('resetValue'),0),mask=int(r.findtext('resetMask'),0),access_label=r.findtext('access'))
    assert definitions['CHIPPN']['reset']==0x10320080 and definitions['SKU']['reset']==0x2d480f
    def structure(text,name):
        end=text.index('} '+name+';');begin=text.rfind('typedef struct',0,end)
        return text[begin:end]+'} '+name+';\n'
    c='#include <stdint.h>\n#include <stddef.h>\n#define __IM volatile const\n#define __IOM volatile\n#define __OM volatile\n'
    c+=structure(h.decode(),'MCUCTRL_Type')
    for name,offset in REGS.items():c+=f'_Static_assert(offsetof(MCUCTRL_Type,{name})=={offset},"{name}");\n'
    c+=structure(texts['am_hal_mcuctrl.h'],'am_hal_mcuctrl_device_t')
    for name,offset in [('ui32ChipPN',0),('ui32ChipRev',12),('ui32SKU',20),('ui32Qualified',24),('ui32FlashSize',28),('ui32ITCMSize',32),('ui32DTCMSize',36),('ui32SSRAMSize',40),('ui32MRAMSize',44),('ui32JedecPN',48)]:c+=f'_Static_assert(offsetof(am_hal_mcuctrl_device_t,{name})=={offset},"{name}");\n'
    c+='_Static_assert(sizeof(am_hal_mcuctrl_device_t)==64,"device-info ABI");\n'
    c+=structure(texts['am_reg_jedec.h'],'JEDEC_Type')
    for name,offset in [('PID0',0xe0),('PID1',0xe4),('PID2',0xe8),('PID3',0xec),('CID0',0xf0),('CID1',0xf4),('CID2',0xf8),('CID3',0xfc)]:c+=f'_Static_assert(offsetof(JEDEC_Type,{name})=={offset},"{name}");\n'
    o.mkdir(mode=0o700);(o/'layout.c').write_text(c)
    execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(o/'layout.c'),'-o',str(o/'layout.o')],o,'compiler')
    cs=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS);cs.detail=True;cases=[]
    for name,file in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        prior=json.loads((s/'rtc-functional-main-comparison-01'/name/'report.json').read_text());start=prior['observed']['pc']-8
        _,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes());base=0x438000
        table_matches={};mmio=[];instructions=[]
        for ins in cs.disasm(raw[start-base:start-base+0x160],start):
            instructions.append(dict(address=hex(ins.address),mnemonic=ins.mnemonic,operands=ins.op_str))
            if ins.mnemonic.startswith('ldr') and len(ins.operands)>1 and ins.operands[1].type==ARM_OP_MEM and ins.operands[1].mem.base==ARM_REG_PC:
                pool=((ins.address+4)&~3)+ins.operands[1].mem.disp;target=struct.unpack_from('<I',raw,pool-base)[0]
                if target in [0x40020000+v for v in REGS.values()] or 0xe00fefe0<=target<=0xe00feffc:mmio.append(target)
                if base<=target<base+len(raw)-24:
                    if struct.unpack_from('<4H',raw,target-base)==MRAM:table_matches['mram']=hex(target)
                    if struct.unpack_from('<12H',raw,target-base)==RAM:table_matches['ram']=hex(target)
            if ins.mnemonic=='pop' and 'pc' in ins.op_str:break
        if set(table_matches)!= {'mram','ram'} or mmio[:6]!=[0x40020000+v for v in REGS.values()]:raise ValueError('Original info path/table contract differs')
        if set(mmio[6:])!={0xe00fefe0,0xe00fefe4,0xe00fefe8,0xe00fefec,0xe00feff0,0xe00feff4,0xe00feff8,0xe00feffc}:raise ValueError('Original JEDEC read sites differ')
        cases.append(dict(name=name,candidate_entry=hex(start),table_addresses=table_matches,mmio_literal_targets=[hex(x) for x in mmio],instructions=instructions))
    report=dict(passed=True,definitions=definitions,source_sha256=PINS,source_commit='61b293a49db34030c545f99101f7ebf6a3050314',mram_table_kib=MRAM,ram_table_kib=RAM,selected_sku_sizes_kib=dict(itcm=256,dtcm=512,system_sram=3072,mram=4096),cases=cases,jedec_part_number_known=False,actual_device_identifiers_known=False,scope='pinned register/ABI compilation and static original literal/table comparison; not identity or hardware verification')
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Pinned register6/device ABI/JEDEC offsets compiled; original3 memory tables and literal paths matched')

if __name__=='__main__':main()
