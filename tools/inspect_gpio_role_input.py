"""Inspect original GPIO156 role selection and run isolated original GPIO read helpers."""
import argparse,hashlib,json,struct,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_XPSR
from inspect_mspi1_config_contract import collect
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[];calls=0
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    collect(s)
    source=s/'gpio-research-01';pin=json.loads((source/'source-report.json').read_text())
    for filename in ['am_hal_gpio.c','am_hal_gpio.h']:
        check(filename+'-pin',pin['commit']=='61b293a49db34030c545f99101f7ebf6a3050314' and hashlib.sha256((source/filename).read_bytes()).hexdigest()==pin['files'][filename]['sha256'])
    hal=(source/'am_hal_gpio.c').read_text();check('HAL-single-pin-extraction','(*pui32Target >> (ui32GpioNum % 32)) & 1' in hal)
    svd=ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot();gpio=next(x for x in svd.findall('./peripherals/peripheral') if x.findtext('name')=='GPIO')
    rd=next(r for r in gpio.findall('./registers/register') if r.findtext('name')=='RD4')
    check('GPIO-RD4-address',int(gpio.findtext('baseAddress'),0)+int(rd.findtext('addressOffset'),0)==0x40010414)
    patterns=sorted({0,0xffffffff}|{1<<i for i in range(32)}|{0xffffffff^(1<<i) for i in range(32)})
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
    for key,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        d=s/'littlefs-format-main-01'/key;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());check(key+'-native-report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        _,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes());check(key+'-original-main',raw==(d/'main.bin').read_bytes())
        def code(addr,size):return {i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[addr-0x438000:addr+size-0x438000],addr)}
        def literal(addr):
            i=next(md.disasm(raw[addr-0x438000:addr+4-0x438000],addr));mem=next(o.mem for o in i.operands if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC)
            return struct.unpack_from('<I',raw,(((addr+4)&~3)+mem.disp)-0x438000)[0]
        def string(addr):return raw[addr-0x438000:addr-0x438000+256].split(b'\0')[0].decode('ascii')
        pc=v['pc'];entry=pc-0x1a;c=code(entry,0x4c);ctx=v['register_context'];caller=(ctx['r14']&~1)-4;role=caller-0x54;rc=code(role,0x158)
        check(key+'-pin156-input-mode-path',ctx['r0']==156 and ctx['r3']==4 and ctx['r1']==0x40010414 and c[entry]==('uxtb','r1, r1') and c[entry+4]==('beq','#'+hex(entry+0xe)))
        check(key+'-RD-bank-and-bit-layout',literal(entry+0xe)==0x40010404 and c[entry+0x12]==('ubfx','r3, r0, #5, #3') and c[entry+0x16]==('add.w','r1, r1, r3, lsl #2') and c[entry+0x1c]==('ands','r0, r0, #0x1f') and c[entry+0x22]==('ands','r1, r1, #1'))
        check(key+'-actual-input-pin-config',v['gpio_config']['values']['0x40010270']==0x93)
        check(key+'-caller-explicit-pin-and-mode',rc[caller-2]==('movs','r0, #0x9c') and rc[caller-4]==('movs','r1, #0') and rc[caller]==('bl','#'+hex(entry)))
        check(key+'-five-sample-loop',rc[role+0x48]==('adds','r4, r4, #1') and rc[role+0x4a]==('cmp','r4, #5') and rc[role+0x4c]==('bge','#'+hex(role+0xa6)))
        check(key+'-sample-mismatch-latches',rc[role+0x38]==('cmp','r0, r1') and rc[role+0x3a]==('beq','#'+hex(role+0x3e)) and rc[role+0x3c]==('movs','r5, #0'))
        check(key+'-inter-sample-delay-argument5',rc[role+0x42]==('movs','r0, #5') and rc[role+0x44][0]=='bl')
        check(key+'-role-function-and-module-names',string(literal(role+0x70))=='_private_getCurrentRoleStatus' and string(literal(role+0x78))=='sync.module.framework')
        check(key+'-read-failure-or-inconsistent-role3',rc[role+0xa2]==('movs','r0, #3') and rc[role+0xee]==('movs','r0, #3'))
        check(key+'-stable-high-role2-low-role1',rc[role+0x13a]==('cmp','r4, #1') and rc[role+0x13c]==('bne','#'+hex(role+0x14a)) and rc[role+0x13e]==('movs','r0, #2') and rc[role+0x14a]==('movs','r0, #1'))
        sync_call=(v['stack_context']['words'][11]&~1)-4;sync=sync_call
        sc=code(sync,0x150)
        check(key+'-parent-dispatch-role1-and2',sc[sync]==('bl','#'+hex(role)) and sc[sync+6]==('cmp','r0, #1') and sc[sync+10]==('cmp','r0, #2') and sc[sync+8][0]=='beq' and sc[sync+12][0]=='beq.w')
        master=int(sc[sync+8][1][1:],0);slave=int(sc[sync+12][1][1:],0)
        check(key+'-role-label-Master-Slave',string(literal(master+8))=='Sync module start up as Master' and string(literal(slave+8))=='Sync module start up as Slave')
        uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);page=entry&~0xfff;uc.mem_map(page,0x1000);uc.mem_write(page,raw[page-0x438000:page-0x438000+0x1000]);uc.mem_map(0x10000,0x1000);uc.mem_map(0x20000000,0x1000);uc.mem_map(0x40010000,0x1000)
        reads=[];uc.hook_add(UC_HOOK_MEM_READ,lambda uc,access,address,size,value,data:reads.append((address,size)),begin=0x40010000,end=0x40010fff)
        for mode,offset in [(0,0xe),(1,0x2c),(2,0x3a)]:
            address=literal(entry+offset)+16
            for word in patterns:
                reads.clear();uc.mem_write(address,struct.pack('<I',word));uc.mem_write(0x20000000,struct.pack('<I',0xa5a5a5a5));uc.reg_write(UC_ARM_REG_XPSR,1<<24);uc.reg_write(UC_ARM_REG_R0,156);uc.reg_write(UC_ARM_REG_R1,mode);uc.reg_write(UC_ARM_REG_R2,0x20000000);uc.reg_write(UC_ARM_REG_LR,0x10001);uc.emu_start(entry|1,0x10000,count=64)
                if uc.reg_read(UC_ARM_REG_PC)!=0x10000 or uc.reg_read(UC_ARM_REG_R0)!=0 or struct.unpack('<I',uc.mem_read(0x20000000,4))[0]!=(word>>28)&1 or reads!=[(address,4)]:raise ValueError(key+'-original-helper-case')
                calls+=1
        check(key+'-isolated-helper-198-calls',len(patterns)==66)
        cases.append(dict(case=key,pin=156,bank=4,bit=28,known_mask='0x10000000',input_register='0x40010414',gpio_function=hex(entry),input_read_pc=hex(pc),role_function=hex(role),role_return=hex(role+0x154),pin_config='0x93',low_role=1,high_role=2,labels={'1':'Master','2':'Slave'},temple_side_mapping_verified=False))
    result=dict(passed=True,count=len(checks),checks=checks,isolated_original_helper_calls=calls,cases=cases,scope='Source role/debounce contract and isolated GPIO getter on synthetic MMIO RAM only; no new full-main run, role/temple electrical validation or GPIO input supplied to Renode')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),isolated_original_helper_calls=calls)))


if __name__=='__main__':main()
