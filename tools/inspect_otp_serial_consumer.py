"""Audit INFOC mapping and serial slots; execute original digit/prefix helpers in isolation."""
import argparse,hashlib,json,re
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_XPSR


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    src=s/'crypto-init-research-01';manifest=json.loads((src/'otp-register-sources.json').read_text());row=next(f for f in manifest['files'] if f['file']=='am_mcu_apollo510_otpinfoc.h');data=(src/row['file']).read_bytes()
    check('INFOC-header-pin',manifest['commit']=='61b293a49db34030c545f99101f7ebf6a3050314' and hashlib.sha256(data).hexdigest()==row['sha256'] and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==row['git_blob'])
    macros={m[0]:int(m[1],16) for m in re.findall(r'^#define\s+(AM_REG_OTP_INFOC_\w+)\s+(0x[0-9a-fA-F]+)\s*$',data.decode(),re.M)}
    check('exact-INFOC-window-base',macros['AM_REG_OTP_INFOC_BASEADDR']==0x400c2000)
    words=[]
    for quadrant in [2,3]:
        for index in range(16):
            prefix='AM_REG_OTP_INFOC_KEYBANK_CUST_QUADRANT'+str(quadrant)+'_KEY'+str(index)
            offset=0x340+(quadrant-2)*0x40+index*4
            check('INFOC-quadrant-'+str(quadrant)+'-word-'+str(index),macros[prefix+'_O']==offset and macros[prefix+'_ADDR']==0x400c2000+offset)
            words.append(macros[prefix+'_ADDR'])
    check('exact-eight-slot-range',words==list(range(0x400c2340,0x400c23c0,4)))
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    ready=json.loads((s/'crypto-host-idle-contract-01/report.json').read_text())
    helper_runs=0;prefix_runs=0
    for key,file in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        d=s/'otp-read-ready-main-01'/key;v=parse_log((d/'renode.log').read_text());check(key+'-native-report',v==json.loads((d/'report.json').read_text())['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        _,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes());check(key+'-original-main',raw==(d/'main.bin').read_bytes())
        call=(v['stack_context']['words'][3]&~1)-4;entry=call-0x15c;meta=next(r for r in ready['cases'] if r['case']==key);wrapper=int(meta['read_wrapper'],0);digit=wrapper-0x60
        code={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[entry-0x438000:entry+0x286-0x438000],entry)}
        def ins(off,mn,op):return code.get(entry+off)==(mn,op)
        def adr_string(off):
            address=entry+off;mn,op=code[address]
            if mn!='adr':raise ValueError('Expected ADR')
            target=((address+4)&~3)+int(op.split('#')[1],0);start=target-0x438000;end=raw.index(0,start)
            return raw[start:end].decode('ascii')
        check(key+'-slot-start-and-count',ins(0xa,'mov.w','r0, #0x340') and ins(0x124,'cmp.w','r8, #8') and ins(0x12e,'adds.w','sb, sb, r8, lsl #4'))
        check(key+'-four-word-read-loop',ins(0x14c,'cmp.w','sl, #4') and ins(0x158,'adds.w','r0, sb, sl, lsl #2') and ins(0x15c,'bl','#'+hex(wrapper)))
        check(key+'-14-byte-copy-terminator',ins(0x44,'movs','r2, #0xe') and ins(0x54,'strb','r0, [r4, #0xe]') and ins(0xba,'movs','r2, #0xe') and ins(0xc8,'strb','r0, [r6, #0xe]'))
        prefixes=[adr_string(0x58),adr_string(0x66)];check(key+'-S2-P1-prefixes',prefixes==['S2','P1'] and ins(0x56,'movs','r2, #2') and ins(0x64,'movs','r2, #2'))
        check(key+'-prefix-reject-branches',ins(0x62,'beq','#'+hex(entry+0x72)) and ins(0x70,'bne','#'+hex(entry+0x120)))
        digit_calls=[0x76,0x82,0x8e,0x9a,0xa6,0xb0]
        check(key+'-six-digit-calls',all(ins(off,'bl','#'+hex(digit)) for off in digit_calls))
        check(key+'-digit-reject-branches',all(ins(off+4,'cmp','r0, #0') and ins(off+6,'beq','#'+hex(entry+0x120)) for off in digit_calls))
        loads=[(0x72,'ldrb.w','r0, [sp, #0x21]'),(0x7e,'ldrb.w','r0, [sp, #0x20]'),(0x8a,'ldrb.w','r0, [sp, #0x1f]'),(0x96,'ldrb.w','r0, [sp, #0x1e]'),(0xa2,'ldrb.w','r0, [sp, #0x1d]'),(0xae,'ldrb','r0, [r4, #8]')]
        check(key+'-positions8-through13',all(ins(off,mn,op) for off,mn,op in loads))
        check(key+'-last-match-retained',ins(0x28,'movs.w','r7, #-1') and ins(0xb8,'mov','r7, r8') and ins(0x120,'adds.w','r8, r8, #1'))
        check(key+'-read-error-aborts-scan',ins(0x162,'cmp','r4, #0') and ins(0x1c0,'movs.w','fp, #0') and ins(0x1cc,'bne.w','#'+hex(entry+0x44)))
        check(key+'-cleanup-before-result',ins(0x1d0,'movs','r0, #0x17') and code.get(entry+0x1d2,('', ''))[0]=='bl' and ins(0x1d6,'movs','r0, #0x1d') and code.get(entry+0x1d8,('', ''))[0]=='bl' and ins(0x1dc,'cmp','r7, #0'))
        helper=raw[digit-0x438000:digit-0x438000+10];decoded=[(i.mnemonic,i.op_str) for i in md.disasm(helper,digit)]
        check(key+'-original-digit-instructions',decoded==[('subs','r0, #0x30'),('cmp','r0, #0xa'),('sbcs','r0, r0'),('lsrs','r0, r0, #0x1f'),('bx','lr')])
        # Conventional subroutine entry/return unit test, not a main-reset boot.
        uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);uc.mem_map(digit&~0xfff,0x1000);uc.mem_write(digit,helper);uc.mem_map(0x10000,0x1000)
        for byte in range(256):
            uc.reg_write(UC_ARM_REG_XPSR,1<<24);uc.reg_write(UC_ARM_REG_R0,byte);uc.reg_write(UC_ARM_REG_LR,0x10001);uc.emu_start(digit|1,0x10000,count=16)
            if uc.reg_read(UC_ARM_REG_PC)!=0x10000 or uc.reg_read(UC_ARM_REG_R0)!=int(0x30<=byte<=0x39):raise ValueError(key+'-digit-byte-'+str(byte))
            helper_runs+=1
        check(key+'-all256-digit-inputs',True)
        compare=int(code[entry+0x5c][1][1:],0)
        check(key+'-same-bounded-prefix-helper',ins(0x6a,'bl','#'+hex(compare)))
        compare_bytes=raw[compare-0x438000:compare-0x438000+0x2a]
        compare_code=[i.mnemonic for i in md.disasm(compare_bytes,compare)]
        check(key+'-self-contained-compare-helper',compare_code[0]=='cbz' and compare_code[-1]=='bx' and 'bl' not in compare_code and 'blx' not in compare_code)
        uc.mem_map(compare&~0xfff,0x1000);uc.mem_write(compare,compare_bytes);uc.mem_map(0x20000000,0x1000)
        for prefix in [b'S2',b'P1']:
            uc.mem_write(0x20000010,prefix+b'\0')
            for position in range(2):
                for byte in range(256):
                    candidate=bytearray(prefix);candidate[position]=byte;uc.mem_write(0x20000000,bytes(candidate)+b'\0')
                    uc.reg_write(UC_ARM_REG_XPSR,1<<24);uc.reg_write(UC_ARM_REG_R0,0x20000000);uc.reg_write(UC_ARM_REG_R1,0x20000010);uc.reg_write(UC_ARM_REG_R2,2);uc.reg_write(UC_ARM_REG_LR,0x10001);uc.emu_start(compare|1,0x10000,count=64)
                    if uc.reg_read(UC_ARM_REG_PC)!=0x10000 or (uc.reg_read(UC_ARM_REG_R0)==0)!=(bytes(candidate)==prefix):raise ValueError(key+'-prefix-byte-'+str(position)+'-'+str(byte))
                    prefix_runs+=1
        check(key+'-all1024-prefix-variants',True)
        cases.append(dict(case=key,consumer_entry=hex(entry),word_call=hex(call),read_wrapper=hex(wrapper),digit_helper=hex(digit),prefixes=prefixes,slot_count=8,slot_bytes=16,used_bytes=14,bank='INFOC customer keybank quadrants2/3',OTP_contents_known=False))
    result=dict(passed=True,count=len(checks),checks=checks,isolated_original_digit_calls=helper_runs,isolated_original_prefix_calls=prefix_runs,cases=cases,scope='Static original consumer and isolated original digit/prefix subroutines only; no high-level consumer or new full-main execution, OTP data not supplied')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),isolated_original_digit_calls=helper_runs,isolated_original_prefix_calls=prefix_runs)))


if __name__=='__main__':main()
