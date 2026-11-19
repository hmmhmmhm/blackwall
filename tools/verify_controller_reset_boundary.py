"""Audit the original reset pulse at the existing single-use controller boundary."""
import argparse
import json
from pathlib import Path
from probe_controller_reset_boundary import SETUP,POST
from run_runtime_connection_m55 import sha
from verify_kv_persistence_cycle import validate_capture
from inspect_ambiq_target import decode

def read(p):return json.loads(p.read_text())

def verify(s,cap,out):
    ref=s/'hci-response-loss-native-01/fault';validate_capture(cap);validate_capture(ref)
    manifest=read(s/'hci-response-loss-research-01/manifest.json')
    for n in ('capture-files.json','strict.cs','main.bin','board.repl','run.py','activation.cs'):
        p=ref/n;pin=manifest['files'][str(p.relative_to(s))]
        if sha(p)!=pin['sha256'] or p.stat().st_size!=pin['bytes']:raise ValueError('Changed pinned reference')
    value=read(cap/'exports/controller-reset.json');hci=read(cap/'exports/hci-timeout.json');rows=value['rows'];states=value['states'];phases=value['phases'];final=value['final']
    if not rows or len(rows)!=len(states) or len(rows)!=len(phases) or any(len(r)!=14 for r in rows):raise ValueError('Incomplete GPIO trace')
    reset=[(r,states[i],phases[i]) for i,r in enumerate(rows) if r[3]==93]
    lows=[r for r,state,phase in reset if r[4]==0];highs=[r for r,state,phase in reset if r[4]==1]
    if len(lows)!=3 or len(highs)!=1:raise ValueError('Missing original reset writes')
    high=highs[0];low=lows[0];source=(cap/'strict.cs').read_text();raw=(cap/'main.bin').read_bytes()
    observer=Path(__file__).with_name('renode-controller-reset-observer.cs').read_bytes();anchor='    start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n'
    def ins(pc,n):return [i.mnemonic+' '+i.op_str for i in decode(raw,pc,n)]
    logged=[json.loads(line.split(' ',1)[1]) for line in (cap/'renode.log').read_text().splitlines() if line.startswith('BLACKWALL_CONTROLLER_RESET ')]
    checks=dict(
        unchanged_inputs=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('strict.cs','main.bin','board.repl','sram-fill.bin','itcm-fill.bin','connection-profile.json','hci-timeout-contract.json')),
        exact_observer=(cap/'activation.cs').read_bytes()==(ref/'activation.cs').read_bytes()+b'\n'+observer and (cap/'renode-controller-reset-observer.cs').read_bytes()==observer,
        exact_run_extension=(cap/'run.py').read_text()==(ref/'run.py').read_text().replace(anchor,SETUP+anchor)+POST,
        original_reports_equal=all(read(cap/'exports'/n)==read(ref/'exports'/n) for n in ('connection.json','disconnect.json','frozen-peer-fault.json','hci-timeout.json')),
        whole_sram_equal=all((cap/'exports'/n).read_bytes()==(ref/'exports'/n).read_bytes() for n in ('connection-sram.bin','disconnect-sram.bin','hci-timeout-sram.bin')),
        complete_logged_trace=logged==[value] and not value['overflow'] and value['hardware_accessed'] is False,
        ordered_after_timeout=all(a[0]<=b[0] for a,b in zip(rows,rows[1:])) and low[0]>hci['timeout_entry_ticks'] and high[0]<hci['end_ticks'],
        original_gpio_callers=[r[2] for r,state,phase in reset]==[0x5013eb,0x5012f3,0x501bd5,0x501be3] and [r[1] for r,state,phase in reset]==[0x4966ec]*3+[0x496704],
        original_low_high_code=ins(0x501bcc,8)==['movs r1, #0','movs r0, #0x5d','bl #0x4966be'] and ins(0x501bda,8)==['movs r1, #1','movs r0, #0x5d','bl #0x4966be'],
        original_timeout_reinit_call=ins(0x563d1a,6)==['movs r0, #0','bl #0x4dcec0'] and ins(0x4dcee4,4)==['bl #0x5013f8'] and ins(0x501522,4)==['bl #0x501ba0'],
        low_preserves_epoch=all(r[5]==1 and r[6]==0 and r[7]==low[7] for r in lows) and low[7]==low[0]//1000,
        release_qualified=high[5]==0 and high[6]==1 and high[7]==low[7] and high[8]==high[0]//1000 and final['released'] and not final['held'] and final['asserted_us']==low[7] and final['released_us']==high[8] and final['released_us']-final['asserted_us']>=final['minimum_us']>0,
        cs_high_through_reset=all(r[12:14]==[1,1] for r,state,phase in reset),
        consumed_peer_stays_exhausted=all(state=='Exhausted' and r[9:12]==[246,59,60] for r,state,phase in reset) and hci['peer']['state']=='Exhausted',
        source_single_use_guard='phase=HasReadScenario && Frames>0?Phase.Exhausted:Phase.Unreleased;' in source and 'if(phase!=Phase.Exhausted)phase=valid?Phase.Queued:Phase.Unreleased;' in source,
        existing_failure_preserved=hci['pc']==0x50190c and not hci['timeout_returned'] and hci['cfsr']==hci['hfsr']==hci['memory_violations']==0 and [(g['name'],g['address'],g['accesses']) for g in hci['guards'] if g['accesses']]==[('guard',0x40010410,1)])
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,reset_writes=len(reset),pulse_us=final['released_us']-final['asserted_us'],minimum_us=final['minimum_us'],ready_us=final['ready_us'],reset_rows=[dict(ticks=r[0],pc=r[1],lr=r[2],level=r[4],state=state,phase=phase) for r,state,phase in reset],
        additional_observer_captured_state_equal=True,raw_hci_json_bytes_equal=(cap/'exports/hci-timeout.json').read_bytes()==(ref/'exports/hci-timeout.json').read_bytes(),model_changes=False,firmware_changes=False,recovery_complete=False,physical_timing_verified=False,e14_complete=False,hardware_accessed=False,
        next_contract='opt-in qualified reset generations with strict initial handshake and startup commands; no unconditional replay or credit/ACK injection')
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.capture,a.output)
    print(json.dumps(dict(passed=True,checks=len(r['checks']),pulse_us=r['pulse_us'],recovery_complete=False)))

if __name__=='__main__':main()
