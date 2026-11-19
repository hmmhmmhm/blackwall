"""Audit original PendSV observations, preserving failed hook-free exact contracts."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def differences(a, b, path=()):
    if type(a) != type(b):
        return [(path, a, b)]
    if isinstance(a, dict) and a.keys() == b.keys():
        return [d for k in a for d in differences(a[k], b[k], path + (k,))]
    if isinstance(a, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in differences(x, y, path + (i,))]
    return [] if a == b else [(path, a, b)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve existing audit')
    s = args.simulator
    paths = dict(baseline=s/'em9305-reset-main-01/stock24',
                 recording=s/'m55-natural-stack-limits-main-01/stock24',
                 empty=s/'m55-stack-empty-hooks-main-01/stock24',
                 core=s/'m55-stack-limit-core-01')
    reports = {k:json.loads((p/'report.json').read_text()) for k,p in paths.items()}
    b, r, e, core = [reports[k] for k in ['baseline','recording','empty','core']]
    checks = []
    def check(name, passed):
        checks.append(dict(name=name, passed=bool(passed)))
        if not passed:
            raise ValueError(name)
    pins = {}
    for key, folder in paths.items():
        names = ['report.json', 'renode.log']
        if key != 'core':
            manifest = json.loads((folder/'derived-inputs.json').read_text())
            for name, digest in manifest['derived'].items():
                check(key+'-asset-'+name, sha(folder/name) == digest)
            names += list(manifest['derived']) + ['derived-inputs.json']
            if key != 'baseline':
                plan = json.loads((folder/'plan.json').read_text())
                check(key+'-plan-pin', sha(folder/'plan.json') == manifest['plan_sha256'])
                check(key+'-runner-pin', sha(folder/'runner-source.py') == manifest['runner_sha256'])
                names += ['plan.json', 'runner-source.py']
                def marker(label):
                    rows = [json.loads(line.split(' ',1)[1]) for line in (folder/'renode.log').read_text().splitlines() if line.startswith(label+' ')]
                    if len(rows) != 1:
                        raise ValueError('Missing unique '+label)
                    return rows[0]
                check(key+'-diagnostic-log', reports[key]['diagnostics'] == marker('BLACKWALL_CANDIDATE_'+plan['id']))
                check(key+'-cpu-log', reports[key]['observed'] == marker('BLACKWALL_REPORT'))
                check(key+'-events-log', reports[key]['selected_observation'] == marker('BLACKWALL_OBSERVATION'))
        else:
            for name, digest in core['files'].items():
                check('core-asset-'+name, sha(folder/name) == digest)
            names += list(core['files'])
        pins[key] = {name:sha(folder/name) for name in sorted(set(names))}
    check('synthetic-register-roundtrips', core['passed'] and len(core['checks']) == 8 and all(core['checks'].values()))
    for key in ['recording','empty']:
        check(key+'-original-main', sha(paths[key]/'main.bin') == 'df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a')
        check(key+'-same-original-inputs', all(sha(paths[key]/name) == sha(paths['baseline']/name) for name in ['main.bin','sram-fill.bin','itcm-fill.bin','board.repl','result.py']))
        check(key+'-same-original-events', reports[key]['selected_observation'] == b['selected_observation'])
        failed = [c['name'] for c in reports[key]['semantic_validation']['checks'] if not c['passed']]
        check(key+'-exact-contract-failure-preserved', reports[key]['passed'] is False and failed == ['comparison:exact'])
    check('recording-vs-empty-cpu-exact', r['observed'] == e['observed'])
    check('empty-no-samples', e['diagnostics']['sequence'] == 0 and e['diagnostics']['events'] == [])
    delta = differences(b['observed'], r['observed'])
    expected = {
        ('instructions',): (65991868,65991958),
        ('startup_fixture','power_reads'): (9683,9684),
        ('sram_windows',0,'bytes',4): (50,49),
        ('mcu_clock_response','mode_reads'): (9683,9684),
        ('controls',0,'device_reads'): (9201,9200),
        ('gpu_power_response','enable_reads'): (5039,5038)
    }
    check('all-six-hook-footprint-deltas', {path:(a,z) for path,a,z in delta} == expected)
    events = r['diagnostics']['events']
    check('bounded-complete-samples', r['diagnostics']['dropped'] == 0 and r['diagnostics']['sequence'] == 362 and [x['sequence'] for x in events] == list(range(1,363)))
    psp = [x for x in events if x['label'] == 'pendsv-psp-read']
    limits = [x for x in events if x['label'] == 'pendsv-psplim-read']
    restored = [x for x in events if x['label'] == 'psplim-write-0x60bbbe']
    check('original-pendsv-counts', len(psp) == len(limits) == len(restored) == 120)
    check('actual-handler-mode', all(x['xpsr'] & 0x1ff == 14 and not x['process_stack_selected'] for x in psp+limits+restored))
    check('handler-msp-observed', all(x['sp'] == 0x2007fa90 for x in psp+limits+restored))
    raw = (paths['recording']/'main.bin').read_bytes()
    expected_sites = {0x60bb70:bytes.fromhex('eff30980'),
                      0x60bb7e:bytes.fromhex('eff30b82'),
                      0x60bbbe:bytes.fromhex('82f30b88')}
    for address, code in expected_sites.items():
        check('raw-original-instruction-'+hex(address), raw[address-0x438000:address-0x438000+4] == code)
    check('nonzero-different-task-limits', len(set(x['value'] for x in limits)) == 29 and all(0x20000000 <= x['value'] < 0x20380000 for x in limits))
    check('ordered-save-restore-observations', all(a['sequence']+1 == z['sequence'] and z['sequence']+1 == w['sequence'] for a,z,w in zip(psp,limits,restored)))
    check('last-observed-psplim-write', restored[-1]['value'] == 0x20046dc8)
    check('returned-to-thread-mode', r['observed']['register_context']['r15'] == 0x58253a and r['diagnostics']['process_stack_selected'])
    args.output.mkdir(parents=True, mode=0o700)
    (args.output/'audit.py').write_bytes(Path(__file__).read_bytes())
    answer = dict(audit_passed=True, checks=checks, pins=pins,
                  native_exact_comparison_passed=False, hook_footprint_leaf_differences=[dict(path=list(p),before=a,after=z) for p,a,z in delta],
                  original_pendsv_entries=120, last_observed_psplim_write=0x20046dc8,
                  current_psplim_directly_read=False, gpu_irq_injected=False,
                  hardware_accessed=False, native_rerun=False, full_boot_verified=False)
    (args.output/'report.json').write_text(json.dumps(answer,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,checks=len(checks),native_exact_comparison_passed=False,original_pendsv_entries=120)))


if __name__ == '__main__':
    main()
