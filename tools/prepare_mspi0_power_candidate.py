"""Prepare optional MSPI0 power ownership, keeping firmware and bus behavior intact."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path)
    p.add_argument('case',choices=['stock24','stock23','cfw']);p.add_argument('profile',choices=['active','stuck-off'])
    p.add_argument('output',type=Path);p.add_argument('--guest-stop-control',action='store_true')
    a=p.parse_args();s=a.simulator;root=Path(__file__).resolve().parents[1]
    if a.output.exists() or s.resolve().is_relative_to(root) or not a.output.resolve().is_relative_to(s.resolve()):
        raise ValueError('Preserve firmware-derived plans outside Git')
    manifest=json.loads((s/'mspi0-power-verification-01/manifest.json').read_text());analysis=s/'mspi0-power-source-01/report.json'
    if manifest.get('passed') is not True or sha(analysis)!=manifest['source_sha256']:raise ValueError('Changed original MSPI0 analysis')
    row=next(c for c in json.loads(analysis.read_text())['cases'] if c['case']==a.case);cap=s/'vbus-status-main-01'/a.case
    if sha(cap/'main.bin')!=row['main_sha256'] or sha(cap/'exports/sram-full.bin')!=row['sram_sha256']:raise ValueError('Changed original native input')
    plan=json.loads((cap/'plan.json').read_text());plan.update(id='mspi0-power-v1',source_root='vbus-status-main-01')
    baseline=s/'mspi0-power-peer-research-01/base-core.cs'
    plan['components']=[dict(name='mspi0-shared-power',baseline=str(baseline.relative_to(s)),candidate='tools/renode-strict-mmio.cs',before_sha256=sha(baseline),after_sha256=sha(root/'tools/renode-strict-mmio.cs'))]
    plan['runtime_edits']=[];plan['board_append']='\nmspi0_power: Miscellaneous.BlackwallPeripheralPower @ none\n    mask: 0x4000\n    profile: '+str(int(a.profile=='active'))+'\n'
    needle='    mspi1Power: mspi1_power\n'
    if (cap/'board.repl').read_text().count(needle)!=1:raise ValueError('Missing unique shared power anchor')
    plan['board_edits']=[dict(before=needle,after=needle+'    mspi0Power: mspi0_power\n')]
    power="m['sysbus.guard'].Mspi0Power"
    fields=",mspi0_selected=("+power+" is not None),mspi0_phase=str("+power+".Phase) if "+power+" is not None else 'unselected'"
    for name,prop in [('requests','Requests'),('responses','Responses'),('request_word','RequestWord'),('status_word','StatusWord')]:
        fields+=',mspi0_'+name+'=int('+power+'.'+prop+') if '+power+' is not None else 0'
    plan['diagnostics']=plan['diagnostics'][:-1]+fields+')';plan['reviewed_sources']={}
    for case in plan['cases']:
        audit=s/'vbus-status-saved-audit-01'/case/'report.json';plan['reviewed_sources'][case]=dict(path=str(audit.relative_to(s)),sha256=sha(audit))
        r=json.loads((s/'vbus-status-main-01'/case/'report.json').read_text());g=next(x for x in r['observed']['guards'] if x['accesses'])
        boundary=dict(kind='strict-mmio',pc=r['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        common=[dict(path=['diagnostics',k],eq=v) for k,v in [('accepted_commands',59),('replies',60),('vbus_status_reads',1)]]
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='prefix',path=['selected_observation','events']),
            checks=common+[dict(path=['diagnostics',k],eq=v) for k,v in [('mspi0_selected',True),('mspi0_phase','on' if a.profile=='active' else 'stuck-off'),('mspi0_requests',1),('mspi0_responses',1),('mspi0_request_word',0x4000),('mspi0_status_word',0x4000 if a.profile=='active' else 0)]],
            allowed_differences=['Explicit MSPI0 power profile only; original HAL controls all subsequent execution.'],unresolved_differences=['Provisional natural frontier; clock/bus/display and full boot unverified.']),
            control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=common+[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','mspi0_selected'],eq=False)],allowed_differences=['Default missing MSPI0 owner preserves CPU/events.'],unresolved_differences=['Power request remains unsupported.']))
    plan.update(host_capture_seconds=120,memory_export_policy='paused-after-observation');plan.pop('execution_mode',None)
    if a.guest_stop_control:
        plan.pop('host_capture_seconds');plan.pop('memory_export_policy');plan['execution_mode']='until-guest-stop'
    plan['mspi0_source_sha256']=sha(analysis);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,indent=2)+'\n')
    print('Prepared private MSPI0 candidate',a.case,a.profile)


if __name__=='__main__':main()
