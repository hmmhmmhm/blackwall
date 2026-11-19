"""Validate bounded startup ring snapshots against pinned static call candidates."""
import argparse
import hashlib
import json
from pathlib import Path

from audit_assets import PINS


def analyze(report, anchor):
    profile = anchor['profile']
    if report['profile'] != profile or report['bundle_sha256'] != PINS[profile] or report['raw_main_sha256'] != anchor['main_sha256']:
        raise ValueError('Pinned main evidence differs')
    observed = report['observed']
    guards = [g for g in observed['guards'] if g['accesses']]
    capture = observed['gpu_ring_capture']
    if report['reason'] != 'unsupported-mmio' or len(guards) != 1 or guards[0]['accesses'] != 1 or (guards[0]['address'],guards[0]['width'],guards[0]['operation']) != (0x400900ec,4,'write'):
        raise ValueError('Expected blocked ring request absent')
    if not observed['gpu_id_initialization']['initialized'] or observed['gpu_interrupt_clear']['clears'] != 1 or observed['gpu_interrupt_clear']['commands_executed'] != 0 or observed['gpu_power_response']['phase'] != 'on':
        raise ValueError('Wrong initialization state')
    candidate = anchor['candidates'][0]
    if capture is None or capture['lr'] != int(candidate['call'],16)+17:
        raise ValueError('Snapshot is not from the static initialization candidate')
    words = capture['descriptor_words']
    if words is None or len(words) != 8:
        raise ValueError('Missing bounded descriptor')
    base = capture['ring_candidate_address']
    length = words[4]
    if not (words[1] == words[2] == base and 16 <= length <= 65536 and length % 4 == 0 and words[3] == length//4-4):
        raise ValueError('Descriptor and observed initialization layout differ')
    if capture['request_word'] != guards[0]['value'] or capture['request_word'] != base|6 or capture['request_low_bits'] != 6 or base%8:
        raise ValueError('Request/base relation differs')
    def sram(address, size):
        return address%4 == 0 and 0x20000000 <= address <= 0x20380000-size
    if not sram(base,length) or not sram(capture['descriptor_candidate_address'],32):
        raise ValueError('Snapshot extent outside SRAM')
    tail = capture['tail_unit_hypotheses']['bytes']
    if tail['address'] != base+length-16 or tail['hypothetical_length_bytes'] != length or tail['words'] != [0xff0000f0,base,0xff0000f4,length]:
        raise ValueError('Expected byte-length ring footer absent')
    prefix = capture['ring_prefix_words']
    if prefix != [0]*16:
        raise ValueError('Unexpected initial ring prefix')
    return dict(profile=profile,ring_address=hex(base),descriptor_address=hex(capture['descriptor_candidate_address']),
                observed_byte_length=length,initial_index=words[3],footer_words=[hex(w) for w in tail['words']],
                scope='snapshot and static-library layout agree for this startup; not allocation provenance, DMA or command execution proof')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('static_report',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--runtime-report',type=Path,action='append',required=True)
    args=p.parse_args()
    static=json.loads(args.static_report.read_text())
    if not static['passed']:
        raise ValueError('Need verified static candidates')
    rows=[]
    for path in args.runtime_report:
        data=path.read_bytes();runtime=json.loads(data)
        anchors=[a for a in static['rows'] if a['profile']==runtime['profile']]
        if len(anchors)!=1:raise ValueError('Need unique pinned profile')
        row=analyze(runtime,anchors[0]);row.update(runtime=str(path),runtime_sha256=hashlib.sha256(data).hexdigest());rows.append(row)
    if {r['profile'] for r in rows} != {'stock_base','stock_current','cfw'} or len(rows)!=3:
        raise ValueError('Need three distinct pinned profiles')
    args.output.mkdir(mode=0o700)
    (args.output/'report.json').write_text(json.dumps(dict(passed=True,rows=rows,static_sha256=hashlib.sha256(args.static_report.read_bytes()).hexdigest(),boot_verified=False,hardware_validated=False),indent=2)+'\n')
    print(json.dumps({'passed':True,'profiles':len(rows),'byte_lengths':[r['observed_byte_length'] for r in rows]}))


if __name__ == '__main__':
    main()
