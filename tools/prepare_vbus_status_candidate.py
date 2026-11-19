"""Prepare explicit VBUS status experiments against saved original-reset inputs."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path)
    p.add_argument('case',choices=['stock24','stock23','cfw'])
    p.add_argument('profile',choices=['test-vbus-absent','test-vbus-present'])
    p.add_argument('output',type=Path);p.add_argument('--guest-stop-control',action='store_true')
    a=p.parse_args();s=a.simulator;root=Path(__file__).resolve().parents[1]
    if a.output.exists() or s.resolve().is_relative_to(root) or not a.output.resolve().is_relative_to(s.resolve()):
        raise ValueError('Preserve private execution plans outside Git')
    source=json.loads((s/'vbus-status-verification-01/manifest.json').read_text())
    analysis=s/'vbus-status-source-01/report.json'
    if source.get('passed') is not True or sha(analysis)!=source['source_sha256']:
        raise ValueError('Changed original VBUS analysis')
    row=next(c for c in json.loads(analysis.read_text())['cases'] if c['case']==a.case)
    cap=s/'advertising-peer-main-01'/a.case
    if sha(cap/'main.bin')!=row['main_sha256'] or sha(cap/'exports/sram-full.bin')!=row['sram_sha256']:
        raise ValueError('Changed native source main/SRAM')
    plan=json.loads((cap/'plan.json').read_text());plan.update(id='vbus-status-v1',source_root='advertising-peer-main-01')
    plan['components']=[]
    for name in ['renode-pmic-restore-probe.cs','renode-pmic-timed-probe.cs']:
        baseline=s/'vbus-status-peer-research-01'/('base-'+name)
        plan['components'].append(dict(name=name[:-3],baseline=str(baseline.relative_to(s)),candidate='tools/'+name,before_sha256=sha(baseline),after_sha256=sha(root/'tools'/name)))
    plan['runtime_edits']=[];plan['board_append']=''
    anchor='pointerProbe: Miscellaneous.BlackwallPmicTimedProbe @ iom7 0x6b\n'
    if (cap/'board.repl').read_text().count(anchor)!=1:raise ValueError('Missing unique PMIC board anchor')
    plan['board_edits']=[dict(before=anchor,after=anchor+'    vbusStatusProfile: "'+a.profile+'"\n')]
    peer="m['sysbus.iom7.pointerProbe'].Inner"
    plan['diagnostics']=plan['diagnostics'][:-1]+",vbus_status_profile="+peer+".VbusStatusProfile,vbus_status_value=int("+peer+".VbusStatusValue),vbus_status_reads=int("+peer+".VbusStatusReads))"
    plan['reviewed_sources']={}
    for case in plan['cases']:
        path=s/'advertising-peer-saved-audit-01'/case/'report.json'
        plan['reviewed_sources'][case]=dict(path=str(path.relative_to(s)),sha256=sha(path))
        report=json.loads((s/'advertising-peer-main-01'/case/'report.json').read_text());g=next(x for x in report['observed']['guards'] if x['accesses'])
        boundary=dict(kind='strict-mmio',pc=report['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        common=[dict(path=['diagnostics',k],eq=v) for k,v in [('accepted_commands',59),('replies',60),('advertising_commands_accepted',5),('advertising_replies_consumed',5)]]
        candidate=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='prefix',path=['selected_observation','events']),
            checks=common+[dict(path=['diagnostics','vbus_status_profile'],eq=a.profile),dict(path=['diagnostics','vbus_status_value'],eq=1 if a.profile=='test-vbus-present' else 0)],
            allowed_differences=['Explicit read-only VBUS snapshot; natural firmware consumes the result.'],
            unresolved_differences=['Provisional natural frontier; completed read, app loop and display require saved-state inspection.'])
        control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),
            checks=common+[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','vbus_status_profile'],eq=None),dict(path=['diagnostics','vbus_status_reads'],eq=0)],
            allowed_differences=['Default unknown VBUS status preserves original CPU/events exactly.'],unresolved_differences=['Status read remains unsupported.'])
        plan['semantics'][case]=dict(candidate=candidate,control=control)
    plan.update(host_capture_seconds=120,memory_export_policy='paused-after-observation');plan.pop('execution_mode',None)
    if a.guest_stop_control:
        plan.pop('host_capture_seconds');plan.pop('memory_export_policy');plan['execution_mode']='until-guest-stop'
    plan['vbus_status_source_sha256']=sha(analysis)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,indent=2)+'\n')
    print('Prepared private VBUS status candidate',a.case,a.profile)


if __name__=='__main__':main()
