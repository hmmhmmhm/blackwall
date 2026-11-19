"""Connect one shared clock and isolated MSPI0 configuration to original main."""
import argparse,json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('case',choices=['stock24','stock23','cfw']);p.add_argument('output',type=Path);p.add_argument('--guest-stop-control',action='store_true');p.add_argument('--stuck-off',action='store_true');a=p.parse_args();s=a.simulator;root=Path(__file__).resolve().parents[1]
    if a.stuck_off and a.guest_stop_control:raise ValueError('Stuck-off is a distinct experiment, not the default control')
    if a.output.exists() or s.resolve().is_relative_to(root) or not a.output.resolve().is_relative_to(s.resolve()):raise ValueError('Preserve private plans outside Git')
    source=s/'mspi0-init-source-03/report.json';manifest=json.loads((s/'mspi0-init-verification-01/manifest.json').read_text())
    if not manifest['passed'] or sha(source)!=manifest['source_sha256']:raise ValueError('Changed original initialization analysis')
    row=next(x for x in json.loads(source.read_text())['cases'] if x['case']==a.case);cap=s/'mspi0-power-main-01'/a.case
    if sha(cap/'main.bin')!=row['main_sha256'] or sha(cap/'exports/sram-full.bin')!=row['sram_sha256']:raise ValueError('Changed original main/SRAM')
    plan=json.loads((cap/'plan.json').read_text());plan.update(id='mspi0-config-v1',source_root='mspi0-power-main-01');plan['components']=[]
    for name in ['renode-strict-mmio.cs','renode-mspi1-clock.cs','renode-mspi1-config.cs']:
        baseline=s/'mspi0-config-peer-research-01'/('base-'+name);plan['components'].append(dict(name=name[:-3],baseline=str(baseline.relative_to(s)),candidate='tools/'+name,before_sha256=sha(baseline),after_sha256=sha(root/'tools'/name)))
    board=(cap/'board.repl').read_text();anchors=[('    mspi0Power: mspi0_power\n','    mspi0Power: mspi0_power\n    mspi0Config: mspi0_config\n'),('mspi1_clock: Miscellaneous.BlackwallMspi1ClockStorage @ none\n','mspi1_clock: Miscellaneous.BlackwallMspi1ClockStorage @ none\n    mspi0Storage: true\n')]
    if any(board.count(before)!=1 for before,_ in anchors):raise ValueError('Missing unique clock/config anchors')
    plan['board_edits']=[dict(before=before,after=after) for before,after in anchors];plan['board_append']='\nmspi0_config: Miscellaneous.BlackwallMspi1ConfigStorage @ none\n    profile: "source-reset-config"\n    baseAddress: 0x40060000\n';plan['runtime_edits']=[]
    if a.stuck_off:
        before='mspi0_power: Miscellaneous.BlackwallPeripheralPower @ none\n    mask: 0x4000\n    profile: 1\n'
        if board.count(before)!=1:raise ValueError('Missing unique active MSPI0 source profile')
        plan['board_edits'].append(dict(before=before,after=before.replace('profile: 1','profile: 0')))
    config="m['sysbus.guard'].Mspi0Config";clock="m['sysbus.guard'].Mspi1Clock"
    fields=',mspi0_config_selected=('+config+' is not None),mspi0_config_used=('+config+' is not None and '+config+'.Writes>=3),mspi0_clock_enabled=bool('+clock+'.Mspi0Enabled),mspi0_clock_selection=int('+clock+'.Mspi0Selection)'
    for k in ['Reads','Writes']:fields+=',mspi0_config_'+k.lower()+'=int('+config+'.'+k+') if '+config+' is not None else 0'
    plan['diagnostics']=plan['diagnostics'][:-1]+fields+')';plan['reviewed_sources']={}
    for case in plan['cases']:
        audit=s/'mspi0-power-saved-audit-01'/case/'report.json';plan['reviewed_sources'][case]=dict(path=str(audit.relative_to(s)),sha256=sha(audit))
        prior=json.loads((s/'mspi0-power-main-01'/case/'report.json').read_text());g=next(x for x in prior['observed']['guards'] if x['accesses']);boundary=dict(kind='strict-mmio',pc=prior['observed']['pc'],**{k:g[k] for k in ['address','operation','width','value']})
        common=[dict(path=['diagnostics',k],eq=v) for k,v in [('accepted_commands',59),('replies',60),('mspi0_phase','on')]]
        plan['semantics'][case]=dict(candidate=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='prefix',path=['selected_observation','events']),checks=common+[dict(path=['diagnostics',k],eq=v) for k,v in [('mspi0_config_selected',True),('mspi0_config_used',True),('mspi0_clock_enabled',True),('mspi0_clock_selection',10)]],allowed_differences=['Explicit module0 fields and configuration storage only.'],unresolved_differences=['Provisional natural frontier; engine/IRQ/queue and full display unverified.']),control=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),checks=common+[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','mspi0_config_selected'],eq=False)],allowed_differences=['Default clock mask/base/owner preserve CPU/events.'],unresolved_differences=['Module0 clock write remains unsupported.']))
        if a.stuck_off:
            c=plan['semantics'][case]['candidate'];c['comparison']=dict(policy='bounded-invariants',paths=[['observed','memory_policy','violations'],['observed','system_control','violations']])
            c['checks']=[dict(path=['diagnostics',k],eq=v) for k,v in [('accepted_commands',59),('replies',60),('mspi0_phase','stuck-off'),('mspi0_status_word',0),('mspi0_config_selected',True),('mspi0_config_used',False),('mspi0_config_reads',0),('mspi0_config_writes',0),('mspi0_clock_enabled',True),('mspi0_clock_selection',8)]]
            c['allowed_differences']=['Original timeout path differs; power-gated configuration must remain unused. Event equality is not claimed.']
    plan.update(host_capture_seconds=120,memory_export_policy='paused-after-observation');plan.pop('execution_mode',None)
    if a.guest_stop_control:plan.pop('host_capture_seconds');plan.pop('memory_export_policy');plan['execution_mode']='until-guest-stop'
    plan['mspi0_init_source_sha256']=sha(source);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared private MSPI0 configuration candidate',a.case)


if __name__=='__main__':main()
