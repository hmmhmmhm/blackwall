"""Verify saved natural application TX entries without replaying the CPU."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from run_native_candidate import memory_exports, validate_memory_exports


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(simulator, case, control=False):
    folder = 'application-hci-idle-control-01' if control else 'application-hci-idle-main-01'
    capture = simulator / folder / case
    audit = simulator / 'application-hci-idle-saved-audit-01' / ('control' if control else case) / 'report.json'
    report = json.loads((capture / 'report.json').read_text())
    reviewed = json.loads(audit.read_text())
    plan = json.loads((capture / 'plan.json').read_text())
    if not report['execution_passed'] or not reviewed['passed'] or report['hardware_accessed']:
        raise ValueError('Unverified native execution')
    for name, digest in reviewed['capture_hashes'].items():
        if sha(capture / name) != digest:
            raise ValueError('Changed saved capture: ' + name)
    validate_memory_exports(capture, memory_exports(plan), report['memory_exports'])
    source = json.loads((simulator / 'application-hci-source-01/report.json').read_text())
    if not source['passed'] or source['original_arm_scenarios'] != 27:
        raise ValueError('Unverified original ARM source contract')
    entry = next(row for row in source['cases'] if row['case'] == case)
    if sha(capture / 'main.bin') != entry['raw_sha256']:
        raise ValueError('Different original main image')
    diagnostics = report['diagnostics']
    for name, expected in [('accepted_commands', 2), ('replies', 2), ('frames', 5),
                           ('commands', 10), ('peer_state', 'Complete'),
                           ('marker_reads', 3), ('keydb_data_bytes', 3680),
                           ('application_idle_reads', 0 if control else 1)]:
        if diagnostics[name] != expected:
            raise ValueError('Different transport history: ' + name)
    if control:
        prior = json.loads((simulator / plan['source_root'] / case / 'report.json').read_text())
        if report['observed'] != prior['observed'] or report['selected_observation'] != prior['selected_observation']:
            raise ValueError('Default-off control changed CPU/events')
        evidence = dict(source_cpu_events_exact=True)
    else:
        pc = 0x501676 if case == 'stock24' else 0x549fce
        guards = [g for g in report['observed']['guards'] if g['accesses']]
        regs = report['observed']['register_context']
        if report['observed']['pc'] != pc or len(guards) != 1:
            raise ValueError('Different native write-ready boundary')
        guard = guards[0]
        if (guard['address'], guard['operation'], guard['width']) != (0x40010410, 'read', 4):
            raise ValueError('Different unsupported peripheral operation')
        if (regs['r0'], regs['r8'], regs['r9'], regs['r10']) != (0x40010410, 4, 0, entry['queued_pointer']):
            raise ValueError('Original writer did not receive the queued packet')
        ram = (capture / 'exports/sram-full.bin').read_bytes()
        packet = ram[regs['r10'] - 0x20000000:regs['r10'] - 0x20000000 + 4]
        ring = struct.unpack_from('<6I', ram, entry['tx_ring'] - 0x20000000)
        if packet.hex() != '01030c00' or list(ring) != entry['ring_words']:
            raise ValueError('Packet or ring changed before transmission')
        evidence = dict(write_ready_pc=pc, packet=packet.hex(), packet_length=4,
                        packet_pointer=regs['r10'], ring_words=list(ring),
                        queued_packet_transmitted=False, ring_not_consumed=True)
    return dict(case=case, control=control, evidence=evidence,
                report_sha256=sha(capture / 'report.json'), audit_sha256=sha(audit))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve existing evidence')
    rows = [inspect(args.simulator, case) for case in ['stock24', 'stock23', 'cfw']]
    rows.append(inspect(args.simulator, 'stock24', control=True))
    args.output.mkdir(parents=True)
    (args.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (args.output / 'report.json').write_text(json.dumps(dict(
        passed=True, cases=rows, native_rerun=False, hardware_accessed=False,
        queued_hci_reset_transmitted=False, full_irq_lifecycle_verified=False,
        boot_verified=False, display_verified=False), indent=2) + '\n')
    print('saved application HCI profiles: 4/4 passed; packet remains queued')


if __name__ == '__main__':
    main()
