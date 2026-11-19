"""Compare pinned original mains with explicit RTC request-latch assumptions; no device access."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
from native_replay import preflight, parse_log, boundary_state, digest
from pinned_main import load_pinned_main
from verify_iom_main import arguments

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('profile',type=Path);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
    if o.exists():raise ValueError('Use a new evidence directory')
    profile=json.loads(a.profile.read_text());preflight(profile,s/'iom-startup-main-comparison-01')
    o.mkdir(mode=0o700);(o/'baseline-profile.json').write_bytes(a.profile.read_bytes())
    cases={c['name']:c for c in profile['cases']}
    plan=[('stock24-xt','stock24','stock-2.4.0.24.bin','xt'),('stock23-xt','stock23','stock-2.3.0.24.bin','xt'),('cfw-xt','cfw','faceclaw-38-research-only.bin','xt'),('stock24-lfrc','stock24','stock-2.4.0.24.bin','lfrc'),('stock24-default','stock24','stock-2.4.0.24.bin',None)]
    rows=[]
    for name,base,file,initial in plan:
        case=cases[base];h=case['selected_hypotheses'];run=o/name
        options=arguments(h)
        options+=['--wall-run-seconds','15','--iom-modules',','.join(map(str,h['iom_modules'])),'--iom2-model',h['iom2_model'],'--iom2-off-response',h['iom2_off_response'],'--iom-cq-input-levels',str(h['iom_cq_input_levels'])]
        if initial is not None:options+=['--rtc-osel-storage',initial]
        bundle=s/'inputs/verified-01'/file
        cmd=[sys.executable,str(ROOT/'tools/run_renode_main_probe.py'),str(bundle),str(run),*options]
        launch=subprocess.run(cmd,capture_output=True,text=True)
        (o/(name+'-launcher.json')).write_text(json.dumps(dict(command=cmd,returncode=launch.returncode,stdout=launch.stdout,stderr=launch.stderr),indent=2)+'\n')
        if launch.returncode:raise ValueError('Original main launch failed: '+name)
        r=json.loads((run/'report.json').read_text());v=parse_log((run/'renode.log').read_text())
        if r['observed']!=v:raise ValueError('Saved native report differs')
        _,raw=load_pinned_main(bundle.read_bytes())
        if raw!=(run/'main.bin').read_bytes() or hashlib.sha256(raw).hexdigest()!=r['raw_main_sha256']:raise ValueError('Original main differs')
        if any(r[k] for k in ('boot_verified','hardware_validated','installable')):raise ValueError('Unproven completion claim')
        guards=[g for g in v['guards'] if g['accesses']]
        rtc=v['rtc_osel_storage']
        if initial is None:
            if rtc is not None or boundary_state(v)!=case['expected_boundary']:raise ValueError('Default strict behavior changed')
        else:
            if rtc['initial_request']!=(0 if initial=='xt' else 128) or rtc['request_word']!=0 or rtc['reads']<1 or rtc['writes']<1:raise ValueError('RTC request latch not exercised as expected')
            if rtc['effective_source'] is not None or any(rtc[k] for k in ('oscillator_implemented','rtc_time_implemented','silicon_revision_effects_implemented','hardware_verified')):raise ValueError('Unproven oscillator behavior claim')
            if guards[0]['address']==0x4000400c:raise ValueError('RTC model did not advance original execution')
        row=dict(name=name,pc=hex(v['pc']),rtc=rtc,guards=guards,uart=[dict(module=u['module'],writes=u['writes'],tx_bytes=len(u['tx_bytes']),isr_entries=u['irq_exception_entries']) for u in v['uarts']],ioms=[dict(module=i['module'],commands=i['commands'],cq_pairs=i['cq']['pairs']) for i in v['ioms']])
        rows.append(row);print(json.dumps(row),flush=True)
    active=rows[:4]
    signatures={(r['guards'][0]['address'],r['guards'][0]['operation'],r['guards'][0]['width']) for r in active}
    if len(signatures)!=1:raise ValueError('Different next native boundaries; inspect preserved runs')
    # The baseline pair must still differ only by original image size in its runtime setup.
    a23=o/'stock23-xt';cfw=o/'cfw-xt'
    for name in ('board.repl','strict.cs','result.py','probe.resc'):
        if (a23/name).read_bytes()!=(cfw/name).read_bytes():raise ValueError('Stock/CFW configuration differs: '+name)
    if (a23/'run.py').read_text().replace('3758688','3829832')!=(cfw/'run.py').read_text():raise ValueError('Stock/CFW runtime differs beyond raw length')
    source=o/'source';source.mkdir(mode=0o700);hashes={}
    for name in ('verify_rtc_osel_main.py','run_renode_main_probe.py','renode-strict-mmio.cs','verify_rtc_osel.py','analyze_rtc_osel.py','verify_iom_main.py','native_replay.py'):
        data=(ROOT/'tools'/name).read_bytes();(source/name).write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    report=dict(passed=True,cases=rows,source_sha256=hashes,profile_sha256=digest(a.profile),stock23_cfw_same_model=True,scope='original main under explicit request-latch assumptions to next strict boundary; no oscillator, boot, display or physical validation')
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
