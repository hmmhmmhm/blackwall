"""Audit original timer cancellation and natural expiry; preserve recovery/timing gaps."""
import argparse
import json
from pathlib import Path
import struct

from hci_response_loss_model import compose
from probe_hci_response_loss import POST
from probe_runtime_reconnect import POST as RECONNECT_POST
from probe_iom_shared_reconnect import POST as POWER_POST
from run_runtime_connection_m55 import inspect,sha
from verify_kv_persistence_cycle import validate_capture


def read(p):return json.loads(p.read_text())
def logged(cap,label):
    rows=[json.loads(l.split(label+' ',1)[1]) for l in (cap/'renode.log').read_text().splitlines() if l.startswith(label+' ')]
    if len(rows)!=1:raise ValueError('Missing or duplicated '+label)
    return rows[0]


def verify(s,root,out):
    control=root/'control';fault=root/'fault';ref=s/'iom-shared-reconnect-native-01/enabled'
    for cap in (control,fault,ref):validate_capture(cap)
    parent=read(s/'iom-shared-power-research-01/manifest.json')
    for n in ('capture-files.json','main.bin','strict.cs','board.repl','run.py','activation.cs'):
        pin=parent['files'][str((ref/n).relative_to(s))]
        if sha(ref/n)!=pin['sha256'] or (ref/n).stat().st_size!=pin['bytes']:raise ValueError('Changed canonical baseline')
    tail=RECONNECT_POST+POWER_POST;stem=(ref/'run.py').read_text()
    if not stem.endswith(tail):raise ValueError('Unknown canonical run suffix')
    stem=stem[:-len(tail)]
    observer=Path(__file__).with_name('renode-hci-timeout-observer.cs').read_bytes()
    diagnostics=[]
    for cap in (control,fault):
        r=inspect(cap,out/(cap.name+'-nominal'))
        diagnostics.append(not r['passed'] and [k for k,v in r['checks'].items() if not v]==['disconnect_rtc_preserved','pinned_gaf_profile'])
    a=read(control/'exports/hci-timeout.json');b=read(fault/'exports/hci-timeout.json');c=read(fault/'hci-timeout-contract.json')
    old=read(ref/'exports/connection.json');ram=(ref/'exports/connection-sram.bin').read_bytes();tcb=old['entry'][4]
    stack=struct.unpack_from('<I',ram,tcb+48-0x20000000)[0];depth=struct.unpack_from('<I',ram,tcb+84-0x20000000)[0]
    raw=(fault/'main.bin').read_bytes();calls=[v['pc'] for v in c['callback_code'] if v['asm'].startswith('bl #')]
    source_exact=all(raw[v['pc']-0x438000:v['pc']-0x438000+len(bytes.fromhex(v['bytes']))]==bytes.fromhex(v['bytes']) for v in c['callback_code'])
    lost=b['lost'][0] if len(b['lost'])==1 else {}
    entry=b['timeout_entry'];actual_elapsed=b['timeout_entry_ticks']-b['timer_start_ticks']
    checks=dict(
        nominal_rejections_preserved=all(diagnostics),
        exact_extended_model=all((cap/'strict.cs').read_text()==compose((ref/'strict.cs').read_text()) and read(cap/'connection-profile.json')['model_sha256']==sha(cap/'strict.cs') for cap in (control,fault)),
        exact_board_selection=all((cap/'board.repl').read_text()==(ref/'board.repl').read_text().replace('    runtimeReadvertise: true\n','    runtimeReadvertise: true\n    runtimeDropFirstReadvertisingReply: '+str(cap==fault).lower()+'\n') for cap in (control,fault)),
        exact_observation_extension=all((cap/'run.py').read_text()==stem+POST and (cap/'activation.cs').read_bytes()==(ref/'activation.cs').read_bytes()+b'\n'+observer and (cap/'renode-hci-timeout-observer.cs').read_bytes()==observer for cap in (control,fault)),
        original_and_fill_exact=all((cap/n).read_bytes()==(ref/n).read_bytes() for cap in (control,fault) for n in ('main.bin','sram-fill.bin','itcm-fill.bin')),
        complete_prefix_sram_exact=all((cap/'exports'/n).read_bytes()==(ref/'exports'/n).read_bytes() for cap in (control,fault) for n in ('connection-sram.bin','disconnect-sram.bin')),
        prefix_report_values_exact=all(read(cap/'exports'/n)==read(ref/'exports'/n) for cap in (control,fault) for n in ('connection.json','disconnect.json','frozen-peer-fault.json')),
        native_reports_match_logs=all(read(cap/'exports/hci-timeout.json')==logged(cap,'BLACKWALL_HCI_RESPONSE_LOSS') for cap in (control,fault)),
        source_callback_exact=source_exact and c['seconds']==10 and c['wsf_ticks']==1000 and c['main_sha256']==sha(fault/'main.bin'),
        original_timer_start=all(v['timer_starts']==1 and v['timer_seconds']==10 for v in (a,b)),
        healthy_original_timer_stop=a['healthy_timer_stop'] and a['pc']==c['healthy_stop_pc'] and not a['timeout_entered'] and not a['timeout_returned'] and len(a['healthy'])==1 and a['healthy_timer'][13]==a['final_timer'][13]==0 and a['final_opcode']==0x200a,
        healthy_exact_replies=a['lost']==[] and a['peer']['dropped']==0 and a['peer']['readvertising_commands']==a['peer']['readvertising_replies']==2 and a['peer']['accepted']=='0106200fa000a0000001000000000000000700;010a200101',
        exactly_one_loss=len(b['lost'])==1 and lost.get('opcode')==0x2006 and lost.get('credit')==0 and struct.unpack('<I',bytes(lost['timer'][4:8]))[0]==1000 and lost['timer'][13]==1 and b['peer']['dropped']==1 and b['peer']['readvertising_commands']==1 and b['peer']['readvertising_replies']==0 and b['peer']['accepted']=='0106200fa000a0000001000000000000000700',
        natural_callback_input=b['timeout_entered'] and len(entry)==5 and entry[0]==c['timer']+8 and b['timeout_message']==[0,0,1,0] and entry[2]==c['owner_timeout_calls'][0]+5 and entry[3]==tcb and entry[4]&511==0 and stack<=entry[1]<stack+4*depth,
        natural_timer_expiry=b['final_timer'][13]==0 and struct.unpack('<I',bytes(b['final_timer'][4:8]))[0]==0 and b['timer_start_ticks']<=lost.get('ticks',0)<=b['timeout_entry_ticks']<=b['end_ticks'] and 0<actual_elapsed<=11500000000,
        original_reinitialization_call_prefix=[row[0] for row in b['calls']]==calls[:5] and b['calls'][0][1]==0x2006 and b['calls'][1][1]==200 and not b['overflow'],
        strict_recovery_frontier=not b['timeout_returned'] and b['timeout_exit']==[] and b['pc']==0x50190c and [g for g in b['guards'] if g['accesses']]==[dict(name='guard',accesses=1,address=0x40010410)] and b['peer']['state']=='Exhausted',
        no_fake_controller_or_completion=all(v['peer']['commands']==59 and v['peer']['replies']==60 and v['peer']['events']==4 for v in (a,b)) and b['healthy']==[],
        no_cpu_fault=all(v['cfsr']==v['hfsr']==v['memory_violations']==0 for v in (a,b)) and not any(g['accesses'] for g in a['guards']),
        sensor_fault_preserved=b['gaf']['on_demand']['pending'] and b['gaf']['on_demand']['requests']==b['gaf']['on_demand']['triggers']==1 and b['gaf']['on_demand']['request_ram']==2 and b['gaf']['on_demand']['busy_reads']>926 and b['gaf']['on_demand']['completed_calculations']==0,
        honest_scope=all(v['hardware_accessed'] is False and v['normal_initialization_verified'] is False for v in (a,b)))
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,original_programmed_seconds=10,original_programmed_wsf_ticks=1000,observed_virtual_nanoseconds=actual_elapsed,
        difference_from_10_seconds_nanoseconds=actual_elapsed-10000000000,timeout_observed=True,healthy_timer_cancelled=True,original_callback_returned=False,
        recovery_complete=False,timing_accuracy_verified=False,observer_neutrality_verified=False,normal_gaf_verified=False,e14_complete=False,hardware_accessed=False,
        scope='natural original timer expiry and partial reinitialization; controller replay guarded, timer timing discrepancy unresolved')
    out.mkdir(mode=0o700,parents=True,exist_ok=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('captures',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve saved audit')
    r=verify(a.simulator,a.captures,a.output);print(json.dumps(dict(passed=r['passed'],checks=len(r['checks']),timeout_observed=True,recovery_complete=False,timing_accuracy_verified=False)))


if __name__=='__main__':main()
