"""Audit-backed original positive header reaches the unsupported RDY phase."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior result')
    source_map=a.simulator/'em9305-hci-framing-03/report.json';mapped=json.loads(source_map.read_text());rows=[]
    if not mapped['passed']:raise ValueError('Unverified source contract')
    for row in mapped['cases']:
        case=row['case'];source=a.simulator/'em9305-hci-payload-boundary-main-01'/case
        audit_path=a.simulator/'em9305-hci-payload-boundary-audit-01'/case/'report.json';audit=json.loads(audit_path.read_text())
        if not audit['passed'] or not audit['execution_passed'] or audit['capture_hashes']['report.json']!=sha(source/'report.json'):raise ValueError('Unverified native capture')
        r=json.loads((source/'report.json').read_text());c=row['contract'];regs=r['observed']['register_context'];stack=r['observed']['stack_context']
        if sha(source/'main.bin')!=row['raw_sha256']:raise ValueError('Changed original main')
        if regs['r15']!=c['read']+0x15a or regs['r8']!=c['rdy_address'] or regs['r9']!=4 or regs['r4']!=0:raise ValueError('Not original post-header RDY consumer')
        if stack['words'][0]!=0x4c0 or stack['base']!=regs['r13']:raise ValueError('Original positive header differs')
        expected=dict(commands=1,completed=1,bytes_exchanged=2,rx_words=0,last_rx_word=0x4c0,peer_tx='8100',peer_finished=1,spi_config=0,cs_output_high=False)
        if any(r['diagnostics'][k]!=v for k,v in expected.items()):raise ValueError('Header scenario/state differs')
        guards=[g for g in r['observed']['guards'] if g['accesses']]
        if len(guards)!=1 or guards[0]['address']!=c['rdy_address'] or guards[0]['operation']!='read':raise ValueError('Different phase boundary')
        rows.append(dict(case=case,raw_sha256=row['raw_sha256'],native_report_sha256=sha(source/'report.json'),saved_audit_sha256=sha(audit_path),
                         native_original_semantic_passed=r['semantic_validation']['passed'],reviewed_boundary_semantic_passed=True,
                         post_header_pc=regs['r15'],original_header_word=stack['words'][0],original_parsed_length=regs['r9'],original_hal_status=regs['r4'],
                         gpio149_high=False,iom_transaction_finished=1,payload_read_not_started=True,expected_payload_read_hal=c['payload_hal'],
                         payload_event_not_supplied=True))
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());report=dict(passed=True,cases=rows,source_map_sha256=sha(source_map),
        guest_executed=False,hardware_accessed=False,physical_pin_mapping_verified=False,
        original_first_prediction_preserved=True,no_execution_plan_change_for_revised_audit=True,
        next_dependency='Phase-aware GPIO149/CS and RDY, then RX-only payload; do not equate IOM FinishTransmission with HCI CSN rising')
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),positive_header_length=4,payload_supplied=False)))


if __name__=='__main__':main()
