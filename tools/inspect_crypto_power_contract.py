"""Pin CRYPTO power, OTP precondition and NVMISIDLE readiness semantics from original code."""
import argparse,hashlib,json,struct,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from inspect_mspi1_config_contract import collect
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    collect(s);root=ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot()
    power=next(p for p in root.findall('./peripherals/peripheral') if p.findtext('name')=='PWRCTRL')
    regs={r.findtext('name'):r for r in power.findall('./registers/register')}
    for rn,fn in [('DEVPWREN','PWRENCRYPTO'),('DEVPWRSTATUS','PWRSTCRYPTO')]:
        check(rn+'-bit21',next(f.findtext('bitRange') for f in regs[rn].findall('./fields/field') if f.findtext('name')==fn)=='[21:21]')
    crypto=next(p for p in root.findall('./peripherals/peripheral') if p.findtext('name')=='CRYPTO')
    nvm=next(r for r in crypto.findall('./registers/register') if r.findtext('name')=='NVMISIDLE')
    check('NVMISIDLE-exact-register',int(crypto.findtext('baseAddress'),0)+int(nvm.findtext('addressOffset'),0)==0x400c1f10 and nvm.find('./fields/field').findtext('bitRange')=='[0:0]' and int(nvm.findtext('resetValue'),0)==1)
    source=s/'mspi1-source-research-01';manifest=json.loads((source/'sources.json').read_text());data=(source/'am_hal_pwrctrl.c').read_bytes();pin=next(f for f in manifest['files'] if f['path'].endswith('/am_hal_pwrctrl.c'))
    check('HAL-pin',manifest['commit']=='61b293a49db34030c545f99101f7ebf6a3050314' and hashlib.sha256(data).hexdigest()==pin['sha256']);hal=data.decode()
    check('HAL-OTP-precondition','PWRCTRL->DEVPWRSTATUS_b.PWRSTOTP == PWRCTRL_DEVPWRSTATUS_PWRSTOTP_OFF' in hal)
    check('HAL-idle-before-HFRC',hal.index('(uint32_t)&CRYPTO->NVMISIDLE',hal.index('am_hal_pwrctrl_periph_enable')) < hal.index('am_hal_clkmgr_clock_request(AM_HAL_CLKMGR_CLK_ID_HFRC, AM_HAL_CLKMGR_USER_ID_CRYPTO)'))
    check('HAL-NVM-timeout100','#define CRYPTO_WAIT_USEC        100' in hal)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
    for key,file,delta in [('stock24','stock-2.4.0.24.bin',0),('stock23','stock-2.3.0.24.bin',0xbee8),('cfw','faceclaw-38-research-only.bin',0xbee8)]:
        d=s/'otp-power-main-02'/key;v=parse_log((d/'renode.log').read_text());r=json.loads((d/'report.json').read_text());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(key+'-native-report',v==r['observed'])
        _,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes());check(key+'-original-main',raw==(d/'main.bin').read_bytes())
        entry,store=0x494ca0-delta,0x494d78-delta
        code={i.address:i for i in md.disasm(raw[entry-0x438000:store+0x62-0x438000],entry)}
        def ins(addr,mn,op):return addr in code and (code[addr].mnemonic,code[addr].op_str)==(mn,op)
        def literal(addr):
            i=code[addr];mem=next(o.mem for o in i.operands if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC)
            address=((addr+4)&~3)+mem.disp
            return struct.unpack_from('<I',raw,address-0x438000)[0]
        check(key+'-OTP-gate',ins(entry+0x28,'cmp','r0, #0x17') and literal(entry+0x2c)==0x40021008 and ins(entry+0x32,'ubfx','r0, r0, #0x1b, #1'))
        stack=v['stack_context']['words'];ctx=v['register_context']
        check(key+'-mask-stack',ctx['r4']==23 and ctx['r1']==0x08200400 and stack[1:5]==[0x40021004,0x200000,0x40021008,0x200000])
        check(key+'-NVM-readiness-arguments',ins(store+0x28,'movs','r3, #1') and ins(store+0x2a,'movs','r2, #1') and literal(store+0x2c)==0x400c1f10 and ins(store+0x30,'movs','r0, #0x64') and code[store+0x32].mnemonic=='bl')
        check(key+'-NVM-failure-exits',ins(store+0x36,'cmp','r0, #0') and ins(store+0x38,'bne','#'+hex(store+0x5e)))
        check(key+'-clock-after-idle',ins(store+0x3a,'movs','r1, #0x17') and ins(store+0x3c,'movs','r0, #4') and code[store+0x3e].mnemonic=='bl')
        caller=(stack[9]&~1)-4
        caller_code={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[caller-0x438000:caller+8-0x438000],caller)}
        check(key+'-caller-unchecked-return',caller_code.get(caller)==('bl','#'+hex(entry)) and caller_code.get(caller+4)==('movs','r0, #1'))
        cases.append(dict(case=key,power_entry=hex(entry),request_pc=hex(store),caller=hex(caller),NVMISIDLE='0x400c1f10',NVM_wait_call=hex(store+0x32),clock_request_call=hex(store+0x3e)))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='Static power and readiness contract; no crypto keys/engine/OTP contents or hardware validation')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))


if __name__=='__main__':main()
