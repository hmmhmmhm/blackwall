"""Verify original credit restoration and post-timeout DM reconnection in one pinned case."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import struct
from probe_post_timeout_reconnect import POST
from run_runtime_connection_m55 import sha
from verify_kv_persistence_cycle import validate_capture
from inspect_ambiq_target import decode

def read(p):return json.loads(p.read_text())

def verify(s,cap,out):
    ref=s/'post-reset-advertising-native-02';validate_capture(ref);validate_capture(cap)
    pins=read(s/'post-reset-advertising-research-01/manifest.json')['files']
    for n in ('capture-files.json','connection-inputs.json','strict.cs','main.bin','board.repl','run.py','activation.cs'):
        p=ref/n;pin=pins[str(p.relative_to(s))]
        if sha(p)!=pin['sha256'] or p.stat().st_size!=pin['bytes']:raise ValueError('Changed fixed predecessor')
    p=read(cap/'connection-profile.json');c=read(cap/'hci-timeout-contract.json');a=read(cap/'exports/credit-restored.json');b=read(cap/'exports/recovery-settled.json');d=read(cap/'exports/recovery-reconnect.json')
    old=read(cap/'exports/notification-after.json');h=read(cap/'exports/hci-timeout.json');raw=(cap/'main.bin').read_bytes()
    am=(cap/'exports/credit-restored-sram.bin').read_bytes();bm=(cap/'exports/recovery-settled-sram.bin').read_bytes();dm=(cap/'exports/recovery-reconnect-sram.bin').read_bytes()
    slots=[p['dm_global']+48*k for k in range(3)];active=[x for x in slots if dm[x+22-0x20000000]];entry=d['entry'];exit=d['exit']
    if len(entry)!=6 or len(exit)!=3 or len(a['context'])!=4:raise ValueError('Incomplete original contexts')
    msg=dm[entry[1]-0x20000000:entry[1]-0x20000000+36];observer=Path(__file__).with_name('renode-hci-credit-observer.cs').read_bytes()
    reports=('connection.json','disconnect.json','frozen-peer-fault.json','hci-timeout.json','controller-reset.json','controller-generation.json','notification-before.json','notification-after.json','hci-emission.json')
    memories=('connection-sram.bin','disconnect-sram.bin','hci-timeout-sram.bin','notification-after-sram.bin')
    def logged(label):return [json.loads(x.split(label+' ',1)[1]) for x in (cap/'renode.log').read_text().splitlines() if x.startswith(label+' ')]
    def credit(mem):return mem[c['credit']-0x20000000]
    def counter(mem):return struct.unpack_from('<I',mem,p['gpio']['counter']-0x20000000)[0]
    span=datetime.fromisoformat(d['rtc']['date'])-datetime.fromisoformat(a['rtc']['date']);rtc_ns=(span.days*86400+span.seconds)*1000000000+span.microseconds*1000
    checks=dict(
        fixed_inputs=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in read(ref/'connection-inputs.json') if n not in ('run.py','activation.cs')),
        exact_observer_extension=(cap/'activation.cs').read_bytes()==(ref/'activation.cs').read_bytes()+b'\n'+observer and (cap/'renode-hci-credit-observer.cs').read_bytes()==observer,
        exact_natural_resume=(cap/'run.py').read_text()==(ref/'run.py').read_text()+POST,
        prefix_reports_equal=all(read(cap/'exports'/n)==read(ref/'exports'/n) for n in reports),
        whole_prefix_sram_equal=all((cap/'exports'/n).read_bytes()==(ref/'exports'/n).read_bytes() for n in memories),
        logged_states=logged('BLACKWALL_CREDIT_RESTORED')==[a] and logged('BLACKWALL_RECOVERY_SETTLED')==[b] and logged('BLACKWALL_RECOVERY_RECONNECT')==[d],
        original_credit_store=[(i.mnemonic,i.op_str) for i in decode(raw,0x563d32,6)]==[('movs','r0, #1'),('strb.w','r0, [r4, #0x22]')],
        original_credit_transition=a['stopped'] and a['before']==0 and a['after']==a['credit']==credit(am)==1 and a['pc']==0x563d3e and a['start_ticks']==old['end_ticks'] and a['finish_ticks']==a['ticks']>a['start_ticks'],
        credit_task_and_thread=a['context'][2]==h['timeout_entry'][3] and a['context'][3]&511==0,
        inactive_timer_preserved=all(v['opcode']==0x200a and v['timer'][13]==0 and v['credit']==credit(mem)==1 for v,mem in ((a,am),(b,bm),(d,dm))),
        natural_settlement=100000000<=b['ticks']-a['ticks']<110000000 and b['peer']['events']==0 and b['peer']['state']=='Complete' and not b['peer']['pending'],
        ccb_released_before_input=all(mem[x+21-0x20000000]==mem[x+22-0x20000000]==0 for mem in (am,bm) for x in slots),
        explicit_new_device_event=d['input']['accepted'] and d['input']['pc']==b['pc'] and d['input']['ticks']==b['ticks'] and d['input']['irq'] and d['input']['pending'],
        original_opened_return=d['stopped'] and d['pc']==p['finished']==0x4d3fc4 and d['calls']==1,
        same_wsf_task=entry[4]==exit[1]==a['context'][2] and entry[5]&511==exit[2]&511==0,
        original_stack=entry[2]==exit[0]+16 and struct.unpack_from('<I',dm,entry[4]+48-0x20000000)[0]<=exit[0]<struct.unpack_from('<I',dm,entry[4]+48-0x20000000)[0]+4*struct.unpack_from('<I',dm,entry[4]+84-0x20000000)[0],
        exact_decoded_connection=len(msg)==36 and msg[4]==0 and struct.unpack_from('<H',msg,6)[0]==64 and msg[8:16]==bytes.fromhex('0100112233445566'),
        ccb_reallocated=len(active)==1 and dm[active[0]+21-0x20000000]==3 and struct.unpack_from('<H',dm,active[0]+12-0x20000000)[0]==64 and dm[active[0]+16-0x20000000]==dm[active[0]+25-0x20000000]==1,
        original_gpio_irq_and_cleanup=d['irq_entries']==1 and d['gpio']['edges']==b['gpio']['edges']+1 and not d['gpio']['irq'] and not d['gpio']['pending'] and counter(dm)==counter(bm)+1,
        generation_wire_set_preserved=all(v['generation']==1 and v['rejection']=='' and v['peer']['commands']==59 and v['peer']['replies']==60 for v in (a,b,d)) and d['peer']['events']==1 and not d['peer']['pending'] and d['peer']['state']=='Complete',
        bounded_new_connection=0<d['ticks']-d['input']['ticks']<=2000000000,
        no_guard_or_cpu_fault=all(not any(g['accesses'] for g in v['guards']) and v['cfsr']==v['hfsr']==v['memory_violations']==0 for v in (a,b,d)),
        rtc_no_new_write=all(v['rtc']['commits']==1 and not v['rtc']['pending'] and v['rtc']['error']=='none' for v in (a,b,d)) and abs(rtc_ns-(d['ticks']-a['ticks']))<10000000,
        frozen_sensor_and_no_hardware=all(v['gaf']['on_demand']['pending'] and v['gaf']['on_demand']['completed_calculations']==0 and not v['hardware_accessed'] for v in (a,b,d)))
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,single_stock24_timeout_reconnect_scenario_passed=True,credit_restored_by_original=True,ccb=active[0],original_task=entry[4],credit_store_to_ready_return_ns=a['ticks']-a['start_ticks'],settlement_ns=b['ticks']-a['ticks'],reconnect_ns=d['ticks']-d['input']['ticks'],post_reset_att_verified=False,full_application_recovery_verified=False,other_original_timeout_reconnect_verified=False,e14_complete=False,normal_gaf_verified=False,hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.capture,a.output);print(json.dumps(dict(passed=True,checks=len(r['checks']),credit_restored=True,original_reconnected=True,e14_complete=False)))

if __name__=='__main__':main()
