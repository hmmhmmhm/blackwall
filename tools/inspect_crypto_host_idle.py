"""Audit original OTP read gating and bounded upstream-model research; no hardware access."""
import argparse,hashlib,json,xml.etree.ElementTree as ET
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
    for pn,rn,address,field in [('CRYPTO','HOSTCCISIDLE',0x400c0a7c,'HOSTCCISIDLE'),('OTP','PTMSTAT',0x40014ac4,'BUSY')]:
        per=next(p for p in root.findall('./peripherals/peripheral') if p.findtext('name')==pn)
        reg=next(r for r in per.findall('./registers/register') if r.findtext('name')==rn)
        check(rn+'-address-bit0',int(per.findtext('baseAddress'),0)+int(reg.findtext('addressOffset'),0)==address and next(f.findtext('bitRange') for f in reg.findall('./fields/field') if f.findtext('name')==field)=='[0:0]')
    src=s/'crypto-init-research-01'
    renode=json.loads((src/'renode-tree.json').read_text());inv=json.loads((src/'renode-model-inventory.json').read_text())
    check('Renode-tree-pin',renode['sha']==inv['commit']=='5fd632c6c6e2f9e42699f55723fd3be2bde9b31e' and hashlib.sha256((src/'renode-tree.json').read_bytes()).hexdigest()==inv['sha256'] and renode['truncated'] is False)
    check('no-CryptoCell-named-file-in-tree',not any('cryptocell' in row['path'].lower() for row in renode['tree']))
    for manifest_name in ['renode-sources.json','otp-register-sources.json']:
        manifest=json.loads((src/manifest_name).read_text())
        tree=renode if manifest_name.startswith('renode') else json.loads((src/'ambiq-tree.json').read_text())
        check(manifest_name+'-commit',manifest['commit']==tree['sha'] and not tree['truncated'])
        for row in manifest['files']:
            data=(src/row['file']).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            check(row['file']+'-pin',hashlib.sha256(data).hexdigest()==row['sha256'] and blob==row['git_blob']==next(t['sha'] for t in tree['tree'] if t['path']==row['path']))
    check('Renode-MIT', 'The MIT License (MIT)' in (src/'renode-LICENSE').read_text())
    check('AES-helper-needs-register-adapter','InternalMemoryManager manager, IBusController bus' in (src/'renode-AESServiceProvider.cs').read_text())
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
    for key,file in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        d=s/'crypto-power-main-01'/key;v=parse_log((d/'renode.log').read_text());r=json.loads((d/'report.json').read_text());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(key+'-native-report',v==r['observed'])
        _,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes());check(key+'-original-main',raw==(d/'main.bin').read_bytes())
        pc=v['pc'];entry=pc-0x18;wrapper=entry+0x3c;validator=entry-0x1a
        code={i.address:i for i in md.disasm(raw[validator-0x438000:wrapper+0x74-0x438000],validator)}
        def ins(at,mn,op):return at in code and (code[at].mnemonic,code[at].op_str)==(mn,op)
        def literal(at):
            i=code[at];mem=next(o.mem for o in i.operands if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC);address=((at+4)&~3)+mem.disp
            return int.from_bytes(raw[address-0x438000:address-0x438000+4],'little')
        check(key+'-actual-HOST-idle-read',literal(entry+0x16)==0x400c0a7c and ins(pc,'ldr','r0, [r0]'))
        check(key+'-power-gates',literal(entry)==0x40021008 and ins(entry+4,'ubfx','r0, r0, #0x15, #1') and ins(entry+0xe,'ubfx','r0, r0, #0x1b, #1'))
        check(key+'-host-bit0-not-ready7',ins(entry+0x1a,'ands','r0, r0, #1') and ins(entry+0x1e,'eors','r0, r0, #1') and ins(entry+0x2c,'movs','r0, #7'))
        check(key+'-PTM-busy-loop-no-timeout',literal(entry+0x30)==0x40014ac4 and ins(entry+0x32,'ldr','r0, [r0]') and ins(entry+0x34,'lsls','r0, r0, #0x1f') and ins(entry+0x36,'bmi','#'+hex(entry+0x30)))
        check(key+'-aligned-offset-bound',ins(validator,'tst.w','r0, #3') and ins(validator+0xa,'movw','r1, #0x3fd') and ins(validator+0x10,'blo','#'+hex(validator+0x16)))
        check(key+'-read-wrapper-checks-readiness',ins(wrapper+0xa,'bl','#'+hex(validator)) and ins(wrapper+0x1a,'bl','#'+hex(entry)) and ins(wrapper+0x24,'str','r1, [r4]'))
        check(key+'-OTP-word-window-formula',ins(wrapper+0x28,'add.w','r5, r5, #0x40000000') and ins(wrapper+0x2c,'adds.w','r5, r5, #0xc2000') and ins(wrapper+0x30,'ldr','r1, [r5]'))
        ctx=v['register_context'];check(key+'-current-offset340-and-SRAM-output',ctx['r5']==0x340 and 0x20000000<=ctx['r4']<=0x20380000-4 and ctx['r14']==wrapper+0x1f)
        check(key+'-separate-program-store-not-read-support',ins(wrapper+0x54,'str','r5, [r2]'))
        cases.append(dict(case=key,ready_function=hex(entry),read_wrapper=hex(wrapper),offset_validator=hex(validator),current_offset='0x340',next_word_if_ready='0x400c2340',OTP_contents_known=False,OTP_bank_identity_verified=False))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='Static original read gates and tree/source inventory; no new native execution, OTP data, complete crypto model or hardware proof')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))


if __name__=='__main__':main()
