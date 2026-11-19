"""Prepare a source-pinned 32-block AES initialization scenario, offline only."""
import argparse
import json
from pathlib import Path
from prepare_vendor_startup_candidate import sha
from bt_crypto_vectors import hci_encrypt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path)
    p.add_argument('case',choices=['stock24','stock23','cfw']);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator;root=Path(__file__).resolve().parents[1]
    if s.resolve().is_relative_to(root) or not a.output.resolve().is_relative_to(s.resolve()) or a.output.exists():
        raise ValueError('Preserve private firmware-derived plans outside Git')
    verification=json.loads((s/'aes-initialization-verification-01/manifest.json').read_text())
    fixture=s/'aes-initialization-verification-01/aes-fixtures.json'
    if not verification['passed'] or sha(fixture)!=verification['fixture_sha256']:
        raise ValueError('Changed verified AES fixture')
    row=next(c for c in json.loads(fixture.read_text())['cases'] if c['case']==a.case)
    if len(row['pairs'])!=32:raise ValueError('Exactly 32 source-derived AES pairs required')
    for pair in row['pairs']:
        command=bytes.fromhex(pair['command']);reply=bytes.fromhex(pair['reply'])
        if len(command)!=36 or command[:4]!=bytes.fromhex('01172020') or reply!=bytes.fromhex('040e1401172000')+hci_encrypt(command[4:20],command[20:36]):
            raise ValueError('AES pair does not match actual encryption input')
    cap=s/'p256-peer-main-01'/a.case
    analysis=s/'aes-initialization-source-06/report.json'
    if sha(analysis)!=verification['source_sha256']:raise ValueError('Changed original AES analysis')
    origin=next(c for c in json.loads(analysis.read_text())['cases'] if c['case']==a.case)
    if sha(cap/'main.bin')!=row['main_sha256'] or sha(cap/'exports/sram-full.bin')!=origin['sram_sha256']:
        raise ValueError('Changed original native input or initial SRAM')
    plan=json.loads((cap/'plan.json').read_text());plan.update(id='aes-initialization-v1',source_root='p256-peer-main-01',execution_mode='until-guest-stop')
    plan.pop('reviewed_sources',None);baseline=s/'aes-peer-research-01/base-reset.cs'
    plan['components']=[dict(name='bounded-aes-peer',baseline=str(baseline.relative_to(s)),candidate='tools/renode-em9305-reset.cs',before_sha256=sha(baseline),after_sha256=sha(root/'tools/renode-em9305-reset.cs'))]
    packed=''.join(pair['command']+pair['reply'] for pair in row['pairs'])
    plan['board_edits']=[dict(before='    p256PublicKeyProfile: "test-generator"\n',after='    p256PublicKeyProfile: "test-generator"\n    aesInitializationHex: "'+packed+'"\n')]
    peer="m['sysbus.iom6'].SpiWordTransfer.Peer"
    plan['diagnostics']=plan['diagnostics'][:-1]+",aes_scenario=bool("+peer+".HasAesInitializationScenario),aes_commands_accepted=int("+peer+".AesCommandsAccepted),aes_replies_consumed=int("+peer+".AesRepliesConsumed))"
    for modes in plan['semantics'].values():
        c=modes['candidate'];values=dict(accepted_commands=54,replies=55,frames=211,commands=422,application_drain_reads=52)
        for check in c['checks']:
            if len(check['path'])==2 and check['path'][0]=='diagnostics' and check['path'][1] in values:check['eq']=values[check['path'][1]]
        c['checks'] += [dict(path=['diagnostics',k],eq=v) for k,v in [('aes_scenario',True),('aes_commands_accepted',32),('aes_replies_consumed',32)]]
        c['allowed_differences']=['32 exact AES commands and mathematically verified replies; original CMAC processing continues.']
        c['unresolved_differences']=['Natural post-CMAC UART/app frontier is provisional; preserve semantic mismatch for saved audit; boot/display unverified.']
        control=modes['control'];control['comparison']=dict(policy='exact',path=['observed'])
        control['checks']=[dict(path=['diagnostics',k],eq=v) for k,v in [('accepted_commands',22),('replies',23),('frames',51),('commands',102),('application_drain_reads',20),('aes_scenario',False),('aes_commands_accepted',0),('aes_replies_consumed',0)]]
        control['checks'].append(dict(path=['selected_observation'],eq_source=['selected_observation']))
        control['allowed_differences']=['Default-off AES preserves existing P256-complete CPU/events exactly.']
        control['unresolved_differences']=['AES remains unsupported with the new scenario disabled.']
    plan['aes_fixture_sha256']=sha(fixture)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,indent=2)+'\n')
    print('Prepared private AES candidate',a.case,'32 verified pairs')


if __name__=='__main__':main()
