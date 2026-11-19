"""Analyze original VBUS status wrappers and bounded post-call ARM consumers."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_nema_blocking_wait import cpu,WORK
from inspect_application_vendor_address import call
from inspect_keydb_record_load import run
from inspect_advertising_profiles import inspect as verify_capture
from prepare_vendor_startup_candidate import sha


COMMIT='4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f'


def source_contract(s):
    tree=json.loads((s/'npmx-research-01/tree.json').read_text())
    if tree['sha']!=COMMIT:raise ValueError('Changed upstream tree')
    pins={}
    for folder in ['npmx-vbus-research-01','npmx-charger-status-research-01']:
        manifest=json.loads((s/folder/'sources.json').read_text())
        if manifest['commit']!=COMMIT:raise ValueError('Changed SDK commit')
        for item in manifest['files']:
            p=s/folder/Path(item['path']).name;data=p.read_bytes()
            blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if sha(p)!=item['sha256'] or blob!=item['git_blob'] or blob!=next(x['sha'] for x in tree['tree'] if x['path']==item['path']):
                raise ValueError('Changed SDK source '+item['path'])
            pins[str(p.relative_to(s))]=sha(p)
    header=(s/'npmx-charger-status-research-01/npm1300.h').read_text()
    if not re.search(r'#define NPM_VBUSIN_BASE\s+0x00000200UL',header) or not re.search(r'__IM uint8_t\s+VBUSINSTATUS;\s*/\*!< \(@ 0x00000007\)',header):
        raise ValueError('Different readonly VBUS register')
    fields={name:int(value) for name,value in re.findall(r'#define VBUSIN_VBUSINSTATUS_(\w+)_Pos \((\d+)UL\)',header)}
    if sorted(fields.values())!=list(range(6)) or fields.get('VBUSINPRESENT')!=0:
        raise ValueError('Different VBUS status fields')
    driver=(s/'npmx-vbus-research-01/npmx_vbusin.c').read_text()
    body=driver[driver.index('npmx_error_t npmx_vbusin_vbus_status_get'):]
    if not re.search(r'NPM_VBUSIN->VBUSINSTATUS\),\s*p_status_mask,\s*1\);',body):
        raise ValueError('Different SDK status read')
    return dict(commit=COMMIT,files=pins,address=0x207,readonly=True,field_mask=63,fields=fields,
                reset_is_not_live_device_state=True,sdk_read_bytes=1)


def calls_to(raw,target):
    result=[]
    for off in range(0,len(raw)-4,2):
        first,second=struct.unpack_from('<HH',raw,off)
        if first&0xf800!=0xf000 or second&0xd000!=0xd000:continue
        sign=(first>>10)&1;i1=1^((second>>13)&1)^sign;i2=1^((second>>11)&1)^sign
        delta=(sign<<24)|(i1<<23)|(i2<<22)|((first&1023)<<12)|((second&2047)<<1)
        if sign:delta-=1<<25
        if 0x438000+off+4+delta==target:result.append(0x438000+off)
    return result


def inspect(s,case):
    evidence=verify_capture(s,case);folder=s/'advertising-peer-main-01'/case
    raw=(folder/'main.bin').read_bytes();ram=(folder/'exports/sram-full.bin').read_bytes()
    signature=bytes.fromhex('80b50a00012340f207210068')
    if raw.count(signature)!=1:raise ValueError('Missing unique VBUS wrapper')
    wrapper=0x438000+raw.index(signature);instructions=decode(raw,wrapper,18)
    if instructions[-2].mnemonic!='bl' or instructions[-1].mnemonic!='pop':raise ValueError('Different wrapper backend call')
    backend=instructions[-2].operands[0].imm;refs=calls_to(raw,wrapper)
    if len(refs)!=1:raise ValueError('Ambiguous original VBUS consumer')
    caller=refs[0];post=caller+4;after=decode(raw,post,8)
    if [(i.mnemonic,i.op_str) for i in after[:2]]!=[('movs','r4, r0'),('cmp','r4, r6')] or after[2].mnemonic!='beq':
        raise ValueError('Different backend return check')
    good=after[2].operands[0].imm;bad=after[2].address+after[2].size
    success_load=decode(raw,caller-0x58,4)[0]
    if success_load.mnemonic!='ldr.w' or not success_load.op_str.startswith('r6, '):raise ValueError('Different success constant setup')
    success=literal(raw,success_load)
    branch=decode(raw,good,0x22)
    if [(i.mnemonic,i.op_str) for i in branch[:2]]!=[('ldrb.w','r0, [sp, #0xd]'),('lsls','r0, r0, #0x1f')]:
        raise ValueError('Different status-bit consumer')
    setters=[i.operands[0].imm for i in branch if i.mnemonic=='bl']
    if len(setters)!=2 or setters[0]!=setters[1] or branch[-1].mnemonic!='beq':raise ValueError('Different setter paths')
    setter=setters[0];end=branch[-1].operands[0].imm
    table=raw[setter+8-0x438000:setter+15-0x438000]
    targets=[setter+8+2*table[n] for n in [0,1]]
    slots=[]
    for n,target in enumerate(targets):
        code=decode(raw,target,12)
        if code[0].op_str!='r2, #'+str(1-n):raise ValueError('Different setter boolean value')
        slots.append(literal(raw,code[1])+1)
    if slots[0]!=slots[1]:raise ValueError('Setter paths use different state')
    slot=slots[0];samples=[]
    u=cpu(raw,ram,WORK+0xf000);u.mem_write(WORK+0x100,struct.pack('<I',0x12345678))
    t=call(u,wrapper,(WORK+0x100,WORK+0x200),[backend])
    args=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(4)]
    if args!=[0x12345678,0x207,WORK+0x200,1]:raise ValueError('Different original wrapper arguments')
    samples.append(dict(kind='wrapper-to-backend',arguments=args,execution=t))
    # Explicit post-call fixtures: no hardware backend is stubbed or resumed here.
    # All byte patterns test consumer masking; reserved bits remain unsupported hardware inputs.
    for status in range(256):
        u=cpu(raw,ram,WORK+0xf000);u.mem_write(WORK+0xf00d,bytes([status]));u.mem_write(slot,b'\xa5')
        u.reg_write(arm.UC_ARM_REG_R0,success);u.reg_write(arm.UC_ARM_REG_R6,success)
        t=run(u,post,[end,bad]);value=bytes(u.mem_read(slot,1))[0]
        if t['stop']!=end or value!=status&1 or bytes(u.mem_read(WORK+0xf00d,1))!=bytes([status]):
            raise ValueError('Original status consumer differs')
        final=bytes(u.mem_read(0x20000000,len(ram)))
        expected=bytearray(ram);expected[slot-0x20000000]=status&1
        if final!=bytes(expected):raise ValueError('Unexpected final SRAM change in bounded consumer')
        samples.append(dict(kind='post-call-success',status=status,state=value,execution=t))
    for result in [0,1,success^1,0xffffffff]:
        u=cpu(raw,ram,WORK+0xf000);u.mem_write(WORK+0xf00d,b'\xff');u.mem_write(slot,b'\xa5')
        u.reg_write(arm.UC_ARM_REG_R0,result);u.reg_write(arm.UC_ARM_REG_R6,success)
        t=run(u,post,[end,bad])
        if t['stop']!=bad or bytes(u.mem_read(slot,1))!=b'\xa5':raise ValueError('Different failed-read consumer boundary')
        samples.append(dict(kind='post-call-error',result=result,status_not_consumed_before_logging=True,execution=t))
    return dict(case=case,main_sha256=sha(folder/'main.bin'),sram_sha256=sha(folder/'exports/sram-full.bin'),
                audit_sha256=evidence['audit_sha256'],wrapper=wrapper,backend=backend,caller=caller,
                consumer=post,success_code=success,setter=setter,state_byte=slot,success_end=end,error_boundary=bad,
                synthetic_post_call_inputs=True,natural_status_read_completed=False,samples=samples)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Preserve private evidence')
    source=source_contract(a.simulator);rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    report=dict(passed=True,source=source,cases=rows,original_arm_scenarios=sum(len(c['samples']) for c in rows),
                engine='Unicorn M7 original ARM; synthetic calls, stack and post-call register inputs',
                native_main_rerun=False,model_changed=False,hardware_accessed=False,boot_verified=False,display_verified=False)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Verified VBUS source and original3 bounded consumers; scenarios',report['original_arm_scenarios'])


if __name__=='__main__':main()
