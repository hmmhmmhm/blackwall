"""Pin the original MSPI0 power request and bounded caller continuation."""
import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
import unicorn.arm_const as arm
from inspect_mspi1_config_contract import collect
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_nema_blocking_wait import cpu,WORK
from inspect_application_vendor_address import call
from inspect_keydb_record_load import run
from inspect_vbus_status_profiles import inspect as verify_capture
from prepare_vendor_startup_candidate import sha


def inspect(s,case):
    evidence=verify_capture(s,case,'vbus-status-main-01',case,0)
    folder=s/'vbus-status-main-01'/case;raw=(folder/'main.bin').read_bytes();ram=(folder/'exports/sram-full.bin').read_bytes()
    v=json.loads((folder/'report.json').read_text())['observed'];regs=v['register_context'];stack=v['stack_context']['words']
    entry=0x494ca0 if case=='stock24' else 0x488db8;store=entry+0xd8
    if regs['r4']!=16 or stack[1:5]!=[0x40021004,0x4000,0x40021008,0x4000] or regs['r1']!=0x4e00:
        raise ValueError('Different original MSPI0 power context')
    loader=decode(raw,entry+0xc,4)[0]
    if loader.mnemonic!='bl':raise ValueError('Missing original table loader')
    loader=loader.operands[0].imm
    table=literal(raw,decode(raw,loader+0xe,4)[0]);words=struct.unpack_from('<4I',raw,table+16*16-0x438000)
    if words!=(0x40021004,0x4000,0x40021008,0x4000):raise ValueError('Original enum16 table differs')
    parent_return=stack[9]&~1;parent_call=decode(raw,parent_return-4,4)[0]
    if parent_call.mnemonic!='bl' or parent_call.operands[0].imm!=entry:raise ValueError('Different parent power call')
    before=decode(raw,parent_return-10,10)
    if [(i.mnemonic,i.op_str) for i in before[:3]]!=[('ldr','r0, [r5, #4]'),('adds','r0, #0x10'),('uxtb','r0, r0')]:
        raise ValueError('Different module-to-enum translation')
    instance=regs['r5'];magic,module=struct.unpack_from('<II',ram,instance-0x20000000)
    if magic!=0x1bebebe or module!=0 or regs['r6']!=0:raise ValueError('Different fresh MSPI0 handle/retain state')
    post=decode(raw,parent_return,10)
    if [(i.mnemonic,i.op_str) for i in post[:2]]!=[('uxtb','r6, r6'),('cmp','r6, #0')] or post[2].mnemonic!='beq.w':
        raise ValueError('Different no-retain continuation')
    no_retain=post[2].operands[0].imm;clock=decode(raw,no_retain+14,4)[0]
    if clock.mnemonic!='bl':raise ValueError('Different original clock request boundary')
    clock_call=clock.address;samples=[]
    for out,number in [(WORK+0x100,16),(0,16),(WORK+0x100,34)]:
        u=cpu(raw,ram,WORK+0xf000);u.mem_write(WORK+0xf0,b'\xa5'*48)
        t=call(u,loader,(out,number));result=u.reg_read(arm.UC_ARM_REG_R0)
        if out and number==16:
            if result!=0 or bytes(u.mem_read(out,16))!=struct.pack('<4I',*words):raise ValueError('Original table copy differs')
        elif result!=6 or bytes(u.mem_read(WORK+0xf0,48))!=b'\xa5'*48:raise ValueError('Different invalid table request')
        samples.append(dict(kind='table-loader',output_null=out==0,enum=number,result=result,execution=t))
    for previous in [0,0xe00,0x8000,0x200000,0xffffffff]:
        u=cpu(raw,ram,WORK+0xf000);u.mem_map(0x40021000,4096)
        u.mem_write(0x40021004,struct.pack('<II',previous,0x12345678))
        u.mem_write(WORK+0xf004,struct.pack('<II',0x40021004,0x4000))
        t=run(u,store-10,[store+2]);value,status=struct.unpack('<II',bytes(u.mem_read(0x40021004,8)))
        if value!=previous|0x4000 or status!=0x12345678:raise ValueError('Original enable OR/store differs')
        samples.append(dict(kind='enable-store-fragment',previous=previous,written=value,status_not_synthesized=True,execution=t))
    for prepared_result in [0,1,4,0xffffffff]:
        u=cpu(raw,ram,WORK+0xf000)
        for n,value in [(0,prepared_result),(5,instance),(6,0)]:u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),value)
        t=run(u,parent_return,[clock_call]);args=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in [0,1]]
        if args!=[4,16] or bytes(u.mem_read(instance+0x8c9,1))!=b'\x04':raise ValueError('Different caller clock arguments/state')
        samples.append(dict(kind='post-power-return-fragment',prepared_result=prepared_result,clock_arguments=args,
                            original_clock_callee=clock.operands[0].imm,execution=t))
    return dict(case=case,main_sha256=sha(folder/'main.bin'),sram_sha256=sha(folder/'exports/sram-full.bin'),
                audit_sha256=evidence['audit_sha256'],power_entry=entry,store_pc=store,table_loader=loader,table=table,
                enum=16,table_words=list(words),instance=instance,module=module,retain_state=False,parent_return=parent_return,
                original_clock_call=clock_call,original_clock_callee=clock.operands[0].imm,samples=samples)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Preserve private evidence')
    collect(s)
    tree=ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot()
    power=next(x for x in tree.findall('./peripherals/peripheral') if x.findtext('name')=='PWRCTRL')
    for register,field in [('DEVPWREN','PWRENMSPI0'),('DEVPWRSTATUS','PWRSTMSPI0')]:
        r=next(x for x in power.findall('./registers/register') if x.findtext('name')==register)
        if next(x.findtext('bitRange') for x in r.findall('./fields/field') if x.findtext('name')==field)!='[14:14]':raise ValueError('Different MSPI0 power mask')
    source=s/'mspi1-source-research-01';manifest=json.loads((source/'sources.json').read_text());pins={}
    if manifest['commit']!='61b293a49db34030c545f99101f7ebf6a3050314':raise ValueError('Changed HAL commit')
    for name in ['am_hal_pwrctrl.c','am_hal_pwrctrl.h']:
        item=next(x for x in manifest['files'] if x['path'].endswith('/'+name));file=source/name
        if sha(file)!=item['sha256']:raise ValueError('Changed HAL source')
        pins[name]=sha(file)
    hal=(source/'am_hal_pwrctrl.c').read_text()
    if 'PWRCTRL_DEVPWREN_PWRENMSPI0_EN' not in hal or 'PWRCTRL_DEVPWRSTATUS_PWRSTMSPI0_Msk' not in hal:
        raise ValueError('Missing SDK MSPI0 enable/status table')
    rows=[inspect(s,c) for c in ['stock24','stock23','cfw']]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    report=dict(passed=True,source_files=pins,cases=rows,original_arm_scenarios=sum(len(c['samples']) for c in rows),
                engine='Unicorn M7 original ARM, synthetic stack/registers and passive enable/status memory',
                native_main_rerun=False,model_changed=False,power_response_verified=False,hardware_accessed=False,boot_verified=False,display_verified=False)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Verified original MSPI0 power/caller scenarios',report['original_arm_scenarios'])


if __name__=='__main__':main()
