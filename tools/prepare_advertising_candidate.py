"""Prepare five source-pinned advertising transactions without device access."""
import argparse
import json
import re
from pathlib import Path
from prepare_vendor_startup_candidate import sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator',type=Path);p.add_argument('case',choices=['stock24','stock23','cfw'])
    p.add_argument('output',type=Path);p.add_argument('--guest-stop-control',action='store_true')
    a=p.parse_args();s=a.simulator;root=Path(__file__).resolve().parents[1]
    if s.resolve().is_relative_to(root) or not a.output.resolve().is_relative_to(s.resolve()) or a.output.exists():
        raise ValueError('Preserve firmware-derived plans outside Git')
    verification=json.loads((s/'address-advertising-verification-01/manifest.json').read_text())
    fixture=s/'address-advertising-verification-01/advertising-fixtures.json'
    if verification.get('passed') is not True or sha(fixture)!=verification['fixture_sha256']:
        raise ValueError('Changed verified advertising fixture')
    row=next(c for c in json.loads(fixture.read_text())['cases'] if c['case']==a.case)
    cap=s/'aes-peer-main-01'/a.case
    if sha(cap/'main.bin')!=row['main_sha256'] or sha(cap/'exports/sram-full.bin')!=row['sram_sha256']:
        raise ValueError('Changed source main or SRAM')
    pairs=row['pairs']
    if len(pairs)!=5:raise ValueError('Exactly five advertising transactions required')
    for pair,opcode,size in zip(pairs,[5,6,8,9,10],[10,19,36,36,5]):
        request=bytes.fromhex(pair['command']);reply=bytes.fromhex(pair['reply'])
        if len(request)!=size or request[:4]!=bytes([1,opcode,32,size-4]) or reply!=bytes([4,14,4,1,opcode,32,0]):
            raise ValueError('Invalid ordered advertising transaction')
    plan=json.loads((cap/'plan.json').read_text());plan.update(id='advertising-initialization-v1',source_root='aes-peer-main-01')
    plan.pop('reviewed_sources',None);plan.pop('execution_mode',None)
    plan.update(host_capture_seconds=120,memory_export_policy='paused-after-observation')
    baseline=s/'advertising-peer-research-01/base-reset.cs'
    plan['components']=[dict(name='bounded-advertising-peer',baseline=str(baseline.relative_to(s)),candidate='tools/renode-em9305-reset.cs',before_sha256=sha(baseline),after_sha256=sha(root/'tools/renode-em9305-reset.cs'))]
    anchors=re.findall(r'^    aesInitializationHex: "[0-9a-f]+"\n',(cap/'board.repl').read_text(),re.MULTILINE)
    if len(anchors)!=1:raise ValueError('Missing unique source AES board fixture')
    packed=''.join(pair['command']+pair['reply'] for pair in pairs)
    plan['board_edits']=[dict(before=anchors[0],after=anchors[0]+'    advertisingInitializationHex: "'+packed+'"\n')]
    peer="m['sysbus.iom6'].SpiWordTransfer.Peer"
    plan['diagnostics']=plan['diagnostics'][:-1]+",advertising_scenario=bool("+peer+".HasAdvertisingInitializationScenario),advertising_commands_accepted=int("+peer+".AdvertisingCommandsAccepted),advertising_replies_consumed=int("+peer+".AdvertisingRepliesConsumed))"
    for modes in plan['semantics'].values():
        previous=modes['candidate'];boundary=previous['boundary']
        modes['control']=dict(boundary=boundary,comparison=dict(policy='exact',path=['observed']),
            checks=[dict(path=['selected_observation'],eq_source=['selected_observation'])]+[dict(path=['diagnostics',k],eq=v) for k,v in [('advertising_scenario',False),('advertising_commands_accepted',0),('advertising_replies_consumed',0),('accepted_commands',54),('replies',55)]],
            allowed_differences=['New optional scenario remains disabled; original CPU/events must match.'],unresolved_differences=['Advertising remains unsupported when disabled.'])
        modes['candidate']=dict(boundary=dict(kind='bounded-capture'),
            comparison=dict(policy='prefix',path=['selected_observation','events']),
            checks=[dict(path=['diagnostics',k],eq=v) for k,v in [('advertising_scenario',True),('advertising_commands_accepted',5),('advertising_replies_consumed',5),('accepted_commands',59),('replies',60),('aes_commands_accepted',32),('aes_replies_consumed',32)]],
            allowed_differences=['Five exact advertising commands; explicit finite host observation and paused SRAM export.'],
            unresolved_differences=['Natural frontier is provisional; boot, radio advertising and display remain unverified.'])
    if a.guest_stop_control:
        plan.pop('host_capture_seconds');plan.pop('memory_export_policy');plan['execution_mode']='until-guest-stop'
    plan['advertising_fixture_sha256']=sha(fixture)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,indent=2)+'\n')
    print('Prepared private advertising candidate',a.case,'five verified pairs')


if __name__=='__main__':main()
