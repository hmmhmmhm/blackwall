"""Prepare source-pinned private plans with named hypothetical controller data."""
import argparse,json
from pathlib import Path
from prepare_vendor_startup_candidate import sha

PROFILES=['le-basic-27x4','le-large-251x8']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('case',choices=['stock24','stock23','cfw']);p.add_argument('output',type=Path);p.add_argument('--profile',choices=PROFILES,default=PROFILES[0]);a=p.parse_args();root=Path(__file__).resolve().parents[1]
    if a.simulator.resolve().is_relative_to(root) or not a.output.resolve().is_relative_to(a.simulator.resolve()):raise ValueError('Information plans must remain in private simulator outside Git')
    if a.output.exists():raise ValueError('Preserve existing plan')
    sp=a.simulator/'controller-information-source-01/report.json';source=json.loads(sp.read_text())
    if not source['passed'] or source['software_profiles']!=6:raise ValueError('Unverified original information profiles')
    row=next(r for r in source['cases'] if r['case']==a.case);profile=next(r for r in row['samples'] if r['profile']==a.profile);cap=a.simulator/'standard-hci-main-01'/a.case
    if sha(cap/'main.bin')!=row['raw_sha256'] or sha(cap/'exports/sram-full.bin')!=row['sram_sha256']:raise ValueError('Changed source image/SRAM')
    plan=json.loads((cap/'plan.json').read_text());plan['id']='controller-information-v1';plan['source_root']='standard-hci-main-01';plan.pop('reviewed_sources',None);plan['execution_mode']='until-guest-stop'
    baseline=a.simulator/'controller-information-research-01/base-reset.cs';candidate=root/'tools/renode-em9305-reset.cs';plan['components']=[dict(name='controller-information-peer',baseline=str(baseline.relative_to(a.simulator)),candidate='tools/renode-em9305-reset.cs',before_sha256=sha(baseline),after_sha256=sha(candidate))]
    plan['board_edits']=[dict(before='    standardInitialization: true\n',after='    standardInitialization: true\n    controllerInformationProfile: "'+a.profile+'"\n')]
    peer="m['sysbus.iom6'].SpiWordTransfer.Peer"
    plan['diagnostics']=plan['diagnostics'][:-1]+",information_commands_accepted=int("+peer+".InformationCommandsAccepted),information_scenario=bool("+peer+".HasControllerInformationScenario),information_profile=(str("+peer+".ControllerInformationProfile) if "+peer+".HasControllerInformationScenario else 'none'),mock_acl_length=int("+peer+".MockAclLength),mock_acl_packets=int("+peer+".MockAclPackets))"
    for case,modes in plan['semantics'].items():
        c=modes['candidate'];c['boundary']['pc']=0x501676 if case=='stock24' else 0x549fce
        values={'accepted_commands':14,'replies':14,'frames':34,'commands':68,'application_drain_reads':12}
        for check in c['checks']:
            if len(check['path'])==2 and check['path'][0]=='diagnostics' and check['path'][1] in values:check['eq']=values[check['path'][1]]
        c['checks'] += [dict(path=['diagnostics',k],eq=v) for k,v in [('information_commands_accepted',4),('information_scenario',True),('information_profile',a.profile),('mock_acl_length',profile['acl_length']),('mock_acl_packets',profile['acl_packets'])]]
        c['allowed_differences']=['Named mock buffer/states/filter/features responses; 10/15/8/15-byte complete replies, no real capability claim.']
        c['unresolved_differences']=['Actual ACL fragmentation/credit decrement and physical capability unknown; next privacy capacity query unsupported; boot/display incomplete.']
        control=modes['control'];control['boundary']['pc']=c['boundary']['pc'];control['checks']=[dict(path=['diagnostics',k],eq=v) for k,v in [('accepted_commands',10),('replies',10),('frames',26),('commands',52),('application_drain_reads',8),('information_commands_accepted',0),('information_scenario',False),('information_profile','none')]]
        control['allowed_differences']=['Default-off information profile preserves source CPU/events exactly.'];control['unresolved_differences']=['Controller information queries remain unsupported.']
    plan['information_source_contract_sha256']=sha(sp);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,indent=2)+'\n');print('Prepared private information plan',a.case,a.profile)


if __name__=='__main__':main()
