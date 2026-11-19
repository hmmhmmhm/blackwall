"""Audit saved natural vendor startup transactions and next HCI mask packet."""
import argparse,json,struct
from pathlib import Path
from inspect_application_vendor_address import sha
from run_native_candidate import memory_exports,validate_memory_exports


def inspect(s,case,control=False):
    f=s/('vendor-startup-control-01' if control else 'vendor-startup-main-01')/case
    ap=s/'vendor-startup-saved-audit-01'/('control' if control else case)/'report.json'
    a=json.loads(ap.read_text());r=json.loads((f/'report.json').read_text());p=json.loads((f/'plan.json').read_text())
    if not a['passed'] or not r['execution_passed'] or r['hardware_accessed']:raise ValueError('Unverified saved capture')
    for name,digest in a['capture_hashes'].items():
        if sha(f/name)!=digest:raise ValueError('Changed capture '+name)
    validate_memory_exports(f,memory_exports(p),r['memory_exports'])
    d=r['diagnostics']
    if control:
        prior=json.loads((s/p['source_root']/case/'report.json').read_text())
        if r['observed']!=prior['observed'] or r['selected_observation']!=prior['selected_observation']:raise ValueError('Default-off CPU/events changed')
        if (d['accepted_commands'],d['replies'],d['frames'],d['commands'],d['vendor_commands_accepted'],d['vendor_scenario'])!=(3,3,7,14,0,False):raise ValueError('Default-off peer changed')
        evidence=dict(source_cpu_events_exact=True)
    else:
        sp=s/'vendor-startup-source-01/report.json'
        if sha(sp)!=p['startup_source_contract_sha256']:raise ValueError('Changed startup source contract')
        source=next(row for row in json.loads(sp.read_text())['cases'] if row['case']==case)
        if sha(f/'main.bin')!=source['raw_sha256']:raise ValueError('Changed original main')
        for key,value in [('accepted_commands',6),('replies',6),('frames',15),('commands',30),('vendor_commands_accepted',3),('vendor_scenario',True),('application_drain_reads',4),('peer_state','Complete'),('retention_unique',True)]:
            if d[key]!=value:raise ValueError('Different transaction history '+key)
        fixture=next(e['after'].split('vendorStartupHex: "')[1].split('"')[0] for e in p['board_edits'] if 'vendorStartupHex' in e['after'])
        if fixture!=source['startup_sequence_hex']:raise ValueError('Different explicit command sequence')
        ring_path=s/'application-hci-source-01/report.json';pin=json.loads((s/'application-hci-idle-verification-01/manifest.json').read_text())['source_report_sha256']
        if sha(ring_path)!=pin:raise ValueError('Changed original ring source')
        old=next(row for row in json.loads(ring_path.read_text())['cases'] if row['case']==case)
        ram=(f/'exports/sram-full.bin').read_bytes();fields=list(struct.unpack_from('<6I',ram,old['tx_ring']-0x20000000))
        if fields[:5]!=[1300,1040,260,2080,260] or fields[5]!=old['ring_words'][5]:raise ValueError('Different consumed/queued records')
        record=fields[5]+fields[1];length=struct.unpack_from('<I',ram,record-0x20000000)[0];packet=ram[record-0x20000000+4:record-0x20000000+4+length]
        regs=r['observed']['register_context'];guards=[g for g in r['observed']['guards'] if g['accesses']]
        pc=0x501676 if case=='stock24' else 0x549fce
        if length!=12 or packet.hex()!=source['next_packet'] or packet[:4].hex()!='01010c08' or (regs['r8'],regs['r9'],regs['r10'])!=(12,0,record+4):raise ValueError('Different next original write packet')
        if r['observed']['pc']!=pc or len(guards)!=1 or (guards[0]['address'],guards[0]['width'],guards[0]['operation'])!=(0x40010410,4,'read'):raise ValueError('Different unsupported command boundary')
        evidence=dict(next_packet=packet.hex(),next_packet_transmitted=False,ring_words=fields,write_ready_pc=pc,source_feature_mask=source['feature_mask'],vendor_payload_chunks=[2,2,1],vendor_replies=[7,7,9])
    return dict(case=case,control=control,evidence=evidence,original_semantic_passed=r['semantic_validation']['passed'],reviewed_audit_passed=True,report_sha256=sha(f/'report.json'),audit_sha256=sha(ap))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior result')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']]+[inspect(a.simulator,'stock24',True)]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_rerun=False,hardware_accessed=False,controller_reset_or_persistence_known=False,physical_2m_phy_verified=False,boot_verified=False,display_verified=False),indent=2)+'\n');print('saved vendor startup:3 images/default-off verified; next HCI mask remains queued')


if __name__=='__main__':main()
