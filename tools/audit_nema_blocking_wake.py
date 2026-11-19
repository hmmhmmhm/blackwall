"""Audit deferred diagnostic IRQ events and original waiter removal/consumption."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior audit')
    s=a.simulator;checks=[];pins={};rows=[]
    def check(name,value):
        checks.append(dict(name=name,passed=bool(value)))
        if not value:raise ValueError(name)
    captures=[(s/'nema-deferred-wake-03/stock24','wake'),(s/'nema-deferred-wake-peers-01/stock23','wake'),(s/'nema-deferred-wake-peers-01/cfw','wake'),(s/'nema-deferred-block-control-03/stock24','blocked'),(s/'nema-deferred-immediate-regression-01/stock24','immediate')]
    for folder,mode in captures:
        case=folder.name;name=mode+'-'+case;r=json.loads((folder/'report.json').read_text());actual=r['actual'];profile=json.loads((folder/'kernel-profile.json').read_text());irq=json.loads((folder/'irq-profile.json').read_text())
        check(name+'-passed',r['passed'] and all(r['checks'].values()))
        for file,digest in r['input_hashes'].items():check(name+'-input-'+file,sha(folder/file)==digest)
        log=(folder/'renode.log').read_text();records=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_SUBMIT_M55 ')]
        check(name+'-native-log',records==[actual] and 'Unhandled exception' not in log)
        check(name+'-no-fault',actual['cfsr']==actual['hfsr']==actual['violations']==0)
        check(name+'-scope',r['hardware_accessed'] is False and r['full_main_rendered'] is False and profile['complete_machine_restore'] is False)
        work=(folder/'result/final-work.bin').read_bytes();before=(folder/'work.bin').read_bytes();low=(folder/'sram.bin').read_bytes();after=(folder/'result/final-sram.bin').read_bytes();system=(folder/'system-sram.bin').read_bytes();system_after=(folder/'result/final-system-sram.bin').read_bytes()
        check(name+'-output-pins',hashlib.sha256(work).hexdigest()==r['final_work_sha256'] and hashlib.sha256(after).hexdigest()==r['final_sram_sha256'])
        check(name+'-cold-generated-commands',before[0x4000:0x5000]==b'\xa5'*4096 and work[0x4000:0x40a8]!=before[0x4000:0x40a8])
        check(name+'-original-pixels',work[0xa000:0xa800]==(s/'nema-live-draw-framebuffer-01'/case/'result/final-work.bin').read_bytes()[0xa000:0xa800])
        check(name+'-no-oracle-loaded','expected-frame' not in (folder/'probe.resc').read_text() and 'expected-frame' not in (folder/'setup.py').read_text())
        allowed=set(profile['allowed_kernel_words'])|{irq['last_address'],irq['count_address']}
        stack_ranges=[(profile['task_low'],profile['task_high']),(profile['handler_low'],profile['handler_high'])]+[(v['low'],v['high']) for v in profile.get('extra_stacks',[])]
        data,final=low+system,after+system_after
        changed=[0x20000000+n for n in range(0,len(data),4) if data[n:n+4]!=final[n:n+4]]
        check(name+'-typed-memory-bounds',all(address in allowed or any(lo<=address<address+4<=hi for lo,hi in stack_ranges) for address in changed))
        for lo,hi in [(profile['task_low'],profile['task_high'])]+[(v['low'],v['high']) for v in profile.get('extra_stacks',[])]:
            start=lo-0x20000000;check(name+'-stack-canary-'+hex(lo),data[start-16:start]==final[start-16:start])
        g=actual['gpu_completion'];k=actual['kernel_context']
        if mode=='immediate':
            check(name+'-old-fast-path',not r['deferred_completion'] and g['messages']==1 and k['selector_entries']==1 and actual['live_phases'][6]['marker']==7)
        else:
            d=actual['deferred_completion'];transaction=Path(profile['blocking_transaction']);tx=json.loads(transaction.read_text())
            check(name+'-transaction-pin',sha(transaction)==profile['blocking_transaction_sha256'] and tx['observer_on_off_equal'])
            check(name+'-real-wait-witness',d['waiters_before']==1 and d['messages_before']==d['suspended_before']==d['ready_count_before']==0 and d['event_container_before']==profile['deferred_queue']+0x24 and d['state_container_before']==profile['deferred_wait_list'])
            check(name+'-deferred-profile','deferCompletionIrq: true' in (folder/'board.repl').read_text() and 'ConfigureDeferredCompletion' in (folder/'setup.py').read_text())
            if mode=='blocked':
                check(name+'-no-release',not d['released'] and not d['gpu_released'] and g['irq_entries']==g['clid_reads']==g['acks']==0 and not g['line'])
                check(name+'-still-blocked',actual['boundary']=='semaphore-blocked' and d['waiters_after']==1 and g['last_id']==0xffffffff and g['messages']==0 and actual['live_phases'][6]['marker']==0 and k['selector_entries']==k['port_returns']==0)
            else:
                check(name+'-real-nvic-completion',d['released'] and d['gpu_released'] and g['irq_entries']==g['acks']==1 and g['clid_reads']==2 and g['entry_xpsr']&0x1ff==44)
                check(name+'-waiter-removed-and-consumed',d['waiters_after']==d['event_container_after']==g['messages']==0 and d['state_container_after']==profile['deferred_ready_list'] and g['last_id']==8 and not g['line'])
                check(name+'-two-source-selections',d['selections']==profile['expected_selections'] and d['selections'][0]!=d['selections'][1]==profile['current_tcb'] and g['pendsv_entries']==k['selector_entries']==k['port_returns']==2)
                check(name+'-thread-return',actual['boundary']=='return' and k['ipsr']==0 and k['process_stack_selected'] and k['exception_return']&0xc==0xc and actual['registers'][13]==profile['psp'] and k['other_sp']==profile['msp'])
                check(name+'-seven-return-markers',[v['marker'] for v in actual['live_phases']]==list(range(1,8)) and all(v['sp']==profile['psp'] for v in actual['live_phases']))
                check(name+'-original-wait-return',k['phase_returns'][6]==0 and actual['list_id']==0xffffffff)
                check(name+'-source-take-give-after-handoff',tx['blocked']['waiters']==1 and tx['awakened']['waiters']==0 and tx['awakened']['higher_woken']==1 and tx['first_selector']['current_after']==d['selections'][0] and tx['second_selector']['current_after']==d['selections'][1])
            pins[str(transaction)]={n:sha(transaction.parent/n) for n in ['report.json','blocked-sram.bin','awakened-sram.bin']}
        pins[str(folder)]={file:sha(folder/file) for file in ['report.json','renode.log','kernel-profile.json','result/final-work.bin','result/final-sram.bin','result/final-system-sram.bin']}
        rows.append(dict(case=case,mode=mode,passed=True))
    a.output.mkdir(parents=True);(a.output/'audit.py').write_bytes(Path(__file__).read_bytes())
    result=dict(passed=True,checks=checks,captures=rows,pins=pins,native_rerun=False,hardware_accessed=False,
                blocking_wait_verified=True,manager_business_code_verified=False,original_main_resumed=False,
                completion_timing='Explicit diagnostic event at original PendSV after verified waiter enrollment, not measured hardware time')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,checks=len(checks),captures=len(rows))))


if __name__=='__main__':main()
