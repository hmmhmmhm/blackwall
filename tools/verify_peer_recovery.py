"""Audit version-specific original timeout/reset/credit/reconnection without rebuilding inputs."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import struct
from run_runtime_connection_m55 import sha
from verify_kv_persistence_cycle import validate_capture
from probe_peer_recovery import contract

def read(p):return json.loads(p.read_text())

def verify(s,cap,out):
    validate_capture(cap);p=read(cap/'connection-profile.json');case=p['case'];c=read(cap/'recovery-contract.json');raw=(cap/'main.bin').read_bytes();v=read(cap/'exports/recovery-diagnostic.json');r=read(cap/'exports/reconnection.json')
    fixed=read(s/'peer-recovery-version-research-01/fixed-inputs.json')[case]
    for n,digest in fixed.items():
        if sha(cap/n)!=digest:raise ValueError('Changed prepared input: '+n)
    ref=s/'post-timeout-reconnect-native-01';pin=read(s/'post-timeout-reconnect-research-01/manifest.json')['files'][str((ref/'strict.cs').relative_to(s))]
    if sha(ref/'strict.cs')!=pin['sha256']:raise ValueError('Changed shared model')
    phases=v['phases'];names=['timeout-return','healthy-stop','credit-return','settled','reconnected']
    if [x['name'] for x in phases]!=names:raise ValueError('Incomplete recovery phases')
    a,b,d,e,f=[x['state'] for x in phases];ram={n:(cap/'exports'/(n+'-sram.bin')).read_bytes() for n in names};mem=ram['reconnected'];slots=[p['dm_global']+48*k for k in range(3)];active=[x for x in slots if mem[x+22-0x20000000]]
    entry=r['entry'];exit=r['exit']
    if len(entry)!=6 or len(exit)!=3 or len(v['entry'])!=5 or len(v['returned_context'])!=5:raise ValueError('Incomplete original context')
    msg=mem[entry[1]-0x20000000:entry[1]-0x20000000+36];task=v['entry'][3];board=(cap/'board.repl').read_text();dc=read(cap/'exports/disconnect.json');packets=[bytes.fromhex(x) for x in v['packets']]
    def logged(label):return [json.loads(x.split(label+' ',1)[1]) for x in (cap/'renode.log').read_text().splitlines() if x.startswith(label+' ')]
    def credit(n):return ram[n][c['credit']-0x20000000]
    def counter(n):return struct.unpack_from('<I',ram[n],p['gpio']['counter']-0x20000000)[0]
    rtc=datetime.fromisoformat(r['rtc']['date'])-datetime.fromisoformat(d['rtc']['date']);rtc_ns=(rtc.days*86400+rtc.seconds)*1000000000+rtc.microseconds*1000
    generation1=[packet for packet,gen in zip(packets,v['packet_generations']) if gen==1]
    history=b['history'].split(':');original=[bytes.fromhex(x)[1:] for x in history[8].split(',')] if len(history)==10 else []
    checks=dict(
        original_main=sha(cap/'main.bin')==p['main_sha256']==c['main_sha256'],
        exact_verified_abi=c==contract(s,raw,case) and c['credit']-c['timer']==0x1a,
        shared_model=(cap/'strict.cs').read_bytes()==(ref/'strict.cs').read_bytes() and p['model_sha256']==sha(cap/'strict.cs'),
        explicit_guarded_profile=all(board.count(x)==1 for x in ('    runtimeReadvertise: true\n','    runtimeDropFirstReadvertisingReply: true\n','    controllerResetLimit: 1\n','    postResetAdvertisingDataFirst: true\n')) and p['gaf_profile']['on_demand_fault']=='frozen-core' and p['gaf_profile']['calculation_supported'] is False,
        logs_match=logged('BLACKWALL_VERSION_RECOVERY_DIAGNOSTIC')==[v] and logged('BLACKWALL_VERSION_RECONNECTION')==[r] and logged('BLACKWALL_RECOVERY_PHASE')==[dict(name=n,state=read(cap/'exports'/(n+'.json'))) for n in names],
        phase_files=all(all(x['state'][k]==value for k,value in read(cap/'exports'/(x['name']+'.json')).items()) for x in phases) and r==f,
        real_long_delay=dc['stopped'] and dc['pc']==p['closed_return'] and p['disconnect_delay_ms']==1000 and 1000000000<=dc['virtual_time']['end_ticks']-dc['virtual_time']['start_ticks']<1020000000,
        original_timeout=v['started'] and v['seconds']==10 and v['entered'] and v['entry'][0]==c['timer']+8 and v['message']==[0,0,1,0] and 9000000000<v['entered_at']-v['started_at']<11500000000,
        original_six_calls=[x[0] for x in v['calls']]==c['callback_sites'] and v['calls'][0][1]==0x2006 and v['calls'][1][1]==200,
        original_callback_return=v['returned'] and a['pc']==c['timer_callback_return'] and a['ticks']==v['returned_at'] and v['returned_context'][1]==v['entry'][1]-8 and v['returned_context'][3]==task and v['entry'][4]&511==v['returned_context'][4]&511==0,
        one_lost_completion=len(history)==10 and history[:8]==['0','246','59','60','4','1','0','1'],
        strict_startup_complete=all(x['generation']==1 and x['rejection']=='' and x['peer']['commands']==59 and x['peer']['replies']==60 and x['peer']['advertising_commands']==x['peer']['advertising_replies']==5 and x['peer']['state']=='Complete' for x in (b,d,e,f)),
        healthy_boundary=v['healthy'] and b['pc']==c['healthy_stop_pc'] and b['ticks']==v['healthy_at'] and b['credit']==credit('healthy-stop')==0 and b['opcode']==0x200a and b['timer'][13]==0,
        original_credit_store=v['credit_returned'] and d['pc']==c['ready_return'] and d['ticks']==v['credit_at'] and d['credit']==credit('credit-return')==1 and all(x['opcode']==0x200a and x['timer'][13]==0 and x['credit']==1 for x in (d,e,f)),
        actual_settlement=100000000<=e['ticks']-d['ticks']<110000000 and e['peer']['events']==0 and not e['peer']['pending'],
        ccb_free_before_input=all(ram['settled'][x+21-0x20000000]==ram['settled'][x+22-0x20000000]==0 for x in slots),
        explicit_device_input=r['input']['accepted'] and r['input']['irq'] and r['input']['pending'] and r['input']['pc']==e['pc'] and r['input']['ticks']==e['ticks'],
        original_opened_return=r['stopped'] and r['pc']==p['finished'] and r['calls']==1 and 0<r['ticks']-e['ticks']<=2000000000,
        original_task_stack=entry[4]==exit[1]==task and entry[5]&511==exit[2]&511==0 and entry[2]==exit[0]+16 and struct.unpack_from('<I',mem,task+48-0x20000000)[0]<=exit[0]<struct.unpack_from('<I',mem,task+48-0x20000000)[0]+4*struct.unpack_from('<I',mem,task+84-0x20000000)[0],
        decoded_connection=len(msg)==36 and msg[4]==0 and struct.unpack_from('<H',msg,6)[0]==64 and msg[8:16]==bytes.fromhex('0100112233445566'),
        ccb_reallocated=len(active)==1 and mem[active[0]+21-0x20000000]==3 and struct.unpack_from('<H',mem,active[0]+12-0x20000000)[0]==64 and mem[active[0]+16-0x20000000]==mem[active[0]+25-0x20000000]==1,
        irq_consumed=r['irq_entries']==1 and r['gpio']['edges']==e['gpio']['edges']+1 and not r['gpio']['pending'] and not r['gpio']['irq'] and counter('reconnected')==counter('settled')+1 and r['peer']['events']==1 and not r['peer']['pending'],
        all_phases_clean=all(not any(g['accesses'] for g in x['guards']) and x['cfsr']==x['hfsr']==x['memory_violations']==0 for x in (a,b,d,e,f)),
        exact_original_emissions=len(packets)==len(v['packet_generations'])==59 and generation1==original[2:54]+[original[54+i] for i in (0,2,3,1,4)] and all(len(x)==3+x[2] for x in packets),
        no_diagnostic_loss=not v['overflow'] and not v['invalid_pointer'],
        rtc_no_new_write=all(x['rtc']['commits']==1 and not x['rtc']['pending'] and x['rtc']['error']=='none' for x in (a,b,d,e,f)) and abs(rtc_ns-(r['ticks']-d['ticks']))<10000000,
        explicit_sensor_fault=all(x['gaf']['on_demand']['pending'] and x['gaf']['on_demand']['completed_calculations']==0 and not x['hardware_accessed'] for x in (a,b,d,e,f)),
        no_hardware=not v['hardware_accessed'])
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,case=case,checks=checks,original_main_sha256=sha(cap/'main.bin'),credit_offset=c['credit']-c['timer'],original_timeout_virtual_ns=v['entered_at']-v['started_at'],single_case_timeout_reconnect_passed=True,post_reset_att_verified=False,normal_gaf_verified=False,full_application_recovery_verified=False,e14_complete=False,observer_neutrality_verified=False,hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.capture,a.output);print(json.dumps(dict(passed=True,case=r['case'],checks=len(r['checks']),e14_complete=False)))

if __name__=='__main__':main()
