"""Verify saved standard-mask/identity transactions without rerunning the CPU."""
import argparse,json,struct
from pathlib import Path
from prepare_vendor_startup_candidate import sha
from run_native_candidate import memory_exports,validate_memory_exports


def inspect(s,case,control=False):
    f=s/('standard-hci-control-01' if control else 'standard-hci-main-01')/case;ap=s/'standard-hci-saved-audit-01'/('control' if control else case)/'report.json';r=json.loads((f/'report.json').read_text());a=json.loads(ap.read_text());p=json.loads((f/'plan.json').read_text())
    if not r['passed'] or not a['passed'] or r['hardware_accessed']:raise ValueError('Unverified capture')
    for n,digest in a['capture_hashes'].items():
        if sha(f/n)!=digest:raise ValueError('Changed capture '+n)
    validate_memory_exports(f,memory_exports(p),r['memory_exports']);d=r['diagnostics']
    if control:
        prior=json.loads((s/p['source_root']/case/'report.json').read_text())
        if r['observed']!=prior['observed'] or r['selected_observation']!=prior['selected_observation']:raise ValueError('Default-off changed CPU/events')
        expected={'accepted_commands':6,'replies':6,'frames':15,'commands':30,'standard_commands_accepted':0,'standard_scenario':False};evidence=dict(source_cpu_events_exact=True)
    else:
        sp=s/'standard-hci-source-01/report.json'
        if sha(sp)!=p['standard_source_contract_sha256']:raise ValueError('Changed standard software source')
        source=next(x for x in json.loads(sp.read_text())['cases'] if x['case']==case)
        if sha(f/'main.bin')!=source['raw_sha256']:raise ValueError('Different original main')
        expected={'accepted_commands':10,'replies':10,'frames':26,'commands':52,'standard_commands_accepted':4,'standard_scenario':True,'vendor_commands_accepted':3,'application_drain_reads':8,'peer_state':'Complete'}
        ring_path=s/'application-hci-source-01/report.json';pin=json.loads((s/'application-hci-idle-verification-01/manifest.json').read_text())['source_report_sha256']
        if sha(ring_path)!=pin:raise ValueError('Changed original ring metadata')
        old=next(x for x in json.loads(ring_path.read_text())['cases'] if x['case']==case);ram=(f/'exports/sram-full.bin').read_bytes();fields=list(struct.unpack_from('<6I',ram,old['tx_ring']-0x20000000))
        if fields[:5]!=[260,0,260,2080,260] or fields[5]!=old['ring_words'][5]:raise ValueError('Different wrapped queue state')
        record=fields[5]+fields[1];length=struct.unpack_from('<I',ram,record-0x20000000)[0];packet=ram[record-0x20000000+4:record-0x20000000+4+length];regs=r['observed']['register_context'];pc=0x501676 if case=='stock24' else 0x549fce
        if length!=4 or packet.hex()!='01022000' or (regs['r8'],regs['r9'],regs['r10'])!=(4,0,record+4) or r['observed']['pc']!=pc:raise ValueError('Different next information query')
        guards=[g for g in r['observed']['guards'] if g['accesses']]
        if len(guards)!=1 or (guards[0]['address'],guards[0]['width'],guards[0]['operation'])!=(0x40010410,4,'read'):raise ValueError('Different unsupported next command boundary')
        evidence=dict(ring_wrapped=True,ring_words=fields,next_packet=packet.hex(),next_packet_transmitted=False,write_ready_pc=pc,identity_reply_is_explicit_fixture=True)
    for key,value in expected.items():
        if d[key]!=value:raise ValueError('Different history '+key)
    return dict(case=case,control=control,evidence=evidence,report_sha256=sha(f/'report.json'),audit_sha256=sha(ap))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve previous evidence')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']]+[inspect(a.simulator,'stock24',True)];a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_rerun=False,physical_identity_or_controller_data_known=False,hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n');print('saved standard HCI:3 images/default-off verified; LE buffer query remains queued')


if __name__=='__main__':main()
