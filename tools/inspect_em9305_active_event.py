"""Verify natural active-event acceptance/rejection using saved native log and RAM."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from inspect_em9305_hci_framing import discover,literal
from inspect_ambiq_target import decode
from run_native_candidate import memory_exports,validate_memory_exports

BASE,SRAM=0x438000,0x20000000


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(simulator,folder,case,audit_name,event_hex,accepted):
    source=simulator/folder/case;r=json.loads((source/'report.json').read_text());plan=json.loads((source/'plan.json').read_text())
    audit_path=simulator/'em9305-active-event-saved-audit-01'/audit_name/'report.json';audit=json.loads(audit_path.read_text())
    if not audit['passed'] or audit['capture_hashes']['report.json']!=sha(source/'report.json'):raise ValueError('Unverified native evidence')
    validate_memory_exports(source,memory_exports(plan),r['memory_exports'])
    raw=(source/'main.bin').read_bytes();ram=(source/'exports/sram-full.bin').read_bytes();c=discover(raw)
    if plan['runtime_edits'] or r['hardware_accessed']:raise ValueError('Unexpected execution scope')
    instruction=decode(raw,c['read']-0x474,4)[0]
    if instruction.op_str.split(',')[0]!='r5':raise ValueError('Unknown original RF error-state pointer')
    rf_state=literal(raw,instruction)
    state=ram[rf_state-SRAM]
    if state!=(0 if accepted else 5):raise ValueError('Original RF state did not accept/reject event')
    d=r['diagnostics'];expected=dict(commands=2,headers=1,payloads=1,frames=1,peer_state='Consumed' if accepted else 'Queued',active_log_seen=accepted,retention_reads=2)
    if any(d[k]!=v for k,v in expected.items()):raise ValueError('Native event path differs')
    if ('eventHex: "'+event_hex+'"') not in (source/'board.repl').read_text():raise ValueError('Different virtual event')
    guards=[g for g in r['observed']['guards'] if g['accesses']]
    if len(guards)!=1 or guards[0]['address']!=0x40010410 or guards[0]['operation']!='read':raise ValueError('Not unsupported HCI-write RDY boundary')
    pc=r['observed']['register_context']['r15']
    if pc!=(c['read']-0x260 if accepted else c['read']+0x72a):raise ValueError('Different HCI write consumer')
    # The success log belongs only to the original matched-event branch. This is
    # source identification, not a new observer or a claimed full PC trace.
    success=decode(raw,c['init']+0xba,4)[0]
    message=literal(raw,success);text=raw[message-BASE:message-BASE+32].split(b'\0')[0]
    if b'Enter active state' not in text:raise ValueError('Different original success message')
    return dict(case=case,accepted=accepted,event_hex=event_hex,original_rf_state_address=rf_state,original_rf_state=state,
                native_active_log_seen=d['active_log_seen'],source_success_log_address=message,source_success_log_call=c['init']+0xbe,
                next_pc=pc,next_guard=guards[0],diagnostics=d,native_original_semantic_passed=r['semantic_validation']['passed'],
                reviewed_audit_passed=True,native_report_sha256=sha(source/'report.json'),raw_sha256=sha(source/'main.bin'),
                sram_sha256=sha(source/'exports/sram-full.bin'),audit_sha256=sha(audit_path))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior result')
    rows=[inspect(a.simulator,'em9305-active-event-main-03',case,case,'04ff0101',True) for case in ['stock24','stock23','cfw']]
    rows.append(inspect(a.simulator,'em9305-wrong-event-main-01','stock24','wrong-event','04ff0103',False))
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());result=dict(passed=True,cases=rows,
        original_reset_main=True,inspection_guest_executed=False,hardware_accessed=False,real_controller_state_or_timing_verified=False,
        whole_ble_stack_or_main_boot_verified=False,display_verified=False,
        result='Original host accepted the explicit active event and rejected the wrong four-byte event; next write-phase RDY remains unsupported')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,accepted_images=3,rejected_event_cases=1)))


if __name__=='__main__':main()
