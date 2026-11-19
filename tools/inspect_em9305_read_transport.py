"""Inspect saved original-reset first-read scenarios without guest execution."""
import argparse,json,hashlib
from pathlib import Path
from inspect_em9305_hci_framing import discover,literal
from inspect_ambiq_target import decode
from run_native_candidate import memory_exports,validate_memory_exports

BASE,SRAM=0x438000,0x20000000

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def inspect(simulator,folder,case,audit_name,zero=False,capacity=9):
    source=simulator/folder/case
    report=json.loads((source/'report.json').read_text());plan=json.loads((source/'plan.json').read_text())
    audit_path=simulator/'em9305-read-command-saved-audit-01'/audit_name/'report.json';audit=json.loads(audit_path.read_text())
    if not audit['passed'] or not report['passed'] or plan['runtime_edits'] or report['hardware_accessed']:raise ValueError('Unverified capture or changed execution scope')
    for name,pin in audit['capture_hashes'].items():
        if sha(source/name)!=pin:raise ValueError('Saved native evidence changed: '+name)
    validate_memory_exports(source,memory_exports(plan),report['memory_exports'])
    raw=(source/'main.bin').read_bytes();ram=(source/'exports/sram-full.bin').read_bytes();c=discover(raw)
    instruction=decode(raw,c['read']-0x474,4)[0]
    if instruction.op_str.split(',')[0]!='r5':raise ValueError('Unknown RF-state pointer')
    state_address=literal(raw,instruction)
    if ram[state_address-SRAM]!=0:raise ValueError('Original RF-state error')
    data='0000000000000000' if zero else '8003000000000000';frames=3 if capacity==9 else 5
    d=report['diagnostics'];expected=dict(accepted_commands=1,replies=1,command_hex='0101fd05884bf00008',read_data_hex=data,frames=frames,headers=frames,payloads=frames,commands=frames*2,active_log_seen=True,trim_match_log=not zero,trim_zero_log=zero,retention_unique=True,peer_state='Exhausted' if zero else 'Complete')
    if any(type(d[k])!=type(v) or d[k]!=v for k,v in expected.items()):raise ValueError('Native command/branch differs')
    guards=[g for g in report['observed']['guards'] if g['accesses']]
    pc=c['read']+(0x72a if zero else -0x260)
    if report['observed']['pc']!=pc or len(guards)!=1 or guards[0]['address']!=0x40010410 or guards[0]['operation']!='read':raise ValueError('Different guarded frontier')
    board=(source/'board.repl').read_text()
    if 'readDataHex: "'+data+'"' not in board or 'writeCapacity: '+str(capacity) not in board:raise ValueError('Fixture differs')
    pending=None
    if not zero:
        regs=report['observed']['register_context'];address,n=regs['r10'],regs['r8']
        if regs['r9']!=0 or n!=9 or not SRAM<=address<=SRAM+len(ram)-n:raise ValueError('Unknown next command buffer')
        pending=ram[address-SRAM:address-SRAM+n].hex()
        if pending!='0101fd050020400004':raise ValueError('Different second read command')
    return dict(case=case,read_fixture=data,write_capacity=capacity,command_hex=d['command_hex'],next_pending_packet=pending,next_pc=pc,rf_state_address=state_address,rf_state=0,diagnostics=d,capture=str(source),audit_sha256=sha(audit_path),raw_sha256=sha(source/'main.bin'),sram_sha256=sha(source/'exports/sram-full.bin'))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve existing evidence')
    rows=[inspect(a.simulator,'em9305-read-command-zero-main-01','stock24','zero',True)]
    rows += [inspect(a.simulator,'em9305-read-command-trim7-main-01',case,case) for case in ['stock24','stock23','cfw']]
    rows += [inspect(a.simulator,'em9305-read-command-capacity4-main-01','stock24','capacity4',capacity=4)]
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    result=dict(passed=True,cases=rows,native_rerun=False,hardware_accessed=False,whole_main_boot_verified=False,display_verified=False,real_read_data_known=False)
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('saved first-read scenarios: 5/5 passed')

if __name__=='__main__':main()
