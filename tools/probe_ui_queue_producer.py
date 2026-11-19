"""Original type-7 UI producer and queue/ring API transactions, isolated M7 callers."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import cpu, WORK, STOP, SRAM, BASE
from run_native_candidate import memory_exports, validate_memory_exports

SIGNATURE=bytes.fromhex('f8b586b004000d0016000c21002203af3800')


def sha(data):return hashlib.sha256(data).hexdigest()


def word(data,address):
    if address%4 or not SRAM<=address<=SRAM+len(data)-4:raise ValueError('Outside captured RAM')
    return struct.unpack_from('<I',data,address-SRAM)[0]


def literal(raw,instruction):
    if instruction.mnemonic not in ['ldr','ldr.w'] or instruction.operands[1].mem.base!=arm.UC_ARM_REG_PC:raise ValueError('Expected PC-relative literal')
    address=((instruction.address+4)&~3)+instruction.operands[1].mem.disp
    return struct.unpack_from('<I',raw,address-BASE)[0]


def discover(raw):
    if raw.count(SIGNATURE)!=1:raise ValueError('Ambiguous producer')
    entry=BASE+raw.index(SIGNATURE);body=decode(raw,entry,0xc8);by_pc={i.address:i for i in body}
    def call(offset):
        i=by_pc[entry+offset]
        if i.mnemonic!='bl':raise ValueError('Expected original BL')
        return i.operands[0].imm
    put=call(0xa6);writer=call(0x8c);ring=literal(raw,by_pc[entry+0x8a]);queue_slot=literal(raw,by_pc[entry+0xa2])
    expected={0x22:('movs','r0, #7'),0x28:('movs','r0, #0'),0x96:('movs','r0, #0xa'),0x9a:('mov.w','r3, #0x3e8'),0x9e:('movs','r2, #0')}
    for offset,want in expected.items():
        i=by_pc[entry+offset]
        if (i.mnemonic,i.op_str)!=want:raise ValueError('Unknown message builder')
    # Adjacent API candidates are accepted only with source prologue/return and
    # ring reader index checks, not solely because of their relative offsets.
    get=put+0x7e;reader=writer+0xe8
    if raw[get-BASE:get-BASE+10]!=bytes.fromhex('f8b506000d001c000027'):raise ValueError('Unknown queue receive wrapper')
    if raw[reader-BASE:reader-BASE+12]!=bytes.fromhex('e0b5002301930023009301ab'):raise ValueError('Unknown ring read wrapper')
    writer_inner=decode(raw,writer+12,4)[0].operands[0].imm
    reader_inner=decode(raw,reader+12,4)[0].operands[0].imm
    tail=decode(raw,reader-4,4)
    if len(tail)!=1 or tail[0].mnemonic!='pop.w' or tail[0].op_str!='{r4, r5, r6, r7, r8, sb, sl, pc}':raise ValueError('Missing writer return')
    reader_body=decode(raw,reader_inner,0xe0)
    if not any(i.mnemonic=='adds.w' and i.op_str=='r0, r5, #8' for i in reader_body):raise ValueError('Unknown ring reader cursor')
    anchor=bytes.fromhex('3078717850ea0120')
    if raw.count(anchor)!=1:raise ValueError('Ambiguous payload parser')
    parser=BASE+raw.index(anchor)-6;parser_body=decode(raw,parser,0x50)
    if parser_body[2].op_str!='r6, r0':raise ValueError('Unknown parser input')
    parser_boundary=next(i.address for i in parser_body if i.mnemonic=='bl')
    sites=[]
    for address in range(entry-0x1000,entry,2):
        if raw[address-BASE+1]&0xf8!=0xf0:continue
        ins=decode(raw,address,4)
        if len(ins)==1 and ins[0].mnemonic=='bl' and ins[0].operands[0].imm==parser:sites.append(address)
    if len(sites)!=1:raise ValueError('Unknown type-7 consumer call')
    consumer=decode(raw,sites[0]-12,12)
    if [(i.mnemonic,i.op_str) for i in consumer[:4]]!=[('ldrb','r0, [r7]'),('cmp','r0, #7'),('bne',consumer[2].op_str),('ldr','r1, [r7, #8]')]:raise ValueError('Parser is not type-7 consumer')
    return dict(producer=entry,put=put,put_call=entry+0xa6,get=get,writer=writer,reader=reader,ring=ring,queue_slot=queue_slot,
                writer_inner=writer_inner,reader_inner=reader_inner,parser=parser,parser_boundary=parser_boundary,consumer_parser_call=sites[0])


def execute(raw,data,entry,args,boundary=None):
    u=cpu(raw,data,WORK+0xff00);captured=[];trace=[]
    for n,v in enumerate(args):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),v)
    if boundary is not None:
        def observer(c,pc,size,user):
            trace.append(pc)
            if pc==boundary:
                regs=[c.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(4)]
                captured.append(dict(arguments=regs,message=bytes(c.mem_read(regs[1],12)).hex()))
        u.hook_add(UC_HOOK_CODE,observer)
    u.emu_start(entry|1,STOP,count=200000)
    if u.reg_read(arm.UC_ARM_REG_PC)!=STOP:raise ValueError('Original function failed to return')
    state=dict(ram=bytes(u.mem_read(SRAM,len(data))),work=bytes(u.mem_read(WORK,0x10000)),scs=bytes(u.mem_read(0xe000e000,0x2000)),
               registers=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(13)]+[u.reg_read(arm.UC_ARM_REG_SP),u.reg_read(arm.UC_ARM_REG_LR),u.reg_read(arm.UC_ARM_REG_PC)])
    return state,captured,trace


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    a.output.mkdir(parents=True);(a.output/'probe.py').write_bytes(Path(__file__).read_bytes());rows=[]
    wait_path=a.simulator/'main-display-wait-map-02/report.json';wait=json.loads(wait_path.read_text())
    if not wait['passed']:raise ValueError('Unverified task map')
    for task_map in wait['cases']:
        case=task_map['case'];source=a.simulator/'original-main-full-memory-02'/case
        report=json.loads((source/'report.json').read_text());plan=json.loads((source/'plan.json').read_text())
        if sha((source/'report.json').read_bytes())!=task_map['source_report_sha256'] or not report['passed']:raise ValueError('Changed source report')
        validate_memory_exports(source,memory_exports(plan),report['memory_exports'])
        raw=(source/'main.bin').read_bytes();data=(source/'exports/sram-full.bin').read_bytes()
        if sha(raw)!=task_map['raw_sha256']:raise ValueError('Changed original main')
        c=discover(raw);ui=next(t for t in task_map['tasks'] if t['name']=='ui_task');q=word(data,c['queue_slot'])
        if q!=ui['queue'] or word(data,q+0x38)!=0 or word(data,q+0x24)!=1:raise ValueError('Unexpected initial UI queue')
        ring=c['ring'];buf=word(data,ring);capacity=word(data,ring+4);read_index=word(data,ring+8);write_index=word(data,ring+12)
        if capacity!=0xa000 or read_index!=0 or write_index!=0 or word(data,ring+16)!=0:raise ValueError('Unknown initial ring state')
        samples=[]
        for args in [(0,0,0),(0x1234,0x89abcdef,0x76543210),(0xffffabcd,0xffffffff,0x80000001)]:
            emitted,observations,trace=execute(raw,data,c['producer'],args,c['put_call']);plain,_,_=execute(raw,data,c['producer'],args)
            if emitted!=plain:raise ValueError('Code observer changed producer final state')
            if len(observations)!=1:raise ValueError('Missing queue send observation')
            expected_message=struct.pack('<III',7,0,10);payload=struct.pack('<HII',args[0]&0xffff,args[1],args[2]);after=emitted['ram'];message=observations[0]
            if message['arguments'][0]!=q or message['arguments'][2:]!=[0,1000] or bytes.fromhex(message['message'])!=expected_message:raise ValueError('Wrong original queue envelope')
            if emitted['registers'][0]!=0 or word(after,q+0x38)!=1 or word(after,q+0x24)!=0 or word(after,ui['tcb']+40)!=0:raise ValueError('Original queue did not release UI receiver')
            destination=word(data,q+4)
            if after[destination-SRAM:destination-SRAM+12]!=expected_message or word(after,q+4)!=destination+12:raise ValueError('Original queue item differs')
            if after[buf-SRAM:buf-SRAM+10]!=payload or word(after,ring+12)!=10 or word(after,ring+8)!=0:raise ValueError('Original payload ring differs')
            received,_,_=execute(raw,after,c['get'],[q,WORK+0x100,0,0])
            if received['registers'][0]!=0 or received['work'][0x100:0x10c]!=expected_message or word(received['ram'],q+0x38)!=0:raise ValueError('Original queue receive differs')
            drained,_,_=execute(raw,received['ram'],c['reader'],[ring,WORK+0x100,10])
            if drained['registers'][0]!=10 or drained['work'][0x100:0x10a]!=payload or word(drained['ram'],ring+8)!=10 or word(drained['ram'],ring+12)!=10:raise ValueError('Original ring read differs')
            parser_cpu=cpu(raw,data,WORK+0xff00);parser_cpu.mem_write(WORK+0x100,payload)
            parser_cpu.reg_write(arm.UC_ARM_REG_R0,WORK+0x100);parser_cpu.reg_write(arm.UC_ARM_REG_R1,10)
            parser_cpu.hook_add(UC_HOOK_CODE,lambda u,pc,size,user:u.emu_stop() if pc==c['parser_boundary'] else None)
            parser_cpu.emu_start(c['parser']|1,STOP,count=1000)
            sp=parser_cpu.reg_read(arm.UC_ARM_REG_SP)
            decoded=[struct.unpack('<I',parser_cpu.mem_read(sp+0x14,4))[0],parser_cpu.reg_read(arm.UC_ARM_REG_R7),struct.unpack('<I',parser_cpu.mem_read(sp+0x10,4))[0]]
            if parser_cpu.reg_read(arm.UC_ARM_REG_PC)!=c['parser_boundary'] or decoded!=[args[0]&0xffff,args[1],args[2]]:raise ValueError('Original consumer payload parse differs')
            samples.append(dict(arguments=list(args),decoded_payload_fields=decoded,message=expected_message.hex(),payload=payload.hex(),queue_send_observation=message,
                                queue_messages_after_send=1,queue_messages_after_receive=0,ui_waiters_after_send=0,ui_event_container_after_send=0,
                                producer_instruction_count=len(trace),producer_trace_sha256=sha(struct.pack('<'+'I'*len(trace),*trace)),
                                producer_ram_sha256=sha(after),observer_on_off_final_state_exact=True,
                                producer_return=0,queue_receive_return=0,ring_read_return=10,ring_read_cursor_after=10))
        rows.append(dict(case=case,raw_sha256=sha(raw),source_report_sha256=sha((source/'report.json').read_bytes()),contract=c,ui_tcb=ui['tcb'],queue=q,ring_buffer=buf,ring_capacity=capacity,samples=samples))
    result=dict(passed=True,cases=rows,wait_map_sha256=sha(wait_path.read_bytes()),engine='Unicorn 2.1.4 Cortex-M7 isolated ARM callers',
                whole_main_resumed=False,ui_business_handler_executed=False,consumer_prefix_only=True,nvic_or_pendsv_executed=False,hardware_accessed=False,
                caller_arguments_and_stack_synthetic=True,scs_zeroed_per_function=True,producer_internal_calls_skipped=False)
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),samples=sum(len(r['samples']) for r in rows),original_api_transactions=27,producer_observer_controls=9)))


if __name__=='__main__':main()
