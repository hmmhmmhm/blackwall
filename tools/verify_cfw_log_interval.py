"""Audit unchanged-run log observations, pending retry state, and a rejected observer experiment."""
import argparse,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from native_replay import FILES,parse_log,validate_assets
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from inspect_paused_sram import parse_range


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    _,raw=load_pinned_main((s/'inputs/verified-01/faceclaw-38-research-only.bin').read_bytes());_,stock=load_pinned_main((s/'inputs/verified-01/stock-2.3.0.24.bin').read_bytes())
    check('compression-logic-original-stock',raw[0x43d000-0x438000:0x43d840-0x438000]==stock[0x43d000-0x438000:0x43d840-0x438000])
    check('async-logger-original-stock',raw[0x44b52a-0x438000:0x44b648-0x438000]==stock[0x44b52a-0x438000:0x44b648-0x438000])
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
    def ins(address):return next(md.disasm(raw[address-0x438000:address-0x438000+4],address))
    def code(address,mn,op):i=ins(address);check(hex(address),(i.mnemonic,i.op_str)==(mn,op))
    def literal(address):
        i=ins(address);m=next(x.mem for x in i.operands if x.type==ARM_OP_MEM and x.mem.base==ARM_REG_PC)
        return struct.unpack_from('<I',raw,((address+4)&~3)+m.disp-0x438000)[0]
    logger_name=literal(0x44b52c);check('logger-name',raw[logger_name-0x438000:].split(b'\0',1)[0]==b'elog_async_handler_thread_handler start\n')
    code(0x44b542,'movs','r4, r0');code(0x44b554,'lsls','r0, r4, #0x1e');code(0x44b560,'bl','#0x43d534')
    code(0x44b63e,'movs','r1, #2');check('logger-event-pointer',literal(0x44b636)==literal(0x44b532)==0x200778a8)
    code(0x457cdc,'ldr','r4, [r4]')
    check('request-generation-address',literal(0x43d254)==0x20077684);code(0x43d25a,'adds','r5, r5, #1');code(0x43d25c,'str','r5, [r0]')
    check('completed-generation-address',literal(0x43d3aa)==0x20077688);code(0x43d3ae,'str','r4, [r0]')
    check('last-attempt-address',literal(0x43d380)==literal(0x43d4d0)==0x20077690);code(0x43d384,'bl','#0x442880');code(0x43d388,'str','r0, [r6]')
    code(0x43d398,'beq','#0x43d3c8');check('failure-counter-address',literal(0x43d3c8)==0x20078427);code(0x43d3d4,'adds','r0, r0, #1');code(0x43d3d6,'strb','r0, [r5]')
    code(0x43d4da,'movw','r0, #0x1388');code(0x43d4e0,'subs','r2, r5, r2');code(0x43d4e4,'bhs','#0x43d4fe')
    check('defer-flag-address',literal(0x43d4e8)==0x20078426);code(0x43d4ec,'strb','r2, [r3]')
    check('kernel-tick-address',literal(0x44c33a)==literal(0x44c344)==0x20077e4c)
    code(0x49a0c2,'push.w','{r2, r4, r5, r6, r7, r8, sb, lr}');code(0x49a0c6,'sub','sp, #0x18');code(0x49a0fc,'bl','#0x4986d6');code(0x49a35c,'bl','#0x49a0c2')
    check('log-file-name',raw[0x79f549-0x438000:].split(b'\0',1)[0]==b'log/compress_manager.bin')
    base_model=models(s);phase_source=Path(__file__).with_name('renode-phase-stack-observer.cs').read_bytes()
    for mode,key,count in [('independent','cfw-independent',30),('shared','cfw',0)]:
        d=s/'cfw-fs-interval-main-05'/mode;r=json.loads((d/'report.json').read_text());prior=s/'uart0-hcpa-main-02'/key;old=json.loads((prior/'report.json').read_text())
        validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(mode+'-original-main',(d/'main.bin').read_bytes()==raw)
        check(mode+'-observer-only-model',(d/'strict.cs').read_bytes()==base_model+b'\n'+phase_source)
        check(mode+'-exact-native-state',r['passed'] and parse_log((d/'renode.log').read_text())==r['observed']==old['observed'])
        check(mode+'-exact-prior-events',r['selected_observation']==old['selected_observation'])
        phase=r['phase'];check(mode+'-bounded-phase',phase['open_hits']==phase['close_hits']==1 and phase['sample_hits']==count and phase['rejected']==0 and not phase['active'])
        check(mode+'-no-extra-PC-watches',not r['extra_watchpoints'] and phase['watches']==[] and 'phase.AddWatch' not in (d/'run.py').read_text())
        for label in ['open','close']:
            x=phase[label];check(mode+'-'+label+'-thread-mode',x['active_vector']==0 and len(x['stack'])==192 and len(x['direct'])==8 and x['indirect_valid'])
            check(mode+'-'+label+'-no-pending-event-flag',x['indirect_word']==0)
        check(mode+'-request-generation',phase['open']['direct'][1:4]==[3,0,0])
        check(mode+'-completed-generation',phase['close']['direct'][1:4]==([3,3,0] if mode=='independent' else [3,0,0]))
        if mode=='independent':
            sample=phase['samples'][0];check('file-stack-thread-mode',sample['active_vector']==0)
            stack=sample['stack'];check('unique-file-open-return-anchor',stack.count(0x49a101)==1);anchor=stack.index(0x49a101)
            # Anchor the caller frame using its direct call and 24-byte local area.
            check('file-open-frame-path-and-return',stack[anchor+7]==0x79f549 and stack[anchor+14]==0x49a361)
        pdir=s/'cfw-log-paused-01'/mode;paused=json.loads((pdir/'report.json').read_text());validate_assets(pdir,json.loads((pdir/'derived-inputs.json').read_text())['derived'])
        check(mode+'-paused-exact-native',paused['passed'] and parse_log((pdir/'renode.log').read_text())==paused['observed']==old['observed'] and paused['selected_observation']==old['selected_observation'])
        check(mode+'-no-new-execution-hooks',not paused['new_execution_hooks'] and all((pdir/f).read_bytes()==(prior/f).read_bytes() for f in FILES if f!='run.py'))
        before='    e.PauseAll()\n';check(mode+'-unchanged-running-script',(pdir/'run.py').read_text().split(before)[0]==(prior/'run.py').read_text().split(before)[0])
        memory={x['label']:x for x in paused['memory']['ranges']};state=memory['log-state']['words'];flags=memory['log-flags']['words'];tick=memory['kernel-tick']['words'][0]
        check(mode+'-paused-snapshot-ranges',paused['memory']['paused'] and memory['log-state']['address']==0x20077680 and memory['log-flags']['address']==0x20078424 and memory['kernel-tick']['address']==0x20077e4c)
        deferred=(flags[0]>>16)&255;failures=(flags[0]>>24)&255;latched=flags[1]&255
        check(mode+'-paused-state-matches-phase',state==phase['close']['direct'] and flags==r['stopped_log_flags']['words'])
        check(mode+'-retry-state',(deferred,failures,latched)==((0,0,0) if mode=='independent' else (1,1,0)))
        if mode=='shared':check('actual-shared-retry-budget-not-elapsed',state[1:3]==[3,0] and 0<tick-state[4]<5000)
        cases.append(dict(case=key,request_generation=state[1],completed_generation=state[2],last_attempt_tick=state[4],stopped_tick=tick,deferred=deferred,failed_attempts=failures,latched=latched,post_FS_read_calls=count))
    rejected=s/'cfw-fs-interval-main-03/shared';r=json.loads((rejected/'report.json').read_text());validate_assets(rejected,json.loads((rejected/'derived-inputs.json').read_text())['derived']);old=json.loads((s/'uart0-hcpa-main-02/cfw/report.json').read_text())
    check('rejected-instrumentation-not-passed',not r.get('passed',False) and (r['observed']!=old['observed'] or r['selected_observation']!=old['selected_observation']))
    check('rejected-extra-watches-preserved','phase.AddWatch' in (rejected/'run.py').read_text() and 'cpu.ExecutedInstructions' in (rejected/'strict.cs').read_text())
    import argparse as ap
    for value in ['a:0x1ffffffc:1','a:0x20380000:1','a:0x40021008:1','a:0x20000001:1','a:0x20000000:0','a:0x20000000:257','A:0x20000000:1','a:0x20000000:-1','x']:
        try:parse_range(value)
        except ap.ArgumentTypeError:check('reject-'+value,True)
        else:raise ValueError('Unsafe paused range accepted')
    for value in ['a:0x20000000:1','b:0x2037fffc:1','log-state:0x20077680:8']:check('accept-'+value,bool(parse_range(value)))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,canonical_phase_runs=2,paused_only_runs=2,
                log_path_verified=True,pending_retry_state_verified=True,first_flush_failure_reason_verified=False,
                observer_effect_rejected=True,precise_observer_effect_cause_verified=False,
                hardware_accessed=False,boot_verified=False,display_verified=False,
                scope='Unmodified stock logger code, valid CFW call frame, and unchanged-run snapshots explain pending generation/backoff versus completed file work; earliest flush failure cause and later retry completion remain unverified')
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),cases=cases)))


if __name__=='__main__':main()
