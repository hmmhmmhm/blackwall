"""Original ARM privacy/data-length initialization with explicit test-only entropy."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from inspect_application_vendor_address import call, sha
from inspect_nema_blocking_wait import cpu, WORK


def queued(u, ring):
    fields = list(struct.unpack('<6I', bytes(u.mem_read(ring, 24))))
    if fields[2] == 0 and fields[0] == fields[1]:
        return None, fields
    if not 260 <= fields[2] <= fields[3] or fields[2] % 260 or fields[4] != 260:
        raise ValueError('Expected complete queued HCI records: ' + str(fields[:5]))
    record = fields[5] + fields[1]
    length = struct.unpack('<I', bytes(u.mem_read(record, 4)))[0]
    if not 4 <= length <= 259:
        raise ValueError('Invalid original queued length')
    packet = bytes(u.mem_read(record + 4, length))
    if packet[0] != 1 or len(packet) != packet[3] + 4:
        raise ValueError('Invalid original HCI framing')
    return packet, fields


def inspect(s, case, profile):
    capture = s / 'controller-information-main-01' / case
    audit_path = s / 'controller-information-saved-audit-01' / case / 'report.json'
    audit = json.loads(audit_path.read_text())
    if not audit['passed'] or audit['hardware_accessed']:
        raise ValueError('Unverified native starting state')
    for name, digest in audit['capture_hashes'].items():
        if sha(capture / name) != digest:
            raise ValueError('Changed native capture: ' + name)
    raw = (capture / 'main.bin').read_bytes()
    ram = (capture / 'exports/sram-full.bin').read_bytes()
    path = s / 'application-hci-transaction-source-02/report.json'
    pin = json.loads((s / 'application-hci-reset-verification-01/manifest.json').read_text())['retained_source_sha256']
    if sha(path) != pin:
        raise ValueError('Changed parser/ring source')
    ctx = next(r for r in json.loads(path.read_text())['cases'] if r['case'] == case)
    path = s / 'application-hci-source-01/report.json'
    pin = json.loads((s / 'application-hci-idle-verification-01/manifest.json').read_text())['source_report_sha256']
    if sha(path) != pin:
        raise ValueError('Changed original ring metadata')
    ring = next(r for r in json.loads(path.read_text())['cases'] if r['case'] == case)['tx_ring']
    u = cpu(raw, ram, WORK + 0xf000)
    rows = []
    tx, time, size = (251, 2120, 4) if profile == 'max-251' else (27, 328, 1)
    expected = [bytes.fromhex('012a2000'), bytes.fromhex('012f2000'),
                bytes.fromhex('01242004') + struct.pack('<2H', tx, time)]
    returns = [bytes([0, size]), bytes([0]) + struct.pack('<4H', tx, time, tx, time), bytes([0])]
    for index in range(11):
        packet, fields = queued(u, ring)
        if packet is None:
            break
        if index < 3:
            if packet != expected[index]:
                raise ValueError('Different privacy/length command')
            result = returns[index]
        else:
            if packet != bytes.fromhex('01182000'):
                break
            # Public deterministic vectors only; never secure entropy or device keys.
            result = bytes([0]) + bytes(range((index - 3) * 8 + 1, (index - 2) * 8 + 1))
        phases = [call(u, ctx['ring_pop'], (ring, 0, 1))]
        reply = bytes([4, 14, len(result) + 3, 1]) + packet[1:3] + result
        u.mem_write(WORK + 0x100, reply)
        phases.append(call(u, ctx['application_parser'], (WORK + 0x100, len(reply))))
        phases.append(call(u, ctx['upper_handler'], (1, 0)))
        successor, following = queued(u, ring)
        rows.append(dict(command=packet.hex(), reply=reply.hex(), ring_before=fields,
                         next_header=successor[:4].hex() if successor else None, next_length=len(successor) if successor else 0,
                         next_sha256=hashlib.sha256(successor).hexdigest() if successor else None, ring_after=following,
                         executions=phases))
    successor, fields = queued(u, ring)
    if len(rows) != 7 or successor is not None or any(r['command'] != '01182000' for r in rows[3:]):
        raise ValueError('Different bounded initialization sequence')
    # Without a completion event, popping the initial request must not manufacture a successor.
    control = cpu(raw, ram, WORK + 0xf000)
    no_event = [call(control, ctx['ring_pop'], (ring, 0, 1)),
                call(control, ctx['upper_handler'], (1, 0))]
    if queued(control, ring)[0] is not None:
        raise ValueError('No-event control unexpectedly progressed')
    return dict(case=case, profile=profile, resolving_list_size=size, max_tx_octets=tx,
                max_tx_time=time, raw_sha256=sha(capture / 'main.bin'),
                sram_sha256=sha(capture / 'exports/sram-full.bin'), audit_sha256=sha(audit_path),
                no_event_executions=no_event,
                stages=rows, next_header=successor[:4].hex() if successor else None, next_length=len(successor) if successor else 0,
                next_packet_sha256=hashlib.sha256(successor).hexdigest() if successor else None, ring_words=fields)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Preserve previous evidence')
    if a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Firmware-derived evidence must stay outside Git')
    rows = [inspect(a.simulator, c, profile) for c in ['stock24', 'stock23', 'cfw']
            for profile in ['max-251', 'min-27']]
    a.output.mkdir()
    (a.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output / 'report.json').write_text(json.dumps(dict(
        passed=True, cases=rows,
        engine='Original ARM on Unicorn M7; synthetic calls/stack/registers; validated native SRAM',
        entropy='Deterministic public test vectors; not secure randomness',
        native_executions=0, hardware_accessed=False, boot_verified=False, display_verified=False,
    ), indent=2) + '\n')
    for row in rows:
        print(row['case'], row['profile'], 'stages', len(row['stages']), 'next', row['next_header'], 'length', row['next_length'])


if __name__ == '__main__':
    main()
