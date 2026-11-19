"""Prepare a private P256 two-event scenario using the original-reset capture runner."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path)
    p.add_argument('case',choices=['stock24','stock23','cfw']);p.add_argument('output',type=Path)
    p.add_argument('--profile',choices=['test-generator','test-error'],default='test-generator')
    a=p.parse_args();s=a.simulator;root=Path(__file__).resolve().parents[1]
    if s.resolve().is_relative_to(root) or not a.output.resolve().is_relative_to(s.resolve()) or a.output.exists():
        raise ValueError('Preserve private evidence outside Git')
    source=s/'p256-event-source-06/report.json'
    verification=json.loads((s/'p256-event-verification-01/manifest.json').read_text())
    if not verification['passed'] or sha(source)!=verification['source_sha256']:
        raise ValueError('Changed original P256 contract')
    sources={'stock24':'privacy-length-main-01','stock23':'privacy-length-main-02/stock23','cfw':'privacy-length-main-02/cfw'}
    aliases=s/'p256-peer-source-01';aliases.mkdir(exist_ok=True)
    for case,folder in sources.items():
        target=s/folder;alias=aliases/case
        if alias.is_symlink():
            if alias.resolve()!=target.resolve():raise ValueError('Changed private source alias')
        elif alias.exists():raise ValueError('Preserve existing private source alias')
        else:alias.symlink_to(target,target_is_directory=True)
    cap=s/sources[a.case];row=next(c for c in json.loads(source.read_text())['cases'] if c['case']==a.case)
    if sha(cap/'main.bin')!=row['raw_sha256'] or sha(cap/'exports/sram-full.bin')!=row['sram_sha256']:
        raise ValueError('Changed native source')
    plan=json.loads((cap/'plan.json').read_text());plan.update(id='p256-two-events-v1',source_root='p256-peer-source-01',execution_mode='until-guest-stop')
    plan.pop('reviewed_sources',None)
    baseline=s/'p256-peer-research-01/base-reset.cs'
    plan['components']=[dict(name='p256-two-events-peer',baseline=str(baseline.relative_to(s)),candidate='tools/renode-em9305-reset.cs',before_sha256=sha(baseline),after_sha256=sha(root/'tools/renode-em9305-reset.cs'))]
    iom=s/'p256-peer-research-01/base-iom.cs'
    plan['components'].append(dict(name='bounded-receive-streaming',baseline=str(iom.relative_to(s)),candidate='tools/renode-iom.cs',before_sha256=sha(iom),after_sha256=sha(root/'tools/renode-iom.cs')))
    plan['board_edits']=[dict(before='    privacyInitializationProfile: "test-max-251"\n',after='    privacyInitializationProfile: "test-max-251"\n    p256PublicKeyProfile: "'+a.profile+'"\n')]
    plan['board_edits'].append(dict(before='    spiWordPeer: spi_header\n',after='    spiReceiveStreaming: true\n    spiWordPeer: spi_header\n'))
    peer="m['sysbus.iom6'].SpiWordTransfer.Peer"
    plan['diagnostics']=plan['diagnostics'][:-1]+",p256_scenario=bool("+peer+".HasP256PublicKeyScenario),p256_events_consumed=int("+peer+".P256EventsConsumed),p256_profile=(str("+peer+".P256PublicKeyProfile) if "+peer+".HasP256PublicKeyScenario else 'none'),spi_receive_streaming=bool(m['sysbus.iom6'].SpiReceiveStreaming))"
    for modes in plan['semantics'].values():
        c=modes['candidate'];values=dict(accepted_commands=22,replies=23,frames=51,commands=102,application_drain_reads=20)
        for check in c['checks']:
            if len(check['path'])==2 and check['path'][0]=='diagnostics' and check['path'][1] in values:check['eq']=values[check['path'][1]]
        c['checks'] += [dict(path=['diagnostics',k],eq=v) for k,v in [('p256_scenario',True),('p256_events_consumed',2),('p256_profile',a.profile),('spi_receive_streaming',True)]]
        c['allowed_differences']=['Explicit public test point and Command Status followed by LE Complete; two reply events for one command.']
        c['unresolved_differences']=['P256/AES follow-up frontier requires saved verification; boot/display/physical behavior unverified.']
        control=modes['control'];control['checks']=[dict(path=['diagnostics',k],eq=v) for k,v in [('accepted_commands',21),('replies',21),('frames',48),('commands',96),('application_drain_reads',19),('p256_scenario',False),('p256_events_consumed',0),('spi_receive_streaming',False)]]
        control['allowed_differences']=['Default-off P256 preserves the existing 21-command source CPU/events exactly.']
        control['unresolved_differences']=['P256 events remain unsupported with the new profile disabled.']
    plan['p256_source_contract_sha256']=sha(source)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,indent=2)+'\n')
    print('Prepared private P256 candidate',a.case,a.profile)


if __name__=='__main__':main()
