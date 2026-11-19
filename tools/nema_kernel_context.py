"""Captured RAM plus an explicitly constructed PSP caller, not a machine restore."""
import hashlib
import json
import struct
from pathlib import Path

from inspect_nema_irq_contract import discover_irq
from inspect_nema_submission import discover_submission, literal
from inspect_ambiq_target import decode
from inspect_ambiq_commands import discover as discover_commands
from native_replay import validate_assets
from run_native_candidate import memory_exports, validate_memory_exports


def prepare(simulator, case, raw, prepared_sram, live, deferred=False, boundary_control=False):
    folder=simulator/'original-main-full-memory-02'/case
    manifest=json.loads((folder/'derived-inputs.json').read_text());validate_assets(folder,manifest['derived'])
    report=json.loads((folder/'report.json').read_text());plan=json.loads((folder/'plan.json').read_text())
    records=[json.loads(l.split(' ',1)[1]) for l in (folder/'renode.log').read_text().splitlines() if l.startswith('BLACKWALL_MEMORY_EXPORTS ')]
    if not report['passed'] or (folder/'main.bin').read_bytes()!=raw or len(records)!=1:
        raise ValueError('Unverified original RAM capture')
    validate_memory_exports(folder,memory_exports(plan),records[0])
    inspection=simulator/'original-main-rtos-memory-inspection-02/report.json'
    audit=json.loads(inspection.read_text());row=next(r for r in audit['cases'] if r['case']==case)
    if not audit['passed'] or row['pins']['report.json']!=hashlib.sha256((folder/'report.json').read_bytes()).hexdigest():
        raise ValueError('RAM graph inspection differs')
    full=bytearray((folder/'exports/sram-full.bin').read_bytes());before=bytes(full)
    contract=discover_irq(raw);submission=discover_submission(raw)
    table=submission['ring_table']-0x20000000
    full[table:table+20]=prepared_sram[table:table+20]
    _,context_slot=discover_commands(raw)
    if struct.unpack_from('<I',prepared_sram,context_slot-0x20000000)[0]!=0x21001000:
        raise ValueError('Declared diagnostic Nema context pointer differs')
    full[context_slot-0x20000000:context_slot-0x20000000+4]=struct.pack('<I',0x21001000)
    current=row['graph']['current'];registers={r['index']:r['value'] for r in report['diagnostics']['registers']}
    if registers[18]&2==0 or registers[25]&0x1ff or not current['stack_base']+16<registers[13]<current['stack_base']+current['stack_depth_word_candidate']*4:
        raise ValueError('Captured current task is not a bounded PSP thread')
    pendsv=decode(raw,contract['pendsv'],0x58)
    call=next(i for i in pendsv if i.mnemonic=='bl')
    selector=call.operands[0].imm;slots={}
    for i in decode(raw,selector,0xce):
        if i.mnemonic.startswith('ldr') and 'pc' in i.op_str:
            slots.setdefault(i.op_str.split(',')[0],set()).add(literal(raw,i))
    if any(len(slots.get(reg,[]))!=1 for reg in ['r1','r2','r3','r4','r5','r7']):
        raise ValueError('Unexpected kernel selector layout')
    slot=lambda reg:next(iter(slots[reg]))
    word=lambda address:struct.unpack_from('<I',full,address-0x20000000)[0]
    index,priority=word(slot('r2')),word(slot('r5'))
    if slot('r4')!=contract['current_tcb_slot'] or word(slot('r4'))!=current['tcb'] or priority!=current['priority'] or not 0<=index<64:
        raise ValueError('Kernel task/priority state differs')
    allowed={slot(reg) for reg in ['r1','r2','r4','r5']}
    allowed|={current['tcb'],slot('r7')+priority*20+4,slot('r3')+index*8,slot('r3')+index*8+4}
    priority_sites=[]
    cursor=0
    while True:
        offset=raw.find(struct.pack('<I',0xe000ed20),cursor)
        if offset<0:break
        cursor=offset+1
        for address in range(max(0x438000,0x438000+offset-0x1000),0x438000+offset,2):
            body=decode(raw,address,18)
            if len(body)!=7 or not body[0].mnemonic.startswith('ldr') or 'pc' not in body[0].op_str:continue
            if literal(raw,body[0])==0xe000ed20 and body[2].op_str=='r1, r1, #0xff0000' and body[5].op_str=='r1, r1, #0xff000000':
                priority_sites.append(dict(pc=address,bytes=raw[address-0x438000:address-0x438000+18].hex()))
    if len(priority_sites)!=1:raise ValueError('Original PendSV/SysTick lowest-priority initializer not identified')
    profile=dict(source=str(folder),inspection_sha256=hashlib.sha256(inspection.read_bytes()).hexdigest(),
                 source_report_sha256=hashlib.sha256((folder/'report.json').read_bytes()).hexdigest(),
                 source_memory_exports=records[0],current_tcb=current['tcb'],tcb_slot=contract['current_tcb_slot'],
                 task_low=current['stack_base']+16,task_high=current['stack_base']+current['stack_depth_word_candidate']*4,
                 psp=registers[13],msp=registers[22],handler_low=0x2007d000,handler_high=0x20080000,
                 stack_limits=dict(psplim=current['stack_base'],msplim=0x2007d000,psp=registers[13],control=6),
                 selector=selector,after_selector=call.address+call.size,port_return=next(i.address for i in pendsv if i.mnemonic=='bx' and i.op_str=='r3'),
                 allowed_kernel_words=sorted(allowed),ring_table_address=submission['ring_table'],
                 diagnostic_nema_context_slot=context_slot,diagnostic_nema_context=0x21001000,
                 original_priority_initializer=priority_sites[0],declared_pendsv_priority=0xff,
                 original_ram_sha256=hashlib.sha256(before).hexdigest(),prepared_ram_sha256=hashlib.sha256(full).hexdigest(),
                 complete_machine_restore=False,declared_stack_limits=True,synthetic_caller=True)
    if deferred:
        transaction=simulator/'nema-blocking-transactions-05'/case/'report.json'
        tx=json.loads(transaction.read_text());tx_source=Path(tx['source'])
        if not tx['passed'] or not tx['observer_on_off_equal'] or hashlib.sha256((tx_source/'report.json').read_bytes()).hexdigest()!=tx['source_report_sha256'] or (tx_source/'main.bin').read_bytes()!=raw:
            raise ValueError('Blocking transaction source differs')
        queue=word(contract['slots']['semaphore']);ready=word(current['tcb']+20)
        if tx['blocked']['event_container']!=queue+0x24 or tx['awakened']['state_container']!=ready:
            raise ValueError('Blocking list ownership differs')
        for address,length in [(queue,96),(current['tcb'],112),(ready,20),(tx['blocked']['state_container'],20)]:
            allowed.update(range(address,address+length,4))
        allowed.update(tx['nonstack_written_words']);allowed.add(contract['scheduler_slots'][1])
        alternate=next(t for t in row['graph']['tasks'] if t['tcb']==tx['first_selector']['current_after'])
        if alternate['tcb']==current['tcb'] or tx['second_selector']['current_after']!=current['tcb']:
            raise ValueError('Expected blocked task handoff and wake selection differ')
        allowed.add(alternate['tcb'])
        allowed.update(range(alternate['state_container'],alternate['state_container']+20,4))
        for n in [1,2]:allowed.update([slot('r3')+((index+n)%64)*8,slot('r3')+((index+n)%64)*8+4])
        profile.update(allowed_kernel_words=sorted(allowed),deferred_completion=True,boundary_control=boundary_control,
                       deferred_queue=queue,deferred_ready_list=ready,deferred_wait_list=tx['blocked']['state_container'],
                       deferred_suspended_slot=contract['scheduler_slots'][1],blocking_transaction=str(transaction),
                       extra_stacks=[dict(low=alternate['stack_base']+16,high=alternate['stack_base']+alternate['stack_depth_word_candidate']*4,tcb=alternate['tcb'])],
                       expected_selections=[alternate['tcb'],current['tcb']],
                       blocking_transaction_sha256=hashlib.sha256(transaction.read_bytes()).hexdigest())
    live['calls'].append(dict(name='blocking-wait' if deferred else 'completed-wait',entry=contract['wait'],args=[0x21002000,0,0,0],stack=[]))
    live['evidence']['phases']=live['calls']
    live['itcm']=(folder/'exports/itcm-full.bin').read_bytes()
    return bytes(full[:0x80000]),bytes(full[0x80000:]),profile


def setup_text(profile):
    code=''.join('f.AddKernelWord('+str(address)+')\n' for address in profile['allowed_kernel_words'])
    code+=''.join('f.AddKernelStack('+str(r['low'])+','+str(r['high'])+')\n' for r in profile.get('extra_stacks',[]))
    fields=['task_low','task_high','handler_low','handler_high','selector','after_selector','port_return','tcb_slot']
    code+='f.EnableKernelContext('+','.join(str(profile[k]) for k in fields)+')\n'
    code+='f.SeedRegister(18,4)\nf.SeedRegister(13,'+str(profile['msp'])+')\nb.WriteByte(0xe000ed22,0xff)\nb.WriteByte(0xe000ed23,0xff)\n'
    if profile.get('deferred_completion'):
        fields=['deferred_queue','current_tcb','deferred_suspended_slot','deferred_ready_list']
        code+='f.ConfigureDeferredCompletion(gpu.ReleaseCompletion,'+','.join(str(profile[k]) for k in fields)+','+str(profile['boundary_control'])+')\n'
    return code


def observation_text(profile):
    text=("r['kernel_context']=dict(selector_entries=int(f.SelectorEntries),port_returns=int(f.PortReturns),selected_tcb=int(f.SelectedTcb),saved_sp=int(f.SavedTaskSp),exception_return=int(f.PortExceptionReturn),current_tcb=int(b.ReadDoubleWord("+str(profile['tcb_slot'])+")),stored_sp=int(b.ReadDoubleWord("+str(profile['current_tcb'])+")),ipsr=int(cpu.GetRegister(25).RawValue)&0x1ff,control=int(cpu.GetRegister(18).RawValue),process_stack_selected=bool(cpu.IsUsingProcessSP),pendsv_priority=int(b.ReadByte(0xe000ed22)),gpu_priority=int(b.ReadByte(0xe000e41c)),other_sp=int(cpu.GetRegister(22).RawValue),bootstrap=[int(b.ReadDoubleWord(0x2100c3f0+4*i)) for i in range(6)],phase_returns=[int(b.ReadDoubleWord(0x2100c02c+64*i)) for i in range(7)])\nFile.WriteAllBytes('/work-output/final-system-sram.bin',b.ReadBytes(0x20080000,0x300000))\n")
    if profile.get('deferred_completion'):
        text+="r['deferred_completion']=dict(released=bool(f.DeferredReleased),gpu_released=bool(gpu.CompletionReleased),waiters_before=int(f.BlockWaiters),messages_before=int(f.BlockMessages),event_container_before=int(f.BlockEventContainer),state_container_before=int(f.BlockStateContainer),suspended_before=int(f.BlockSchedulerSuspended),ready_count_before=int(f.BlockReadyCount),waiters_after=int(b.ReadDoubleWord("+str(profile['deferred_queue']+0x24)+")),event_container_after=int(b.ReadDoubleWord("+str(profile['current_tcb']+40)+")),state_container_after=int(b.ReadDoubleWord("+str(profile['current_tcb']+20)+")),selections=[int(f.GetSelectedTask(i)) for i in range(int(f.SelectionCount))])\n"
    return text


def checks(actual,before,after,system_before,system_after,profile,irq,enabled=True):
    c=actual['gpu_completion'];k=actual['kernel_context']
    allowed=set(profile['allowed_kernel_words'])|{irq['last_address'],irq['count_address']}
    changes=[0x20000000+n for n in range(0,len(before),4) if before[n:n+4]!=after[n:n+4]]
    bounded=all(a in allowed or profile['task_low']<=a<a+4<=profile['task_high'] or profile['handler_low']<=a<a+4<=profile['handler_high'] for a in changes)
    expected_entries=int(enabled)
    system_bounded=all(any(r['low']<=0x20080000+n<0x20080000+n+4<=r['high'] for r in profile.get('extra_stacks',[])) for n in range(0,len(system_before),4) if system_before[n:n+4]!=system_after[n:n+4])
    if profile.get('deferred_completion') and profile['boundary_control']:
        d=actual['deferred_completion']
        return dict(kernel_sram_writes_bounded=bounded,system_sram_unchanged=system_before==system_after,
                    real_wait_boundary=actual['boundary']=='semaphore-blocked' and actual['violations']==0 and d['waiters_before']==d['waiters_after']==1 and d['event_container_after']==profile['deferred_queue']+0x24,
                    completion_withheld=not d['released'] and not d['gpu_released'] and c['irq_entries']==c['clid_reads']==c['acks']==0 and c['last_id']==0xffffffff and c['messages']==0,
                    wait_did_not_return=actual['live_phases'][5]['marker']==6 and actual['live_phases'][6]['marker']==0)
    result=dict(kernel_sram_writes_bounded=bounded,system_sram_unchanged=system_before==system_after,
                guest_msr_bootstrap=k['bootstrap']==[profile['psp'],profile['msp'],6,profile['stack_limits']['psplim'],profile['stack_limits']['msplim'],profile['psp']],
                psp_stack_restored=actual['registers'][13]==profile['psp'] and k['other_sp']==profile['msp'] and k['control']&2!=0 and k['process_stack_selected'],
                actual_thread_resume=actual['boundary']=='return' and actual['violations']==0 and k['ipsr']==0,
                original_irq_path=c['irq_entries']==expected_entries and c['clid_reads']==2*expected_entries and c['acks']==expected_entries,
                original_pendsv_selector_return=c['pendsv_entries']==k['selector_entries']==k['port_returns']==expected_entries,
                original_lowest_pendsv_priority=k['pendsv_priority']>k['gpu_priority'] and k['exception_return']&0xc==0xc,
                same_task_selected=not enabled or k['selected_tcb']==k['current_tcb']==profile['current_tcb'],
                original_port_saved_stack=not enabled or profile['task_low']<=k['saved_sp']==k['stored_sp']<profile['psp'],
                original_completed_wait_returned=enabled and actual['live_phases'][6]['marker']==7 and k['phase_returns'][6]==0 and actual['list_id']==0xffffffff,
                original_completion_publication=c['last_id']==8 and c['messages']==1 and not c['line'])
    if profile.get('deferred_completion'):
        d=actual['deferred_completion']
        result.pop('system_sram_unchanged');result['system_sram_changes_bounded']=system_bounded
        result['original_pendsv_selector_return']=1<=c['pendsv_entries']==k['selector_entries']==k['port_returns']<=3
        result['original_completion_publication']=c['last_id']==8 and c['messages']==0 and not c['line']
        result['real_wait_then_wake']=d['released'] and d['gpu_released'] and d['waiters_before']==1 and d['messages_before']==0 and d['event_container_before']==profile['deferred_queue']+0x24 and d['state_container_before']==profile['deferred_wait_list'] and d['suspended_before']==d['ready_count_before']==0 and d['waiters_after']==d['event_container_after']==0 and d['state_container_after']==profile['deferred_ready_list']
        result['original_task_handoff_and_reselection']=d['selections']==profile['expected_selections']
    return result
