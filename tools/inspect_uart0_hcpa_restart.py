"""Check original HCPA last-user decisions without patching code or executing hardware."""
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC,UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    source=s/'mspi1-source-research-01';manifest=json.loads((source/'sources.json').read_text())
    for file in ['am_hal_pwrctrl.c','am_hal_pwrctrl.h','apollo510.h']:
        check(file+'-pin',hashlib.sha256((source/file).read_bytes()).hexdigest()==next(f['sha256'] for f in manifest['files'] if f['path'].endswith('/'+file)))
    hal=(source/'am_hal_pwrctrl.c').read_text();check('HAL-shared-disable-skips-poll','if ( pwrctrl_periph_disable_msk_check(ePeripheral) )' in hal and 'bIsLastOneInDomain = false;' in hal)
    meta=json.loads((s/'post-font-uart0-contract-02/report.json').read_text());md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    for key,file in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        d=s/'uart0-idle-dma-main-01'/key;r=json.loads((d/'report.json').read_text());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);v=parse_log((d/'renode.log').read_text());_,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes())
        check(key+'-original-native',r['passed'] and v==r['observed'] and raw==(d/'main.bin').read_bytes())
        entry=int(next(c for c in meta['cases'] if c['case']==key)['enable_entry'],0);helper=entry+0x13a;disable=entry+0x1f6
        code={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[disable-0x438000:disable+0x15e-0x438000],disable)}
        check(key+'-disable-clear-store',code[disable+0xa8]==('str','r1, [r0]'))
        check(key+'-last-user-call',code[disable+0xb4]==('bl','#'+hex(helper)))
        check(key+'-shared-skips-status-poll',code[disable+0xba]==('beq','#'+hex(disable+0x154)) and code[disable+0xc8]==('bl','#'+next(c for c in meta['cases'] if c['case']==key)['poll']))
        records=[]
        for module in range(4):
            own=0x200<<module;other=0x200<<((module+1)%4)
            for enabled in [0,own,other,own|other,0x40000]:
                u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);size=(len(raw)+4095)&~4095;u.mem_map(0x438000,size);u.mem_write(0x438000,raw);u.mem_protect(0x438000,size,UC_PROT_READ|UC_PROT_EXEC);u.mem_map(0x40021000,0x1000);u.mem_write(0x40021004,struct.pack('<I',enabled));u.mem_map(0x21000000,0x1000);u.mem_map(0x10000000,0x1000,UC_PROT_READ|UC_PROT_EXEC)
                u.reg_write(UC_ARM_REG_R0,11+module);u.reg_write(UC_ARM_REG_SP,0x21000800);u.reg_write(UC_ARM_REG_LR,0x10000001);reads=[]
                u.hook_add(UC_HOOK_MEM_READ,lambda uc,access,address,size,value,data:reads.append(address),begin=0x40021000,end=0x40021fff)
                u.emu_start(helper|1,0x10000000,count=1000);ret=u.reg_read(UC_ARM_REG_R0);expected=0 if enabled&0x1e00 and not enabled&own else 1
                check(key+'-original-last-user-'+str(module)+'-'+hex(enabled),u.reg_read(UC_ARM_REG_PC)==0x10000000 and u.reg_read(UC_ARM_REG_SP)==0x21000800 and ret==expected and reads and set(reads)=={0x40021004})
                records.append(dict(module=module,enable=hex(enabled),return_value=ret,enable_reads=len(reads),status_reads=0))
        uart=next(x for x in v['uarts'] if x['module']==0);check(key+'-pending-gate-with-peer-active',uart['phase']=='off-requested' and uart['request_word']==0 and uart['status_word']==0x200 and uart['control']==0 and any(x['module']!=0 and x['request_word'] for x in v['uarts']))
        cases.append(dict(case=key,last_user_helper=hex(helper),disable_entry=hex(disable),probes=records))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,original_helper_executions=60,hardware_accessed=False,new_full_main_executed=False,register_retention_hardware_verified=False,scope='Original helper + pinned HAL explain no status poll while another UART is enabled. Shared powered-domain retention remains explicit hardware hypothesis; main code unmodified.')
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),original_helper_executions=60)))

if __name__=='__main__':main()
