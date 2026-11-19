"""Verify Timer0 config/IRQ setup after role selection and shared Timer14 engine limits."""
import argparse,hashlib,json,re,struct,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from inspect_mspi1_config_contract import collect
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main
from timer14_engine_source import load_engine


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    collect(s);src=s/'timer-source-research-01';pins=json.loads((src/'sources.json').read_text())
    for filename in ['am_hal_timer.c','am_hal_timer.h','apollo510.h']:
        pin=next(f for f in pins['files'] if f['path'].endswith('/'+filename));check(filename+'-pin',pins['commit']=='61b293a49db34030c545f99101f7ebf6a3050314' and hashlib.sha256((src/filename).read_bytes()).hexdigest()==pin['sha256'])
    clock=s/'timer0-clock-research-01';cp=json.loads((clock/'sources.json').read_text());b=(clock/'am_hal_clkgen.h').read_bytes()
    check('clock-header-pin',hashlib.sha256(b).hexdigest()==cp['sha256'] and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==cp['git_blob']=='deed0f50cfd471b58cac5eb3e82165a492105a6b')
    check('clock-header-MAX96-not-timer-measurement','#define AM_HAL_CLKGEN_FREQ_MAX_HZ           96000000' in b.decode())
    h=(src/'apollo510.h').read_text();check('Timer0-IRQ67',re.search(r'TIMER0_IRQn\s*=\s*67,',h) is not None)
    per=next(p for p in ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot().findall('./peripherals/peripheral') if p.findtext('name')=='TIMER');regs={r.findtext('name'):r for r in per.findall('./registers/register')}
    offsets={'GLOBEN':0x10,'INTEN':0x60,'INTSTAT':0x64,'INTCLR':0x68,'INTSET':0x6c,'CTRL0':0x200,'TIMER0':0x204,'TMR0CMP0':0x208,'TMR0CMP1':0x20c,'MODE0':0x210}
    for name,offset in offsets.items():check(name+'-offset',int(regs[name].findtext('addressOffset'),0)==offset)
    fields={f.findtext('name'):f for f in regs['CTRL0'].findall('./fields/field')}
    enums=lambda f:{e.findtext('name'):int(e.findtext('value'),0) for e in fields[f].findall('./enumeratedValues/enumeratedValue')}
    check('UPCOUNT-function2-HFRC-div16-clock1',enums('TMR0FN')['UPCOUNT']==2 and enums('TMR0CLK')['HFRC_DIV16']==1)
    end=h.index('} TIMER_Type;');start=h.rfind('typedef struct {',0,end);c='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+h[start:end]+'} TIMER_Type;\n'
    for name,offset in offsets.items():c+='_Static_assert(offsetof(TIMER_Type,'+name+')=='+str(offset)+',"'+name+'");\n'
    (o/'layout.c').write_text(c);r=subprocess.run(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(o/'layout.c'),'-o',str(o/'layout.o')],capture_output=True,text=True,timeout=30);(o/'compiler.log').write_text(r.stdout+r.stderr);check('compiled-register-offsets',r.returncode==0)
    engine=load_engine(s);check('pinned-engine-HFRC96','private const long HFRCFrequency = 96000000;' in engine)
    reload=engine[engine.index('private void CompareReached()'):];reload=reload[:reload.index('private readonly ComparingTimer compare0Timer;')]
    check('engine-OneShot-flag-reloads-not-stops','if(OneShot)' in reload and 'Value = 0;' in reload and 'Enabled = false' not in reload)
    check('engine-UPCOUNT-uses-reload-flag','case FunctionSelect.Upcount:\n                                internalTimers[index].OneShot = true;' in engine)
    check('HAL-clear-stop-distinct-from-disable','am_hal_timer_clear_stop(uint32_t ui32TimerNumber)' in (src/'am_hal_timer.c').read_text())
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
    for key,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        _,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
        def code(addr,size):return {i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[addr-0x438000:addr+size-0x438000],addr)}
        def target(addr):
            ins=code(addr,4)[addr];check(key+'-BL-'+hex(addr),ins[0]=='bl');return int(ins[1][1:],0)
        def literal(addr):
            i=next(md.disasm(raw[addr-0x438000:addr+4-0x438000],addr));mem=next(o.mem for o in i.operands if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC)
            return struct.unpack_from('<I',raw,(((addr+4)&~3)+mem.disp)-0x438000)[0]
        meta=None
        for level in ['low','high']:
            d=s/'gpio-role-main-01'/(key+'-'+level);r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());check(key+'-'+level+'-native-report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(key+'-'+level+'-original-main',raw==(d/'main.bin').read_bytes())
            ctx=v['register_context'];pc=v['pc'];seq=code(pc,0x3e)
            check(key+'-'+level+'-Timer0-config-state',ctx['r0']==0 and ctx['r1']==0x40008000 and ctx['r6']==0x40008200 and ctx['r5']==0x120 and ctx['r4']==0x100 and ctx['r2']==6000 and ctx['r3']==0xffffffff)
            check(key+'-'+level+'-disable-before-config',seq[pc]==('ldr','r7, [r6]') and seq[pc+2]==('lsrs','r7, r7, #1') and seq[pc+4]==('lsls','r7, r7, #1') and seq[pc+6]==('str','r7, [r6]'))
            check(key+'-'+level+'-config-register-stores',seq[pc+12]==('str.w','r5, [r6, #0x200]') and seq[pc+20]==('str.w','r4, [r5, #0x210]') and seq[pc+28]==('str.w','r2, [r4, #0x208]') and seq[pc+36]==('str.w','r3, [r2, #0x20c]'))
            check(key+'-'+level+'-clear-after-config',seq[pc+50]==('orrs','r1, r1, #2') and seq[pc+54]==('str','r1, [r0]'))
            caller_return=v['stack_context']['words'][5]&~1;setup=caller_return-0x24;sc=code(setup,0x48)
            check(key+'-'+level+'-explicit-request',sc[setup+0xa]==('movs','r0, #1') and sc[setup+0xe]==('movs','r0, #2') and sc[setup+0x16]==('movw','r0, #0x1770') and sc[setup+0x1e]==('movs','r0, #0'))
            check(key+'-'+level+'-IRQ-priority-enable',sc[setup+0x30]==('movs','r1, #4') and sc[setup+0x32]==('movs','r0, #0x43') and sc[setup+0x38]==('movs','r0, #0x43'))
            check(key+'-'+level+'-compare0-interrupt-request',sc[setup+0x2a]==('movs','r0, #1'))
            isr=struct.unpack_from('<I',raw,4*(16+67))[0]&~1;ic=code(isr,0x18)
            check(key+'-'+level+'-original-vector-ISR',ic[isr]==('push','{r7, lr}') and ic[isr+2]==('mov','r1, sp') and ic[isr+4]==('movs','r0, #0') and ic[isr+10]==('ldr','r0, [sp]'))
            clear_stop=target(setup+0x26);irq_enable=target(setup+0x2c);disable=target(setup+0x44)
            cs=code(clear_stop,0x54);ds=code(disable,0x34);ie=code(irq_enable,10)
            check(key+'-'+level+'-clear-stop-EN-and-CLR',cs[clear_stop+0x2e]==('lsrs','r1, r1, #1') and cs[clear_stop+0x3e]==('orrs','r1, r1, #2') and cs[clear_stop+0x4e]==('bics','r1, r1, #2'))
            check(key+'-'+level+'-final-disable-clears-EN',ds[disable+0x2e]==('lsrs','r1, r1, #1') and ds[disable+0x32]==('str','r1, [r0]'))
            check(key+'-'+level+'-interrupt-enable-register',literal(irq_enable)==0x40008060 and ie[irq_enable+4]==('orrs','r0, r2') and ie[irq_enable+6]==('str','r0, [r1]'))
            meta=dict(case=key,read_pc=hex(pc),setup=hex(setup),config_request=hex(literal(setup+2)),control='0x120',mode='0x100',compare0=6000,compare1='0xffffffff',irqn=67,irq_priority=4,compare_irq_mask=1,vector_handler=hex(isr),clear_stop_call=hex(setup+0x26),clear_stop_function=hex(clear_stop),disable_call=hex(setup+0x44),disable_function=hex(disable),IRQ_enable_call=hex(setup+0x2c),IRQ_enable_function=hex(irq_enable))
        cases.append(meta)
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='Static Timer0 disabled config and IRQ setup from six prior main runs; engine reuse candidate only, nominal HFRC rate/UPCOUNT period/ISR untested and no new main or hardware execution')
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))


if __name__=='__main__':main()
