"""Verify bounded reset generation integration without claiming full recovery."""
import argparse
import json
from pathlib import Path
import struct
from controller_reset_generation_model import compose
from probe_controller_reset_generations import GENERATION_POST
from run_runtime_connection_m55 import sha
from verify_kv_persistence_cycle import validate_capture

def read(p):return json.loads(p.read_text())

def verify(s,cap,out,enabled):
    ref=s/'controller-reset-boundary-native-01';validate_capture(cap);validate_capture(ref)
    pins=read(s/'controller-reset-boundary-research-01/manifest.json')['files']
    for n in ('capture-files.json','strict.cs','main.bin','board.repl','run.py','activation.cs'):
        pin=pins[str((ref/n).relative_to(s))]
        if sha(ref/n)!=pin['sha256'] or (ref/n).stat().st_size!=pin['bytes']:raise ValueError('Changed reference')
    h=read(cap/'exports/hci-timeout.json');old=read(ref/'exports/hci-timeout.json');g=read(cap/'exports/controller-generation.json');reset=read(cap/'exports/controller-reset.json')
    expected_board=(ref/'board.repl').read_text().replace('    runtimeReadvertise: true\n','    runtimeReadvertise: true\n    controllerResetLimit: '+('1' if enabled else '0')+'\n')
    expected_run=(ref/'run.py').read_text().replace('deadline=time.time()+75','deadline=time.time()+105').replace('<11500000000','<18000000000')+GENERATION_POST
    profile=read(ref/'connection-profile.json');profile.update(model_sha256=sha(cap/'strict.cs'),controller_reset_limit=1 if enabled else 0)
    def logged(label):return [json.loads(line.split(label+' ',1)[1]) for line in (cap/'renode.log').read_text().splitlines() if line.startswith(label+' ')]
    checks=dict(
        exact_model=(cap/'strict.cs').read_text()==compose((ref/'strict.cs').read_text()),
        exact_board=(cap/'board.repl').read_text()==expected_board,
        exact_run=(cap/'run.py').read_text()==expected_run,
        exact_profile=read(cap/'connection-profile.json')==profile,
        unchanged_firmware_observer_inputs=all((cap/n).read_bytes()==(ref/n).read_bytes() for n in ('main.bin','sram-fill.bin','itcm-fill.bin','activation.cs','renode-controller-reset-observer.cs','hci-timeout-contract.json')),
        original_prefix_reports=all(read(cap/'exports'/n)==read(ref/'exports'/n) for n in ('connection.json','disconnect.json','frozen-peer-fault.json')),
        original_prefix_sram=all((cap/'exports'/n).read_bytes()==(ref/'exports'/n).read_bytes() for n in ('connection-sram.bin','disconnect-sram.bin')),
        logged_values=logged('BLACKWALL_CONTROLLER_GENERATION')==[g] and logged('BLACKWALL_CONTROLLER_RESET')==[reset] and logged('BLACKWALL_HCI_RESPONSE_LOSS')==[h],
        original_timeout_prefix=all(h[k]==old[k] for k in ('timer_starts','timer_seconds','timer_start_ticks','timeout_entered','timeout_entry_ticks','timeout_entry','timeout_message','lost')) and h['calls'][:5]==old['calls'],
        cpu_faults_absent=h['cfsr']==h['hfsr']==h['memory_violations']==0 and not h['overflow'] and not reset['overflow'],
        no_hardware=g['hardware_accessed'] is False and reset['hardware_accessed'] is False and h['hardware_accessed'] is False,
        bounded_limit=g['limit']==(1 if enabled else 0) and g['rejection']=='')
    if enabled:
        rows=[(r,reset['states'][i]) for i,r in enumerate(reset['rows']) if r[3]==93];history=g['history'].split(':');stack=(cap/'exports/hci-timeout-sram.bin').read_bytes()
        checks.update(
            original_qualified_reset=len(rows)==4 and [r[4] for r,state in rows]==[0,0,0,1] and all(r[12:14]==[1,1] for r,state in rows) and reset['final']['released_us']-reset['final']['asserted_us']==17784 and reset['final']['released'],
            fresh_generation=g['generation']==1 and len(history)==10 and history[:8]==['0','246','59','60','4','1','0','1'] and history[9]==old['peer']['accepted'] and len(history[8].split(','))==59,
            release_transition=all(state=='Exhausted' and r[9:12]==[246,59,60] for r,state in rows[:3]) and rows[-1][1]=='Queued' and rows[-1][0][9:12]==[0,0,0],
            callback_return_boundary=h['timeout_returned'] and h['pc']==0x563d24 and h['timeout_return_ticks']==h['end_ticks'] and [r[0] for r in h['calls']]==[0x563d08,0x563d0e,0x563d12,0x563d16,0x563d1c,0x563d20],
            original_stack_task=h['timeout_exit'][0]==h['timeout_entry'][1]-8 and h['timeout_exit'][1]==h['timeout_entry'][3] and h['timeout_exit'][2]&0x1ff==0 and struct.unpack_from('<I',stack,h['timeout_exit'][0]-0x20000000+4)[0]==h['timeout_entry'][2],
            strict_early_startup=h['peer']['commands']==h['peer']['replies']==2 and h['peer']['state']=='Consumed' and h['peer']['events']==h['peer']['readvertising_commands']==h['peer']['readvertising_replies']==h['peer']['dropped']==0 and not h['peer']['pending'],
            no_guard=not any(x['accesses'] for x in h['guards']),
            no_credit_injection=h['final_credit']==old['final_credit']==0 and h['final_timer']==old['final_timer'] and h['final_opcode']==old['final_opcode'])
    else:
        checks.update(legacy_failure_exact=h==old and reset==read(ref/'exports/controller-reset.json') and (cap/'exports/hci-timeout-sram.bin').read_bytes()==(ref/'exports/hci-timeout-sram.bin').read_bytes(),no_generation=g['generation']==0 and g['history']=='')
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,enabled=enabled,generation=g['generation'],callback_return_instruction_reached=h['timeout_returned'],callback_return_executed_verified=False,full_startup_verified=False,application_error_consumed_verified=False,reconnection_verified=False,recovery_complete=False,e14_complete=False,hardware_accessed=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);p.add_argument('--disabled',action='store_true');a=p.parse_args();r=verify(a.simulator,a.capture,a.output,not a.disabled)
    print(json.dumps(dict(passed=True,checks=len(r['checks']),generation=r['generation'],recovery_complete=False)))

if __name__=='__main__':main()
