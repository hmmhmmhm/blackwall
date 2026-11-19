"""Audit saved original-ARM A/B runs; do not execute or rebuild firmware."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics


OLD_OBSERVER='cbb91e4a0a779a39ce0c185e3bc9a842a770aea3b838001dedc2cfd12df8aaef'
NEW_OBSERVER='a9fc473f2e80239a81dad57642660070ac815c458c3cf87d0b7188d84477ae0b'
FROZEN_CORE='0a8386c96f11c1c2949bce8f2e6b3a8cc119dad84a90d9cfc7c9b37c95b741f9'
ORIGINAL_MAIN='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a'


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text())


def logged(cap,label):
    rows=[json.loads(line[len(label)+1:]) for line in (cap/'renode.log').read_text().splitlines() if line.startswith(label+' ')]
    if len(rows)!=1:raise ValueError('Missing or duplicated original report: '+label)
    return rows[0]


def validate(cap):
    pins=read(cap/'capture-files.json')['files']
    for name,digest in pins.items():
        p=cap/name
        if not p.resolve().is_relative_to(cap.resolve()) or sha(p.read_bytes())!=digest:
            raise ValueError('Changed capture: '+str(p))
    inputs=read(cap/'connection-inputs.json')
    if not set(inputs).issubset(pins) or any(sha((cap/n).read_bytes())!=d for n,d in inputs.items()):
        raise ValueError('Unpinned execution input')


def observer(model):
    point=model.index('    public sealed class BlackwallExecutionObserver')
    begin=model.rfind('namespace Antmicro.Renode.Peripherals.Miscellaneous',0,point)
    end=model.find('\nnamespace ',point)
    if end<0:end=len(model)
    block=model[begin:end].rstrip()
    return block+'\n',model[:begin]+model[begin+len(block):]


def source_clock_contract(s):
    source=(s/'gaf-frozen-core-research-01/frozen/tools/renode-gaf-frozen-core.cs').read_text()
    if sha(source.encode())!=FROZEN_CORE:raise ValueError('Changed frozen engine contract')
    for name in ('RequestedAt','TriggeredAt'):
        lines=[line for line in source.splitlines() if re.search(r'\b'+name+r'\b',line)]
        if len(lines)!=3 or not any(name+'=Now()' in line for line in lines) or not any('public ulong '+name+' ' in line for line in lines):
            raise ValueError('Diagnostic clock acquired another consumer')
    return source


def verify_pair(s,number,fragment):
    root=s/('observer-suspension-native-'+str(number).zfill(2));full=root/'full';scoped=root/'scoped'
    for cap in (full,scoped):validate(cap)
    before,body_a=observer((full/'strict.cs').read_text());after,body_b=observer((scoped/'strict.cs').read_text())
    a=read(full/'exports/frozen-core.json');b=read(scoped/'exports/frozen-core.json')
    pa=read(full/'connection-profile.json');pb=read(scoped/'connection-profile.json')
    fa=read(full/'exports/fixed-boundary.json');fb=read(scoped/'exports/fixed-boundary.json')
    points=b.pop('suspended_startup_observer_points')
    aa=read(full/'exports/frozen-core.json');bb=read(scoped/'exports/frozen-core.json')
    clocks=[]
    for name in ('requested_ticks','triggered_ticks'):
        av=a['gaf']['on_demand'][name];bv=b['gaf']['on_demand'][name]
        clocks.append(dict(field=name,full=av,scoped=bv,delta=bv-av))
        b['gaf']['on_demand'][name]=av
    files=('main.bin','board.repl','sram-fill.bin','itcm-fill.bin','run.py','activation.cs','failure-observer.cs',
           'exports/sram-full.bin','exports/connected-sram.bin','exports/connection-sram.bin','exports/frozen-core-sram.bin')
    checks=dict(
        capture_original=sha((full/'main.bin').read_bytes())==ORIGINAL_MAIN,
        only_observer_component=body_a==body_b and sha(before.encode())==OLD_OBSERVER and sha(after.encode())==NEW_OBSERVER,
        frozen_engine_same=all((cap/'strict.cs').read_text().count(fragment)==1 for cap in (full,scoped)),
        inputs_and_entire_sram_exact=all((full/n).read_bytes()==(scoped/n).read_bytes() for n in files),
        core_reports_match_logs=all(read(cap/'exports/frozen-core.json')==logged(cap,'BLACKWALL_GAF_FROZEN_CORE') for cap in (full,scoped)),
        att_reports_match_logs=all(read(cap/'exports/connection.json')==logged(cap,'BLACKWALL_RUNTIME_CONNECTION') for cap in (full,scoped)),
        initial_att_report_values_exact=read(full/'exports/connection.json')==read(scoped/'exports/connection.json'),
        general_registers_exact=fa['registers']==fb['registers'] and len(fa['registers'])==16,
        instruction_count_exact=fa['instructions']==fb['instructions'],
        same_fixed_virtual_interval=fa['start_ticks']==fb['start_ticks'] and fa['end_ticks']==fb['end_ticks']
            and fa['end_ticks']-fa['start_ticks']==500000000 and fa['requested_ms']==fb['requested_ms']==500,
        boundary_matches_core=fa['start_ticks']==aa['start_ticks'] and fa['end_ticks']==aa['virtual_ticks'] and fa['registers'][15]==aa['pc']
            and fb['start_ticks']==bb['start_ticks'] and fb['end_ticks']==bb['virtual_ticks'] and fb['registers'][15]==bb['pc'],
        diagnostic_clock_difference_classified=all(c['delta']==-100 for c in clocks),
        other_runtime_values_exact=a==b,
        three_owned_points=points==[dict(address=5775828,hits=1136,label='iom7-address'),
                                   dict(address=5776212,hits=876,label='iom7-fifo'),
                                   dict(address=5776236,hits=875,label='iom7-command')],
        profile_explicit=not pa.get('suspended_startup_observer_labels') and pb['suspended_startup_observer_labels']==[p['label'] for p in points],
        memory_model_hashes=pa['model_sha256']==sha((full/'strict.cs').read_bytes()) and pb['model_sha256']==sha((scoped/'strict.cs').read_bytes()),
        valid_busy_scenario=a['busy_reads']==362 and a['requests']==a['triggers']==1 and a['phase']=='pending'
            and a['ram_reads']==a['ram_written_bytes']==a['completed_calculations']==0 and not a['calculation_supported'],
        no_guard_or_architectural_fault=not any(g['accesses'] for g in a['guards']) and a['cfsr']==a['hfsr']==a['memory_violations']==0,
        no_timeout_success_claim=not a['rows'] and not a['observer_overflow'],
    )
    if not all(checks.values()):raise ValueError(dict(pair=number,failed=[k for k,v in checks.items() if not v]))
    runs=read(s/'observer-suspension-research-01'/('native-pair-runs-'+str(number).zfill(2)+'.json'))
    if [r['profile'] for r in runs]!=['full','scoped'] or any(r['phase_wall_seconds']!=f['wall_seconds'] for r,f in zip(runs,(fa,fb))):
        raise ValueError('Timing record differs from target result')
    if any(r['total_wall_seconds']<r['phase_wall_seconds'] or r['phase_wall_seconds']<=0 for r in runs):
        raise ValueError('Impossible recorded run duration')
    return dict(pair=number,passed=True,checks=checks,runs=runs,diagnostic_clock_differences=clocks,
                raw_runtime_values_exact=aa==bb,general_registers_verified=True,special_registers_verified=False,
                entire_sram_exact=True,fixed_scenario_only=True,full_boot_complete=False)


def verify(s):
    fragment=source_clock_contract(s)
    rows=[verify_pair(s,n,fragment) for n in range(2,7)]
    summary={}
    for key in ('phase_wall_seconds','total_wall_seconds'):
        values={mode:[next(r[key] for r in pair['runs'] if r['profile']==mode) for pair in rows] for mode in ('full','scoped')}
        summary[key]={mode:dict(n=len(v),median=statistics.median(v),minimum=min(v),maximum=max(v),samples=v) for mode,v in values.items()}
        summary[key]['median_ratio']=statistics.median(values['full'])/statistics.median(values['scoped'])
    return dict(passed=True,pairs=rows,summary=summary,alternating_order=True,profiler_enabled=False,
                input_profile='stock24 frozen-core failure; fixed500ms after ATT; CPU1/memory512MiB',
                raw_runtime_reports_equal=False,diagnostic_clock_delta_nanoseconds=-100,
                original_arm_or_protection_modified=False,default_observation_profile_changed=False,
                all_firmware_or_input_equivalence_verified=False,full_boot_complete=False,hardware_accessed=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior audit')
    a.output.mkdir(mode=0o700,parents=True);report=verify(a.simulator)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,pairs=len(report['pairs']),summary=report['summary'])))


if __name__=='__main__':main()
