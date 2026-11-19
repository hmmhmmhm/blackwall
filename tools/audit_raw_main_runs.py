"""Audit frozen original-main inputs and stock-base/CFW comparison conditions."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from audit_assets import PINS
from blackwall_package import parse_bundle

BASE=0x438000
DIAGNOSTICS={'capture_itcm_prefix','capture_sram_windows'}


def audit(simulator):
    rows=[]
    binaries={}
    for name,key in [('stock24','stock_current'),('stock23','stock_base'),('cfw','cfw')]:
        folder=simulator/f'uart1-irq-main-{name}-02'
        launcher=json.loads((folder/'launcher.json').read_text())
        command=launcher['command']
        bundle=Path(command[2]).read_bytes()
        if launcher['returncode']!=0 or hashlib.sha256(bundle).hexdigest()!=PINS[key]:
            raise ValueError('Unsuccessful run or unpinned bundle')
        raw=next(c for c in parse_bundle(bundle) if c.type_id==0).payload[32:]
        loaded=(folder/'main.bin').read_bytes()
        report=json.loads((folder/'report.json').read_text())
        if raw!=loaded or hashlib.sha256(raw).hexdigest()!=report['raw_main_sha256']:
            raise ValueError('Loaded image differs from source main')
        if report['observed']['memory_policy']['violations'] or report['unmodeled_engine_messages']:
            raise ValueError('Memory violation or unmodeled engine messages')
        startup=(folder/'probe.resc').read_text()
        if 'sysbus LoadBinary @/work/main.bin 0x438000' not in startup or 'cpu VectorTableOffset 0x438000' not in startup:
            raise ValueError('Unexpected startup script')
        binaries[name]=raw
        guards=[g for g in report['observed']['guards'] if g['accesses']]
        rows.append(dict(name=name,loaded_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                         initial_sp=hex(struct.unpack_from('<I',raw)[0]),reset_vector=hex(struct.unpack_from('<I',raw,4)[0]),
                         cpu_model=report['cpu_model'],image_id=report['image_id'],
                         hypotheses=report['selected_hypotheses'],command_options=command[4:],
                         runtime_source_sha256=hashlib.sha256((folder/'strict.cs').read_bytes()).hexdigest(),
                         runtime_script_sha256=hashlib.sha256((folder/'run.py').read_bytes()).hexdigest(),
                         stopped_pc=hex(report['observed']['pc']),guards=guards,
                         irq_exception_entries=report['observed']['uart1']['irq_exception_entries'],
                         tx_bytes=report['observed']['uart1']['tx_bytes']))
    left,right=rows[1:]
    same_options=left['command_options']==right['command_options']
    same_hypotheses=left['hypotheses']==right['hypotheses']
    same_runtime=left['runtime_source_sha256']==right['runtime_source_sha256']
    if not (same_options and same_hypotheses and same_runtime):
        raise ValueError('Stock-base/CFW comparison conditions differ')
    base,cfw=binaries['stock23'],binaries['cfw']
    changes=[i for i,(a,b) in enumerate(zip(base,cfw)) if a!=b]
    ranges=[]
    for offset in changes:
        if ranges and offset==ranges[-1][1]:ranges[-1][1]+=1
        else:ranges.append([offset,offset+1])
    return dict(passed=True,rows=rows,base_pair='stock2.3.0.24 vs Faceclaw38',
                base_pair_same_options=same_options,base_pair_same_hypotheses=same_hypotheses,
                base_pair_same_runtime_source=same_runtime,
                stock24_diagnostic_differences={k:[rows[0]['hypotheses'][k],left['hypotheses'][k]] for k in DIAGNOSTICS if rows[0]['hypotheses'][k]!=left['hypotheses'][k]},
                cfw_byte_changes_in_overlap=len(changes),cfw_length_delta=len(cfw)-len(base),
                changed_byte_ranges=[dict(start=hex(BASE+a),end_exclusive=hex(BASE+b)) for a,b in ranges],
                limitations=['original application main only; ROM/bootloader and other component processors not executed',
                             'reset-to-stop path uses synthetic board responses, not verified physical startup conditions',
                             'source review found no PC/return register rewrite or success-forcing branch hook in main runner',
                             'current audit verifies input file identity and enforced read-only CPU mapping, not a post-run full memory digest',
                             'same endpoint does not prove identical full instruction traces; patch-site execution coverage not collected',
                             'stock2.4 vs CFW2.3 confounds vendor-version and patch changes'],
                boot_verified=False,hardware_validated=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();report=audit(args.simulator)
    args.output.mkdir(mode=0o700)
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k in ['passed','base_pair','base_pair_same_options','cfw_byte_changes_in_overlap','cfw_length_delta']}))


if __name__=='__main__':main()
