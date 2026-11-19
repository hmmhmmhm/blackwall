"""Audit the saved original post-close advertising request; never execute it."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from probe_frozen_peer_disconnect import audit as close_audit
from verify_kv_persistence_cycle import validate_capture
from inspect_ambiq_target import decode


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def verify(s,cap,out):
    validate_capture(cap)
    ref=s/'frozen-peer-disconnect-native-01/immediate'
    validate_capture(ref)
    lineage=read(s/'frozen-peer-disconnect-research-01/manifest.json')
    for name in ('capture-files.json','strict.cs','main.bin','board.repl','run.py'):
        pin=lineage['files'][str((ref/name).relative_to(s))]
        if sha(ref/name)!=pin['sha256'] or (ref/name).stat().st_size!=pin['bytes']:
            raise ValueError('Changed completed-close reference')
    prior=close_audit(s,cap,out/'prior-close')
    a=read(cap/'exports/post-close.json');p=read(cap/'connection-profile.json')
    rows=[json.loads(line.split('BLACKWALL_POST_CLOSE ',1)[1]) for line in (cap/'renode.log').read_text().splitlines() if line.startswith('BLACKWALL_POST_CLOSE ')]
    ram=(cap/'exports/post-close-sram.bin').read_bytes();raw=(cap/'main.bin').read_bytes()
    regs=a['registers'];pointer=regs[10];size=regs[8]
    if len(regs)!=16 or not 0x20000000<=pointer<=0x20380000-size or not 4<=size<=255:
        raise ValueError('Invalid original command buffer')
    packet=ram[pointer-0x20000000:pointer-0x20000000+size]
    fixture=re.findall(r'advertisingInitializationHex: "([^"]+)"',(cap/'board.repl').read_text())
    if len(fixture)!=1:raise ValueError('Ambiguous advertising fixture')
    frames=bytes.fromhex(fixture[0]);commands=[];offset=0
    while offset<len(frames):
        if frames[offset]!=1:raise ValueError('Expected HCI command')
        end=offset+4+frames[offset+3];commands.append(frames[offset:end]);offset=end
        if frames[offset:offset+3]!=bytes.fromhex('040e04'):raise ValueError('Expected explicit command-complete fixture')
        offset+=7
    original_instruction=decode(raw,a['pc'],2)
    active_guards=[g for g in a['guards'] if g['accesses']]
    checks=dict(
        completed_close_preserved=prior['passed'],
        report_matches_log=rows==[a],
        main_model_board_exact=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('main.bin','strict.cs','board.repl','sram-fill.bin','itcm-fill.bin')),
        original_runner_prefix=(cap/'run.py').read_bytes().startswith((ref/'run.py').read_bytes()),
        close_sram_exact=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('exports/connection-sram.bin','exports/disconnect-sram.bin')),
        close_report_values_exact=all(read(cap/n)==read(ref/n) for n in ('exports/connection.json','exports/disconnect.json','exports/frozen-peer-fault.json')),
        bounded_new_execution=a['start_ticks']==read(cap/'exports/disconnect.json')['virtual_time']['end_ticks'] and 0<a['end_ticks']-a['start_ticks']<500000000,
        ready_read_boundary=a['pc']==regs[15]==0x501676 and regs[0]==0x40010410 and len(original_instruction)==1 and original_instruction[0].mnemonic=='ldr' and original_instruction[0].op_str=='r0, [r0]',
        strict_stop=active_guards==[dict(name='guard',accesses=1,address=0x40010410)] and a['cfsr']==a['hfsr']==a['memory_violations']==0,
        exact_original_advertising_parameters=len(commands)==5 and len(packet)==19 and packet==commands[1] and packet[:4]==bytes.fromhex('0106200f'),
        no_command_sent=a['peer']['commands']==59 and a['peer']['replies']==60 and a['peer']['events']==4 and a['peer']['written']==0 and a['peer']['pending'] is False and a['peer']['state']=='Complete',
        ccb_remains_released=all(ram[p['dm_global']+48*k+21-0x20000000]==ram[p['dm_global']+48*k+22-0x20000000]==0 for k in range(3)),
        no_sensor_success=a['gaf']['on_demand']['requests']==a['gaf']['on_demand']['completed_calculations']==0 and a['gaf']['on_demand']['calculation_supported'] is False,
        hardware_not_accessed=a['hardware'] is False)
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,prepared_packet=packet.hex(),opcode='0x2006',elapsed_virtual_nanoseconds=a['end_ticks']-a['start_ticks'],
        reconnection_executed=False,advertising_restart_completed=False,normal_initialization_verified=False,
        scope='original post-close prepared request, blocked before SPI transmission; not firmware error or reconnect success',e14_complete=False,hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve previous audit')
    r=verify(a.simulator,a.capture,a.output)
    print(json.dumps(dict(passed=r['passed'],checks=len(r['checks']),prepared_packet=r['prepared_packet'],reconnection_executed=False)))


if __name__=='__main__':main()
