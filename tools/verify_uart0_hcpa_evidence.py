"""Audit UART0 power success versus independent-status timeout and unchanged default."""
import argparse,json
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import parse_log,validate_assets,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from probe_uart0_hcpa_main import baseline_core


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700);checks=[];cases=[];model=models(s)
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    labels=['UART-power-enable-return','UART-power-wrapper-return','UART0-power-client-return'];trace_differences=[]
    for key in ['stock24','stock23','cfw','stock24-independent','cfw-independent','stock24-default']:
        name=key.split('-')[0];d=s/'uart0-hcpa-main-02'/key;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);obs=r['selected_observation'];default=key.endswith('-default');independent=key.endswith('-independent')
        validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(key+'-current-model',(d/'strict.cs').read_bytes()==model)
        file={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[name];_,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes())
        check(key+'-original-main',raw==(d/'main.bin').read_bytes() and r['original_main_sha256']==digest(d/'main.bin'))
        check(key+'-native-report',r['passed'] and r['observed']==v and not r['boot_verified'] and not r['display_verified'])
        for marker,expected in [('BLACKWALL_OBSERVATION',obs),('BLACKWALL_UART_HCPA',r['HCPA']),('BLACKWALL_MISSING_FONT',r['font_diagnostic'])]:
            rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(marker+' ')];check(key+'-'+marker,rows==[expected])
        check(key+'-complete-events',obs['dropped_events']==0 and obs['sequence']==len(obs['events']))
        check(key+'-two-invalid-font-headers',r['font_diagnostic']['reads']==2 and not r['font_diagnostic']['stock_font_assets'])
        prior=s/'missing-font-header-main-01'/(name+'-low');old=json.loads((prior/'report.json').read_text());core=Path(__file__).with_name('renode-strict-mmio.cs').read_bytes();original_core=baseline_core(core.decode()).encode();frozen=(prior/'strict.cs').read_bytes()
        check(key+'-only-reviewed-core-changes',frozen.startswith(original_core) and model==core+frozen[len(original_core):])
        if key!='cfw':check(key+'-old-event-prefix',r['prior_prefix_equal'])
        else:
            # The new status hypothesis changes an observed CFW storage interval.
            # Preserve the difference; do not report whole-trace equivalence.
            new_events=[e for e in obs['events'] if e['label'] not in labels];old_events=old['selected_observation']['events']
            def partition(events):
                first=next(i for i,e in enumerate(events) if e['label']=='LittleFS-app-init-return')
                last=next(i for i,e in enumerate(events) if e['label']=='GPIO-role-sample-return')
                return events[:first+1],events[first+1:last],events[last:]
            new_parts=partition(new_events);old_parts=partition(old_events)
            def normalized(events):return [dict(e,sequence=i+1) for i,e in enumerate(events)]
            check('CFW-prefix-through-app-filesystem-return',normalized(new_parts[0])==normalized(old_parts[0]))
            check('CFW-suffix-from-GPIO-through-fonts',normalized(new_parts[2])==normalized(old_parts[2]))
            allowed={'LittleFS-read-entry','status-poll-return','wren-wrapper-return','WRDI-wrapper-return'}
            check('CFW-recorded-storage-interval-only',all(e['label'] in allowed for e in new_parts[1]+old_parts[1]) and not r['prior_prefix_equal'])
            trace_differences.append(dict(case=key,prefix_events=len(new_parts[0]),old_storage_events=len(old_parts[1]),new_storage_events=len(new_parts[1]),suffix_events=len(new_parts[2]),cause_verified=False,whole_trace_equivalent=False))
        if default:
            check('default-exact-state-and-instructions',v==old['observed'])
            check('default-exact-events',obs==old['selected_observation'])
            check('default-no-UART0',not r['HCPA']['shared'] and not r['HCPA']['UART0'] and [u['module'] for u in v['uarts']]==[1,2,3])
            continue
        check(key+'-profile',r['HCPA']['UART0'] and r['HCPA']['shared']==(not independent))
        end=next(e['sequence'] for e in obs['events'] if e['label']=='font-manager-return')
        after={label:[e for e in obs['events'] if e['label']==label and e['sequence']>end] for label in labels}
        check(key+'-UART0-post-font-points-once',all(len(x)==1 for x in after.values()))
        power=after[labels[0]][0];wrapper=after[labels[1]][0];client=after[labels[2]][0]
        check(key+'-actual-power-result',power['r0']==(4 if independent else 0))
        check(key+'-wrapper-ignores-power-status',wrapper['r0']==client['r0']==0 and power['sequence']<wrapper['sequence']<client['sequence'])
        uart=next(u for u in v['uarts'] if u['module']==0)
        check(key+'-UART0-enabled',uart['phase']=='on' and uart['request_word']==uart['status_word']==0x200 and uart['requests']==uart['responses']==1)
        check(key+'-UART0-configured',uart['reads']>0 and uart['writes']>0 and uart['control']==0x319 and uart['clock_spare_clears']==1)
        check(key+'-UART0-IRQ-gated',uart['irq_number']==15 and uart['interrupt_mask']==0 and not uart['irq_level'] and uart['irq_exception_entries']==0 and not uart['tx_bytes'])
        guards=[g for g in v['guards'] if g['accesses']];check(key+'-next-unknown-IRQ-mask',[(g['address'],g['width'],g['operation'],g['value']) for g in guards]==[(0x40039038,4,'write',0x1fd0)])
        i=next(Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS).disasm(raw[v['pc']-0x438000:v['pc']-0x438000+2],v['pc']))
        check(key+'-original-next-store',i.mnemonic=='str' and v['register_context']['r1']==0x1fd0)
        cases.append(dict(case=key,power_return=power['r0'],wrapper_return=wrapper['r0'],pc=hex(v['pc']),next_address='0x40039038',next_value='0x1fd0'))
    for name,shared in [('uart-hcpa-unit-01',True),('uart-hcpa-independent-unit-01',False)]:
        r=json.loads((s/name/'report.json').read_text());check(name,r['passed'] and r['count']==30 and r['shared']==shared and (s/name/'strict.cs').read_bytes()==model)
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,unit_checks=60,native_cases=6,trace_differences=trace_differences,
                hardware_accessed=False,boot_verified=False,display_verified=False,
                scope='Opt-in HCPA source-supported status hypothesis makes original UART0 5us power poll succeed; independent-status controls time out and wrapper ignores it; default exact state/trace unchanged. CFW storage interval differs and its cause remains unverified.')
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),native=6,CFW_trace_equivalent=False)))


if __name__=='__main__':main()
