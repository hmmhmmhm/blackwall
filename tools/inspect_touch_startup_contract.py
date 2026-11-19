"""Execute pinned original gesture decode/validation/command/initialization fragments."""
import argparse,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5
from pinned_main import load_pinned_main
BASE=0x438000
RANGES=dict(decode=(0x4fbc68,0x4fbc76),valid=(0x4fbaf2,0x4fbb08),write=(0x4fbb42,0x4fbb5a),frame=(0x4fbb6c,0x4fbb7c),status=(0x4fbbe0,0x4fbbe6),startup=(0x504f72,0x504f82),read_args=(0x4fbc5a,0x4fbc64))
def cpu(raw):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);n=(len(raw)+4095)&~4095;u.mem_map(BASE,n);u.mem_write(BASE,raw);u.mem_protect(BASE,n,UC_PROT_READ|UC_PROT_EXEC);u.mem_map(0x20000000,0x10000);u.reg_write(UC_ARM_REG_SP,0x20001000);return u
def branch(u,entry,stops):
 u.hook_add(UC_HOOK_CODE,lambda uc,pc,size,data:uc.emu_stop() if pc in stops else None);u.emu_start(entry|1,0,count=100);return u.reg_read(UC_ARM_REG_PC)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(mode=0o700);checks=[];cases=[];md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 names=[('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')];raws={k:load_pinned_main((a.simulator/'inputs/verified-01'/f).read_bytes())[1] for k,f in names};reference=raws['stock24']
 for key,raw in raws.items():
  at={}
  for label,(start,end) in RANGES.items():
   code=reference[start-BASE:end-BASE];offset=raw.find(code);check(key+':unique:'+label,offset>=0 and raw.find(code,offset+1)<0);at[label]=BASE+offset
  for value in [0,1,800,65535]:
   u=cpu(raw);u.mem_write(0x2000100c,value.to_bytes(2,'little'));u.reg_write(UC_ARM_REG_R4,0x20002000);u.emu_start(at['decode']|1,at['decode']+14,count=20);check(key+':decode:'+str(value),struct.unpack('<H',u.mem_read(0x20002000,2))[0]==value)
  for value in [None,0,1,800,65535]:
   u=cpu(raw);u.reg_write(UC_ARM_REG_LR,0x20003001);u.reg_write(UC_ARM_REG_R0,0 if value is None else 0x20002000)
   if value is not None:u.mem_write(0x20002000,value.to_bytes(2,'little'))
   u.emu_start(at['valid']|1,0x20003000,count=50);check(key+':valid:'+str(value),u.reg_read(UC_ARM_REG_PC)==0x20003000 and u.reg_read(UC_ARM_REG_R0)==(0 if value is None or value==0 else 1))
  for value in [1,800,65535]:
   u=cpu(raw);u.mem_write(0x20002000,value.to_bytes(2,'little'));u.mem_write(0x20002100,struct.pack('<I',0x4fb9f5+(at['write']-RANGES['write'][0])));u.reg_write(UC_ARM_REG_R4,0x20002100);u.reg_write(UC_ARM_REG_R5,0x20002000);u.emu_start(at['write']|1,at['write']+24,count=50)
   check(key+':write-payload:'+str(value),u.mem_read(0x20001014,2)==value.to_bytes(2,'little') and u.reg_read(UC_ARM_REG_R0)==7 and u.reg_read(UC_ARM_REG_R1)==0x20001014 and u.reg_read(UC_ARM_REG_R2)==2)
  for payload in [b'\x07\x00\x17',b'\x06\x00\x17',b'\x07\x00\x16',b'\x07\xff\x17']:
   entry=at['frame'];seq=list(md.disasm(raw[entry-BASE:entry-BASE+16],entry));good=seq[-1].operands[0].imm;bad=entry+16;u=cpu(raw);u.mem_write(0x20001018,payload);pc=branch(u,entry,[good,bad]);check(key+':frame:'+payload.hex(),pc==(good if payload[0]==7 and payload[2]==0x17 else bad))
  for status in [0,1]:
   entry=at['status'];seq=list(md.disasm(raw[entry-BASE:entry-BASE+6],entry));good=seq[-1].operands[0].imm;bad=entry+6;u=cpu(raw);u.reg_write(UC_ARM_REG_R4,0x20002000);u.mem_write(0x20002000,bytes([7,status,0x17]));check(key+':status:'+str(status),branch(u,entry,[good,bad])==(good if status==0 else bad))
  for status,value in [(0,800),(0,123),(255,800),(255,0)]:
   entry=at['startup'];seq=list(md.disasm(raw[entry-BASE:entry-BASE+16],entry));write=seq[1].operands[0].imm;skip=seq[-1].operands[0].imm;u=cpu(raw);u.reg_write(UC_ARM_REG_R4,status);u.mem_write(0x20001010,value.to_bytes(2,'little'));check(key+':startup:'+str(status)+':'+str(value),branch(u,entry,[write,skip])==(skip if status==0 and value==800 else write))
  entry=at['read_args'];ops=[(i.mnemonic,i.op_str) for i in md.disasm(raw[entry-BASE:entry-BASE+10],entry)];check(key+':read-register8-length2',ops==[('movs','r2, #2'),('add','r1, sp, #0xc'),('movs','r0, #8'),('ldr','r3, [r5, #4]'),('blx','r3')]);cases.append(dict(case=key,addresses={k:hex(v) for k,v in at.items()},target_threshold=800,write_register=7,read_register=8,read_bytes=2,write_bytes=2,reply_frame=[7,0,23]))
 r=dict(passed=True,count=len(checks),checks=checks,cases=cases,original_scenarios=66,scope='Original isolated main ARM only: no external callbacks, logs, whole initialization, touch MCU binary execution, physical defaults, device writes or events.')
 (a.output/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),original_scenarios=66,cases=cases)))
if __name__=='__main__':main()
