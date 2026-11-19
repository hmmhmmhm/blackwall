"""Read original stopped-task frames and display wait objects; no guest execution."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from inspect_ambiq_target import decode
from inspect_nema_irq_contract import discover_irq
from run_native_candidate import memory_exports,validate_memory_exports

BASE,SRAM=0x438000,0x20000000


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve original evidence')
    inspection=a.simulator/'original-main-rtos-memory-inspection-02/report.json';all_rows=json.loads(inspection.read_text());rows=[]
    for row in all_rows['cases']:
        case=row['case'];source=a.simulator/'original-main-full-memory-02'/case;report=json.loads((source/'report.json').read_text());plan=json.loads((source/'plan.json').read_text())
        if not all_rows['passed'] or not report['passed'] or sha(source/'report.json')!=row['pins']['report.json']:raise ValueError('Unverified RAM source')
        validate_memory_exports(source,memory_exports(plan),report['memory_exports'])
        raw=(source/'main.bin').read_bytes();data=(source/'exports/sram-full.bin').read_bytes();contract=discover_irq(raw)
        if sha(source/'main.bin')!=row['pins']['main.bin']:raise ValueError('Raw code changed')
        body=decode(raw,contract['pendsv'],0x34)
        if not any(i.mnemonic=='stmdb' and i.op_str=='r0!, {r2, r3, r4, r5, r6, r7, r8, sb, sl, fp}' for i in body):raise ValueError('Unknown software frame layout')
        def word(address):
            if address%4 or not SRAM<=address<=SRAM+len(data)-4:raise ValueError('Read outside captured RAM')
            return struct.unpack_from('<I',data,address-SRAM)[0]
        tasks=[]
        for task in row['graph']['tasks']:
            name=task['name']
            if name not in ['ui_task','displaydrv_mgr_task','ambiqdraw']:continue
            tcb,sp=task['tcb'],task['saved_sp'];exc=word(sp+4);extended=exc&16==0
            core=sp+40+(64 if extended else 0);hardware=[word(core+4*n) for n in range(8)]
            if hardware[7]&0x01000000==0 or hardware[7]&0x1ff or not BASE<=hardware[6]<BASE+len(raw):raise ValueError('Invalid saved thread core frame')
            saved=[word(sp+8+4*n) for n in range(8)];event=word(tcb+40)
            entry=dict(name=name,tcb=tcb,saved_sp=sp,exception_return=exc,saved_pc=hardware[6],saved_lr=hardware[5],saved_r4_r11=saved,event_container=event,
                       notify_value=word(tcb+0x68),notify_state=data[tcb+0x6c-SRAM])
            if name=='ui_task':
                queue=event-0x24
                if saved[2]!=queue or word(queue+0x24)!=1 or word(queue+0x38)!=0 or word(queue+0x3c)!=96 or word(queue+0x40)!=12:raise ValueError('UI queue ownership/shape differs')
                entry.update(wait_kind='queue receive',queue=queue,receiver_waiters=1,messages=0,capacity=96,item_bytes=12)
            else:
                if event!=0 or entry['notify_state']!=1 or entry['notify_value']!=0 or saved[0]!=0:raise ValueError('Notification wait state differs')
                caller=core+32+(72 if extended else 0)+(4 if hardware[7]&0x200 else 0)
                candidates=[]
                for n in range(16):
                    address=word(caller+4*n)
                    if address&1==0 or not BASE+4<=address<BASE+len(raw):continue
                    ret=address&~1;instructions=decode(raw,ret-4,4)
                    if len(instructions)!=1 or instructions[0].mnemonic!='bl':continue
                    target=instructions[0].operands[0].imm
                    ops=[i.op_str for i in decode(raw,target,20)]
                    if name=='ambiqdraw' and all(v in ops for v in ['r4, r0','r5, r1','r6, r2']):
                        if saved[1]!=1 or saved[2]!=0xffffffff:raise ValueError('Counter notification arguments differ')
                        candidates.append(dict(call_pc=ret-4,target=target,kind='indexed notification counter wait',index=0,clear_on_exit=1,ticks=0xffffffff))
                    if name=='displaydrv_mgr_task' and all(v in ops for v in ['r4, r0','r8, r1','r7, r2','r5, r3']):
                        if saved[3]!=0x800000:raise ValueError('Display notification mask differs')
                        candidates.append(dict(call_pc=ret-4,target=target,kind='indexed notification bits wait',index=0,mask=0x800000))
                if len(candidates)!=1:raise ValueError('Saved caller does not uniquely identify notification primitive')
                entry.update(wait_kind=candidates[0]['kind'],source_call=candidates[0])
            tasks.append(entry)
        if len(tasks)!=3:raise ValueError('Missing display task')
        rows.append(dict(case=case,tasks=tasks,source_report_sha256=sha(source/'report.json'),raw_sha256=sha(source/'main.bin'),memory_exports=report['memory_exports']))
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    result=dict(passed=True,cases=rows,inspection_sha256=sha(inspection),guest_executed=False,hardware_accessed=False,
                queue_message_semantics_verified=False,notification_producer_verified=False)
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),display_tasks=sum(len(r['tasks']) for r in rows))))


if __name__=='__main__':main()
