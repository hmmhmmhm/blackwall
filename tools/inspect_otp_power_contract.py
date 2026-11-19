"""Correlate the original OTP power request with pinned SVD/HAL and stopped native state."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from inspect_mspi1_config_contract import collect
from native_replay import parse_log, validate_assets
from pinned_main import load_pinned_main


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    collect(s)
    root=ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot()
    per=next(p for p in root.findall('./peripherals/peripheral') if p.findtext('name')=='PWRCTRL')
    regs={r.findtext('name'):r for r in per.findall('./registers/register')}
    for rn,field,offset in [('DEVPWREN','PWRENOTP',4),('DEVPWRSTATUS','PWRSTOTP',8)]:
        r=regs[rn];fields={f.findtext('name'):f.findtext('bitRange') for f in r.findall('./fields/field')}
        check(rn+'-OTP27',int(per.findtext('baseAddress'),0)==0x40021000 and int(r.findtext('addressOffset'),0)==offset and fields[field]=='[27:27]')
    check('UART1-independent-bit10',next(f.findtext('bitRange') for f in regs['DEVPWREN'].findall('./fields/field') if f.findtext('name')=='PWRENUART1')=='[10:10]')
    src=s/'mspi1-source-research-01';manifest=json.loads((src/'sources.json').read_text())
    check('HAL-commit',manifest['commit']=='61b293a49db34030c545f99101f7ebf6a3050314')
    data=(src/'am_hal_pwrctrl.c').read_bytes();pin=next(f for f in manifest['files'] if f['path'].endswith('/am_hal_pwrctrl.c'))
    check('HAL-source-hash',hashlib.sha256(data).hexdigest()==pin['sha256']);hal=data.decode()
    check('HAL-OTP-enable-status', '_VAL2FLD(PWRCTRL_DEVPWREN_PWRENOTP, PWRCTRL_DEVPWREN_PWRENOTP_EN)' in hal and 'PWRCTRL_DEVPWRSTATUS_PWRSTOTP_Msk' in hal)
    check('HAL-OTP-post-delay', 'if ( ePeripheral == AM_HAL_PWRCTRL_PERIPH_OTP)' in hal and 'am_hal_delay_us(100);' in hal)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    for key,file,delta in [('stock24','stock-2.4.0.24.bin',0),('stock23','stock-2.3.0.24.bin',0xbee8),('cfw','faceclaw-38-research-only.bin',0xbee8)]:
        d=s/'mspi1-rx-stream-main-01'/key;log=(d/'renode.log').read_text();v=parse_log(log)
        check(key+'-native-report',v==json.loads((d/'report.json').read_text())['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        _,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes());check(key+'-original-main',raw==(d/'main.bin').read_bytes())
        pc=0x494d78-delta;entry=0x494ca0-delta
        code={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[entry-0x438000:pc+0x62-0x438000],entry)}
        check(key+'-read-OR-write',all(code.get(pc+off)==pair for off,pair in [(-10,('ldr','r0, [sp, #4]')),(-8,('ldr','r1, [r0]')),(-6,('ldr','r0, [sp, #8]')),(-4,('orrs','r1, r0')),(-2,('ldr','r0, [sp, #4]')),(0,('str','r1, [r0]'))]))
        ctx,stack=v['register_context'],v['stack_context']['words']
        check(key+'-OTP29-stack-contract',v['pc']==pc and ctx['r4']==29 and stack[1:5]==[0x40021004,0x08000000,0x40021008,0x08000000])
        check(key+'-UART1-preserved',ctx['r0']==0x40021004 and ctx['r1']==0x08000400)
        check(key+'-OTP-100us-branch',code.get(pc+0x44)==('cmp','r4, #0x1d') and code.get(pc+0x48)==('movs','r0, #0x64') and code.get(pc+0x4a,('', ''))[0]=='bl')
        caller=(stack[9]&~1)-4
        cc={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[caller-2-0x438000:caller+12-0x438000],caller-2)}
        check(key+'-caller-OTP-then-crypto-unchecked',cc.get(caller-2)==('movs','r0, #0x1d') and cc.get(caller)==('bl','#'+hex(entry)) and cc.get(caller+4)==('movs','r0, #0x17') and cc.get(caller+6)==('bl','#'+hex(entry)))
        guards=[g for g in v['guards'] if g['accesses']]
        check(key+'-only-OTP-request-guard',len(guards)==1 and guards[0]['address']==0x40021004 and guards[0]['value']==0x08000400)
        cases.append(dict(case=key,entry=hex(entry),request_pc=hex(pc),caller=hex(caller),request='0x08000400',OTP_contents_known=False,source_only_delay_us=100))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='OTP power request contract only; no OTP contents, fuse program, crypto engine or hardware verification')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))


if __name__=='__main__':main()
