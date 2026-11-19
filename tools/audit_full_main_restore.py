"""Independently audit actual MRAM bytes, native ARM logs and fresh-reset lineage."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from run_original_boot_screen import PRIVATE,EXPORTS,assess,valid_frame,logged_json,same
from run_restored_boot import reboot_path_matches


def run(restore,screen,matrix,output):
    restore,screen,matrix,output=map(lambda p:Path(p).resolve(),(restore,screen,matrix,output))
    if any(not p.is_relative_to(PRIVATE) for p in (restore,screen,matrix,output)) or output.exists():raise ValueError('Private inputs and fresh audit output required')
    sha=lambda d:hashlib.sha256(d).hexdigest()
    read=lambda p:json.loads(p.read_text())
    checks={};root=PRIVATE/'simulator'
    main=(root/'sustained-render-guard-native-01/stock24/main.bin').read_bytes()
    base=(restore/'body-capture/mram.bin').read_bytes();body=(restore/'body/exports/final-mram.bin').read_bytes();final=(restore/'vector/exports/final-mram.bin').read_bytes()
    payload=main[16:]+base[0x38000+len(main):0x38000+((len(main)+15)&~15)]
    expected=bytearray(base);expected[0x38010:0x38010+len(payload)]=payload;checks['body_whole_mram']=body==expected
    expected[0x38000:0x38010]=main[:16];checks['vector_whole_mram']=final==expected;checks['main_full_hash']=sha(final[0x38000:0x38000+len(main)])==sha(main)
    for name,count in [('body',(len(payload)+255)//256),('vector',1)]:
        p=restore/name;r=read(p/'report.json');native=logged_json((p/'renode.log').read_text(),'BLACKWALL_RECOVERY_WRITER ')
        checks[name+'_actual_arm_counters']=native['context_entries']==native['context_returns']==native['writer_entries']==1 and native['rom_calls']==native['stock_mram_entries']==count and native['programmed_bytes']==(len(payload) if name=='body' else 16)
        checks[name+'_arm_context']=native['initial_regs']==native['return_regs'] and native['initial_special']==native['return_special'] and native['initial_float']==native['return_float'] and native['violations']==0
        checks[name+'_whole_hash']=sha(body if name=='body' else final)==r['final_mram_sha256']
        checks[name+'_owned_job_removed']=read(p/'renode.process.json')['status']=='removed'
    e=screen/'exports';v={k:read(e/n) for k,n in EXPORTS.items()};rep=read(screen/'report.json');manifest=read(screen/'manifest.json');removed={r['name']:r for r in rep['cleanup']}
    v['image_equal']=removed['exports/guest-boot.bin']['sha256']==manifest['boot_sha256'] and removed['exports/guest-main.bin']['sha256']==sha(main)
    v['cadence_equal']=removed['exports/cadence-before-sram.bin']['sha256']==removed['exports/cadence-after-sram.bin']['sha256']
    raw=(e/'complete-screen.bin').read_bytes();v['frame_equal']=valid_frame(v['screen'],raw,(e/'main-state-sram.bin').read_bytes())
    checks.update({'screen_'+k:val for k,val in assess(v).items()})
    checks['screen_actual_native_records']=all(same(logged_json((screen/'native.log').read_text(),tag),v[k]) for k,tag in [('native','BLACKWALL_BOOT_RESET '),('wire','BLACKWALL_BOOT_WIRE '),('screen','BLACKWALL_BOOT_SCREEN '),('delegated','BLACKWALL_DELEGATED_GUARDS ')])
    checks['screen_actual_writer_lineage']=manifest['persistent_input_sha256']==sha(final) and manifest['marker']==0xffffffff
    checks['screen_prior_raw_frame_exact']=sha(raw)=='81200ab102c507de6a5853a33086958d16bcb93168ff631ee76b6c8c391adba2'
    checks['screen_owned_job_removed']=read(screen/'native.process.json')['status']=='removed'
    for name,mode in [(f'cut-{n}','incomplete') for n in (0,4,64,68)]+[('valid-vectors','interrupted-valid-vectors')]:
        p=matrix/name;br=read(p/'boot/report.json');wr=read(p/'writer/report.json');bm=read(p/'boot/manifest.json');prefix=(p/'writer/exports/programmed-prefix.bin').read_bytes()
        before=base if name!='valid-vectors' else (p/'initial-mram.bin').read_bytes();reconstructed=bytearray(before);reconstructed[0x38010:0x38010+len(prefix)]=prefix
        checks[name+'_prefix']=prefix==payload[:len(prefix)] and len(prefix)==wr['observed']['programmed_bytes']
        checks[name+'_persistent_lineage']=sha(reconstructed)==wr['final_mram_sha256']==bm['persistent_input_sha256']
        points={x['label']:x['hits'] for x in br['points']};checks[name+'_actual_branch_order']=reboot_path_matches(points,br['events'],mode)
        checks[name+'_owned_jobs_removed']=read(p/'writer/renode.process.json')['status']=='removed' and read(p/'boot/native.process.json')['status']=='removed'
    policy=root/'full-restore-policy-bw564-02'
    checks['full_scope_policy']=read(policy/'report.json')['passed'] and all(tag in (policy/'native.log').read_text() for tag in ('BLACKWALL_MRAM_BOUNDARY 23','BLACKWALL_MRAM_FULL_SCOPE 11','BLACKWALL_MRAM_ATOMIC 8'))
    result=dict(passed=all(checks.values()),checks=checks,hardware_accessed=False,scope='Independent byte reconstruction, original native log/context/frame validation and interrupted-state reboot lineage')
    output.mkdir(mode=0o700,parents=True);shutil.copy2(__file__,output/'audit-source.py')
    result['frozen_support_sha256']={}
    for name in ('run_original_boot_screen.py','run_restored_boot.py','run_boot_validation.py','run_renode_m55_probe.py'):
        source=Path(__file__).resolve().parent/name;shutil.copy2(source,output/name)
        result['frozen_support_sha256'][name]=sha(source.read_bytes())
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])),flush=True)
    if not result['passed']:raise ValueError('Independent restoration audit failed')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('restore','screen','matrix','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.restore,a.screen,a.matrix,a.output)
if __name__=='__main__':main()
