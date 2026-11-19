"""Audit saved synthetic reset protection runs against their actual native logs."""
import argparse, hashlib, json
from pathlib import Path
from probe_reset_memory_protection import CASES, SCRIPT, SOURCE, validate

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(cap, policy, out, baseline=False):
    if out.exists():
        raise ValueError('Fresh audit output required')
    report=json.loads((cap/'report.json').read_text())
    expected={(n,t,'device-aircr',True) for n in CASES for t in (1,2)}
    expected.update((n,2,'guest-aircr',True) for n in ('main-byte','unwritten-itcm','retained-itcm'))
    if not baseline:
        expected.add(('padding-read',2,'guest-aircr',True))
    expected.update((n,2,'device-aircr',False) for n in ('main-byte','unwritten-itcm','padding-execute','sram-execute'))
    actual=set(); failed=[]; hashes={}; checks=0
    if report['policy_sha256']!=sha(policy) or (cap/'compiled/fixture.c').read_text()!=SOURCE:
        raise ValueError('Changed policy or compiled source')
    for row in report['cases']:
        p=cap/row['case']
        values=[json.loads(line.split('BLACKWALL_RESET_MEMORY ',1)[1]) for line in (p/'renode.log').read_text().splitlines() if line.startswith('BLACKWALL_RESET_MEMORY ')]
        if len(values)!=1:
            raise ValueError('Missing native log result')
        observed=values[0]; result=validate(observed)
        if result!=json.loads((p/'report.json').read_text()) or row!={'case':p.name,**result}:
            raise ValueError('Native log/report disagreement')
        name=next(n for n,v in CASES.items() if v[0]==observed['mode'])
        target=observed['target_boot'];method=observed['method'];guarded=observed['guarded']
        key=(name,target,method,guarded)
        if key in actual or p.name!=f'{name}-{target}-{method}-{str(guarded).lower()}':
            raise ValueError('Duplicate or mislabeled case')
        actual.add(key)
        script=SCRIPT.replace('__TARGET__',str(target)).replace('__GUARDED__',str(guarded)).replace('__METHOD__',method).replace('__MODE__',str(observed['mode']))
        if (p/'run.py').read_text()!=script or (p/'memory-policy.cs').read_bytes()!=policy.read_bytes() or (p/'fixture.elf').read_bytes()!=(cap/'compiled'/f"mode-{observed['mode']}.elf").read_bytes():
            raise ValueError('Changed execution input')
        checks+=len(result['checks'])
        if not result['passed']:failed.append(p.name)
    if actual!=expected or failed!=(['padding-read-2-device-aircr-true'] if baseline else []) or report['passed']!= (not baseline):
        raise ValueError('Unexpected plan or failures')
    for p in sorted(cap.rglob('*')):
        if p.is_file():hashes[str(p.relative_to(cap))]=sha(p)
    result=dict(passed=True,baseline=baseline,observed_cases=len(actual),behavior_checks=checks,expected_failures=failed,policy_sha256=sha(policy),capture_hashes=hashes,original_g2_executed=False,physical_hardware_access=False)
    out.mkdir(parents=True,mode=0o700);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('policy',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args();r=verify(a.capture,a.policy,a.output,a.baseline);print(json.dumps({k:v for k,v in r.items() if k!='capture_hashes'}))
if __name__=='__main__':main()
