"""Audit saved M55 port save/select/restore and explicit PSP caller resumption."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Preserve prior audits')
    s=args.simulator;checks=[];pins={};results=[]
    def check(name, value):
        checks.append(dict(name=name,passed=bool(value)))
        if not value:raise ValueError(name)
    paths=[s/'nema-native-kernel-final-01/stock24',s/'nema-native-kernel-final-peers-01/stock23',s/'nema-native-kernel-final-peers-01/cfw']
    hashes=['df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a',
            'fffbf74b3439bf0e4752fb620a7990d0a133898c54f6fb08005ea6b7029655c5',
            '4118af85ebb8e634493a61a3ce4a62ae37451e17cea6d0b8b08465f29538dd8f']
    for folder,raw_hash in zip(paths,hashes):
        case=folder.name;r=json.loads((folder/'report.json').read_text());a=r['actual'];k=a['kernel_context'];p=json.loads((folder/'kernel-profile.json').read_text());irq=json.loads((folder/'irq-profile.json').read_text())
        check(case+'-passed',r['passed'] and all(r['checks'].values()))
        check(case+'-main-pin',sha(folder/'main.bin')==raw_hash)
        for name,digest in r['input_hashes'].items():check(case+'-input-'+name,sha(folder/name)==digest)
        log=(folder/'renode.log').read_text();native=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_SUBMIT_M55 ')]
        check(case+'-native-log',native==[a] and 'Unhandled exception' not in log)
        source=Path(p['source']);full=(source/'exports/sram-full.bin').read_bytes()
        check(case+'-source-report',sha(source/'report.json')==p['source_report_sha256'])
        for export in p['source_memory_exports']:check(case+'-source-export-'+export['name'],sha(source/'exports'/export['name'])==export['sha256'])
        low=(folder/'sram.bin').read_bytes();system=(folder/'system-sram.bin').read_bytes();prepared=bytearray(full)
        for address,length in [(p['ring_table_address'],20),(p['diagnostic_nema_context_slot'],4)]:
            offset=address-0x20000000;prepared[offset:offset+length]=low[offset:offset+length]
        check(case+'-only-declared-fixture-overlays',bytes(prepared)==low+system and hashlib.sha256(prepared).hexdigest()==p['prepared_ram_sha256'])
        check(case+'-diagnostic-context-pointer',struct.unpack_from('<I',low,p['diagnostic_nema_context_slot']-0x20000000)[0]==0x21001000)
        before_work=(folder/'work.bin').read_bytes();work=(folder/'result/final-work.bin').read_bytes();after=(folder/'result/final-sram.bin').read_bytes()
        check(case+'-output-pins',hashlib.sha256(work).hexdigest()==r['final_work_sha256'] and hashlib.sha256(after).hexdigest()==r['final_sram_sha256'])
        check(case+'-system-sram-unchanged',(folder/'result/final-system-sram.bin').read_bytes()==system)
        allowed=set(p['allowed_kernel_words'])|{irq['last_address'],irq['count_address']}
        changes=[0x20000000+n for n in range(0,len(low),4) if low[n:n+4]!=after[n:n+4]]
        check(case+'-bounded-sram-changes',all(address in allowed or p['task_low']<=address<address+4<=p['task_high'] or p['handler_low']<=address<address+4<=p['handler_high'] for address in changes))
        check(case+'-stack-canary-preserved',low[p['task_low']-0x20000000-16:p['task_low']-0x20000000]==after[p['task_low']-0x20000000-16:p['task_low']-0x20000000])
        check(case+'-real-msr-bootstrap',k['bootstrap']==[p['psp'],p['msp'],6,p['stack_limits']['psplim'],p['stack_limits']['msplim'],p['psp']])
        check(case+'-irq-and-pendsv',a['gpu_completion']['irq_entries']==a['gpu_completion']['pendsv_entries']==k['selector_entries']==k['port_returns']==1)
        check(case+'-thread-psp-exception-return',k['exception_return']&0xc==0xc and k['exception_return']&0x10==0 and k['pendsv_priority']>k['gpu_priority'])
        check(case+'-source-priority-initializer',(folder/'main.bin').read_bytes()[p['original_priority_initializer']['pc']-0x438000:p['original_priority_initializer']['pc']-0x438000+18].hex()==p['original_priority_initializer']['bytes'])
        check(case+'-same-original-task',k['selected_tcb']==k['current_tcb']==p['current_tcb'])
        check(case+'-port-saved-tcb-stack',p['task_low']<=k['saved_sp']==k['stored_sp']<p['psp'] and struct.unpack_from('<I',after,p['current_tcb']-0x20000000)[0]==k['stored_sp'])
        check(case+'-actual-caller-resumed',a['boundary']=='return' and a['violations']==a['cfsr']==a['hfsr']==0 and k['ipsr']==0 and k['process_stack_selected'])
        check(case+'-stack-banks-restored',a['registers'][13]==p['psp'] and k['other_sp']==p['msp'])
        check(case+'-seven-original-calls-returned',[v['marker'] for v in a['live_phases']]==list(range(1,8)) and all(v['sp']==p['psp'] for v in a['live_phases']))
        expected_saved=[json.loads((folder/'draw-snapshot.json').read_text())['registers']['R'+str(n)] for n in range(4,12)]
        check(case+'-callee-registers-preserved',all(v['saved']==expected_saved for v in a['live_phases']))
        check(case+'-completed-wait-return',k['phase_returns'][6]==0 and a['list_id']==0xffffffff)
        check(case+'-original-publication',a['gpu_completion']['last_id']==8 and a['gpu_completion']['messages']==1 and a['gpu_completion']['clid_reads']==2 and a['gpu_completion']['acks']==1 and not a['gpu_completion']['line'])
        check(case+'-real-command-generation',before_work[0x4000:0x5000]==b'\xa5'*4096 and work[0x4000:0x40a8]!=before_work[0x4000:0x40a8])
        check(case+'-prior-verified-pixels',work[0xa000:0xa800]==(s/'nema-live-draw-framebuffer-01'/case/'result/final-work.bin').read_bytes()[0xa000:0xa800])
        check(case+'-scope',p['complete_machine_restore'] is False and p['synthetic_caller'] and r['full_main_rendered'] is False and r['hardware_accessed'] is False)
        pins[str(folder)]={name:sha(folder/name) for name in ['report.json','renode.log','kernel-profile.json','result/final-sram.bin','result/final-system-sram.bin','result/final-work.bin']}
        results.append(dict(case=case,exception_return=k['exception_return'],saved_sp=k['saved_sp'],current_tcb=k['current_tcb'],frame_sha256=hashlib.sha256(work[0xa000:0xa800]).hexdigest()))
    for name,folder in [('missing-context',s/'nema-kernel-missing-context-control-01/stock24'),('default',s/'nema-kernel-default-regression-01/stock24')]:
        r=json.loads((folder/'report.json').read_text());a=r['actual'];check(name+'-passed',r['passed'] and all(r['checks'].values()))
        for file,digest in r['input_hashes'].items():check(name+'-input-'+file,sha(folder/file)==digest)
        if name=='missing-context':check(name+'-stop-retained',a['boundary']=='rtos-context-required' and a['live_phases'][5]['marker']==0)
        else:
            check(name+'-caller-byte-identical',(folder/'harness.bin').read_bytes()==(s/'nema-live-draw-framebuffer-01/stock24/harness.bin').read_bytes())
            check(name+'-work-exact',(folder/'result/final-work.bin').read_bytes()==(s/'nema-live-draw-framebuffer-01/stock24/result/final-work.bin').read_bytes())
        pins[str(folder)]={file:sha(folder/file) for file in ['report.json','renode.log']}
    for root,case in [('nema-native-kernel-resume-04','stock24'),('nema-native-kernel-peers-01','stock23'),('nema-native-kernel-peers-01','cfw')]:
        folder=s/root/case;r=json.loads((folder/'report.json').read_text())
        check('earlier-nested-priority-not-final-'+case,r['passed'] and r['actual']['kernel_context']['exception_return']&8==0)
        pins[str(folder)]={file:sha(folder/file) for file in ['report.json','renode.log']}
    for root,label in [('m55-host-control-sp-probe-02','CONTROL_SP_PROBE'),('m55-host-control-guard-01','CONTROL_GUARD')]:
        folder=s/root;log=(folder/'renode.log').read_text();rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(label+' ')]
        check(root+'-unique',len(rows)==1)
        if label=='CONTROL_SP_PROBE':check(root+'-host-field-not-bank',rows[0][1]['control']==6 and rows[0][1]['process_stack_selected'] is False)
        else:check(root+'-blocked-before-change',rows[0]==dict(blocked=True,control=4,process_stack_selected=False))
        pins[str(folder)]={file:sha(folder/file) for file in ['query.py','fixture.cs','renode.log']}
    args.output.mkdir(parents=True,mode=0o700);(args.output/'audit.py').write_bytes(Path(__file__).read_bytes())
    report=dict(passed=True,checks=checks,cases=results,pins=pins,native_rerun=False,hardware_accessed=False,
                synthetic_caller=True,original_main_resumed=False,blocking_wait_verified=False,different_task_switch_verified=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),resumed_cases=len(results))))


if __name__=='__main__':main()
