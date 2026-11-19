"""Saved native marker fixtures: cleared continuation, pending write intent, unknown/off."""
import argparse,json,hashlib,struct
from pathlib import Path
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from run_native_candidate import memory_exports,validate_memory_exports

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def inspect(s,folder,case,an,kind):
    f=s/folder/case;r=json.loads((f/'report.json').read_text());p=json.loads((f/'plan.json').read_text());ap=s/'ota-marker-read-saved-audit-01'/an/'report.json';a=json.loads(ap.read_text())
    if not r['execution_passed'] or not a['passed'] or r['hardware_accessed']:raise ValueError('Unverified capture')
    for n,h in a['capture_hashes'].items():
        if sha(f/n)!=h:raise ValueError('Changed capture '+n)
    validate_memory_exports(f,memory_exports(p),r['memory_exports']);raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();d=r['diagnostics'];regs=r['observed']['register_context'];guards=[g for g in r['observed']['guards'] if g['accesses']]
    if len(guards)!=1 or d['accepted_commands']!=2 or d['replies']!=2:raise ValueError('Different boundary/BLE history')
    evidence={}
    if kind in ['cleared','pending']:
        if d['marker_profile']!=kind or d['marker_reads']!=3 or d['marker_startup_reads']!=1 or d['marker_setter_reads']!=2 or d['keydb_data_bytes']!=3680:raise ValueError('Different original marker consumers')
        if kind=='cleared':
            pc=r['observed']['pc'];expected=0x4dd1d4 if case=='stock24' else 0x4c9990
            if pc!=expected or guards[0]['address']!=0x40010410 or guards[0]['operation']!='read' or regs['r0']!=0x40010410:raise ValueError('Different GPIO117 consumer')
            i=decode(raw,pc-12,4)[0];load=decode(raw,pc-4,4)[0];bit=decode(raw,pc+2,4)[0]
            if (i.mnemonic,i.op_str)!=('cmp.w','r0, #0x3e8') or literal(raw,load)!=0x40010410 or bit.op_str!='r0, r0, #0x15, #1':raise ValueError('Unidentified GPIO source loop')
            evidence=dict(next_gpio_address=0x40010410,next_gpio_bit=21,source_poll_limit=1000,new_read_pc=pc,ready_value_provided_at_new_consumer=False)
        else:
            if r['observed']['pc']!=0x494ada or guards[0]['address']!=0x40021014 or guards[0]['value']!=0x3f or regs['r6']*4+0x400000!=0x7fe000 or regs['r7']!=4:raise ValueError('Different marker write preparation')
            buffer=regs['r5'];data=ram[buffer-0x20000000:buffer-0x20000000+16]
            if data!=b'\xff'*16:raise ValueError('Different pending clear payload')
            key,lr=struct.unpack_from('<II',ram,regs['r13']-0x20000000+8)
            if key!=0x12344321 or lr!=0x4f5837:raise ValueError('Different cache call frame')
            evidence=dict(program_destination=0x7fe000,words=4,payload=data.hex(),program_constant=key,actual_mram_program_executed=False,fixture_still_pending=True)
    else:
        prior=json.loads((s/p['source_root']/case/'report.json').read_text())
        if d['marker_reads']!=0 or r['observed']!=prior['observed'] or r['selected_observation']!=prior['selected_observation']:raise ValueError('Unknown/off changed CPU or events')
        evidence=dict(source_cpu_events_exact=True,marker_value_not_provided=True)
    return dict(case=case,kind=kind,diagnostics=d,evidence=evidence,original_semantic_passed=r['semantic_validation']['passed'],reviewed_audit_passed=True,report_sha256=sha(f/'report.json'),audit_sha256=sha(ap))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve existing evidence')
    rows=[inspect(a.simulator,'ota-marker-cleared-main-01',c,c,'cleared') for c in ['stock24','stock23','cfw']]
    rows +=[inspect(a.simulator,'ota-marker-pending-main-01','stock24','pending','pending'),inspect(a.simulator,'ota-marker-unknown-main-01','stock24','unknown','unknown'),inspect(a.simulator,'ota-marker-read-control-01','stock24','control','control')]
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_rerun=False,hardware_accessed=False,real_marker_known=False,marker_write_reset_or_update_executed=False,whole_main_boot_verified=False,display_verified=False),indent=2)+'\n');print('saved marker profiles:6/6 passed')
if __name__=='__main__':main()
