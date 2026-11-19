"""Verify saved advertising initialization and the next strict IOM7 request."""
import argparse
import json
import struct
from pathlib import Path
from prepare_vendor_startup_candidate import sha
from native_replay import MAIN_LAYOUT
from inspect_aes_profiles import tx_bytes
from run_native_candidate import memory_exports,validate_memory_exports,read_memory_snapshot,memory_export_policy


def inspect(s,case,control=False):
    folder=s/('advertising-peer-control-01' if control else 'advertising-peer-main-01')/case
    audit=s/'advertising-peer-saved-audit-01'/('control' if control else case)/'report.json'
    reviewed=json.loads(audit.read_text());v=json.loads((folder/'report.json').read_text())
    plan=json.loads((folder/'plan.json').read_text());old=json.loads((s/'aes-peer-main-01'/case/'report.json').read_text())
    if reviewed.get('passed') is not True or not v['execution_passed'] or v['hardware_accessed'] or v['control']!=control:
        raise ValueError('Unverified saved capture')
    for name,digest in reviewed['capture_hashes'].items():
        if sha(folder/name)!=digest:raise ValueError('Changed capture: '+name)
    if sha(folder/'main.bin')!=MAIN_LAYOUT[plan['cases'][case]][3]:raise ValueError('Changed original main')
    validate_memory_exports(folder,memory_exports(plan),v['memory_exports'])
    snapshot=read_memory_snapshot((folder/'renode.log').read_text(),memory_export_policy(plan),v['observed'])
    if snapshot!=v.get('memory_snapshot'):raise ValueError('Snapshot metadata changed')
    keys=['accepted_commands','replies','frames','commands','advertising_commands_accepted','advertising_replies_consumed']
    if tuple(v['diagnostics'][k] for k in keys)!=((54,55,211,422,0,0) if control else (59,60,230,460,5,5)):
        raise ValueError('Different command/response history')
    before=tx_bytes(old['observed']['uart1']);after=tx_bytes(v['observed']['uart1'])
    delta=len(after)-len(before);irq=v['observed']['uart1']['irq_exception_entries']-old['observed']['uart1']['irq_exception_entries']
    if not after.startswith(before) or (delta,irq)!=((0,0) if control else (10,4)):
        raise ValueError('Different original UART1 continuation')
    if control:
        if v['observed']!=old['observed'] or v['selected_observation']!=old['selected_observation']:
            raise ValueError('Default-off CPU/events changed')
        frontier=dict(source_cpu_events_exact=True)
    else:
        guards=[g for g in v['observed']['guards'] if g['accesses']]
        pc=0x58236c if case=='stock24' else 0x57b014
        if v['observed']['pc']!=pc or len(guards)!=1:raise ValueError('Different native frontier')
        g=guards[0]
        if (g['name'],g['accesses'],g['address'],g['operation'],g['width'],g['value'])!=('iom7.pointerProbe',1,0x501,'peer-write-unsupported',2,0x207):
            raise ValueError('Different rejected PMIC request')
        ram=(folder/'exports/sram-full.bin').read_bytes();ring=0x20076304 if case=='stock24' else 0x20076cbc
        words=list(struct.unpack_from('<6I',ram,ring-0x20000000))
        frontier=dict(pc=pc,rejected_request_hex='0207',request_completed=False,previous_pointer=0x501,ring_words=words)
    return dict(case=case,control=control,capture=str(folder.relative_to(s)),report_sha256=sha(folder/'report.json'),
                audit_sha256=sha(audit),sram_sha256=sha(folder/'exports/sram-full.bin'),frontier=frontier,
                extra_uart1_tx_bytes=delta,extra_uart1_irq_entries=irq)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence outside Git')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']]+[inspect(a.simulator,'stock24',True)]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_captures=4,
        hardware_accessed=False,radio_advertising_verified=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('Verified advertising5 on original3, UART1 TX/IRQ continuation and default-off CPU/events equality')


if __name__=='__main__':main()
