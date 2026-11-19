"""Observe original mount/read entry and active config; no new backing or guest writes."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,parse_log,validate_assets,digest
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--case',choices=['stock24','stock23','cfw'],default='stock24');a=p.parse_args();s=a.simulator;out=a.output;key=a.case
    contract=json.loads((s/'littlefs-mount-policy-contract-01/report.json').read_text());meta=next(c for c in contract['cases'] if c['case']==key)
    if not contract['passed'] or contract['count']!=55:raise ValueError('Source contract missing')
    src=s/'crypto-otp-off-main-01'/key;prior=json.loads((src/'report.json').read_text());validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived'])
    if parse_log((src/'renode.log').read_text())!=prior['observed'] or (src/'strict.cs').read_bytes()!=models(s):raise ValueError('Prior assets/model differ')
    out.mkdir(mode=0o700,parents=True)
    for filename in FILES:shutil.copyfile(src/filename,out/filename)
    runtime=(src/'run.py').read_text()
    if runtime.count('    e.StartAll()\n')!=1:raise ValueError('Unexpected start boundary')
    labels=['LittleFS-mount-entry','LittleFS-format-entry','LittleFS-read-entry']
    points=list(zip(labels,[meta['mount'],meta['format'],meta['read_callback']]))
    extra=''.join("    observer.AddPoint('"+label+"',"+str(int(addr,0))+')\n' for label,addr in points)
    extra+="    observer.CaptureSram(m,'LittleFS-read-entry',"+str(int(meta['config_snapshot'],0))+',2)\n'
    runtime=runtime.replace('    e.StartAll()\n',extra+'    e.StartAll()\n');compile(runtime,'run.py','exec');(out/'run.py').write_text(runtime)
    derived={f:digest(out/f) for f in FILES};(out/'derived-inputs.json').write_text(json.dumps(dict(derived=derived,base={f:digest(src/f) for f in FILES}),indent=2)+'\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode',timeout=None)
    validate_assets(out,derived);v=parse_log(log)
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_OBSERVATION ')]
    if len(rows)!=1:raise ValueError('Missing observation')
    obs=rows[0];checks=[]
    def check(n,ok):
        if not ok:raise ValueError(n)
        checks.append(n)
    check('same-CPU-boundary-and-state',v==prior['observed'])
    check('no-event-loss',not obs['dropped_events'] and obs['sequence']==len(obs['events']))
    projected=[dict(e,sequence=i+1) for i,e in enumerate(e for e in obs['events'] if e['label'] not in labels)]
    check('all-prior-events-identical',projected==prior['selected_observation']['events'])
    pts={p['label']:p for p in obs['points']}
    check('mount-and-read-once',pts[labels[0]]['hits']==pts[labels[2]]['hits']==1)
    check('format-not-reached',pts[labels[1]]['hits']==0)
    read=[e for e in obs['events'] if e['label']==labels[2]][0]
    check('callback-active-config-pointer',read['r0']==int(meta['config'],0))
    check('original-state-config-pointer-and-count',pts[labels[2]]['snapshot']['words']==[int(meta['config'],0),3008])
    check('original-mount-object',next(e for e in obs['events'] if e['label']==labels[0])['r0']==int(meta['state_object'],0))
    result=dict(passed=True,count=len(checks),checks=checks,case=key,observed=v,selected_observation=obs,config=meta,
                scope='Read-only observation of original active config before first unsupported volume read; no mount completion, format execution, boot/display or hardware proof')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,case=key,count=len(checks),config=meta['config'],blocks=3008)))


if __name__=='__main__':main()
