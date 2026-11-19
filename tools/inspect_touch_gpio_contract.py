"""Execute original GPIO27 reader/wrapper and inspect the touch startup level branch."""
import argparse,json
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2
from pinned_main import load_pinned_main
from native_replay import validate_assets
BASE=0x438000
def cpu(raw,word):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);n=(len(raw)+4095)&~4095;u.mem_map(BASE,n);u.mem_write(BASE,raw);u.mem_protect(BASE,n,UC_PROT_READ|UC_PROT_EXEC);u.mem_map(0x20000000,0x10000);u.mem_map(0x40010000,0x1000);u.mem_write(0x40010404,word.to_bytes(4,'little'));u.reg_write(UC_ARM_REG_SP,0x20001000);u.reg_write(UC_ARM_REG_LR,0x20003001);return u
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(mode=0o700);checks=[];cases=[];m=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);m.detail=True;pattern=bytes.fromhex('002827d19df80800002823d1')
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 for key,name in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
  _,raw=load_pinned_main((a.simulator/'inputs/verified-01'/name).read_bytes());d=a.simulator/'touch-startup-main-01'/key;r=json.loads((d/'report.json').read_text());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);v=r['observed'];ctx=v['register_context'];wrapper=(ctx['r14']&~1)-16
  check(key+':native-context',r['passed'] and raw==(d/'main.bin').read_bytes() and ctx['r0']==27 and ctx['r1']==0x40010404 and v['gpio_config']['values']['0x4001006c']==0x53)
  call=next(m.disasm(raw[wrapper+12-BASE:wrapper+16-BASE],wrapper+12));check(key+':wrapper-original-call',call.mnemonic=='bl');hal=call.operands[0].imm
  seq=list(m.disasm(raw[hal-BASE:hal-BASE+0x2c],hal));check(key+':HAL-original-load',any(i.address==v['pc'] and i.mnemonic=='ldr' and i.op_str=='r1, [r1]' for i in seq))
  for level in [0,1]:
   for noise in [0,0xffffffff]:
    word=(noise&~(1<<27))|(level<<27)
    for label,entry in [('HAL',hal),('wrapper',wrapper)]:
     u=cpu(raw,word);u.reg_write(UC_ARM_REG_R0,27);u.mem_write(0x20002000,b'\xa5'*4)
     if label=='HAL':u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_R2,0x20002000)
     else:u.reg_write(UC_ARM_REG_R1,0x20002000)
     u.emu_start(entry|1,0x20003000,count=200)
     expected=level.to_bytes(4,'little') if label=='HAL' else bytes([level,0xa5,0xa5,0xa5])
     check(key+':'+label+':'+str(level)+':'+str(noise),u.reg_read(UC_ARM_REG_PC)==0x20003000 and u.reg_read(UC_ARM_REG_R0)==0 and u.mem_read(0x20002000,4)==expected)
  offset=raw.find(pattern);check(key+':unique-startup-branch',offset>=0 and raw.find(pattern,offset+1)<0);entry=BASE+offset;seq=list(m.disasm(pattern,entry));returns=seq[1].operands[0].imm;service=entry+12;check(key+':both-error-or-high-return',seq[-1].mnemonic=='bne' and seq[-1].operands[0].imm==returns)
  for status,level in [(0,0),(0,1),(6,0)]:
   u=cpu(raw,0);u.reg_write(UC_ARM_REG_R0,status);u.mem_write(0x20001008,bytes([level]));u.hook_add(UC_HOOK_CODE,lambda uc,pc,size,data:uc.emu_stop() if pc in [returns,service] else None);u.emu_start(entry|1,0,count=50)
   check(key+':startup-branch:'+str(status)+':'+str(level),u.reg_read(UC_ARM_REG_PC)==(service if status==0 and level==0 else returns))
  cases.append(dict(case=key,hal=hex(hal),read_pc=hex(v['pc']),wrapper=hex(wrapper),branch=hex(entry),service_path=hex(service),return_path=hex(returns),guest_pad_configuration=0x53))
 result=dict(passed=True,count=len(checks),checks=checks,cases=cases,original_scenarios=33,scope='Original isolated reader/wrapper execution with backing-memory levels, plus branch only. No GPIO edges, physical idle polarity, IRQ generation, touch controller execution, full main boot or display.')
 (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),cases=cases,original_scenarios=33)))
if __name__=='__main__':main()
