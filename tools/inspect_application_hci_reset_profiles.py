"""Saved natural Reset transaction and next queued command; no native replay."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from run_native_candidate import memory_exports, validate_memory_exports


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(simulator, case, control=False, capture_folder=None, audit_folder='application-hci-reset-saved-audit-01'):
    folder = capture_folder or ('application-hci-reset-control-01' if control else 'application-hci-reset-main-01')
    capture = simulator / folder / case
    audit = simulator / audit_folder / ('control' if control else case) / 'report.json'
    report = json.loads((capture / 'report.json').read_text())
    reviewed = json.loads(audit.read_text())
    plan = json.loads((capture / 'plan.json').read_text())
    if not report['passed'] or not reviewed['passed'] or report['hardware_accessed']:
        raise ValueError('Unverified native source')
    for name, digest in reviewed['capture_hashes'].items():
        if sha(capture / name) != digest:
            raise ValueError('Changed native source ' + name)
    validate_memory_exports(capture, memory_exports(plan), report['memory_exports'])
    d = report['diagnostics']
    if control:
        prior = json.loads((simulator / plan['source_root'] / case / 'report.json').read_text())
        if report['observed'] != prior['observed'] or report['selected_observation'] != prior['selected_observation']:
            raise ValueError('Default-off CPU/events changed')
        evidence = dict(source_cpu_events_exact=True)
    else:
        for key, expected in [('accepted_commands',3),('replies',3),('frames',7),('commands',14),
                              ('application_idle_reads',4),('application_drain_reads',1),
                              ('application_reset_command_hex','01030c00'),('peer_state','Complete')]:
            if d[key] != expected:
                raise ValueError('Unexpected transaction history ' + key)
        source = json.loads((simulator / 'application-hci-source-01/report.json').read_text())
        old = next(row for row in source['cases'] if row['case'] == case)
        if sha(capture/'main.bin') != old['raw_sha256']:
            raise ValueError('Original main changed')
        ram = (capture/'exports/sram-full.bin').read_bytes()
        fields = list(struct.unpack_from('<6I',ram,old['tx_ring']-0x20000000))
        if fields[:5] != [520,260,260,2080,260] or fields[5] != old['ring_words'][5]:
            raise ValueError('Reset record not consumed / next record not queued')
        record = fields[5]+fields[1]
        length = struct.unpack_from('<I',ram,record-0x20000000)[0]
        packet = ram[record-0x20000000+4:record-0x20000000+4+length]
        regs = report['observed']['register_context']
        if length != 10 or packet[:4].hex() != '0143fc06' or (regs['r8'],regs['r9'],regs['r10']) != (10,0,record+4):
            raise ValueError('Original write helper did not receive next packet')
        expected_pc = 0x501676 if case == 'stock24' else 0x549fce
        guards = [g for g in report['observed']['guards'] if g['accesses']]
        if report['observed']['pc'] != expected_pc or len(guards) != 1 or (guards[0]['address'],guards[0]['width'],guards[0]['operation']) != (0x40010410,4,'read'):
            raise ValueError('Different unsupported fourth command boundary')
        evidence = dict(reset_record_consumed=True,next_record_length=10,next_opcode=0xfc43,
                        next_packet_sha256=hashlib.sha256(packet).hexdigest(),ring_words=fields,
                        next_packet_transmitted=False,write_ready_pc=expected_pc)
    return dict(case=case,control=control,evidence=evidence,report_sha256=sha(capture/'report.json'),audit_sha256=sha(audit))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--stock24-completion',action='store_true')
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Preserve prior evidence')
    rows = [inspect(a.simulator,c) for c in ['stock23','cfw']]
    rows.append(inspect(a.simulator,'stock23',True))
    if a.stock24_completion:
        rows.append(inspect(a.simulator,'stock24',capture_folder='application-hci-reset-main-02',audit_folder='application-hci-reset-saved-audit-02'))
    failure = a.simulator/'application-hci-reset-main-01/stock24/failure.json'
    failed = json.loads(failure.read_text())
    if failed['execution_status'] != 'host-observation-ended-before-guest-stop' or failed['cpu_report_present']:
        raise ValueError('Different stock24 incomplete capture')
    for name,digest in failed['capture_files_sha256'].items():
        if sha(failure.parent/name) != digest:
            raise ValueError('Changed incomplete stock24 capture')
    a.output.mkdir(parents=True)
    (a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(
        passed=True,verified_cases=rows,stock24_natural_transaction_verified=a.stock24_completion,
        stock24_incomplete_capture_sha256=sha(failure),native_rerun=False,
        hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('saved Reset transactions: stock23/Faceclaw and default-off verified; stock24 '+('verified' if a.stock24_completion else 'incomplete'))


if __name__ == '__main__':
    main()
