"""Prepare private exact-command mask and identity-readback startup plans."""
import argparse,json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('case',choices=['stock24','stock23','cfw']);p.add_argument('output',type=Path);a=p.parse_args();root=Path(__file__).resolve().parents[1]
    if a.simulator.resolve().is_relative_to(root) or not a.output.resolve().is_relative_to(a.simulator.resolve()):raise ValueError('Plan must stay in private simulator outside Git')
    if a.output.exists():raise ValueError('Preserve existing plan')
    sp=a.simulator/'standard-hci-source-01/report.json';source=json.loads(sp.read_text())
    if not source['passed'] or source['original_software_scenarios']!=12:raise ValueError('Unverified standard startup contract')
    row=next(r for r in source['cases'] if r['case']==a.case);cap=a.simulator/'vendor-startup-main-01'/a.case
    if sha(cap/'main.bin')!=row['raw_sha256'] or sha(cap/'exports/sram-full.bin')!=row['sram_sha256']:raise ValueError('Changed source image/SRAM')
    plan=json.loads((cap/'plan.json').read_text());plan['id']='standard-hci-v1';plan['source_root']='vendor-startup-main-01';plan['execution_mode']='until-guest-stop'
    ap=a.simulator/'vendor-startup-saved-audit-01/stock24/report.json';plan['reviewed_sources']={'stock24':dict(path=str(ap.relative_to(a.simulator)),sha256=sha(ap))}
    baseline=a.simulator/'standard-hci-research-01/base-reset.cs';candidate=root/'tools/renode-em9305-reset.cs';plan['components']=[dict(name='standard-initialization-peer',baseline=str(baseline.relative_to(a.simulator)),candidate='tools/renode-em9305-reset.cs',before_sha256=sha(baseline),after_sha256=sha(candidate))]
    plan['board_edits']=[dict(before='    applicationReset: true\n',after='    applicationReset: true\n    standardInitialization: true\n')]
    plan['diagnostics']=plan['diagnostics'][:-1]+",standard_commands_accepted=int(m['sysbus.iom6'].SpiWordTransfer.Peer.StandardCommandsAccepted),standard_scenario=bool(m['sysbus.iom6'].SpiWordTransfer.Peer.HasStandardInitializationScenario))"
    for case,modes in plan['semantics'].items():
        c=modes['candidate'];c['boundary']['pc']=0x501676 if case=='stock24' else 0x549fce
        values={'accepted_commands':10,'replies':10,'frames':26,'commands':52,'application_drain_reads':8}
        for check in c['checks']:
            if len(check['path'])==2 and check['path'][0]=='diagnostics' and check['path'][1] in values:check['eq']=values[check['path'][1]]
        c['checks'] += [dict(path=['diagnostics','standard_commands_accepted'],eq=4),dict(path=['diagnostics','standard_scenario'],eq=True)]
        c['allowed_differences']=['Explicit source-derived masks and consistent virtual identity readback; fixed7/7/7/13-byte replies, no real controller identity claim.']
        c['unresolved_differences']=['Real controller data/reset/persistence unknown; next LE buffer-size information query remains unsupported; main/display incomplete.']
        control=modes['control'];control['boundary']['pc']=c['boundary']['pc'];control['checks']=[dict(path=['diagnostics',k],eq=v) for k,v in [('accepted_commands',6),('replies',6),('frames',15),('commands',30),('application_drain_reads',4),('vendor_commands_accepted',3),('standard_commands_accepted',0),('standard_scenario',False)]]
        control['allowed_differences']=['Default-off standard scenario preserves source CPU/events exactly.'];control['unresolved_differences']=['Standard initialization remains unsupported.']
    plan['standard_source_contract_sha256']=sha(sp);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared private standard initialization plan',a.case)


if __name__=='__main__':main()
