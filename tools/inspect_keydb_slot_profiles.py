"""Saved original M55 keydb mock profiles and their next unsupported consumers."""
import argparse,hashlib,json,struct
from pathlib import Path
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from run_native_candidate import memory_exports,validate_memory_exports

SRAM=0x20000000

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def inspect(s,folder,case,audit_name,profile):
    f=s/folder/case;r=json.loads((f/'report.json').read_text());plan=json.loads((f/'plan.json').read_text());ap=s/'keydb-slot-saved-audit-01'/audit_name/'report.json';audit=json.loads(ap.read_text())
    if not r['execution_passed'] or not audit['passed'] or r['hardware_accessed']:raise ValueError('Unverified capture')
    for name,pin in audit['capture_hashes'].items():
        if sha(f/name)!=pin:raise ValueError('Changed saved native '+name)
    validate_memory_exports(f,memory_exports(plan),r['memory_exports']);d=r['diagnostics'];regs=r['observed']['register_context'];raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();guards=[g for g in r['observed']['guards'] if g['accesses']]
    if len(guards)!=1:raise ValueError('Ambiguous stop')
    expected_counts={'zero':(2570,10),'uninit-ff':(257,1),'unknown':(0,0),'not-selected':(0,0)}[profile]
    if (d['keydb_reads'],d['keydb_slots'])!=expected_counts or d['keydb_position']!=0 or d['keydb_profile']!=profile or d['accepted_commands']!=2 or d['replies']!=2:raise ValueError('Different profile or BLE history')
    evidence={}
    if profile=='zero':
        if guards[0]['name']!='guard_mram_tail' or guards[0]['address']!=0x7ff000 or guards[0]['width']!=4 or r['observed']['pc']!=0x439c0c:raise ValueError('Different copy read frontier')
        ins=decode(raw,0x439c0a,4)[0]
        if ins.mnemonic!='ldm.w' or not ins.op_str.startswith('r1!,'):raise ValueError('Not the original LDM instruction')
        h=d['keydb_last_pc']+0x87c;call=decode(raw,h-0x468,4)[0];length=decode(raw,h-0x46e,2)[0]
        if call.op_str!='#0x439be4' or (length.mnemonic,length.op_str)!=('movs','r2, #0xc8') or regs['r14']!=((call.address+4)|1) or regs['r1']!=0x7ff000 or regs['r2']!=184:raise ValueError('Different original 200-byte copy context')
        evidence=dict(copy_bytes_requested=200,copy_source=regs['r1'],copy_destination=regs['r0'],ldm_instruction_pc=ins.address,reported_pc=r['observed']['pc'],copy_complete=False)
    elif profile=='uninit-ff':
        if guards[0]['address']!=0x40021014 or guards[0]['operation']!='write' or guards[0]['value']!=0x3f or r['observed']['pc']!=0x494ada:raise ValueError('Different MRAM prelude boundary')
        h=d['keydb_last_pc']+0x87c;buffer=literal(raw,decode(raw,h-0x9c2+14,4)[0])
        if regs['r5']!=buffer or ram[buffer-SRAM:buffer-SRAM+256]!=bytes(256) or regs['r6']*4+0x400000!=0x7ff000 or regs['r7']!=32:raise ValueError('Different original zero-write preparation')
        stack=regs['r13']-SRAM;key,saved_lr=struct.unpack_from('<II',ram,stack+8)
        if key!=0x12344321:raise ValueError('Different saved program constant')
        prior=json.loads((s/'mram-keydb-contract-01/report.json').read_text());row=next(x for x in prior['cases'] if x['case']==case);callee=row['program_argument_samples'][0]['callee']
        calls=[i for i in decode(raw,callee-0x54,0x54) if i.mnemonic=='bl' and i.op_str=='#0x494aae']
        if len(calls)!=1 or saved_lr!=((calls[0].address+4)|1):raise ValueError('Different call into cache prelude')
        evidence=dict(source_buffer=buffer,prepared_destination=regs['r6']*4+0x400000,words=regs['r7'],program_constant=key,cache_call=calls[0].address,actual_mram_program_executed=False,heal_uart_log_seen=d['keydb_heal_log'])
    else:
        src=s/plan['source_root']/case;prior=json.loads((src/'report.json').read_text())
        if r['observed']!=prior['observed'] or r['selected_observation']!=prior['selected_observation']:raise ValueError('Unknown/off changed original CPU or events')
        evidence=dict(exact_source_cpu_events=True)
    return dict(case=case,profile=profile,diagnostics=d,evidence=evidence,original_semantic_passed=r['semantic_validation']['passed'],reviewed_audit_passed=True,native_report_sha256=sha(f/'report.json'),audit_sha256=sha(ap),raw_sha256=sha(f/'main.bin'))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior report')
    rows=[inspect(a.simulator,'keydb-slot-zero-main-01',case,case,'zero') for case in ['stock24','stock23','cfw']]
    rows += [inspect(a.simulator,'keydb-slot-uninit-main-01','stock24','uninit','uninit-ff'),inspect(a.simulator,'keydb-slot-unknown-main-01','stock24','unknown','unknown'),inspect(a.simulator,'keydb-slot-control-01','stock24','control','not-selected')]
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_rerun=False,hardware_accessed=False,actual_pairing_data_known=False,writable_mram_implemented=False,whole_main_boot_verified=False,display_verified=False),indent=2)+'\n');print('saved keydb profiles: 6/6 passed')

if __name__=='__main__':main()
