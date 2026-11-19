"""Verify saved natural AES initialization, UART1 continuation and actual next requests."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from prepare_vendor_startup_candidate import sha
from native_replay import MAIN_LAYOUT


def tx_bytes(uart):
    value=uart['tx_bytes']
    return bytes.fromhex(value) if isinstance(value,str) else bytes(value)


def inspect(s,case,folder,control):
    d=json.loads((folder/'report.json').read_text());plan=json.loads((folder/'plan.json').read_text())
    if not d['passed'] or not d['execution_passed'] or d['control']!=control or d['hardware_accessed']:
        raise ValueError('Unverified saved native capture')
    if sha(folder/'main.bin')!=MAIN_LAYOUT[plan['cases'][case]][3]:raise ValueError('Changed original main')
    for export in d['memory_exports']:
        if sha(folder/'exports'/export['name'])!=export['sha256']:raise ValueError('Changed native SRAM export')
    old=json.loads((s/'p256-peer-main-01'/case/'report.json').read_text())
    if control and (d['observed']!=old['observed'] or d['selected_observation']!=old['selected_observation']):
        raise ValueError('Default-off CPU or events changed')
    ram=(folder/'exports/sram-full.bin').read_bytes();regs=d['observed']['register_context']
    length=36 if control else 10;header=bytes.fromhex('01172020' if control else '01052006')
    if regs['r8']!=length or regs['r9']!=0:raise ValueError('Different original write arguments')
    pointer=regs['r10'];offset=pointer-0x20000000
    if not 0<=offset<=len(ram)-length:raise ValueError('Packet outside captured SRAM')
    packet=ram[offset:offset+length]
    if packet[:4]!=header:raise ValueError('Different next original HCI request')
    ring=0x20076304 if case=='stock24' else 0x20076cbc
    words=list(struct.unpack_from('<6I',ram,ring-0x20000000))
    if words[2:5]!=[260,2080,260] or words[5]+words[1]+4!=pointer:
        raise ValueError('Original ring record differs from transport pointer')
    expected=(22,23,51,102,0,0) if control else (54,55,211,422,32,32)
    if tuple(d['diagnostics'][k] for k in ['accepted_commands','replies','frames','commands','aes_commands_accepted','aes_replies_consumed'])!=expected:
        raise ValueError('Incomplete AES command/response sequence')
    if d['observed']['pc']!=(0x501676 if case=='stock24' else 0x549fce):raise ValueError('Different write-ready frontier')
    before=tx_bytes(old['observed']['uart1']);after=tx_bytes(d['observed']['uart1'])
    if not after.startswith(before):raise ValueError('Earlier UART1 transmission prefix changed')
    delta=len(after)-len(before);irq=d['observed']['uart1']['irq_exception_entries']-old['observed']['uart1']['irq_exception_entries']
    if (delta,irq)!=((0,0) if control else (30,12)):raise ValueError('Different UART1 continuation')
    return dict(case=case,control=control,capture=str(folder.relative_to(s)),report_sha256=sha(folder/'report.json'),
        main_sha256=sha(folder/'main.bin'),sram_sha256=sha(folder/'exports/sram-full.bin'),
        next_header=packet[:4].hex(),next_length=length,next_packet_sha256=hashlib.sha256(packet).hexdigest(),
        ring_words=words,extra_uart1_tx_bytes=delta,extra_uart1_irq_entries=irq,
        extra_uart1_tx_sha256=hashlib.sha256(after[len(before):]).hexdigest(),
        semantic_checks=len(d['semantic_validation']['checks']))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence outside Git')
    rows=[inspect(s,c,s/'aes-peer-main-01'/c,False) for c in ['stock24','stock23','cfw']]
    rows.append(inspect(s,'stock24',s/'aes-peer-control-01/stock24',True))
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_captures=4,
        hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('Verified native4: AES32 consumed, UART1 TX/IRQ continued, default-off CPU/events exact')


if __name__=='__main__':main()
