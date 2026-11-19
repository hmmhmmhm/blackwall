"""Original take/give RAM transactions; passive ICSR, not NVIC execution."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
import unicorn.arm_const as arm
from inspect_nema_irq_contract import discover_irq
from inspect_original_rtos_memory import original_selector

BASE,SRAM,WORK,STOP=0x438000,0x20000000,0x21000000,0x10000000


def cpu(raw,data,sp):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
    size=(len(raw)+4095)&~4095;u.mem_map(BASE,size);u.mem_write(BASE,raw);u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
    u.mem_map(SRAM,len(data));u.mem_write(SRAM,data);u.mem_map(WORK,0x10000);u.mem_map(STOP,4096);u.mem_map(0xe000e000,0x2000)
    u.reg_write(arm.UC_ARM_REG_SP,sp);u.reg_write(arm.UC_ARM_REG_LR,STOP|1);u.reg_write(arm.UC_ARM_REG_XPSR,0x01000000)
    return u


def execute_phase(raw,data,profile,q,contract,phase,observe_writes):
    u=cpu(raw,data,profile['psp'] if phase=='wait' else WORK+0xff00);trace=[];writes=[];pending=[]
    if phase=='wait':
        u.mem_write(WORK+0x201c,struct.pack('<I',8));u.reg_write(arm.UC_ARM_REG_R0,WORK+0x2000);entry=contract['wait']
    else:
        u.reg_write(arm.UC_ARM_REG_R0,q);u.reg_write(arm.UC_ARM_REG_R1,WORK+0x100);entry=contract['give']
    def code(c,address,size,user):
        trace.append(address)
        if phase=='wait' and struct.unpack('<I',c.mem_read(0xe000ed04,4))[0]==0x10000000:
            pending.append(address);c.emu_stop()
    u.hook_add(UC_HOOK_CODE,code)
    if observe_writes:u.hook_add(UC_HOOK_MEM_WRITE,lambda c,op,address,size,value,user:writes.append(dict(pc=c.reg_read(arm.UC_ARM_REG_PC),address=address,size=size)))
    u.emu_start(entry|1,STOP,count=200000)
    if phase=='wait' and len(pending)!=1 or phase=='give' and u.reg_read(arm.UC_ARM_REG_PC)!=STOP:
        raise ValueError('Original phase did not reach its declared boundary')
    state=dict(sram=bytes(u.mem_read(SRAM,len(data))),work=bytes(u.mem_read(WORK,0x10000)),
               registers=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(13)]+[u.reg_read(arm.UC_ARM_REG_SP),u.reg_read(arm.UC_ARM_REG_LR),u.reg_read(arm.UC_ARM_REG_PC)],
               trace=trace,pending=pending)
    return state,writes


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    a.output.mkdir(parents=True);rows=[];(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    for case,root in [('stock24','nema-native-kernel-final-01'),('stock23','nema-native-kernel-final-peers-01'),('cfw','nema-native-kernel-final-peers-01')]:
        source=a.simulator/root/case;report=json.loads((source/'report.json').read_text());profile=json.loads((source/'kernel-profile.json').read_text());irq=json.loads((source/'irq-profile.json').read_text())
        if not report['passed']:raise ValueError('Unverified full context source')
        for name,digest in report['input_hashes'].items():
            if hashlib.sha256((source/name).read_bytes()).hexdigest()!=digest:raise ValueError('Source input changed')
        raw=(source/'main.bin').read_bytes();initial=(source/'sram.bin').read_bytes()+(source/'system-sram.bin').read_bytes();contract=discover_irq(raw)
        blocking,wait_writes=execute_phase(raw,initial,profile,irq['queue'],contract,'wait',True)
        off,_=execute_phase(raw,initial,profile,irq['queue'],contract,'wait',False)
        if blocking!=off:raise ValueError('Write observer changed original wait path/state')
        blocked=blocking['sram'];word=lambda data,address:struct.unpack_from('<I',data,address-SRAM)[0]
        tcb=profile['current_tcb'];q=irq['queue'];suspended=contract['scheduler_slots'][1]
        state=dict(waiters=word(blocked,q+0x24),messages=word(blocked,q+0x38),event_container=word(blocked,tcb+40),state_container=word(blocked,tcb+20),scheduler_suspended=word(blocked,suspended),stop_pc=blocking['pending'][0])
        if state['waiters']!=1 or state['messages']!=0 or state['event_container']!=q+0x24:raise ValueError('Original event-list enrollment differs')
        selected,selected_ram=original_selector(raw,blocked,contract,True)
        giving,give_writes=execute_phase(raw,selected_ram,profile,q,contract,'give',True)
        off,_=execute_phase(raw,selected_ram,profile,q,contract,'give',False)
        if giving!=off:raise ValueError('Write observer changed original give path/state')
        awakened=giving['sram']
        reselected,reselected_ram=original_selector(raw,awakened,contract,True)
        restored=dict(waiters=word(awakened,q+0x24),messages=word(awakened,q+0x38),event_container=word(awakened,tcb+40),state_container=word(awakened,tcb+20),higher_woken=struct.unpack_from('<I',giving['work'],0x100)[0])
        out=a.output/case;out.mkdir();(out/'blocked-sram.bin').write_bytes(blocked);(out/'awakened-sram.bin').write_bytes(awakened)
        if restored['waiters']!=0 or restored['messages']!=1 or restored['event_container']!=0 or restored['higher_woken'] not in (0,1):
            (out/'failure.json').write_text(json.dumps(dict(blocked=state,after_give=restored),indent=2)+'\n')
            raise ValueError('Original give state: '+repr(dict(blocked=state,after_give=restored)))
        changed={SRAM+n for left,right in [(initial,blocked),(blocked,selected_ram),(selected_ram,awakened),(awakened,reselected_ram)] for n in range(0,len(initial),4) if left[n:n+4]!=right[n:n+4]}
        changed={address for address in changed if not profile['task_low']<=address<profile['task_high']}
        written={address for w in wait_writes+give_writes if SRAM<=w['address']<SRAM+len(initial) for address in range(w['address']&~3,(w['address']+w['size']+3)&~3,4) if not profile['task_low']<=address<profile['task_high']}
        written.update(c['address'] for r in [selected,reselected] for c in r['changes'])
        row=dict(case=case,passed=True,blocked=state,awakened=restored,nonstack_changed_words=sorted(changed),nonstack_written_words=sorted(written),
                 observer_on_off_equal=True,wait_trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(blocking['trace']),*blocking['trace'])).hexdigest(),
                 first_selector=selected,second_selector=reselected,
                 give_trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(giving['trace']),*giving['trace'])).hexdigest(),write_events=wait_writes+give_writes,
                 source_report_sha256=hashlib.sha256((source/'report.json').read_bytes()).hexdigest(),source=str(source),
                 blocked_sha256=hashlib.sha256(blocked).hexdigest(),awakened_sha256=hashlib.sha256(awakened).hexdigest(),
                 actual_nvic=False,engine='Unicorn M7 passive ICSR transactions',write_observer_scope='Only these exact wait/give inputs, with full path/RAM/WORK/register on-off equality')
        (out/'report.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row)
    (a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows),indent=2)+'\n')
    print(json.dumps([dict(case=r['case'],blocked=r['blocked'],awakened=r['awakened'],changed_words=len(r['nonstack_changed_words'])) for r in rows]))


if __name__=='__main__':main()
