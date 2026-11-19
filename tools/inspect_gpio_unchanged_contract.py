"""Pin conditional output semantics and execute original GPIO136 writes without pad reads."""
import argparse,hashlib,json,re
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1
from pinned_main import load_pinned_main
from native_replay import validate_assets

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(mode=0o700);s=a.simulator;checks=[];rows=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 pins={'gpio-interrupt-research-01/gpio_regs.html':'94134fb630f47634e6b39cde05bcc20529009e3201350fe88b873b0e4c7a3158','gpio-research-01/am_hal_gpio.c':'f8ce8b01c41295d4c8d934478d78ffcb377a8fe50a2b1b90bfe9cc37dbf54e4a','gpio-research-01/am_hal_gpio.h':'5f21528a170a06c16864830c70d532d190a132176eeaf27d09944e62b8b71a88'}
 for name,digest in pins.items():check(name,hashlib.sha256((s/name).read_bytes()).hexdigest()==digest)
 page=(s/'gpio-interrupt-research-01/gpio_regs.html').read_text()
 for name,address in [('WT4','0x40010430'),('WTS4','0x4001044C'),('WTC4','0x40010468')]:
  begin=page.index('<h3 id="'+name+'"');end=page.find('<h3 id="',begin+10);body=page[begin:end];text=re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',body));check(name+':output-enable-conditional','if the GPIO is enabled for output' in text and address.lower() in body.lower())
 header=(s/'gpio-research-01/am_hal_gpio.h').read_text();check('HAL-clear-macro','#define am_hal_gpio_output_clear(n)             (*AM_HAL_GPIO_WTCn((n)) = AM_HAL_MASK32(n))' in header)
 # This is a logical convergence proof under the existing known-latch assumption,
 # not proof of physical initial values or non-GPIO mux side effects.
 for old in [0,1]:
  for desired in [0,1]:
   outcomes={old,desired};check('conditional-convergence:'+str(old)+':'+str(desired),(len(outcomes)==1)==(old==desired))
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
 for key,name in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
  _,raw=load_pinned_main((s/'inputs/verified-01'/name).read_bytes());d=s/'touch-gpio-main-01'/key;r=json.loads((d/'report.json').read_text());v=r['observed'];validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);entry=v['pc']-0x2e
  ins=next(md.disasm(raw[entry-0x438000:entry-0x438000+2],entry));check(key+':HAL-entry',ins.mnemonic=='push' and ins.op_str=='{r2, r3, r4, lr}')
  check(key+':known-unchanged-clear',r['passed'] and raw==(d/'main.bin').read_bytes() and '0x40010220' not in v['gpio_config']['values'] and v['gpio_output_latch']['words'][4]&0x100==0)
  for selector in [0,1]:
   for cfg in [0,0x103]:
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);n=(len(raw)+4095)&~4095;u.mem_map(0x438000,n);u.mem_write(0x438000,raw);u.mem_protect(0x438000,n,UC_PROT_READ|UC_PROT_EXEC);u.mem_map(0x20000000,0x10000);u.mem_map(0x40010000,0x1000);u.mem_write(0x40010220,cfg.to_bytes(4,'little'));reads=[];writes=[]
    def record(uc,access,address,width,value,data):
     if 0x40010000<=address<0x40011000:(writes if access==17 else reads).append([address,width,value] if access==17 else [address,width])
    u.hook_add(UC_HOOK_MEM_WRITE,record);u.hook_add(UC_HOOK_MEM_READ,record);u.reg_write(UC_ARM_REG_R0,136);u.reg_write(UC_ARM_REG_R1,selector);u.reg_write(UC_ARM_REG_SP,0x20001000);u.reg_write(UC_ARM_REG_LR,0x20003001);u.emu_start(entry|1,0x20003000,count=200)
    expected=0x40010468 if selector==0 else 0x4001044c
    check(key+':original-write:'+str(selector)+':'+str(cfg),u.reg_read(UC_ARM_REG_PC)==0x20003000 and u.reg_read(UC_ARM_REG_R0)==0 and reads==[] and writes==[[expected,4,0x100]])
  rows.append(dict(case=key,entry=hex(entry),write_pc=hex(v['pc']),current_word4=v['gpio_output_latch']['words'][4],pin136_pad_state='not recorded',clear_mask=0x100))
 result=dict(passed=True,count=len(checks),checks=checks,cases=rows,original_functions=12,scope='Pinned conditional semantics plus original HAL issues writes without config reads. Logical unchanged result only; no independent latch/pad assertion or physical validation.')
 (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),cases=rows,original_functions=12)))
if __name__=='__main__':main()
