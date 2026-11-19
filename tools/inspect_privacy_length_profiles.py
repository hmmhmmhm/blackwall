"""Check saved natural M55 initialization and the actual next queued request."""
import argparse
import json
import struct
from pathlib import Path
from prepare_vendor_startup_candidate import sha
from native_replay import MAIN_LAYOUT


def inspect(s, folder, case, control=False):
    report=json.loads((folder/'report.json').read_text())
    if not report['passed'] or not report['execution_passed'] or report['control']!=control:
        raise ValueError('Unverified native capture')
    plan=json.loads((folder/'plan.json').read_text())
    if sha(folder/'main.bin')!=MAIN_LAYOUT[plan['cases'][case]][3]:
        raise ValueError('Changed original ARM image')
    for record in report['memory_exports']:
        if sha(folder/'exports'/record['name'])!=record['sha256']:
            raise ValueError('Changed SRAM export')
    raw=(folder/'exports/sram-full.bin').read_bytes()
    regs=report['observed']['register_context']
    if regs['r8']!=4 or regs['r9']!=0:
        raise ValueError('Different queued transport arguments')
    pointer=regs['r10'];offset=pointer-0x20000000
    if not 0<=offset<=len(raw)-4:
        raise ValueError('Packet outside captured SRAM')
    packet=raw[offset:offset+4]
    expected=bytes.fromhex('012a2000' if control else '01252000')
    if packet!=expected:
        raise ValueError('Different next native request')
    ring=0x20076304 if case=='stock24' else 0x20076cbc
    fields=list(struct.unpack_from('<6I',raw,ring-0x20000000))
    if fields[2:]!=[260,2080,260,fields[5]] or fields[5]+fields[1]+4!=pointer:
        raise ValueError('Different original queue linkage')
    count=14 if control else 21;d=report['diagnostics']
    if (d['accepted_commands'],d['replies'],d['frames'],d['commands'])!=(count,count,34 if control else 48,68 if control else 96):
        raise ValueError('Incomplete native command/reply sequence')
    if report['observed']['pc']!=(0x501676 if case=='stock24' else 0x549fce):
        raise ValueError('Different strict write-ready frontier')
    return dict(case=case,control=control,capture=str(folder.relative_to(s)),report_sha256=sha(folder/'report.json'),
        raw_sha256=sha(folder/'main.bin'),sram_sha256=sha(folder/'exports/sram-full.bin'),
        queued_packet=packet.hex(),ring_words=fields,commands=count,
        semantic_checks=len(report['semantic_validation']['checks']))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve evidence privately outside Git')
    captures=[('privacy-length-main-01','stock24',False),('privacy-length-main-02/stock23','stock23',False),
              ('privacy-length-main-02/cfw','cfw',False),('privacy-length-control-01/stock24','stock24',True),
              ('privacy-length-minimum-01/stock24','stock24',False)]
    rows=[inspect(s,s/f,c,control) for f,c,control in captures]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_captures=5,
        hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('Saved native captures verified:',len(rows),'with actual packet/ring/register linkage')


if __name__=='__main__':
    main()
