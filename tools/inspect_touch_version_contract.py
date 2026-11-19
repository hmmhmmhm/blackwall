"""Validate pinned touch packages and execute original package-header/version-compare fragments."""
import argparse,hashlib,json,re,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_R4,UC_ARM_REG_R5
from blackwall_package import parse_bundle
from pinned_main import load_pinned_main

BASE=0x438000
TOUCH_SHA='c14456cd4d432815d79700b251c9a575f75c76a3710f4148c0df6ddba4cb7ba2'
VERSION=0x02020900

def cpu(raw):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);extent=(len(raw)+4095)&~4095;u.mem_map(BASE,extent);u.mem_write(BASE,raw);u.mem_protect(BASE,extent,UC_PROT_READ|UC_PROT_EXEC);u.mem_map(0x20000000,0x10000);return u

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(mode=0o700);checks=[];cases=[];m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);m.detail=True
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 for key,name in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
  bundle=(a.simulator/'inputs/verified-01'/name).read_bytes();_,raw=load_pinned_main(bundle);touch=next(c for c in parse_bundle(bundle) if c.name=='firmware/touch.bin').payload
  check(key+':touch-hash',hashlib.sha256(touch).hexdigest()==TOUCH_SHA and len(touch)==34720)
  check(key+':package-version',touch[:4]==b'FWPK' and struct.unpack_from('<I',touch,4)[0]==VERSION)
  # Find the original parser's literal load + magic check, not an assumed ABI.
  matches=[]
  for pool in [BASE+x.start() for x in re.finditer(b'FWPK',raw)]:
   for address in range(max(BASE,pool-0x1000),pool,2):
    ins=next(m.disasm(raw[address-BASE:address-BASE+4],address),None)
    if not ins or ins.mnemonic!='ldr.w' or ins.op_str.split(',')[0]!='r4':continue
    if not any(op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC and ((address+4)&~3)+op.mem.disp==pool for op in ins.operands):continue
    seq=list(m.disasm(raw[address-BASE:address-BASE+10],address))
    if len(seq)==4 and [(x.mnemonic,x.op_str) for x in seq[1:3]]==[('ldr','r0, [sp, #0x10]'),('cmp','r0, r4')] and seq[3].mnemonic=='beq':matches.append(seq)
  check(key+':unique-magic-check',len(matches)==1);seq=matches[0];entry=seq[0].address;success=seq[3].operands[0].imm;failure=seq[3].address+2
  copy=list(m.disasm(raw[success-BASE:success-BASE+4],success));check(key+':version-field-load',[(x.mnemonic,x.op_str) for x in copy]==[('ldr','r0, [sp, #0x14]'),('str','r0, [r5]')])
  for valid in [True,False]:
   u=cpu(raw);header=bytearray(touch[:16]);header[0]^=0 if valid else 1;u.mem_write(0x20001010,bytes(header));u.mem_write(0x20002000,struct.pack('<I',0xa5a5a5a5));u.reg_write(UC_ARM_REG_SP,0x20001000);u.reg_write(UC_ARM_REG_R5,0x20002000)
   handle=u.hook_add(UC_HOOK_CODE,lambda uc,pc,size,data:uc.emu_stop() if pc in [success,failure] else None)
   u.emu_start(entry|1,0,count=100);u.hook_del(handle);check(key+':magic-branch:'+str(valid),u.reg_read(UC_ARM_REG_PC)==(success if valid else failure))
   if valid:u.emu_start(success|1,success+4,count=4)
   check(key+':version-output:'+str(valid),struct.unpack('<I',u.mem_read(0x20002000,4))[0]==(VERSION if valid else 0xa5a5a5a5))
  # Exact comparison fragment is unique in all three pinned originals.
  pattern=bytes.fromhex('ac4221d1');offset=raw.find(pattern);check(key+':unique-version-compare',offset>=0 and raw.find(pattern,offset+1)<0);compare=BASE+offset;branch=list(m.disasm(pattern,compare))[1];mismatch=branch.operands[0].imm
  for current,package in [(VERSION,VERSION),(VERSION-1,VERSION),(VERSION+1,VERSION),(0,VERSION)]:
   u=cpu(raw);u.reg_write(UC_ARM_REG_R4,current);u.reg_write(UC_ARM_REG_R5,package);u.hook_add(UC_HOOK_CODE,lambda uc,pc,size,data:uc.emu_stop() if pc in [compare+4,mismatch] else None);u.emu_start(compare|1,0,count=10)
   check(key+':equal-or-mismatch:'+hex(current),u.reg_read(UC_ARM_REG_PC)==(compare+4 if current==package else mismatch))
  cases.append(dict(case=key,bundle_sha256=hashlib.sha256(bundle).hexdigest(),touch_sha256=TOUCH_SHA,version=VERSION,display_version='2.2.9.0',wire_bytes=list(VERSION.to_bytes(4,'big')),magic_check=hex(entry),header_version_copy=hex(success),compare=hex(compare),mismatch_branch=hex(mismatch)))
 r=dict(passed=True,count=len(checks),checks=checks,cases=cases,original_fragments=18,physical_version_known=False,scope='Pinned package/CRC/hash and isolated original magic/version field/inequality branches. No filesystem I/O, full updater, read failure or forced-DFU path execution; no installed touch version or hardware validation.')
 (a.output/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),cases=cases,original_fragments=18)))

if __name__=='__main__':main()
