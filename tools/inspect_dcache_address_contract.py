"""Pin CMSIS and inspect original SRAM DCCMVAC loop; no firmware modifications."""
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R4,UC_ARM_REG_R10,UC_ARM_REG_PC
from pinned_main import load_pinned_main
from native_replay import validate_assets
from probe_uart_hcpa_gate_main import parse_boundary

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    cmsis=s/'upstream/cmsis-6.3.0';manifest=json.loads((cmsis/'manifest.json').read_text());check('CMSIS-commit',manifest['commit']=='45dab712ad84f8cbbf2b7bfc089c19088507df6f')
    for f in manifest['files']:check(Path(f['path']).name+'-pin',hashlib.sha256((cmsis/Path(f['path']).name).read_bytes()).hexdigest()==f['sha256'])
    header=(cmsis/'core_cm55.h').read_text();api=(cmsis/'armv7m_cachel1.h').read_text();check('DCCMVAC-register', 'Offset: 0x268 ( /W)  D-Cache Clean by MVA to PoC' in header);check('CMSIS-clean-address-loop','SCB->DCCMVAC = op_addr;' in api and '#define __SCB_DCACHE_LINE_SIZE  32U' in api)
    old=Path(__file__).with_name('renode-system-control.cs').read_bytes();(o/'base-system-control.cs').write_bytes(old)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
    for key,file in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        d=s/'uart-hcpa-gate-main-01'/key;r=json.loads((d/'report.json').read_text());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);v,kind=parse_boundary((d/'renode.log').read_text());_,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes());pc=v['pc'];begin=pc-0x1a;end=pc+0x12
        check(key+'-original-native',r['passed'] and r['observed']==v and raw==(d/'main.bin').read_bytes() and kind=='unsupported-data-cache-by-address')
        code={i.address:i for i in md.disasm(raw[begin-0x438000:end-0x438000],begin)};check(key+'-clean-loop-store',(code[pc].mnemonic,code[pc].op_str)==('str','r2, [r0]') and (code[pc+2].mnemonic,code[pc+2].op_str)==('adds','r2, #0x20'))
        ins=code[pc-2];mem=next(x.mem for x in ins.operands if x.type==ARM_OP_MEM and x.mem.base==ARM_REG_PC);reg=struct.unpack_from('<I',raw,((ins.address+4)&~3)+mem.disp-0x438000)[0];check(key+'-literal-register',reg==0xe000ef68)
        ctx=v['register_context'];check(key+'-live-range',ctx['r4']==25 and ctx['r1']==32 and ctx['r2']==ctx['r10']==v['system_control']['value'] and ctx['r2']&31==0)
        probes=[]
        for base in [ctx['r2'],0x20000103]:
            for length in [0,1,25,32,33,1023,1024]:
                u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);size=(len(raw)+4095)&~4095;u.mem_map(0x438000,size);u.mem_write(0x438000,raw);u.mem_protect(0x438000,size,UC_PROT_READ|UC_PROT_EXEC);u.mem_map(0xe000e000,0x1000);writes=[];u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,access,address,size,value,data:writes.append((address,size,value)));u.reg_write(UC_ARM_REG_R4,length);u.reg_write(UC_ARM_REG_R10,base);u.emu_start(begin|1,end,count=1000)
                rounded=(length+31)&~31;count=(rounded+(base&31)+31)//32 if rounded else 0;expected=[(0xe000ef68,4,base+32*i) for i in range(count)]
                check(key+'-original-loop-'+hex(base)+'-'+str(length),u.reg_read(UC_ARM_REG_PC)==end and writes==expected)
                probes.append(dict(base=hex(base),length=length,writes=count))
        cases.append(dict(case=key,store=hex(pc),loop_begin=hex(begin),loop_end=hex(end),live_buffer=hex(ctx['r2']),live_length=25,live_lines=1,probes=probes))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,original_loop_fragments=42,base_system_control_sha256=hashlib.sha256(old).hexdigest(),hardware_accessed=False,new_full_main_executed=False,scope='CMSIS/source and isolated original instruction fragments. Full main frontier is one SRAM clean line, not a completed DMA transfer or boot.')
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),original_loop_fragments=42)))

if __name__=='__main__':main()
