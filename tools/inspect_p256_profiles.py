"""Verify saved natural M55 public-key events against original ARM follow-up requests."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from prepare_vendor_startup_candidate import sha
from native_replay import MAIN_LAYOUT

PUBLIC_POINT_BE=bytes.fromhex(
    '6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296'
    '4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5')


def inspect(s, case, folder, scenario, source):
    report=json.loads((folder/'report.json').read_text())
    if not report['passed'] or not report['execution_passed'] or report['hardware_accessed']:
        raise ValueError('Unverified native capture')
    plan=json.loads((folder/'plan.json').read_text())
    if sha(folder/'main.bin')!=MAIN_LAYOUT[plan['cases'][case]][3]:raise ValueError('Changed original main')
    for export in report['memory_exports']:
        if sha(folder/'exports'/export['name'])!=export['sha256']:raise ValueError('Changed native SRAM')
    ram=(folder/'exports/sram-full.bin').read_bytes();registers=report['observed']['register_context']
    control=scenario=='control';length=4 if control else 36
    if registers['r8']!=length or registers['r9']!=0:raise ValueError('Different actual transport arguments')
    pointer=registers['r10'];offset=pointer-0x20000000
    if not 0<=offset<=len(ram)-length:raise ValueError('Packet outside saved SRAM')
    packet=ram[offset:offset+length];digest=hashlib.sha256(packet).hexdigest()
    ring=0x20076304 if case=='stock24' else 0x20076cbc
    fields=list(struct.unpack_from('<6I',ram,ring-0x20000000))
    if fields[2:5]!=[260,2080,260] or fields[5]+fields[1]+4!=pointer:
        raise ValueError('Different native ring/packet linkage')
    if control:
        if packet!=bytes.fromhex('01252000'):raise ValueError('Changed default-off frontier')
        old=json.loads((s/'privacy-length-main-01/report.json').read_text())
        if report['observed']!=old['observed'] or report['selected_observation']!=old['selected_observation']:
            raise ValueError('Default-off CPU/events changed')
    else:
        name='completion-error' if scenario=='error' else 'status-then-public-point'
        sample=next(r for c in source['cases'] if c['case']==case for r in c['samples'] if r['scenario']==name)
        if packet[:4]!=bytes.fromhex('01172020') or digest!=sample['next_after_owner_sha256']:
            raise ValueError('Natural request differs from original isolated owner execution')
    d=report['diagnostics']
    expected=(21,21,48,96,0) if control else (22,23,51,102,2)
    if tuple(d[k] for k in ['accepted_commands','replies','frames','commands','p256_events_consumed'])!=expected:
        raise ValueError('Incomplete command/event sequence')
    if report['observed']['pc']!=(0x501676 if case=='stock24' else 0x549fce):
        raise ValueError('Different write-ready frontier')
    initial=s/('privacy-length-main-01' if case=='stock24' else 'privacy-length-main-02/'+case)/'exports/sram-full.bin'
    if PUBLIC_POINT_BE in initial.read_bytes():raise ValueError('Test point was already present in the initial SRAM')
    converted=[];start=0
    while True:
        start=ram.find(PUBLIC_POINT_BE,start)
        if start<0:break
        converted.append(0x20000000+start);start+=64
    if bool(converted)!=(scenario=='nominal'):
        raise ValueError('Different converted test-point witness in actual SRAM')
    return dict(case=case,scenario=scenario,capture=str(folder.relative_to(s)),report_sha256=sha(folder/'report.json'),
        main_sha256=sha(folder/'main.bin'),sram_sha256=sha(folder/'exports/sram-full.bin'),
        packet_header=packet[:4].hex(),packet_length=length,packet_sha256=digest,ring_words=fields,
        converted_public_point_locations=converted,semantic_checks=len(report['semantic_validation']['checks']))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence outside Git')
    source_path=s/'p256-event-source-06/report.json'
    manifest=json.loads((s/'p256-event-verification-01/manifest.json').read_text())
    if not manifest['passed'] or sha(source_path)!=manifest['source_sha256']:raise ValueError('Changed original contract')
    source=json.loads(source_path.read_text())
    jobs=[('stock24','p256-peer-main-01/stock24','nominal'),('stock23','p256-peer-main-01/stock23','nominal'),
        ('cfw','p256-peer-main-01/cfw','nominal'),('stock24','p256-peer-control-01/stock24','control'),
        ('stock24','p256-peer-error-01/stock24','error')]
    rows=[inspect(s,c,s/f,profile,source) for c,f,profile in jobs]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,final_native_captures=5,
        hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('Verified 5 natural captures: original request bytes match, default-off CPU/events exact')


if __name__=='__main__':main()
