"""Offline vector-last stock24 main restore with the pinned ARM RAM writer."""
import argparse
import hashlib
import json
from pathlib import Path
from run_recovery_m55_writer import prepare_capture,run_case,ROOT
from run_original_boot_screen import PRIVATE,PROFILE,read_json,validate_profile,checked_asset

MAIN_SHA='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a'

def sha(data):return hashlib.sha256(data).hexdigest()

def run(output,*,baseline_path=None):
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE) or output.is_relative_to(ROOT):raise ValueError('Fresh private output required')
    profile=read_json(PROFILE);validate_profile(profile)
    main_path=checked_asset(PRIVATE,profile['assets']['main']);main=main_path.read_bytes()
    if sha(main)!=MAIN_SHA or len(main)!=3700068:raise ValueError('Pinned stock24 main required')
    candidate=PRIVATE/'recovery/private-boot-24-candidate-01'
    output.mkdir(parents=True,mode=0o700)
    (output/'runner-source.py').write_bytes(Path(__file__).read_bytes())
    # Isolated worker baseline has declared zero MRAM outside the patched boot.
    # The 12 padding bytes are preserved from that virtual baseline, not assumed
    # to be a physical device's original contents.
    baseline_path=Path(baseline_path).resolve() if baseline_path else PRIVATE/'simulator/recovery-m55-writer-12/success/mram.bin'
    if not baseline_path.is_relative_to(PRIVATE):raise ValueError('Private virtual baseline required')
    baseline=baseline_path.read_bytes()
    if len(baseline)!=0x400000:raise ValueError('Whole virtual baseline required')
    tail=baseline[0x38000+len(main):0x38000+((len(main)+15)&~15)]
    body=main[16:]+tail
    prepare_capture(candidate,output/'body-capture',body,full_main_restore=True,mram_before=baseline_path)
    r=run_case(output/'body-capture',output/'body')
    after_body=(output/'body/exports/final-mram.bin').read_bytes()
    expected=bytearray(baseline);expected[0x38010:0x38010+len(body)]=body
    if after_body!=expected:raise ValueError('Body readback differs; vectors will remain uncommitted')
    (output/'body-verified.json').write_text(json.dumps(dict(passed=True,bytes=len(body),main_vectors_unchanged=after_body[0x38000:0x38010]==baseline[0x38000:0x38010],whole_mram_sha256=sha(after_body),body_sha256=sha(body)),indent=2)+'\n')
    print('BODY_VERIFIED '+str(len(body)),flush=True)
    prepare_capture(candidate,output/'vector-capture',main[:16],destination=0x438000,full_main_restore=True,mram_before=output/'body/exports/final-mram.bin')
    v=run_case(output/'vector-capture',output/'vector')
    final=(output/'vector/exports/final-mram.bin').read_bytes()
    expected[0x38000:0x38010]=main[:16]
    checks=dict(body_writer=r['passed'],vector_writer=v['passed'],whole_mram_expected=final==expected,
                entire_main_hash=sha(final[0x38000:0x38000+len(main)])==MAIN_SHA,
                body_to_vector_snapshot=(output/'vector-capture/mram.bin').read_bytes()==after_body,
                tail_preserved=final[0x38000+len(main):0x38000+((len(main)+15)&~15)]==tail)
    result=dict(passed=all(checks.values()),checks=checks,main_sha256=sha(final[0x38000:0x38000+len(main)]),
                baseline_path=str(baseline_path),baseline_sha256=sha(baseline),final_mram_sha256=sha(final),main_bytes=len(main),padding_bytes=len(tail),
                hardware_accessed=False,rom_programming_modeled=True,natural_reboot_verified=False,
                original_host_install_workflow_executed=False,scope='Actual ARM resident writer twice; isolated worker snapshot bridge; vector-last; not same-board UART auth/recovery integration')
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    if not result['passed']:raise ValueError('Full main restoration failed')
    print(json.dumps(result),flush=True)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--baseline',type=Path);a=p.parse_args();run(a.output,baseline_path=a.baseline)
if __name__=='__main__':main()
