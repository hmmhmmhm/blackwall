"""Identify UART0 enable and shared HCPA polling from pinned original main, not HAL enum guesses."""
import argparse,hashlib,json,re,struct,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    src=s/'mspi1-source-research-01';manifest=json.loads((src/'sources.json').read_text())
    check('HAL-commit',manifest['commit']=='61b293a49db34030c545f99101f7ebf6a3050314')
    for filename in ['am_hal_pwrctrl.c','am_hal_pwrctrl.h','apollo510.h']:
        pin=next(f for f in manifest['files'] if f['path'].endswith('/'+filename));check(filename+'-pin',hashlib.sha256((src/filename).read_bytes()).hexdigest()==pin['sha256'])
    header=(src/'am_hal_pwrctrl.h').read_text();enum=header[header.index('AM_HAL_PWRCTRL_PERIPH_IOS0,'):header.index('} am_hal_pwrctrl_periph_e;')]
    names=re.findall(r'AM_HAL_PWRCTRL_PERIPH_\w+',enum);check('public-UART0-enum9',names.index('AM_HAL_PWRCTRL_PERIPH_UART0')==9)
    hal=(src/'am_hal_pwrctrl.c').read_text();group=hal[hal.index('#define PWRCTRL_HCPA_DEVPWRSTATUS_MASK'):hal.index('#define PWRCTRL_I2S_DEVPWRSTATUS_MASK')]
    check('public-HCPA-four-status-bits',all('PWRSTUART'+str(i)+'_Msk' in group for i in range(4)))
    up=s/'uart1-research-01';uartpin=json.loads((up/'source-report.json').read_text());uart=(up/'am_hal_uart.c').read_bytes()
    check('UART-HAL-pin',hashlib.sha256(uart).hexdigest()==uartpin['source_sha256']['am_hal_uart.c'])
    svd=(s/'apollo-dfp-research-01/apollo510.svd').read_bytes();prior=json.loads((s/'multi-uart-research-01/source-report.json').read_text())
    check('SVD-pin',hashlib.sha256(svd).hexdigest()==prior['svd_sha256'])
    peripherals=ET.fromstring(svd).findall('./peripherals/peripheral');pw=next(x for x in peripherals if x.findtext('name')=='PWRCTRL')
    for register,field in [('DEVPWREN','PWRENUART'),('DEVPWRSTATUS','PWRSTUART')]:
        node=next(x for x in pw.findall('./registers/register') if x.findtext('name')==register)
        for module in range(4):check(register+'-UART'+str(module),next(x.findtext('bitRange') for x in node.findall('./fields/field') if x.findtext('name')==field+str(module))=='['+str(9+module)+':'+str(9+module)+']')
    uart0=next(x for x in peripherals if x.findtext('name')=='UART0');check('UART0-base-IRQ',int(uart0.findtext('baseAddress'),0)==0x40039000 and int(uart0.find('./interrupt').findtext('value'),0)==15)
    model=Path(__file__).with_name('renode-strict-mmio.cs').read_text()
    check('existing-adapter-module0','if(module<0 || module>3)' in model and 'AddUart(0,uart0,uart0PowerResponse,uart0OffResponse);' in model and '0x40039000u+(uint)Module*0x1000u' in model)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
    for key,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        d=s/'missing-font-header-main-01'/(key+'-low');r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        _,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes());check(key+'-native-original',v==r['observed'] and raw==(d/'main.bin').read_bytes())
        def code(address,size):return {i.address:i for i in md.disasm(raw[address-0x438000:address+size-0x438000],address)}
        def literal(i):
            m=next(x.mem for x in i.operands if x.type==ARM_OP_MEM and x.mem.base==ARM_REG_PC)
            return struct.unpack_from('<I',raw,((i.address+4)&~3)+m.disp-0x438000)[0]
        def target(i):return int(i.op_str[1:],0)
        store=v['pc'];entry=store-0xd8;c=code(entry,0x13a);stack=v['stack_context']['words'];ctx=v['register_context']
        check(key+'-UART0-table-frame',ctx['r4']==11 and ctx['r5']==0 and ctx['r6']==11 and stack[1:5]==[0x40021004,0x200,0x40021008,0x1e00])
        check(key+'-read-modify-write',(c[store-4].mnemonic,c[store-4].op_str)==('orrs','r1, r0') and ctx['r1']==0x600 and ctx['r0']==0x40021004)
        lookup=target(c[entry+0xc]);table=literal(code(lookup,0x20)[lookup+0xe]);rows=[struct.unpack_from('<4I',raw,table-0x438000+16*i) for i in range(11,15)]
        check(key+'-four-original-UART-rows',rows==[(0x40021004,0x200<<i,0x40021008,0x1e00) for i in range(4)])
        caller=(stack[9]&~1)-4;cc=code(caller-0x28,0x30)
        check(key+'-caller-UART-module-plus11',(cc[caller-0x28].mnemonic,cc[caller-0x28].op_str)==('ldr','r5, [r4, #0x28]') and (cc[caller-0x26].mnemonic,cc[caller-0x26].op_str)==('adds.w','r6, r5, #0xb') and target(cc[caller])==entry)
        check(key+'-caller-does-not-test-power-return',(cc[caller+4].mnemonic,cc[caller+4].op_str)==('uxtb','r7, r7'))
        check(key+'-native-five-us-equality-request',(c[store+0xc].mnemonic,c[store+0xc].op_str)==('movs','r0, #1') and (c[store+0x16].mnemonic,c[store+0x16].op_str)==('movs','r0, #5'))
        poll=target(c[store+0x18]);pc=code(poll,0x42)
        check(key+'-poll-compares-all-mask',(pc[poll+0x28].mnemonic,pc[poll+0x28].op_str)==('ands','r0, r7') and (pc[poll+0x2a].mnemonic,pc[poll+0x2a].op_str)==('cmp','r0, r8'))
        check(key+'-current-status-is-partial',sum(u['status_word'] for u in v['uarts'])==0x400)
        vector=struct.unpack_from('<I',raw,4*(16+15))[0];check(key+'-UART0-vector-in-main',vector&1 and 0x438000<=vector&~1<0x438000+len(raw))
        probes=[]
        for status in [0,0x600,0x1e00]:
            u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);size=(len(raw)+4095)&~4095;u.mem_map(0x438000,size);u.mem_write(0x438000,raw);u.mem_protect(0x438000,size,UC_PROT_READ|UC_PROT_EXEC)
            u.mem_map(0x40021000,0x1000);u.mem_write(0x40021008,struct.pack('<I',status));u.mem_map(0x21000000,0x1000);u.mem_map(0x10000000,0x1000,UC_PROT_READ|UC_PROT_EXEC)
            sp=0x21000800;u.mem_write(sp,struct.pack('<I',1))
            for register,value in [(UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0x40021008),(UC_ARM_REG_R2,0x1e00),(UC_ARM_REG_R3,0x1e00),(UC_ARM_REG_SP,sp),(UC_ARM_REG_LR,0x10000001)]:u.reg_write(register,value)
            u.emu_start(poll|1,0x10000000,count=200)
            returned=u.reg_read(UC_ARM_REG_R0);check(key+'-original-zero-budget-poll-'+hex(status),u.reg_read(UC_ARM_REG_PC)==0x10000000 and u.reg_read(UC_ARM_REG_SP)==sp and returned==(0 if status==0x1e00 else 4))
            probes.append(dict(status=hex(status),return_value=returned))
        cases.append(dict(case=key,enable_entry=hex(entry),store=hex(store),UART_power_call=hex(caller),UART_power_entry=hex(caller-0x44),native_UART0_enum=11,public_UART0_enum=9,power_table=hex(table),poll=hex(poll),UART0_vector=hex(vector&~1),zero_budget_probes=probes))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,UART0_base='0x40039000',UART0_irq=15,UART0_power_mask='0x200',HCPA_status_mask='0x1e00',original_poll_probes=9,
                source_supported_group_status=True,hardware_group_behavior_verified=False,new_main_executed=False,
                scope='Source/prior-native UART0 identification and original zero-timeout poll probes; actual native request is 5us. Group status needs explicit model, no UART0 hardware or new full-main execution')
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),original_poll_probes=9)))


if __name__=='__main__':main()
