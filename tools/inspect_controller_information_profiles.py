"""Verify saved natural mock-information consumers and next privacy-capacity query."""
import argparse,json,struct
from pathlib import Path
from prepare_vendor_startup_candidate import sha
from run_native_candidate import memory_exports,validate_memory_exports


def inspect(s,case,kind='basic'):
    folder={'basic':'controller-information-main-01','large':'controller-information-large-01','control':'controller-information-control-01'}[kind]
    f=s/folder/case;ap=s/'controller-information-saved-audit-01'/(case if kind=='basic' else kind)/'report.json';r=json.loads((f/'report.json').read_text());a=json.loads(ap.read_text());p=json.loads((f/'plan.json').read_text())
    if not r['passed'] or not a['passed'] or r['hardware_accessed']:raise ValueError('Unverified saved native capture')
    for n,digest in a['capture_hashes'].items():
        if sha(f/n)!=digest:raise ValueError('Changed capture '+n)
    validate_memory_exports(f,memory_exports(p),r['memory_exports']);d=r['diagnostics']
    if kind=='control':
        prior=json.loads((s/p['source_root']/case/'report.json').read_text())
        if r['observed']!=prior['observed'] or r['selected_observation']!=prior['selected_observation']:raise ValueError('Default-off changed CPU/events')
        expected={'accepted_commands':10,'replies':10,'frames':26,'commands':52,'information_commands_accepted':0,'information_scenario':False,'information_profile':'none'};evidence=dict(source_cpu_events_exact=True)
    else:
        sp=s/'controller-information-source-01/report.json'
        if sha(sp)!=p['information_source_contract_sha256']:raise ValueError('Changed original information source')
        row=next(x for x in json.loads(sp.read_text())['cases'] if x['case']==case);profile=next(x for x in row['samples'] if x['profile']==d['information_profile'])
        if sha(f/'main.bin')!=row['raw_sha256']:raise ValueError('Different original main')
        expected={'accepted_commands':14,'replies':14,'frames':34,'commands':68,'information_commands_accepted':4,'information_scenario':True,'vendor_commands_accepted':3,'standard_commands_accepted':4,'application_drain_reads':12,'peer_state':'Complete','mock_acl_length':profile['acl_length'],'mock_acl_packets':profile['acl_packets']}
        if profile['profile']!=('le-large-251x8' if kind=='large' else 'le-basic-27x4'):raise ValueError('Wrong comparison profile')
        ram=(f/'exports/sram-full.bin').read_bytes();base=row['control_base'];read=lambda address,n:ram[address-0x20000000:address-0x20000000+n]
        if struct.unpack('<H',read(base+0x7e,2))[0]!=profile['acl_length'] or read(base+0x82,2)!=bytes([profile['acl_packets']]*2) or read(base+0x84,1)!=bytes([profile['filter_accept_list_size']]):raise ValueError('Original native metadata consumers differ')
        if read(base+0x88,8).hex()!=profile['features'] or read(row['states_slot'],8).hex()!=profile['states']:raise ValueError('Original native features/states differ')
        ring_path=s/'application-hci-source-01/report.json';pin=json.loads((s/'application-hci-idle-verification-01/manifest.json').read_text())['source_report_sha256']
        if sha(ring_path)!=pin:raise ValueError('Changed original ring source')
        old=next(x for x in json.loads(ring_path.read_text())['cases'] if x['case']==case);fields=list(struct.unpack('<6I',read(old['tx_ring'],24)));record=fields[5]+fields[1];n=struct.unpack('<I',read(record,4))[0];packet=read(record+4,n);regs=r['observed']['register_context'];pc=0x501676 if case=='stock24' else 0x549fce
        if fields[:5]!=[1300,1040,260,2080,260] or fields[5]!=old['ring_words'][5] or packet.hex()!='012a2000' or n!=4 or (regs['r8'],regs['r9'],regs['r10'])!=(4,0,record+4) or r['observed']['pc']!=pc:raise ValueError('Different next privacy-capacity command')
        guards=[g for g in r['observed']['guards'] if g['accesses']]
        if len(guards)!=1 or (guards[0]['address'],guards[0]['width'],guards[0]['operation'])!=(0x40010410,4,'read'):raise ValueError('Different unsupported next command boundary')
        evidence=dict(profile=profile['profile'],native_acl_length=profile['acl_length'],native_packet_count_copies=[profile['acl_packets']]*2,native_filter_size=profile['filter_accept_list_size'],native_features=profile['features'],native_states=profile['states'],next_packet=packet.hex(),next_packet_transmitted=False,write_ready_pc=pc)
    for key,value in expected.items():
        if d[key]!=value:raise ValueError('Different transaction history '+key)
    return dict(case=case,kind=kind,evidence=evidence,report_sha256=sha(f/'report.json'),audit_sha256=sha(ap))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve previous evidence')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']]+[inspect(a.simulator,'stock24','large'),inspect(a.simulator,'stock24','control')];a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_rerun=False,actual_acl_transmission_or_credit_consumption_verified=False,physical_controller_data_known=False,hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n');print('saved information profiles:3 images/large comparison/default-off verified')


if __name__=='__main__':main()
