"""Prepare a private source-pinned vendor startup candidate; never access hardware."""
import argparse,hashlib,json
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('case',choices=['stock24','stock23','cfw']);p.add_argument('output',type=Path);a=p.parse_args();root=Path(__file__).resolve().parents[1]
    if a.simulator.resolve().is_relative_to(root) or not a.output.resolve().is_relative_to(a.simulator.resolve()):
        raise ValueError('Address-bearing plans must stay in the private simulator directory outside Git')
    if a.output.exists():raise ValueError('Preserve previous plan')
    source_path=a.simulator/'vendor-startup-source-01/report.json';source=json.loads(source_path.read_text())
    if not source['passed'] or source['original_arm_scenarios']!=777:raise ValueError('Unverified original startup contract')
    row=next(r for r in source['cases'] if r['case']==a.case)
    source_root='application-hci-reset-main-02' if a.case=='stock24' else 'application-hci-reset-main-01'
    cap=a.simulator/source_root/a.case
    if sha(cap/'main.bin')!=row['raw_sha256'] or sha(cap/'exports/sram-full.bin')!=row['sram_sha256']:raise ValueError('Source image/SRAM changed')
    old=json.loads((root/'tools/application-hci-reset-guest-stop-candidate.json').read_text());old['id']='vendor-startup-v1';old['source_root']=source_root;old['execution_mode']='until-guest-stop';old.pop('reviewed_sources',None)
    baseline=a.simulator/'vendor-startup-research-01/base-reset.cs';candidate=root/'tools/renode-em9305-reset.cs'
    old['components']=[dict(name='vendor-startup-peer',baseline=str(baseline.relative_to(a.simulator)),candidate='tools/renode-em9305-reset.cs',before_sha256=sha(baseline),after_sha256=sha(candidate))]
    old['board_edits']=[dict(before='    applicationReset: true\n',after='    applicationReset: true\n    vendorStartupHex: "'+row['startup_sequence_hex']+'"\n')]
    old['diagnostics']=old['diagnostics'][:-1]+",vendor_commands_accepted=int(m['sysbus.iom6'].SpiWordTransfer.Peer.VendorCommandsAccepted),vendor_feature_profile=('source-cfw-mask' if '7d'=="+repr(row['feature_mask'])+"[2:4] else 'source-stock-mask'),vendor_scenario=bool(m['sysbus.iom6'].SpiWordTransfer.Peer.HasVendorStartupScenario))"
    for case,modes in old['semantics'].items():
        c=modes['candidate'];c['boundary']['pc']=0x501676 if case=='stock24' else 0x549fce
        c['checks']=[x for x in c['checks'] if x['path'] not in [['diagnostics','application_drain_reads']]]
        for x in c['checks']:
            if x['path'] in [['diagnostics','accepted_commands'],['diagnostics','replies']]:x['eq']=6
            if x['path']==['diagnostics','frames']:x['eq']=15
            if x['path']==['diagnostics','commands']:x['eq']=30
        c['checks'] += [dict(path=['diagnostics','application_drain_reads'],eq=4),dict(path=['diagnostics','vendor_commands_accepted'],eq=3),dict(path=['diagnostics','vendor_scenario'],eq=True)]
        c['allowed_differences']=['Explicit source-derived fc43/fff2/fcc4 scenario with 7/7/9-byte normal fixtures. No controller reset or persistence modeled.']
        c['unresolved_differences']=['Real controller reboot/persistence/RF behavior unknown; natural application/display not complete.']
        control=modes['control'];control['boundary']['pc']=0x501676 if case=='stock24' else 0x549fce
        control['checks']=[dict(path=['diagnostics',k],eq=v) for k,v in [('accepted_commands',3),('replies',3),('frames',7),('commands',14),('application_drain_reads',1),('vendor_commands_accepted',0),('vendor_scenario',False)]]
        control['allowed_differences']=['Default-off vendor scenario preserves source CPU/events exactly.'];control['unresolved_differences']=['Vendor startup remains unsupported.']
    old['startup_source_contract_sha256']=sha(source_path)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(old,indent=2)+'\n');print('Prepared private plan',a.case,'sequence hash',hashlib.sha256(bytes.fromhex(row['startup_sequence_hex'])).hexdigest())


if __name__=='__main__':main()
