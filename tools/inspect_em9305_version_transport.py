"""Saved native version-response effects, original destination, and strict MRAM end."""
import argparse,json,hashlib,struct
from pathlib import Path
from inspect_em9305_hci_framing import discover,literal
from inspect_ambiq_target import decode
from run_native_candidate import memory_exports,validate_memory_exports

SRAM=0x20000000

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def inspect(s,folder,case,audit_name,data,status):
    f=s/folder/case;r=json.loads((f/'report.json').read_text());p=json.loads((f/'plan.json').read_text());ap=s/'em9305-version-saved-audit-01'/audit_name/'report.json';audit=json.loads(ap.read_text())
    if not audit['passed'] or not r['passed'] or r['hardware_accessed']:raise ValueError('Unverified native evidence')
    for name,pin in audit['capture_hashes'].items():
        if sha(f/name)!=pin:raise ValueError('Changed saved evidence: '+name)
    validate_memory_exports(f,memory_exports(p),r['memory_exports']);raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();c=discover(raw)
    instruction=decode(raw,c['read']-0x35e,4)[0]
    if instruction.op_str.split(',')[0]!='r4':raise ValueError('Different original version destination')
    dest=literal(raw,instruction)
    if not SRAM<=dest<=SRAM+len(ram)-4:raise ValueError('Version slot outside captured SRAM')
    prior=s/p['source_root']/case;pr=json.loads((prior/'report.json').read_text());pp=json.loads((prior/'plan.json').read_text());validate_memory_exports(prior,memory_exports(pp),pr['memory_exports']);before=(prior/'exports/sram-full.bin').read_bytes()[dest-SRAM:dest-SRAM+4];after=ram[dest-SRAM:dest-SRAM+4]
    expected=before if status else bytes.fromhex(data)
    if after!=expected:raise ValueError('Generic read copy/status result differs')
    logged=status==0 and data!='ffffffff';d=r['diagnostics']
    expected_diag=dict(accepted_commands=2,replies=2,frames=5,commands=10,command_hex='0101fd05884bf00008',version_command_hex='0101fd050020400004',version_data_hex=data,version_status=status,version_log_seen=logged,version_sample_log=logged,retention_unique=True)
    if any(type(d[k])!=type(v) or d[k]!=v for k,v in expected_diag.items()):raise ValueError('Different version response path')
    guards=[g for g in r['observed']['guards'] if g['accesses']]
    expected_pc=0x484e64 if case=='stock24' else 0x4824b0
    if len(guards)!=1 or guards[0]['name']!='guard_mram_tail' or guards[0]['address']!=0x7ff000 or guards[0]['width']!=1 or r['observed']['pc']!=expected_pc:raise ValueError('Unknown MRAM frontier')
    return dict(case=case,fixture_data=data,fixture_status=status,version_slot=dest,slot_before=before.hex(),slot_after=after.hex(),version_logged=logged,next_pc=expected_pc,next_unbacked_address=0x7ff000,diagnostics=d,raw_sha256=sha(f/'main.bin'),native_report_sha256=sha(f/'report.json'),audit_sha256=sha(ap))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve existing evidence')
    rows=[inspect(a.simulator,'em9305-version-sample-main-02',case,case,'04030201',0) for case in ['stock24','stock23','cfw']]
    rows += [inspect(a.simulator,'em9305-version-erased-main-01','stock24','erased','ffffffff',0),inspect(a.simulator,'em9305-version-error-main-01','stock24','error','04030201',1)]
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,native_rerun=False,hardware_accessed=False,real_version_known=False,controller_nvm_modified=False,whole_main_boot_verified=False,display_verified=False),indent=2)+'\n');print('saved version response scenarios: 5/5 passed')

if __name__=='__main__':main()
