"""Validate full original-main RAM captures and inspect linked RTOS task state.

The separate M7 leaf fixture executes the original task selector, not PendSV or
an exception return. Task layout candidates are cross-checked against live lists.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC
import unicorn.arm_const as arm
from inspect_nema_irq_contract import discover_irq
from inspect_ambiq_target import decode
from inspect_nema_submission import literal
from native_replay import FILES, MAIN_LAYOUT, validate_assets
from run_native_candidate import memory_exports, validate_memory_exports, observe

BASE, SRAM, WORK, STOP = 0x438000, 0x20000000, 0x21000000, 0x10000000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task_graph(data, current):
    def valid(address, length=4):
        return address % 4 == 0 and SRAM <= address <= SRAM+len(data)-length
    def word(address):
        if not valid(address):
            raise ValueError('Task graph pointer outside captured SRAM')
        return struct.unpack_from('<I',data,address-SRAM)[0]
    candidates = []
    for offset in range(0,len(data)-112,4):
        address = SRAM+offset
        if word(address+16) != address or word(address+36) != address:
            continue
        saved, stack, priority, depth = word(address),word(address+48),word(address+44),word(address+84)
        if not (priority < 256 and valid(stack) and valid(saved,40) and 0 < depth <= 0x100000 and stack <= saved < stack+depth*4 <= SRAM+len(data)):
            continue
        name = data[offset+52:offset+84].split(b'\0',1)[0].decode('ascii',errors='replace')
        candidates.append(dict(tcb=address,name=name,priority=priority,stack_base=stack,
                               stack_depth_word_candidate=depth,saved_sp=saved,
                               state_container=word(address+20),saved_psplim_word=word(saved),
                               saved_exc_return_word=word(saved+4),current=address==current))
    by_tcb = {t['tcb']:t for t in candidates}
    if current not in by_tcb:
        raise ValueError('Current TCB was not found in captured task layout')
    containers = {}
    for task in candidates:
        container = task['state_container']
        if container not in containers:
            count = word(container)
            if not 1 <= count <= 128 or word(container+8) != 0xffffffff:
                raise ValueError('Invalid active state-list container')
            sentinel, node, nodes, owners = container+8,word(container+12),[],[]
            while node != sentinel:
                if node in nodes or len(nodes) >= count:
                    raise ValueError('Unexpected state-list cycle')
                nxt, prev, owner = word(node+4),word(node+8),word(node+12)
                if word(nxt+8) != node or word(prev+4) != node or owner not in by_tcb or node != owner+4 or word(node+16) != container:
                    raise ValueError('State-list links/owner do not agree')
                nodes.append(node);owners.append(owner);node=nxt
            if len(nodes) != count or word(container+4) not in nodes+[sentinel]:
                raise ValueError('State-list count/index does not agree')
            containers[container] = dict(count=count,owners=owners)
        if task['tcb'] not in containers[container]['owners']:
            raise ValueError('Candidate is not a member of its state-list')
        task['saved_header_matches_stack_base'] = task['saved_psplim_word'] == task['stack_base']
        if not task['current'] and (not task['saved_header_matches_stack_base'] or task['saved_exc_return_word']&0xffffff00 != 0xffffff00):
            raise ValueError('Inactive task saved header is not the expected port frame')
    return dict(tasks=candidates,containers=containers,current=by_tcb[current],
                candidates=len(candidates),inactive_headers_validated=sum(not t['current'] for t in candidates))


def original_selector(raw, data, contract, include_memory=False):
    entry = next(i.operands[0].imm for i in decode(raw,contract['pendsv'],0x40) if i.mnemonic=='bl')
    body = decode(raw,entry,0xce)
    slots = {}
    for i in body:
        if i.mnemonic.startswith('ldr') and 'pc' in i.op_str:
            slots.setdefault(i.op_str.split(',')[0],set()).add(literal(raw,i))
    slot = lambda reg: next(iter(slots[reg])) if len(slots[reg]) == 1 else None
    if slot('r4') != contract['current_tcb_slot'] or any(slot(reg) is None for reg in ['r1','r2','r3','r4','r5','r7']):
        raise ValueError('Unexpected original task selector literal layout')
    word = lambda a:struct.unpack_from('<I',data,a-SRAM)[0]
    index, priority = word(slot('r2')),word(slot('r5'))
    if index >= 64 or priority >= 256:
        raise ValueError('Unbounded selector history/priority')
    u = Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
    size = (len(raw)+4095)&~4095
    u.mem_map(BASE,size);u.mem_write(BASE,raw);u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
    u.mem_map(SRAM,len(data));u.mem_write(SRAM,data)
    u.mem_map(WORK,0x10000);u.mem_map(STOP,4096)
    u.reg_write(arm.UC_ARM_REG_SP,WORK+0xff00);u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
    u.reg_write(arm.UC_ARM_REG_XPSR,0x01000000)
    u.emu_start(entry|1,STOP,count=4096)
    if u.reg_read(arm.UC_ARM_REG_PC) != STOP:
        raise ValueError('Original task selector did not return')
    after = bytes(u.mem_read(SRAM,len(data)))
    selected_priority = struct.unpack_from('<I',after,slot('r5')-SRAM)[0]
    allowed = {slot(reg) for reg in ['r1','r2','r4','r5']}
    allowed |= {slot('r7')+selected_priority*20+4,slot('r3')+index*8,slot('r3')+index*8+4}
    changes = [dict(address=SRAM+n,before=struct.unpack_from('<I',data,n)[0],after=struct.unpack_from('<I',after,n)[0])
               for n in range(0,len(data),4) if data[n:n+4] != after[n:n+4]]
    if any(c['address'] not in allowed for c in changes):
        raise ValueError('Original selector wrote outside its discovered state fields')
    result=dict(entry=entry,returned=True,current_before=word(slot('r4')),
                current_after=struct.unpack_from('<I',after,slot('r4')-SRAM)[0],priority=selected_priority,
                changes=changes,observer_hooks_used=False,engine='Unicorn Cortex-M7 leaf fixture',
                pendsv_executed=False,exception_return_executed=False)
    return (result,after) if include_memory else result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator',type=Path);parser.add_argument('captures',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Preserve existing inspection')
    rows=[]
    for case in ['stock24','stock23','cfw']:
        folder=args.captures/case
        report=json.loads((folder/'report.json').read_text());plan=json.loads((folder/'plan.json').read_text())
        manifest=json.loads((folder/'derived-inputs.json').read_text());validate_assets(folder,manifest['derived'])
        if sha(folder/'plan.json')!=manifest['plan_sha256'] or sha(folder/'runner-source.py')!=manifest['runner_sha256']:
            raise ValueError('Plan/runner provenance differs')
        source=args.simulator/plan['source_root']/case;prior=json.loads((source/'report.json').read_text())
        log=(folder/'renode.log').read_text();observed,kind=observe(log)
        native=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_MEMORY_EXPORTS ')]
        if len(native)!=1 or validate_memory_exports(folder,memory_exports(plan),native[0])!=report['memory_exports']:
            raise ValueError('Memory export provenance differs')
        if not report['passed'] or observed!=report['observed'] or kind!=report['boundary_kind'] or observed!=prior['observed'] or report['selected_observation']!=prior['selected_observation']:
            raise ValueError('Original main CPU/event path differs')
        if sha(folder/'main.bin')!=MAIN_LAYOUT[plan['cases'][case]][3]:raise ValueError('Main pin differs')
        raw=(folder/'main.bin').read_bytes();data=(folder/'exports/sram-full.bin').read_bytes()
        diagnostic_rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_CANDIDATE_'+plan['id']+' ')]
        if diagnostic_rows!=[report['diagnostics']]:raise ValueError('Diagnostics differ from native log')
        kernel,=report['diagnostics']['kernel']
        for address,value in zip(kernel['slots'],kernel['values']):
            if struct.unpack_from('<I',data,address-SRAM)[0]!=value:raise ValueError('Kernel globals differ from independent diagnostics')
        for address,words in [(kernel['tcb'],kernel['tcb_words'])]+[(x['address'],x['words']) for x in kernel['stacks']]:
            expected=struct.pack('<'+'I'*len(words),*words)
            if data[address-SRAM:address-SRAM+len(expected)]!=expected:raise ValueError('Independent diagnostic SRAM words differ')
        for window in observed['sram_windows']:
            address=window['base'];expected=bytes(window['bytes'])
            if data[address-SRAM:address-SRAM+len(expected)]!=expected:raise ValueError('Original snapshot window differs')
        graph=task_graph(data,kernel['tcb']);contract=discover_irq(raw)
        selected=original_selector(raw,data,contract)
        if selected['current_before']!=kernel['tcb'] or selected['current_after'] not in {t['tcb'] for t in graph['tasks']}:raise ValueError('Selector current/selected task differs')
        rows.append(dict(case=case,graph=graph,selector=selected,passed=True,
                         pins={name:sha(folder/name) for name in list(FILES)+['report.json','renode.log','derived-inputs.json','plan.json']},exports=report['memory_exports']))
    args.output.mkdir(parents=True,mode=0o700)
    (args.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    result=dict(passed=True,cases=rows,native_rerun=False,hardware_accessed=False,
                complete_machine_checkpoint=False,full_main_booted=False)
    (args.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=[dict(case=r['case'],tasks=r['graph']['candidates'],inactive_headers=r['graph']['inactive_headers_validated'],selector_same_task=r['selector']['current_before']==r['selector']['current_after']) for r in rows])))


if __name__=='__main__':main()
