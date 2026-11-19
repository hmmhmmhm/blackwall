"""Compare original mains with a declared functional RTC profile and default strict fallback."""
import argparse,json,hashlib,subprocess,sys
from pathlib import Path
from native_replay import parse_log,boundary_state
from pinned_main import load_pinned_main
from rtc_engine_source import UPSTREAM_SHA,load_engine
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
    if o.exists():raise ValueError('Use a new evidence directory')
    o.mkdir(mode=0o700);rows=[]
    cases=[('stock24','stock24-xt',True,True),('stock23','stock23-xt',True,True),('cfw','cfw-xt',True,True),('stock24-no-writes','stock24-xt',True,False),('stock24-default','stock24-xt',False,False)]
    for name,prior,enabled,writes in cases:
        prior_root=s/'rtc-osel-main-comparison-01';cmd=json.loads((prior_root/(prior+'-launcher.json')).read_text())['command']
        run=o/name;cmd[3]=str(run)
        if enabled:cmd+=['--rtc-model','epoch2000-100hz']
        if writes:cmd+=['--rtc-counter-writes','hal-low-upper']
        launch=subprocess.run(cmd,capture_output=True,text=True)
        (o/(name+'-launcher.json')).write_text(json.dumps(dict(command=cmd,returncode=launch.returncode,stdout=launch.stdout,stderr=launch.stderr),indent=2)+'\n')
        if launch.returncode:raise ValueError('Original main failed: '+name)
        report=json.loads((run/'report.json').read_text());v=parse_log((run/'renode.log').read_text())
        if report['observed']!=v:raise ValueError('Saved runtime differs')
        _,raw=load_pinned_main(Path(cmd[2]).read_bytes())
        if (run/'main.bin').read_bytes()!=raw:raise ValueError('Original image differs')
        if any(report[k] for k in ('boot_verified','hardware_validated','installable')):raise ValueError('Unproven completion claim')
        rtc=v['rtc'];guards=[g for g in v['guards'] if g['accesses']]
        if enabled:
            if rtc is None or rtc['reads']<1 or rtc['writes']<1 or rtc['hardware_verified'] or rtc['physical_oscillator_verified']:raise ValueError('RTC profile was not exercised safely')
            if rtc['counter_write_profile']!=('hal-low-upper' if writes else 'unsupported'):raise ValueError('Wrong write profile')
            if report['rtc_engine_provenance']['upstream_sha256']!=UPSTREAM_SHA or report['rtc_engine_provenance']['generated_sha256']!=hashlib.sha256(load_engine().encode()).hexdigest():raise ValueError('RTC engine differs')
            if guards[0]['address']==0x40004800:raise ValueError('RTC control boundary not crossed')
        else:
            previous=json.loads((prior_root/prior/'report.json').read_text())
            if rtc is not None or boundary_state(v)!=boundary_state(previous['observed']):raise ValueError('Default strict behavior changed')
        row=dict(name=name,pc=hex(v['pc']),rtc=rtc,guards=guards,uarts=[dict(module=u['module'],tx=len(u['tx_bytes']),isr=u['irq_exception_entries']) for u in v['uarts']],ioms=[dict(module=i['module'],commands=i['commands'],cq_pairs=i['cq']['pairs']) for i in v['ioms']])
        rows.append(row);print(json.dumps(row),flush=True)
    left=o/'stock23';right=o/'cfw'
    for name in ('board.repl','strict.cs','result.py','probe.resc'):
        if (left/name).read_bytes()!=(right/name).read_bytes():raise ValueError('Stock/CFW configuration differs')
    if (left/'run.py').read_text().replace('3758688','3829832')!=(right/'run.py').read_text():raise ValueError('Stock/CFW runtime differs beyond size')
    source=o/'source';source.mkdir(mode=0o700);hashes={}
    for name in ('verify_rtc_main.py','run_renode_main_probe.py','renode-strict-mmio.cs','renode-rtc.cs','rtc_engine_source.py','verify_rtc_adapter.py'):
        data=(ROOT/'tools'/name).read_bytes();(source/name).write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,source_sha256=hashes,scope='original main under explicit virtual RTC/epoch/optional write assumptions to next strict boundary; no physical or full boot proof'),indent=2)+'\n')

if __name__=='__main__':main()
