"""Audit original packet emission and the exact opt-in post-reset wire sequence."""
import argparse
import json
from pathlib import Path
import struct
from post_reset_advertising_model import compose
from probe_post_reset_advertising import SETUP,POST
from run_runtime_connection_m55 import sha
from verify_kv_persistence_cycle import validate_capture
from inspect_ambiq_target import decode

def read(p):return json.loads(p.read_text())

def verify(s,cap,out,enabled):
    gold=s/'controller-notification-native-01';base=s/'post-reset-advertising-native-01'
    for c in (gold,base,cap):validate_capture(c)
    pins=read(s/'controller-notification-research-01/manifest.json')['files']
    for n in ('capture-files.json','main.bin','strict.cs','board.repl','activation.cs','run.py'):
        p=gold/n;pin=pins[str(p.relative_to(s))]
        if sha(p)!=pin['sha256'] or p.stat().st_size!=pin['bytes']:raise ValueError('Changed source baseline')
    observer=Path(__file__).with_name('renode-hci-emission-observer.cs').read_bytes();anchor='    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n'
    reports=('connection.json','disconnect.json','frozen-peer-fault.json','hci-timeout.json','controller-reset.json','controller-generation.json','notification-before.json','notification-after.json')
    memories=('connection-sram.bin','disconnect-sram.bin','hci-timeout-sram.bin','notification-after-sram.bin')
    baseline_checks=dict(
        inputs_equal=all((base/n).read_bytes()==(gold/n).read_bytes() for n in ('main.bin','strict.cs','board.repl','connection-profile.json','sram-fill.bin','itcm-fill.bin','hci-timeout-contract.json')),
        exact_observer=(base/'activation.cs').read_bytes()==(gold/'activation.cs').read_bytes()+b'\n'+observer and (base/'renode-hci-emission-observer.cs').read_bytes()==observer,
        exact_run=(base/'run.py').read_text()==(gold/'run.py').read_text().replace(anchor,SETUP+anchor,1)+POST,
        reports_equal=all(read(base/'exports'/n)==read(gold/'exports'/n) for n in reports),
        whole_sram_equal=all((base/'exports'/n).read_bytes()==(gold/'exports'/n).read_bytes() for n in memories))
    if not all(baseline_checks.values()):raise ValueError({'baseline':baseline_checks})
    model=compose((base/'strict.cs').read_text()) if enabled else (base/'strict.cs').read_text()
    board=(base/'board.repl').read_text();profile=read(base/'connection-profile.json')
    if enabled:
        board=board.replace('    controllerResetLimit: 1\n','    controllerResetLimit: 1\n    postResetAdvertisingDataFirst: true\n');profile.update(model_sha256=sha(cap/'strict.cs'),post_reset_advertising_data_first=True)
    v=read(cap/'exports/hci-emission.json');rows=v['rows'];packets=[bytes.fromhex(p) for p in v['packets']];after=read(cap/'exports/notification-after.json');h=read(cap/'exports/hci-timeout.json');raw=(cap/'main.bin').read_bytes();mem=(cap/'exports/notification-after-sram.bin').read_bytes()
    history=read(base/'exports/controller-generation.json')['history'].split(':')[8].split(',');order=[0,2,3,1,4];expected=[bytes.fromhex(history[i][2:]) for i in (55,58)]+[bytes.fromhex(p[2:]) for p in history[2:54]]+[bytes.fromhex(history[54+i][2:]) for i in order]
    if len(rows)!=len(packets) or any(len(r)!=7 for r in rows):raise ValueError('Incomplete sender capture')
    def logged(label):return [json.loads(l.split(label+' ',1)[1]) for l in (cap/'renode.log').read_text().splitlines() if l.startswith(label+' ')]
    checks=dict(
        exact_model=(cap/'strict.cs').read_text()==model,
        exact_board=(cap/'board.repl').read_text()==board,
        exact_profile=read(cap/'connection-profile.json')==profile,
        original_firmware_and_observers=all((cap/n).read_bytes()==(base/n).read_bytes() for n in ('main.bin','sram-fill.bin','itcm-fill.bin','activation.cs','run.py','hci-timeout-contract.json')),
        original_prefix_reports=all(read(cap/'exports'/n)==read(base/'exports'/n) for n in reports[:-1]),
        original_prefix_sram=all((cap/'exports'/n).read_bytes()==(base/'exports'/n).read_bytes() for n in memories[:-1]),
        logged_values=logged('BLACKWALL_HCI_EMISSION')==[v] and logged('BLACKWALL_NOTIFICATION_AFTER')==[after],
        complete_trace=not v['overflow'] and not v['invalid_pointer'] and not v['hardware_accessed'],
        exact_original_candidates=packets==expected and [r[6] for r in rows]==[0,0]+[1]*57,
        exact_packet_lengths=all(len(p)>=3 and len(p)==3+p[2] for p in packets),
        original_sender_callers=all((ins:=decode(raw,(r[2]&~1)-4,4)) and ins[0].mnemonic=='bl' and ins[0].operands[0].imm==0x563c08 for r in rows),
        original_thread_and_buffers=all(0x20000000<=r[1] and r[1]+len(p)<=0x20380000 and r[4]==h['timeout_entry'][3] and r[5]&0x1ff==0 for r,p in zip(rows,packets)),
        ordered_timestamps=all(a[0]<=b[0] for a,b in zip(rows,rows[1:])),
        consumed_notification=after['notification']==read(base/'exports/notification-after.json')['notification'],
        generation_preserved=after['generation']==1 and after['rejection']=='' and after['history']==read(base/'exports/notification-after.json')['history'],
        no_cpu_fault=all(after[k]==0 for k in ('cfsr','hfsr','memory_violations')),
        sensor_not_synthesized=after['gaf']['on_demand']['pending'] and after['gaf']['on_demand']['completed_calculations']==0)
    contract=read(cap/'hci-timeout-contract.json')
    if enabled:
        timer=contract['timer']-0x20000000
        checks.update(
            complete_strict_wire_set=after['peer']['commands']==59 and after['peer']['replies']==60 and after['peer']['advertising_commands']==after['peer']['advertising_replies']==5 and after['peer']['state']=='Complete' and not after['peer']['pending'] and after['peer']['events']==0,
            no_guard=not any(g['accesses'] for g in after['guards']),
            healthy_stop_boundary=after['pc']==contract['healthy_stop_pc']==0x563d32 and decode(raw,after['pc']-4,4)[0].operands[0].imm==contract['timer_stop'] and struct.unpack_from('<H',mem,contract['opcode']-0x20000000)[0]==0x200a and mem[timer+13]==0,
            credit_store_not_claimed=mem[contract['credit']-0x20000000]==0,
            stopped_before_time_budget=after['start_ticks']==h['end_ticks'] and 0<after['end_ticks']-after['start_ticks']<3000000000)
    else:
        checks.update(legacy_boundary_preserved=after==read(base/'exports/notification-after.json') and (cap/'exports/notification-after-sram.bin').read_bytes()==(base/'exports/notification-after-sram.bin').read_bytes())
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,baseline_checks=baseline_checks,checks=checks,enabled=enabled,candidate_packets=59,later_generation_candidates=57,advertising_order=[0x2005,0x2008,0x2009,0x2006,0x200a],payloads_identical_to_original_fixture=True,wire_commands=after['peer']['commands'],wire_replies=after['peer']['replies'],full_declared_startup_wire_set_consumed=enabled,final_credit_restore_verified=False,post_recovery_reconnection_verified=False,recovery_complete=False,e14_complete=False,normal_gaf_verified=False,hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);p.add_argument('--data-first',action='store_true');a=p.parse_args();r=verify(a.simulator,a.capture,a.output,a.data_first);print(json.dumps(dict(passed=True,baseline_checks=len(r['baseline_checks']),checks=len(r['checks']),wire_commands=r['wire_commands'],wire_replies=r['wire_replies'],recovery_complete=False)))

if __name__=='__main__':main()
