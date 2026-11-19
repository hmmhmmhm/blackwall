"""Original IRQ/wait function contracts with captured main semaphore objects.

CLID read sequences and passive MMIO are explicit test inputs. This is not NVIC
exception delivery, scheduler integration, or completion of the live GPU model.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC,UC_HOOK_MEM_READ,UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import BASE,decode
from inspect_nema_submission import literal,discover_submission
from native_replay import validate_assets,parse_log
from pinned_main import load_pinned_main

SRAM,WORK,STOP=0x20000000,0x21000000,0x10000000
def sha(data):return hashlib.sha256(data).hexdigest()


def discover_irq(raw):
    vector=struct.unpack_from('<I',raw,4*(16+28))[0];wrapper=decode(raw,vector&~1,10)
    if [(i.mnemonic,i.op_str) for i in wrapper[:2]]!=[('push','{r7, lr}'),('movs','r0, #0')]:raise ValueError('Unexpected GPU IRQ vector')
    core=wrapper[2].operands[0].imm;body=decode(raw,core,0x5e)
    calls=[i.operands[0].imm for i in body if i.mnemonic=='bl']
    if len(calls)!=5 or calls[0]!=calls[3]:raise ValueError('Unexpected IRQ stabilization path')
    slots={}
    for i in body:
        if i.mnemonic.startswith('ldr') and 'pc' in i.op_str:
            value=literal(raw,i)
            if i.op_str.startswith('r5,'):slots['last_id']=value
            elif i.op_str.startswith('r0,'):slots['semaphore']=value
            elif i.op_str.startswith('r1,') and value!=0xe000ed04:slots['callback']=value
    submission=discover_submission(raw);wait_irq=next(i.operands[0].imm for i in decode(raw,submission['wait_id'],0x16) if i.mnemonic=='bl')
    take=next(i.operands[0].imm for i in decode(raw,wait_irq,0x1c) if i.mnemonic=='bl')
    query=[i.operands[0].imm for i in decode(raw,take,0x40) if i.mnemonic=='bl'][-1]
    scheduler_slots=[literal(raw,i) for i in decode(raw,query,0x1e) if i.mnemonic.startswith('ldr') and 'pc' in i.op_str]
    pendsv=struct.unpack_from('<I',raw,14*4)[0]&~1
    pendsv_body=decode(raw,pendsv,0x34)
    tcb_slot=literal(raw,next(i for i in pendsv_body if i.mnemonic.startswith('ldr') and 'pc' in i.op_str))
    if len(scheduler_slots)!=2 or pendsv_body[0].op_str!='r0, psp':raise ValueError('Unexpected scheduler context contract')
    loads=[i for i in decode(raw,submission['wait_id'],0x16) if i.mnemonic.startswith('ldr') and 'pc' in i.op_str]
    if literal(raw,loads[0])!=slots['last_id']:raise ValueError('IRQ publisher and waiter disagree')
    return dict(vector=vector,core=core,read=calls[0],write=calls[1],nvic_clear=calls[2],give=calls[4],
                wait=submission['wait'],wait_id=submission['wait_id'],wait_irq=wait_irq,take=take,slots=slots,
                scheduler_query=query,scheduler_slots=scheduler_slots,pendsv=pendsv,current_tcb_slot=tcb_slot,
                body=[dict(pc=i.address,bytes=i.bytes.hex(),instruction=i.mnemonic+' '+i.op_str) for i in body])


def runtime(raw,base_sram,state,contract,sequence,r3,observer=True):
    sram=bytearray(base_sram);q=state['handle'];slots=contract['slots']
    struct.pack_into('<2I',sram,slots['semaphore']-SRAM,q,state['callback'])
    struct.pack_into('<I',sram,slots['last_id']-SRAM,state['last_id'])
    queue=struct.pack('<24I',*state['queue_words']);sram[q-SRAM:q-SRAM+96]=queue
    if not (state['callback']==0 and state['queue_words'][14:17]==[0,1,0] and state['queue_words'][9]==0):
        raise ValueError('Only captured empty binary semaphore without waiters/callback is supported')
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
    extent=(len(raw)+4095)&~4095
    for address,data,size in [(BASE,raw,extent),(SRAM,bytes(sram),0x80000),(WORK,bytes(0x10000),0x10000)]:
        u.mem_map(address,size);u.mem_write(address,data)
    u.mem_protect(BASE,extent,UC_PROT_READ|UC_PROT_EXEC);u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
    for address in (0x40090000,0xe000e000):u.mem_map(address,0x1000);u.mem_write(address,b'\xa5'*0x1000)
    reads=[];writes=[];boundaries=[];give_calls=[];take_calls=[]
    regions=[(BASE,BASE+len(raw)),(SRAM,SRAM+0x6000),(WORK,WORK+0x10000),
             (slots['semaphore'],slots['semaphore']+8),(q,q+96),(slots['last_id'],slots['last_id']+4)]
    class Boundary(Exception):pass
    def access(cpu,kind,address,size,value,user):
        if address==0x40090148 and size==4:
            if len(reads)>=len(sequence):boundaries.append('CLID sample budget exhausted');raise Boundary()
            value=sequence[len(reads)];reads.append(value);cpu.mem_write(address,struct.pack('<I',value));return
        if not any(a<=address and address+size<=b for a,b in regions):raise ValueError('Read outside captured/declared input: '+hex(address))
    u.hook_add(UC_HOOK_MEM_READ,access)
    def code(cpu,address,size,user):
        if address==contract['write']:writes.append([cpu.reg_read(arm.UC_ARM_REG_R0),cpu.reg_read(arm.UC_ARM_REG_R1)])
        if address==contract['give']:give_calls.append([cpu.reg_read(arm.UC_ARM_REG_R0),cpu.reg_read(arm.UC_ARM_REG_R1)])
        if address==contract['take']:take_calls.append(cpu.reg_read(arm.UC_ARM_REG_R0))
    if observer:u.hook_add(UC_HOOK_CODE,code)
    def call(entry,args,until=STOP):
        for n in range(4,12):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),0x12340000+n)
        for n,v in enumerate(args):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),v)
        u.reg_write(arm.UC_ARM_REG_SP,WORK+0xff00);u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
        u.emu_start(entry|1,until,count=100000)
        return dict(pc=u.reg_read(arm.UC_ARM_REG_PC),r0=u.reg_read(arm.UC_ARM_REG_R0),sp=u.reg_read(arm.UC_ARM_REG_SP))
    ended=False
    try:
        returned=call(contract['vector']&~1,[0,0,0,r3]);ended=returned['pc']==STOP
    except Boundary:returned=dict(pc=u.reg_read(arm.UC_ARM_REG_PC))
    after=bytes(u.mem_read(SRAM,0x80000));work=bytes(u.mem_read(WORK,0x10000))
    allowed=[(slots['last_id']-SRAM,slots['last_id']-SRAM+4),(q-SRAM+0x38,q-SRAM+0x3c)]
    if any(not any(a<=i<b for a,b in allowed) for i,(x,y) in enumerate(zip(sram,after)) if x!=y):raise ValueError('IRQ modified unrelated SRAM')
    if any(v for i,v in enumerate(work) if not 0xfc00<=i<0xff00):raise ValueError('IRQ wrote outside stack')
    last=struct.unpack_from('<I',after,slots['last_id']-SRAM)[0]
    result=dict(returned=ended,exit=returned,reads=reads,write_calls=writes,give_calls=give_calls,take_calls=take_calls,
                last_id=last,messages=struct.unpack_from('<I',after,q-SRAM+0x38)[0],
                woken_stack=struct.unpack_from('<I',work,0xfee8)[0],icsr=struct.unpack('<I',u.mem_read(0xe000ed04,4))[0],
                icpr=struct.unpack('<I',u.mem_read(0xe000e280,4))[0],basepri=u.reg_read(arm.UC_ARM_REG_BASEPRI),
                sram_sha256=sha(after),work_sha256=sha(work),sample_boundary=boundaries,waits=[])
    for address,allowed_words in [(0x40090000,[0xf8,0x148]),(0xe000e000,[0x280,0xd04])]:
        page=bytes(u.mem_read(address,0x1000))
        if any(v!=0xa5 for i,v in enumerate(page) if not any(o<=i<o+4 for o in allowed_words)):
            raise ValueError('Unexpected passive MMIO effect')
    if ended:
        if returned['sp']!=WORK+0xff00 or any(u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n)))!=0x12340000+n for n in range(4,12)):
            raise ValueError('IRQ wrapper did not preserve ABI')
        if last!=sequence[-1] or result['messages']!=1 or result['basepri']!=0:raise ValueError('Unexpected IRQ publication/semaphore effect')
        if observer and (writes!=[[0xf8,0]]*(len(sequence)-1) or len(give_calls)!=1 or give_calls[0][0]!=q):raise ValueError('Unexpected original IRQ calls')
        if result['woken_stack']!=r3 or result['icsr']!=(0x10000000 if r3 else 0xa5a5a5a5):raise ValueError('Unexpected higher-priority-woken behavior')
        for requested in [last,max(0,last-1)]:
            u.mem_write(WORK+0x201c,struct.pack('<I',requested));answer=call(contract['wait'],[WORK+0x2000,0,0,0])
            if answer['pc']!=STOP or answer['r0']!=0 or struct.unpack('<I',u.mem_read(WORK+0x201c,4))[0]!=0xffffffff:raise ValueError('Original completed-ID wait did not return')
            result['waits'].append(dict(requested=requested,returned=True,result=answer['r0']))
        u.mem_write(WORK+0x201c,struct.pack('<I',last+1));answer=call(contract['wait'],[WORK+0x2000,0,0,0],until=contract['wait_irq'])
        if answer['pc']!=contract['wait_irq']:raise ValueError('Expected original semaphore wait boundary')
        result['waits'].append(dict(requested=last+1,returned=False,boundary=answer['pc']))
        if take_calls:raise ValueError('Unexpected semaphore take executed in bounded wait test')
    else:
        if (last!=state['last_id'] or result['messages']!=0 or give_calls
                or boundaries!=['CLID sample budget exhausted'] or reads!=sequence):
            raise ValueError('Unstable ID must stop at the explicit sample budget without publishing/signaling')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
    if any((x/'.git').exists() for x in [out,*out.parents]):raise ValueError('Private output required')
    out.mkdir(mode=0o700);cases=[]
    for case,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        _,raw=load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes());c=discover_irq(raw)
        source=a.simulator/'nema-irq-semaphore-main-01'/case;r=json.loads((source/'report.json').read_text());validate_assets(source,json.loads((source/'derived-inputs.json').read_text())['derived'])
        if not r['passed'] or parse_log((source/'renode.log').read_text())!=r['observed'] or (source/'main.bin').read_bytes()!=raw:raise ValueError('Unverified main semaphore source')
        state=r['diagnostics']['records'][0]
        if (state['handle_slot']!=c['slots']['semaphore'] or state['last_id_address']!=c['slots']['last_id'] or c['slots']['callback']!=state['handle_slot']+4):raise ValueError('IRQ slots disagree with captured main')
        sram=(a.simulator/'nema-live-draw-framebuffer-01'/case/'sram.bin').read_bytes();runs={}
        for name,seq,seed in [('stable8',[8,8],0),('racing9',[8,9,9],0),('racing10',[8,9,10,10],0),('woken1',[8,8],1),('woken-pattern',[8,8],0xa5a5a5a5),('unstable',[8,9,10],0)]:
            runs[name]=runtime(raw,sram,state,c,seq,seed)
        control=runtime(raw,sram,state,c,[8,8],0,observer=False)
        if any(control[k]!=runs['stable8'][k] for k in ['sram_sha256','work_sha256','icsr','icpr']):raise ValueError('Code observer changed IRQ execution')
        runs['observer-off']=control;cases.append(dict(case=case,contract=c,state=state,runs=runs,main_report_sha256=sha((source/'report.json').read_bytes())))
    result=dict(passed=True,cases=cases,cpu='Unicorn M7 bounded function fixture',actual_NVIC_irq=False,live_gpu_completion=False,
                semaphore_mocked=False,scheduler_executed=False,full_main_rendered=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');(out/'inspector.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(passed=True,irq_entries=21,semaphore_gives=18,wait_returns=36,future_wait_boundaries=18,actual_NVIC_irq=False)))


if __name__=='__main__':main()
