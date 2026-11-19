"""Prepare a pinned, opt-in test-entropy initialization candidate; no hardware access."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('case', choices=['stock24', 'stock23', 'cfw'])
    p.add_argument('output', type=Path)
    p.add_argument('--profile', choices=['test-max-251', 'test-min-27'], default='test-max-251')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    s = a.simulator
    if s.resolve().is_relative_to(root) or not a.output.resolve().is_relative_to(s.resolve()):
        raise ValueError('Plans and firmware-derived data must remain outside Git')
    if a.output.exists():
        raise ValueError('Preserve existing plan')
    source = s / 'privacy-length-source-02/report.json'
    verification = json.loads((s / 'privacy-length-verification-01/manifest.json').read_text())
    if not verification['passed'] or sha(source) != verification['source_sha256']:
        raise ValueError('Changed original initialization contract')
    row = next(r for r in json.loads(source.read_text())['cases'] if r['case'] == a.case)
    cap = s / 'controller-information-main-01' / a.case
    if sha(cap / 'main.bin') != row['raw_sha256'] or sha(cap / 'exports/sram-full.bin') != row['sram_sha256']:
        raise ValueError('Changed original native input')
    plan = json.loads((cap / 'plan.json').read_text())
    plan.update(id='privacy-length-v1', source_root='controller-information-main-01', execution_mode='until-guest-stop')
    plan.pop('reviewed_sources', None)
    baseline = s / 'privacy-length-research-01/base-reset.cs'
    plan['components'] = [dict(name='privacy-length-peer', baseline=str(baseline.relative_to(s)),
        candidate='tools/renode-em9305-reset.cs', before_sha256=sha(baseline), after_sha256=sha(root / 'tools/renode-em9305-reset.cs'))]
    plan['board_edits'] = [dict(before='    controllerInformationProfile: "le-basic-27x4"\n',
        after='    controllerInformationProfile: "le-basic-27x4"\n    privacyInitializationProfile: "'+a.profile+'"\n')]
    peer="m['sysbus.iom6'].SpiWordTransfer.Peer"
    plan['diagnostics'] = plan['diagnostics'][:-1]+",privacy_commands_accepted=int("+peer+".PrivacyCommandsAccepted),privacy_scenario=bool("+peer+".HasPrivacyInitializationScenario),privacy_profile=(str("+peer+".PrivacyInitializationProfile) if "+peer+".HasPrivacyInitializationScenario else 'none'))"
    for modes in plan['semantics'].values():
        candidate = modes['candidate']
        values = dict(accepted_commands=21, replies=21, frames=48, commands=96, application_drain_reads=19)
        for check in candidate['checks']:
            if len(check['path']) == 2 and check['path'][0] == 'diagnostics' and check['path'][1] in values:
                check['eq'] = values[check['path'][1]]
        candidate['checks'] += [dict(path=['diagnostics', k], eq=v) for k,v in
            [('privacy_commands_accepted',7), ('privacy_scenario',True), ('privacy_profile',a.profile)]]
        candidate['allowed_differences'] = ['Seven explicit source-supported completions; deterministic public test vectors only.']
        candidate['unresolved_differences'] = ['Post-Rand natural frontier is provisional; preserve any semantic failure for saved audit. Boot/display and physical controller behavior unverified.']
        control = modes['control']
        control['checks'] = [dict(path=['diagnostics',k],eq=v) for k,v in
            [('accepted_commands',14),('replies',14),('frames',34),('commands',68),('application_drain_reads',12),('privacy_scenario',False),('privacy_commands_accepted',0)]]
        control['allowed_differences'] = ['Default-off privacy profile preserves the existing 14-command source CPU/events exactly.']
        control['unresolved_differences'] = ['Privacy initialization remains unsupported with this profile disabled.']
    plan['privacy_source_contract_sha256'] = sha(source)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan,indent=2)+'\n')
    print('Prepared private privacy/length plan',a.case,a.profile)


if __name__ == '__main__':
    main()
