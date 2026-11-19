"""Explain WSF expiry using original tick arithmetic under the declared clock profile."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import struct

from probe_wsf_tick_accounting import SETUP,POST
from run_runtime_connection_m55 import sha
from verify_kv_persistence_cycle import validate_capture
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal


def read(p):return json.loads(p.read_text())
def word(data,address):return struct.unpack_from('<I',data,address-0x20000000)[0]
def logged(cap,label):
    rows=[json.loads(l.split(label+' ',1)[1]) for l in (cap/'renode.log').read_text().splitlines() if l.startswith(label+' ')]
    if len(rows)!=1:raise ValueError('Missing or duplicated '+label)
    return rows[0]


def verify(s,cap,out):
    ref=s/'hci-response-loss-native-01/fault';validate_capture(cap);validate_capture(ref)
    manifest=read(s/'hci-response-loss-research-01/manifest.json')
    for name in ('capture-files.json','main.bin','strict.cs','board.repl','run.py','activation.cs'):
        pin=manifest['files'][str((ref/name).relative_to(s))]
        if sha(ref/name)!=pin['sha256'] or (ref/name).stat().st_size!=pin['bytes']:raise ValueError('Changed reference')
    trace=read(cap/'exports/wsf-ticks.json');v=read(cap/'exports/hci-timeout.json');before=(cap/'exports/disconnect-sram.bin').read_bytes();after=(cap/'exports/hci-timeout-sram.bin').read_bytes()
    start=trace['start'];rows=trace['rows'];raw=(cap/'main.bin').read_bytes()
    if len(start)!=6 or not rows or any(len(r)!=9 for r in rows):raise ValueError('Incomplete tick trace')
    # All captured updates occur after timer programming and while it is active.
    deltas=[r[1]-r[2] for r in rows];arguments=[r[3] for r in rows];remainders=[delta%10 for delta in deltas]
    summed=sum(arguments);discarded=sum(remainders);carry=start[1]-rows[0][2];final_os=word(after,trace['previous_tick_address']);elapsed_os=final_os-start[1]
    period=word(before,0x2007745c);frequency=32768;rate=Fraction(frequency,period);quantum=Fraction(1000000000,1)/rate
    observed=v['timeout_entry_ticks']-v['timer_start_ticks'];counter_duration=elapsed_os*quantum;phase_residual=counter_duration-observed
    phase_samples=[dict(os_delta=r[1]-start[1],elapsed_ns=r[0]-start[0],residual_ns=float((r[1]-start[1])*quantum-(r[0]-start[0]))) for r in rows]
    source={pc:decode(raw,pc,n) for pc,n in ((0x45882c,8),(0x4587a0,0x72),(0x44cd88,12),(0x4d7d44,0x24),(0x4d7cb6,0x34))}
    init=source[0x45882c];kernel=source[0x44cd88];dispatch=source[0x4d7d44]
    observer=Path(__file__).with_name('renode-wsf-tick-observer.cs').read_bytes();anchor='    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n'
    checks=dict(
        unchanged_model_firmware_board=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('strict.cs','main.bin','board.repl','sram-fill.bin','itcm-fill.bin','connection-profile.json')),
        exact_added_observer=(cap/'activation.cs').read_bytes()==(ref/'activation.cs').read_bytes()+b'\n'+observer and (cap/'renode-wsf-tick-observer.cs').read_bytes()==observer,
        exact_observation_extension=(cap/'run.py').read_text()==(ref/'run.py').read_text().replace(anchor,SETUP+anchor)+POST,
        original_reports_identical=all(read(cap/'exports'/n)==read(ref/'exports'/n) for n in ('connection.json','disconnect.json','frozen-peer-fault.json','hci-timeout.json')),
        entire_sram_identical=all((cap/'exports'/n).read_bytes()==(ref/'exports'/n).read_bytes() for n in ('connection-sram.bin','disconnect-sram.bin','hci-timeout-sram.bin')),
        logged_values=trace==logged(cap,'BLACKWALL_WSF_TICKS') and v==logged(cap,'BLACKWALL_HCI_RESPONSE_LOSS'),
        no_overflow=not trace['overflow'] and trace['hardware_accessed'] is False,
        observed_programming=start[0]==v['timer_start_ticks'] and start[5]==v['timer_seconds']==10 and start[4]==0,
        original_tick_period=period==word(after,0x2007745c)==32 and init[0].op_str.startswith('r5, [pc,') and literal(raw,init[0])==0x2007745c and init[1].op_str=='r0, #0x20' and init[2].op_str=='r0, [r5]',
        original_kernel_counter=literal(raw,kernel[0])==trace['os_tick_address']==0x20077660 and [i.op_str for i in kernel[1:4]]==['r4, [r0]','r4, r4, #1','r4, [r0]'],
        original_divisor10=literal(raw,dispatch[3])==trace['previous_tick_address']==0x20077b3c and any(i.mnemonic=='udiv' and i.op_str=='r0, r1, r0' for i in dispatch) and sum(i.op_str=='r0, #0xa' for i in dispatch)==2,
        original_irq_catchup=any(i.mnemonic=='udiv' and i.op_str=='r5, r1, r2' for i in source[0x4587a0]) and any(i.mnemonic=='bl' and i.operands[0].imm==0x44cd78 for i in source[0x4587a0]),
        declared_stimer_clock=logged(cap,'BLACKWALL_STIMER_CLOCK')['frequency']==32768 and logged(cap,'BLACKWALL_STIMER_CLOCK')['config']==0x103 and 'case ClockSelectValues.XTAL_32KHZ:\n                frequencySet = 32768;' in (cap/'strict.cs').read_text(),
        update_formula=all(delta>=10 and r[3]==delta//10 and r[5]==r[8]==1 and r[0]>=start[0] and r[6]>=r[0] for r,delta in zip(rows,deltas)),
        exact_decrements=rows[0][4]==1000 and rows[-1][7]==0 and all(r[7]==max(0,r[4]-r[3]) for r in rows) and all(a[7]==b[4] and a[1]==b[2] for a,b in zip(rows,rows[1:])),
        wsf_total=summed==1000 and sum(deltas)==final_os-rows[0][2] and summed*10+discarded-carry==elapsed_os and final_os==rows[-1][1],
        observed_rate_within_one_tick=abs(phase_residual)<quantum and all(abs(Fraction(r[1]-start[1])*quantum-(r[0]-start[0]))<quantum for r in rows),
        original_expiry_still_observed=v['timeout_entered'] and not v['timeout_returned'] and v['timer_seconds']==10 and v['guards']==read(ref/'exports/hci-timeout.json')['guards'])
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,additional_observer_state_equal_for_this_case=True,raw_json_bytes_equal=(cap/'exports/hci-timeout.json').read_bytes()==(ref/'exports/hci-timeout.json').read_bytes(),
        wsf_update_arguments=arguments,rtos_deltas=deltas,discarded_remainders=remainders,prestart_rtos_carry=carry,elapsed_rtos_ticks=elapsed_os,
        stimer_hz=frequency,rtos_period_stimer_counts=period,rtos_ticks_per_virtual_second=float(rate),programmed_wsf_ticks=summed,
        counter_duration_ns=float(counter_duration),observed_virtual_ns=observed,phase_residual_ns=float(phase_residual),phase_samples=phase_samples,
        difference_components_ns=dict(rate=10000000000-float(10000*quantum),epoch_and_integer_accounting=float((carry-discarded)*quantum),counter_phase=float(phase_residual)),
        tick_accounting_verified=True,physical_clock_accuracy_verified=False,si_ten_second_timeout_verified=False,recovery_complete=False,normal_gaf_verified=False,e14_complete=False,hardware_accessed=False,
        scope='explained under unchanged declared32768Hz clock and original32-count/WSF divide10 code; not a hardware timing calibration')
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    r=verify(a.simulator,a.capture,a.output);print(json.dumps(dict(passed=True,checks=len(r['checks']),updates=r['wsf_update_arguments'],os_hz=r['rtos_ticks_per_virtual_second'],physical_clock_verified=False)))


if __name__=='__main__':main()
