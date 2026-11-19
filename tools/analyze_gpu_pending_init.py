"""Recognize a bounded, unexecuted GPU initialization prefix in captured SRAM."""
import argparse
import hashlib
import json
from pathlib import Path

from audit_assets import PINS

MAIN_SHA256={
    "stock_base":"fffbf74b3439bf0e4752fb620a7990d0a133898c54f6fb08005ea6b7029655c5",
    "stock_current":"df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a",
    "cfw":"4118af85ebb8e634493a61a3ce4a62ae37451e17cea6d0b8b08465f29538dd8f",
}


def analyze(report):
    profile=report['profile']
    if report['bundle_sha256']!=PINS[profile] or report['raw_main_sha256']!=MAIN_SHA256[profile]:raise ValueError('Unknown firmware evidence')
    o=report['observed'];guards=[g for g in o['guards'] if g['accesses']]
    if len(guards)!=1 or guards[0]['accesses']!=1 or (guards[0]['address'],guards[0]['width'],guards[0]['operation'])!=(0x400901f0,4,'read'):
        raise ValueError('Expected CONFIG read boundary absent')
    storage=o['gpu_raster_init_storage']
    if not storage['stored'] or not storage['trace_only'] or storage['rendering_effect_implemented'] or not o['gpu_initial_resets']['ring_requires_revalidation'] or o['gpu_interrupt_clear']['commands_executed']!=0:
        raise ValueError('Wrong trace-only observation state')
    snap=o['gpu_configured_ring_snapshot'];words=snap['words'];base=snap['base_address']
    if snap['byte_length']!=4864 or len(words)!=1216 or base%8 or not 0x20000000<=base<=0x20380000-4864:
        raise ValueError('Unexpected bounded ring layout')
    expected=[0xf8,0];uploads=[]
    for slot in range(24,32):
        datah,datal=(0,0) if slot<31 else (0x08000002,0x80000009)
        expected.extend([0xc4,slot,0xc8,datah,0xcc,datal])
        uploads.append(dict(slot=slot,register_c8_word=hex(datah),register_cc_word=hex(datal)))
    if words[:50]!=expected or words[50:1212]!=[0]*1162 or words[-4:]!=[0xff0000f0,base,0xff0000f4,4864]:
        raise ValueError('Captured prefix differs from the bounded initialization fixture')
    return dict(profile=profile,candidate_register_pairs=25,prefix_words=50,instruction_upload_candidates=uploads,
                nonzero_prefix_words=sum(w!=0 for w in words[:50]),producer_pointer_observed=False,
                valid_submission_length_verified=False,execution_verified=False,
                scope='recognized initialization prefix only; no generic packet execution or shader ISA interpretation')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path);p.add_argument('--runtime-report',type=Path,action='append',required=True);args=p.parse_args()
    rows=[]
    for path in args.runtime_report:
        data=path.read_bytes();row=analyze(json.loads(data));row.update(runtime=str(path),runtime_sha256=hashlib.sha256(data).hexdigest());rows.append(row)
    if len(rows)!=3 or {r['profile'] for r in rows}!={'stock_base','stock_current','cfw'}:raise ValueError('Need three distinct pinned profiles')
    args.output.mkdir(mode=0o700)
    (args.output/'report.json').write_text(json.dumps(dict(passed=True,rows=rows,hardware_validated=False,boot_verified=False),indent=2)+'\n')
    print(json.dumps({'passed':True,'profiles':3,'candidate_pairs_each':25,'gpu_execution_verified':False}))


if __name__=='__main__':main()
