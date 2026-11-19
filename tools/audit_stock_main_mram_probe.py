"""Audit frozen diagnostic ARM runs without rerunning or importing the current model."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

PRIVATE = Path.home() / 'Library/Application Support/Blackwall'
INITIAL_SHA = '3e5f340ef2ae006f60bbd476670a38f0ff1a45fbedff805b481a7cbfd4d9ede4'
SRAM_SHA = '95db71c2f3961db017dd8f8cef708768a331fb1a4e478990c03ab6e11ab5b268'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit_case(case, *, cleanup=False):
    manifest = read(case / 'manifest.json')
    report = read(case / 'report.json')
    raw = read(case / 'exports/result.json')
    initial = Path(manifest['initial_mram']['path']).read_bytes()
    sram = Path(manifest['initial_sram']['path']).read_bytes()
    payload = (case / 'payload.bin').read_bytes()
    original = (PRIVATE / 'simulator/boot-self-restore-bw567-01/virtual-original-mram.bin').read_bytes()
    checks = {}
    checks['pinned_inputs'] = (len(initial) == 0x400000 and sha(initial) == INITIAL_SHA == manifest['initial_mram']['sha256']
                               and len(sram) == 0x380000 and sha(sram) == SRAM_SHA == manifest['initial_sram']['sha256'])
    checks['stock_main'] = sha(initial[0x38000:0x38000 + 3700068]) == 'df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a'
    checks['distinguishing_payload'] = len(payload) == 4096 and sha(payload) == manifest['payload_sha256'] and payload == original[0x34000:0x35000] and payload != initial[0x34000:0x35000]
    checks['frozen_sources'] = all(sha((case / name).read_bytes()) == digest for name, digest in manifest['components'].items())
    checks['native_report_matches'] = all(report[key] == value for key, value in raw.items())
    checks['owned_container_removed'] = read(case / 'native.process.json')['status'] == 'removed'
    checks['scope'] = manifest['hardware_accessed'] is False and manifest['natural_ota_executed'] is False and report['hardware_accessed'] is False and report['natural_ota_executed'] is False
    entry, fault = manifest['entry'], manifest['fault']
    checks['fixed_request'] = manifest['source'] == 0x20240000 and manifest['bytes'] == 4096 and manifest['destination'] == (0x434004 if fault == 'misaligned' else 0x434000)
    expected = bytearray(initial)
    if report['programmed_bytes']:
        checks['whole_page_programmed'] = report['programmed_bytes'] == 4096
        expected[0x34000:0x35000] = payload
        if fault == 'readback-corrupt':
            expected[0x34000] ^= 1
    final_path = case / 'exports/final-mram.bin'
    if final_path.exists():
        final = final_path.read_bytes()
    else:
        page = (case / 'exports/page-after.bin').read_bytes()
        final = initial[:0x34000] + page + initial[0x35000:]
        removed = {row['name']: row for row in read(case / 'cleanup.json')['removed']}
        checks['prior_cleanup_digest'] = removed['exports/final-mram.bin']['sha256'] == sha(final)
    checks['exact_whole_mram'] = final == expected and len(final) == 0x400000 and sha(final) == report['final_mram_sha256']
    checks['reported_memory_facts'] = (report['whole_mram_unchanged'] == (final == initial)
                                       and report['page_equals_payload'] == (final[0x34000:0x35000] == payload)
                                       and report['other_mram_unchanged'] is True)
    checks['retained_callbacks'] = sram[0x7573c:0x7573c+32].hex() == '85235c0027225c000d255c0087225c0091225c0000000000bd225c00e3225c00' and sram[0x77c02] == 1
    hits = report['hits']
    hit = lambda address: hits[hex(address)]
    checks['initial_thread_profile'] = report['initial_control'] == report['initial_primask'] == 0 and report.get('initial_ipsr', 0) == 0
    delay_profile = manifest.get('delay_profile', False)
    ota = manifest.get('verification') == 'ota'
    ota_boundary = ota and not report['completed']
    if delay_profile:
        contract = manifest['delay_contract']
        observed_path = Path(contract['observation'])
        observed = read(observed_path)
        checks['original_itcm_delay'] = (sha(observed_path.read_bytes()) == contract['observation_sha256']
                                         and bytes(observed['itcm_bytes'])[:6] == (case / 'delay.bin').read_bytes() == initial[0x3bf54f:0x3bf555]
                                         and (case / 'delay.bin').read_bytes().hex() == '0138fdd17047')
        checks['initialized_delay_clock'] = report['delay_calls'] == report['delay_returns'] == report['clock_reads'] == 10 and report['initial_cpacr'] == report['cpacr'] == 0xf00000 and report['info_returned'] and report['info_return'] == 0 and report['info_mram_size'] == 0x400000
    if entry == 'callback' and not delay_profile:
        classification = 'unsupported-diagnostic-environment'
        checks['callback_incomplete'] = not report['completed'] and report['programmed_bytes'] == report['rom_calls'] == 0 and hit(0x5c69f8) == hit(0x5c6994) == 1 and hit(0x488d34) == hit(0x480dc8) == 0 and final == initial
        if not manifest.get('chip_profile', False):
            checks['jedec_boundary'] = report['violations'] > 0 and report['failure'] == 'unexpected memory' and report['failure_address'] == 0xe00fefe0 and report['cfsr'] == report['hfsr'] == 0
        elif 'initial_cpacr' not in report:
            checks['fpu_setup_fault'] = report['pc'] == 0x495e8a and report['cfsr'] == 0x80000 and report['hfsr'] == 0x40000000 and report['violations'] == 0
        else:
            checks['clock_boundary'] = report['initial_cpacr'] == report['cpacr'] == 0xf00000 and report['control'] == 4 and report['ipsr'] == 0 and report['violations'] == 1 and report['failure'] == 'unsupported MMIO read' and report['failure_address'] == 0x40021000 and report['cfsr'] == report['hfsr'] == 0
    else:
        classification = 'verified-isolated-arm-contract'
        checks['no_fault_or_guard'] = report['cfsr'] == report['hfsr'] == 0 and (ota_boundary or report['violations'] == 0 and report['failure'] == 'none')
        checks['original_adapter'] = hit(0x4f5864) == 1 and hit(0x488d34) == (1 if entry in ('buffer', 'callback') else 0)
        if fault == 'rom-unready':
            classification = 'verified-unready-rom-boundary'
            checks['unready_stop'] = not report['completed'] and report['rom_unready_boundary'] and report['pc'] == 0x0200ff20 and report['rom_calls'] == report['programmed_bytes'] == 0 and report['power_returned'] and report['power_return'] == 4 and report['primask'] == 1 and hit(0x480dc8) == 0
        else:
            if ota_boundary:
                classification = 'unsupported-ota-error-log-rtc'
                checks['ota_error_log_boundary'] = fault in ('rom-error', 'readback-corrupt') and report['failure_address'] == 0x4000400c and report['failure'] == 'unexpected memory' and report['violations'] == 3 and report['primask'] == 1
            else:
                checks['normal_return'] = report['completed'] and report['primask'] == 0 and report['control'] == (4 if delay_profile else 0) and hit(0x480dc8) == 1
            if fault == 'misaligned':
                checks['alignment_rejected'] = report['api_return'] == 0x08000140 and report['rom_calls'] == report['programmed_bytes'] == 0 and report['compare_return'] != 0
            else:
                checks['original_power_irq_path'] = report['rom_calls'] == report['rom_attempts'] == report['rom_enables'] == report['rom_disables'] == 1 and report['rom_primask'] == 1 and report['power_returned'] and report['power_return'] == 0 and hit(0x494aae) == hit(0x494b00) == hit(0x5791e8) == 1 and hit(0x5c2226) == 2
                expected_return = 0x08000107 if fault == 'rom-error' and entry == 'adapter' else 0
                if not ota_boundary:
                    checks['actual_api_return'] = report['api_return'] == expected_return
                    checks['actual_readback_compare'] = report['compare_return'] == (0 if fault == 'success' else 1 if fault == 'readback-corrupt' else 0xffffffff)
                checks['write_count'] = report['programmed_bytes'] == (0 if fault == 'rom-error' else 4096)
            if ota:
                checks['actual_ota_call_chain'] = hit(0x446ab4) == hit(0x480c14) == hit(0x5c69d0) == hit(0x480dc8) == 1 and hit(0x5c6994) == 2
                checks['explicit_reset_cache_profile'] = report['initial_ccr'] == report['final_ccr'] == 0 and 'SetRegister(18' not in (case / 'model.cs').read_text()
                if 'verifier_compared' in report:
                    checks['actual_ota_mismatch'] = report['verifier_compared'] and report['verifier_compare'] == (0 if fault == 'success' else 1 if fault == 'rom-error' else 0xffffffff)
                    checks['real_ota_readback_bytes'] = (case / 'exports/ota-readback.bin').read_bytes() == final[0x34000:0x35000]
    passed = all(checks.values())
    removed_bytes = 0
    if cleanup and passed:
        removed = read(case / 'cleanup.json')['removed'] if (case / 'cleanup.json').exists() else []
        page_path = case / 'exports/page-after.bin'
        if page_path.exists() and page_path.read_bytes() != final[0x34000:0x35000]:
            raise ValueError('Retained page differs')
        page_path.write_bytes(final[0x34000:0x35000])
        for name in ('exports/final-mram.bin', 'caller.elf'):
            path = case / name
            if path.exists():
                data = path.read_bytes()
                removed.append(dict(name=name, bytes=len(data), sha256=sha(data)))
                removed_bytes += len(data)
                path.unlink()
        (case / 'cleanup.json').write_text(json.dumps(dict(removed=removed, reconstruction='canonical initial MRAM with retained page-after.bin at offset0x34000'), indent=2) + '\n')
    return dict(case=str(case.relative_to(PRIVATE)), audit_passed=passed, classification=classification, checks=checks, removed_bytes_this_run=removed_bytes)


def run(output, *, cleanup=False):
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE):
        raise ValueError('Fresh private output required')
    cases = []
    for name in ('stock-main-mram-bw569-01', 'stock-main-mram-bw569-02', 'stock-main-mram-bw569-03'):
        cases.extend(sorted(path.parent for path in (PRIVATE / 'simulator' / name).glob('*/manifest.json')))
    if len(cases) != 10:
        raise ValueError('Exactly ten frozen experiments required')
    results = [audit_case(case, cleanup=cleanup) for case in cases]
    result = dict(passed=all(row['audit_passed'] for row in results), cases=results, hardware_accessed=False, natural_ota_verified=False, full_stock_verified=False)
    output.mkdir(parents=True, mode=0o700)
    shutil.copy2(__file__, output / 'audit-source.py')
    result['audit_source_sha256'] = sha((output / 'audit-source.py').read_bytes())
    (output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=result['passed'], cases=len(results), checks=sum(len(row['checks']) for row in results), failed={row['case']: [k for k, v in row['checks'].items() if not v] for row in results if not row['audit_passed']}, removed_bytes_this_run=sum(row['removed_bytes_this_run'] for row in results))))
    if not result['passed']:
        raise ValueError('Frozen main MRAM audit failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    run(args.output, cleanup=args.cleanup)
