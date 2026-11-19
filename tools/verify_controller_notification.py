"""Audit real timeout return, internal notification consumption, and the next strict boundary."""
import argparse
import json
from pathlib import Path
import re
import struct
from probe_controller_notification import SETUP,POST
from run_runtime_connection_m55 import sha
from verify_kv_persistence_cycle import validate_capture
from inspect_ambiq_target import decode

def read(p):return json.loads(p.read_text())

def verify(s,cap,out):
    ref=s/'controller-reset-generations-native-03/enabled';validate_capture(cap);validate_capture(ref)
    pins=read(s/'controller-reset-generations-research-01/manifest.json')['files']
    for n in ('capture-files.json','main.bin','strict.cs','board.repl','run.py','activation.cs'):
        p=ref/n;pin=pins[str(p.relative_to(s))]
        if sha(p)!=pin['sha256'] or p.stat().st_size!=pin['bytes']:raise ValueError('Changed baseline')
    h=read(cap/'exports/hci-timeout.json');before=read(cap/'exports/notification-before.json');after=read(cap/'exports/notification-after.json');v=after['notification'];rows=v['rows']
    if len(rows)!=9 or any(len(r)!=12 for r in rows):raise ValueError('Incomplete notification path')
    raw=(cap/'main.bin').read_bytes();mem=(cap/'exports/notification-after-sram.bin').read_bytes();pre=(cap/'exports/hci-timeout-sram.bin').read_bytes()
    contract=read(s/'controller-notification-research-01/original-notification-contract.json')
    source_ok=contract['main_sha256']==sha(cap/'main.bin') and all(raw[row['pc']-0x438000:row['pc']-0x438000+len(bytes.fromhex(row['bytes']))]==bytes.fromhex(row['bytes']) for fn in contract['functions'].values() for row in fn)
    packet=bytes.fromhex(re.search('advertisingInitializationHex: "([0-9a-f]+)"',(cap/'board.repl').read_text())[1]);offset=0;commands=[]
    for n in (10,19,36,36,5):commands.append(packet[offset:offset+n]);offset+=n+7
    regs=after['registers'];chunk=mem[regs[4]-0x20000000:regs[4]-0x20000000+9];observer=Path(__file__).with_name('renode-controller-notification-observer.cs').read_bytes();anchor='    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n'
    def logged(label):return [json.loads(l.split(label+' ',1)[1]) for l in (cap/'renode.log').read_text().splitlines() if l.startswith(label+' ')]
    checks=dict(
        unchanged_inputs=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('main.bin','strict.cs','board.repl','connection-profile.json','sram-fill.bin','itcm-fill.bin','hci-timeout-contract.json')),
        exact_added_observer=(cap/'activation.cs').read_bytes()==(ref/'activation.cs').read_bytes()+b'\n'+observer and (cap/'renode-controller-notification-observer.cs').read_bytes()==observer,
        exact_run_extension=(cap/'run.py').read_text()==(ref/'run.py').read_text().replace(anchor,SETUP+anchor)+POST,
        original_reports_equal=all(read(cap/'exports'/n)==read(ref/'exports'/n) for n in ('connection.json','disconnect.json','frozen-peer-fault.json','hci-timeout.json','controller-reset.json','controller-generation.json')),
        whole_prefix_sram_equal=all((cap/'exports'/n).read_bytes()==(ref/'exports'/n).read_bytes() for n in ('connection-sram.bin','disconnect-sram.bin','hci-timeout-sram.bin')),
        logged_reports=logged('BLACKWALL_NOTIFICATION_BEFORE')==[before] and logged('BLACKWALL_NOTIFICATION_AFTER')==[after],
        original_source_bytes=source_ok and contract['handler1']==0x4fa0f1 and contract['group7_dispatch']==0x4da999 and contract['leaf0']==0x4da8f9,
        ordered_stages=[r[0] for r in rows]==list(range(1,10)) and all(a[1]<=b[1] for a,b in zip(rows,rows[1:])),
        before_stop=before['rows']==rows[:2] and before['sent'] and not any(before[k] for k in ('callback_returned','handler_entered','message_freed','overflow')),
        same_original_message=0x20000000<=v['message']<=0x2037fffc and all(r[10]==v['message'] for r in rows) and all((r[11]>>16)&255==0x38 for r in rows[1:8]),
        original_send=rows[0][2]==0x4dab72 and rows[0][3]==v['message'] and rows[1][2:5]==[0x4dab7e,1,v['message']],
        original_pop_executed=rows[2][2]==(h['timeout_entry'][2]&~1)==0x5647e2 and rows[2][6]==h['timeout_entry'][1] and rows[2][3]==struct.unpack_from('<I',pre,h['timeout_exit'][0]-0x20000000)[0] and rows[2][1]>h['timeout_return_ticks'],
        original_handler_dispatch=rows[3][2:5]==[0x4fa0f0,0,v['message']] and rows[4][2:5]==[0x4fa10c,v['message'],contract['group7_dispatch']] and rows[5][2:5]==[0x4da9a6,v['message'],contract['leaf0']],
        original_handler_pop_and_free=rows[6][2]==0x4fa110 and rows[7][2]==0x4d7aec and rows[8][2]==0x4d7af2 and rows[3][7]==0x4d7aed and rows[7][6]==rows[3][6] and rows[6][6]==rows[3][6]-8,
        original_task_thread=all(r[8]==h['timeout_entry'][3] and r[9]&0x1ff==0 for r in rows),
        complete_flags=all(v[k] for k in ('sent','callback_returned','handler_entered','dispatched','leaf_entered','handler_return_instruction','handler_returned','message_freed')) and not v['overflow'],
        natural_resume=after['start_ticks']==h['end_ticks'] and 0<after['end_ticks']-after['start_ticks']<3000000000 and all(after[k]==0 for k in ('cfsr','hfsr','memory_violations')),
        generation_preserved=after['generation']==1 and after['rejection']=='' and after['history']==read(cap/'exports/controller-generation.json')['history'],
        reset_and_startup_frontier=after['peer']['commands']==55 and after['peer']['replies']==56 and after['peer']['reset_command']=='01030c00' and after['peer']['advertising_commands']==after['peer']['advertising_replies']==1 and after['peer']['state']=='WritePayloadActive' and not after['peer']['pending'],
        strict_opcode_mismatch=commands[1][:4]==bytes.fromhex('0106200f') and chunk[:4]==bytes.fromhex('01082020') and regs[2]==struct.unpack('<I',chunk[:4])[0] and regs[3]+0x10c==0x4005610c and after['pc']==0x582660 and decode(raw,after['pc'],4)[0].op_str=='r2, [r3, #0x10c]',
        strict_guard=[(g['name'],g['address'],g['accesses']) for g in after['guards'] if g['accesses']]==[('iom6',0x4005610c,1)],
        frozen_gaf_preserved=after['gaf']['on_demand']['pending'] and after['gaf']['on_demand']['completed_calculations']==0 and not after['hardware_accessed'])
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,additional_observer_prefix_captured_state_equal=True,callback_return_executed_verified=True,internal_event38_consumed_and_free_returned=True,event_name_verified=False,application_error_display_verified=False,full_controller_startup_verified=False,recovery_complete=False,e14_complete=False,post_return_elapsed_ns=after['end_ticks']-after['start_ticks'],commands=55,replies=56,expected_first_chunk_command=commands[1].hex(),actual_first_chunk=chunk.hex(),next_action='derive post-reset advertising order and payload from original state; retain opcode guard',hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.capture,a.output);print(json.dumps(dict(passed=True,checks=len(r['checks']),callback_returned=True,recovery_complete=False)))

if __name__=='__main__':main()
