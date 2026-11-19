"""Recheck exact previously pinned research assets; no hardware transport or image writes."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

PINS={
    'stock_base':('simulator/inputs/verified-01/stock-2.3.0.24.bin','187ccf2bcc5c17a212106e8a376745511e8289c4232b634a7ea94b9bf25a0979'),
    'stock_current':('simulator/inputs/verified-01/stock-2.4.0.24.bin','363198f8d543a5c1181d8a213e9077285cb865700a1885c8dc7c1b9324fd0e05'),
    'cfw':('simulator/inputs/verified-01/faceclaw-38-research-only.bin','4aac023f49ec6965186d9106e328a516f20a2915ab400d561f662f984023a432'),
    'stock_boot':('recovery/research-2026-11-10/stock-boot-patch-bundle.bin','26b6067665a441b779c47f6b95427b8b4bb5f502aaf527466dadce628aeb00b2'),
}


def revalidate(root):
    rows={}
    manifests=[root/'recovery/research-2026-11-10/manifest.json',root/'recovery/offline-check-01/manifest.json']
    research=json.loads(manifests[0].read_text())
    offline=json.loads(manifests[1].read_text())
    provenance={r['local_filename']:r for r in research['official_bundles']}
    provenance.update({r['path']:r for r in offline['files'] if r['path'] in ['stock-2.4.0.24.bin','faceclaw-38-research-only.bin']})
    for name,(relative,expected) in PINS.items():
        path=root/relative
        payload=path.read_bytes()
        actual=hashlib.sha256(payload).hexdigest()
        if actual!=expected:
            raise ValueError('Pinned research asset mismatch: '+name)
        baseline=provenance[path.name]
        if baseline['sha256']!=expected or baseline['bytes']!=len(payload):
            raise ValueError('Prior provenance differs: '+name)
        rows[name]=dict(path=relative,bytes=len(payload),expected_sha256=expected,actual_sha256=actual,prior_provenance_match=True)
    return dict(schema='blackwall-exact-asset-revalidation/1',integrity='passed',
                readyForHardwareInstall=False,hardwareValidation='none',inputs=rows,prior_provenance_confirmed=True,baseline_manifest_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in manifests},
                method='fresh exact-byte SHA256 equality with existing research pins',
                format_reparsed=False,bootloader_recovery_retested=False,
                limits=['Does not re-run the original container/bootloader structural audit.',
                        'Exact byte identity preserves the previously verified input identity.',
                        'Does not establish physical installation or restoration compatibility.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('private_root',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();report=revalidate(args.private_root)
    args.output.mkdir(mode=0o700)
    shutil.copy2(__file__,args.output/'revalidate_research_assets.py')
    report['verifier_sha256']=hashlib.sha256((args.output/'revalidate_research_assets.py').read_bytes()).hexdigest()
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(integrity=report['integrity'],assets=len(report['inputs']),readyForHardwareInstall=False)))


if __name__=='__main__':main()
