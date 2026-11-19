"""Audit offline boot restoration bytes, overwritten ARM execution and fresh boot artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from run_original_boot_screen import PRIVATE,EXPORTS,assess as assess_boot,valid_frame,logged_json,same,validate_runtime
from check_virtual_restore import assess as assess_restore


def run(experiment,output):
    experiment,output=map(lambda p:Path(p).resolve(),(experiment,output))
    if not experiment.is_relative_to(PRIVATE) or not output.is_relative_to(PRIVATE) or output.exists():raise ValueError('Private experiment and fresh output required')
    root=PRIVATE/'simulator';read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest();checks={}
    manifest=read(experiment/'manifest.json');initial=Path(manifest['initial_source']).read_bytes();backup=(experiment/'virtual-original-mram.bin').read_bytes()
    checks['known_virtual_inventory']=len(initial)==len(backup)==0x400000 and sha(initial)==manifest['initial_sha256'] and sha(backup)==manifest['virtual_original_sha256'] and initial[:0x10000]==backup[:0x10000] and initial[0x37000:]==backup[0x37000:]
    checks['original_stock_boot']=sha(backup[0x10000:0x10000+149773])=='ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665'
    checks['explicit_virtual_original_tail']=backup[0x10000+149773:0x37000]==bytes(9971)
    checks['original_stock_main']=sha(backup[0x38000:0x38000+3700068])=='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a'
    slices={'boot':(0x10000,149773),'boot-tail':(0x10000+149773,9971),'main':(0x38000,3700068)}
    stock={k:sha(backup[a:a+n]) for k,(a,n) in slices.items()};extents={k:dict(space='mram',address=0x400000+a,bytes=n) for k,(a,n) in slices.items()}
    for name,destination,length in [('prefix',0x410000,149776),('whole',0x410000,159744),('tail-after-prefix',0x434910,9968)]:
        p=experiment/name;before=(experiment/'prefix/native/exports/final-mram.bin').read_bytes() if name=='tail-after-prefix' else initial
        native=p/'native';log=(native/'renode.log').read_text();a=logged_json(log,'BLACKWALL_RECOVERY_WRITER ');d=logged_json(log,'BLACKWALL_RECOVERY_DIAGNOSTIC ');r=read(native/'report.json');final=(native/'exports/final-mram.bin').read_bytes();written=a['programmed_bytes'];data=backup[destination-0x400000:destination-0x400000+length]
        expected=bytearray(before);expected[destination-0x400000:destination-0x400000+written]=data[:written]
        checks[name+'_actual_mram_prefix']=0<=written<=length and written%4==0 and final==expected and sha(final)==r['final_mram_sha256']
        checks[name+'_arm_writer']=a['context_entries']==a['writer_entries']==1 and a['rom_calls']==a['stock_mram_entries']==a['code_invalidations'] and a['rom_calls']==(written+255)//256
        checks[name+'_pinned_payload']=read(p/'capture/snapshot.json')['worker']['uploaded_code_sha256']=='9abc30c98bec432981d0c40ded3159085f273700e6c3b54716e37360df8cb8b2'
        checks[name+'_fixed_model']=sha((native/'fixture.cs').read_bytes())==r['sha256']['fixture.cs']
        checks[name+'_owned_writer_removed']=read(native/'renode.process.json')['status']=='removed'
        actual_parts={k:sha(final[a:a+n]) for k,(a,n) in slices.items()};restored=assess_restore(stock,actual_parts,['boot','boot-tail','main'],True,stock_extents=extents,modified_regions=[dict(space='mram',address=0x410000,bytes=159744)])
        checks[name+'_not_full_stock']=restored['full_stock_bytes'] is False and final!=backup and actual_parts['boot']==stock['boot'] and actual_parts['main']==stock['main']
        if name=='prefix':checks[name+'_normal_completion']=written==149776 and a['result_seen'] and a['context_returns']==1 and a['violations']==0 and d['cfsr']==d['hfsr']==0 and r['passed']
        else:
            pc=a['first_changed_code_pc'];index=pc-0x400000
            checks[name+'_overwritten_fetch']=pc==0x434be4 and a['changed_code_fetches']>0 and a['original_code_word']==int.from_bytes(before[index:index+2],'little') and a['updated_code_word']==int.from_bytes(final[index:index+2],'little')==0
            checks[name+'_failed_protocol']=not a['result_seen'] and a['context_returns']==0 and not r['passed'] and d['cfsr']==0x20000 and d['hfsr']==0x40000000
        cold=p/'cold-boot';cm=read(cold/'manifest.json');cr=read(cold/'report.json');validate_runtime((cold/'run.py').read_text())
        checks[name+'_cold_lineage']=cm['persistent_input_sha256']==sha(final) and cm['boot_state']=='stock-prefix' and cm['boot_executable_bytes']==149773 and cm['writer_completed']==r['passed']
        checks[name+'_cold_source_pins']=all(sha((cold/n).read_bytes())==h for n,h in cm['components'].items() if n not in ('boot-region.bin','main-region.bin'))
        checks[name+'_cold_owned_removed']=read(cold/'native.process.json')['status']=='removed'
        checks[name+'_cold_input_windows']=cm['components']['boot-region.bin']==sha(final[0x10000:0x38000]) and cm['components']['main-region.bin']==sha(final[0x38000:0x3f8000])
        if name!='tail-after-prefix':
            e=cold/'exports';v={k:read(e/n) for k,n in EXPORTS.items()};removed={x['name']:x for x in cr['cleanup']}
            v['image_equal']=removed['exports/guest-boot.bin']['sha256']==stock['boot'] and removed['exports/guest-main.bin']['sha256']==stock['main'];v['cadence_equal']=removed['exports/cadence-before-sram.bin']['sha256']==removed['exports/cadence-after-sram.bin']['sha256']
            raw=(e/'complete-screen.bin').read_bytes();v['frame_equal']=valid_frame(v['screen'],raw,(e/'main-state-sram.bin').read_bytes())
            checks.update({name+'_cold_'+k:val for k,val in assess_boot(v).items()})
            checks[name+'_native_records']=all(same(logged_json((cold/'native.log').read_text(),tag),v[k]) for k,tag in [('native','BLACKWALL_BOOT_RESET '),('wire','BLACKWALL_BOOT_WIRE '),('screen','BLACKWALL_BOOT_SCREEN '),('delegated','BLACKWALL_DELEGATED_GUARDS ')])
            checks[name+'_actual_frame']=sha(raw)=='81200ab102c507de6a5853a33086958d16bcb93168ff631ee76b6c8c391adba2'
        else:
            a=read(cold/'exports/result.json');pnts={x['label']:x for x in a['points']}
            checks[name+'_cold_native_entry']=a['cfsr']==a['hfsr']==a['policy']==a['system_control_violations']==0 and all(x['accesses']==0 for x in a['guards']) and pnts['boot-reset']['first']<pnts['stock-handoff']['first']<pnts['main-reset']['first'] and pnts['main-reset']['hits']>0
    cache=root/'mram-code-coherency-bw567-03';cs=read(cache/'report.json')['cases']
    checks['coherency_three_controls']=len(cs)==3 and all(r['first']==18 and r['callee']==0x47702034 and r['cfsr']==r['hfsr']==0 for r in cs) and [r['second'] for r in cs]==[18,18,52]
    checks['coherency_same_model']=len({sha((cache/n/'model.cs').read_bytes()) for n in ('default','drain-only','ordered-range')})==1
    policy=root/'boot-restore-policy-bw567-02';checks['scope_component60']=read(policy/'report.json')['passed'] and all(s in (policy/'native.log').read_text() for s in ('BLACKWALL_MRAM_BOUNDARY 23','BLACKWALL_MRAM_FULL_SCOPE 11','BLACKWALL_MRAM_BOOT_SCOPE 18','BLACKWALL_MRAM_ATOMIC 8'))
    checks['same_tested_model']=sha((experiment/'prefix/native/fixture.cs').read_bytes())==read(policy/'report.json')['model_sha256']
    result=dict(passed=all(checks.values()),checks=checks,hardware_accessed=False,full_stock_restoration_verified=False,scope='Independent raw MRAM/ARM fault/coherency/fresh boot audit; functional coherent IO, not physical I-cache/ROM')
    output.mkdir(mode=0o700,parents=True);shutil.copy2(__file__,output/'audit-source.py');result['frozen_support_sha256']={}
    for name in ('run_original_boot_screen.py','run_renode_m55_probe.py','check_virtual_restore.py'):
        source=Path(__file__).resolve().parent/name;shutil.copy2(source,output/name);result['frozen_support_sha256'][name]=sha(source.read_bytes())
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])),flush=True)
    if not result['passed']:raise ValueError('Boot restoration audit failed')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('experiment',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.experiment,a.output)
if __name__=='__main__':main()
