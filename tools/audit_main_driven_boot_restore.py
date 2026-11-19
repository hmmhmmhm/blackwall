"""Audit original main-driven virtual full-stock bytes and fresh boot/frame evidence."""
import argparse
import json
from pathlib import Path
import shutil
from audit_stock_main_mram_probe import PRIVATE, INITIAL_SHA, SRAM_SHA, sha, read, audit_case
from run_original_boot_screen import EXPORTS, assess, valid_frame, logged_json, same, validate_runtime
from check_virtual_restore import assess as assess_restore


def run(experiment, output, *, regression_source=None):
    experiment, output = Path(experiment).resolve(), Path(output).resolve()
    if not experiment.is_relative_to(PRIVATE) or not output.is_relative_to(PRIVATE) or output.exists():
        raise ValueError('Private experiment and fresh audit output required')
    regression_source=experiment if regression_source is None else Path(regression_source).resolve()
    if not regression_source.is_relative_to(PRIVATE):raise ValueError('Private frozen regression source required')
    writer = experiment / 'writer'
    manifest, report, raw = (read(writer / name) for name in ('manifest.json', 'report.json', 'exports/result.json'))
    initial = Path(manifest['initial_mram']['path']).read_bytes()
    backup = Path(manifest['virtual_original']['path']).read_bytes()
    final_path = writer / 'exports/final-mram.bin'
    final = final_path.read_bytes() if final_path.exists() else backup
    payload = (writer / 'payload.bin').read_bytes()
    checks = {}
    checks['input_provenance'] = sha(initial) == INITIAL_SHA == manifest['initial_mram']['sha256'] and sha(Path(manifest['initial_sram']['path']).read_bytes()) == SRAM_SHA == manifest['initial_sram']['sha256']
    checks['declared_virtual_original'] = sha(backup) == manifest['virtual_original']['sha256'] == '8e0e4761fa99f1c90f8080dc91c998d4379396cb059c2a929681c95083def7f5' and not any(backup[0x10000+149773:0x37000])
    checks['explicit_scope'] = manifest['boot_restore'] and manifest['entry'] == 'callback' and manifest['verification'] == 'ota' and manifest['bytes'] == 159744 and manifest['destination'] == 0x410000 and report['hardware_accessed'] is False and report['natural_ota_executed'] is False
    checks['frozen_writer'] = all(sha((writer / name).read_bytes()) == digest for name, digest in manifest['components'].items())
    checks['raw_matches_report'] = all(report[key] == value for key, value in raw.items())
    checks['complete_actual_mram'] = final == backup and sha(final) == report['final_mram_sha256'] and initial[:0x10000] == final[:0x10000] and initial[0x37000:] == final[0x37000:]
    if not final_path.exists():
        removed = {row['name']: row for row in read(writer / 'cleanup.json')['removed']}
        checks['removed_actual_mram_digest'] = removed['exports/final-mram.bin']['sha256'] == sha(final) and removed['exports/final-mram.bin']['bytes'] == len(final)
    checks['actual_39page_readbacks'] = payload == backup[0x10000:0x37000] == (writer / 'exports/verified-pages.bin').read_bytes() and sha(payload) == manifest['payload_sha256']
    checks['rom_request_sequence'] = report['rom_requests'] == [[0x12344321, 1, 0x4000+i*1024, 1024, 0x20240000+i*4096, 1] for i in range(39)]
    checks['original_verification_returns'] = report['verification_rows'] == [[0x410000+i*4096, 0x20240000+i*4096, 0, 0, 0] for i in range(39)]
    checks['original_call_counts'] = all(report['hits'][hex(a)] == count for a, count in [(0x5c69f8,39),(0x5c6994,78),(0x488d34,39),(0x4f5864,39),(0x494aae,39),(0x494b00,39),(0x5c2226,78),(0x5791e8,39),(0x446ab4,39),(0x480c14,39),(0x5c69d0,39),(0x480dc8,39)])
    checks['normal_thread_completion'] = report['completed'] and report['pages_verified'] == report['rom_calls'] == report['rom_attempts'] == report['rom_enables'] == report['rom_disables'] == 39 and report['programmed_bytes'] == 159744 and report['cfsr'] == report['hfsr'] == report['violations'] == 0 and report['initial_primask'] == report['primask'] == report['initial_control'] == report['initial_ipsr'] == report['ipsr'] == 0 and report['stack'] == 0x2007f000 and report['control'] == 4
    observed = Path(manifest['delay_contract']['observation'])
    checks['original_itcm_initialized_profile'] = bytes(read(observed)['itcm_bytes'])[:6] == (writer / 'delay.bin').read_bytes() == initial[0x3bf54f:0x3bf555] and sha(observed.read_bytes()) == manifest['delay_contract']['observation_sha256'] and report['delay_calls'] == report['delay_returns'] == report['clock_reads'] == 10 and report['info_mram_size'] == 0x400000
    checks['explicit_cache_profile'] = report['initial_ccr'] == report['final_ccr'] == 0 and report['initial_cpacr'] == report['cpacr'] == 0xf00000
    checks['writer_container_removed'] = read(writer / 'native.process.json')['status'] == 'removed'
    extents = {'boot':dict(space='mram',address=0x410000,bytes=149773),'boot-tail':dict(space='mram',address=0x410000+149773,bytes=9971),'main':dict(space='mram',address=0x438000,bytes=3700068)}
    stock = {key:sha(backup[v['address']-0x400000:v['address']-0x400000+v['bytes']]) for key,v in extents.items()}
    actual = {key:sha(final[v['address']-0x400000:v['address']-0x400000+v['bytes']]) for key,v in extents.items()}
    restoration = assess_restore(stock, actual, ['boot','boot-tail','main'], True, stock_extents=extents, modified_regions=[dict(space='mram',address=0x410000,bytes=159744),dict(space='mram',address=0x438000,bytes=3700068)])
    checks['all_modified_components_stock'] = restoration['full_stock_bytes'] and actual == stock and stock['boot'] == 'ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665' and stock['main'] == 'df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a'
    cold = experiment / 'cold-boot'
    cm, cr = read(cold / 'manifest.json'), read(cold / 'report.json')
    validate_runtime((cold / 'run.py').read_text())
    checks['fresh_boot_actual_lineage'] = cm['persistent_input_sha256'] == sha(final) and cm['writer_report_sha256'] == sha((writer / 'report.json').read_bytes()) and cm['writer_completed'] and cm['boot_state'] == 'stock-prefix'
    checks['frozen_cold_sources'] = all(sha((cold / name).read_bytes()) == digest for name,digest in cm['components'].items() if name not in ('boot-region.bin','main-region.bin'))
    removed = {row['name']:row for row in cr['cleanup']}
    checks['cold_input_actual_windows'] = cm['components']['boot-region.bin'] == sha(final[0x10000:0x38000]) and cm['components']['main-region.bin'] == sha(final[0x38000:0x3f8000])
    v = {key:read(cold / 'exports' / name) for key,name in EXPORTS.items()}
    v['image_equal'] = removed['exports/guest-boot.bin']['sha256'] == stock['boot'] and removed['exports/guest-main.bin']['sha256'] == stock['main']
    v['cadence_equal'] = removed['exports/cadence-before-sram.bin']['sha256'] == removed['exports/cadence-after-sram.bin']['sha256']
    frame = (cold / 'exports/complete-screen.bin').read_bytes()
    v['frame_equal'] = valid_frame(v['screen'],frame,(cold / 'exports/main-state-sram.bin').read_bytes())
    checks.update({'cold_'+key:value for key,value in assess(v).items()})
    checks['cold_actual_records'] = all(same(logged_json((cold/'native.log').read_text(),tag),v[key]) for key,tag in [('native','BLACKWALL_BOOT_RESET '),('wire','BLACKWALL_BOOT_WIRE '),('screen','BLACKWALL_BOOT_SCREEN '),('delegated','BLACKWALL_DELEGATED_GUARDS ')])
    checks['cold_completed_frame'] = cr['passed'] and cr['boot_prefix_reboot_verified'] and cr['frame_sha256'] == sha(frame) == '81200ab102c507de6a5853a33086958d16bcb93168ff631ee76b6c8c391adba2' and len(frame) == 165888
    checks['cold_container_removed'] = read(cold / 'native.process.json')['status'] == 'removed'
    regression = audit_case(regression_source / 'default-regression')
    checks['default_4k_regression'] = regression['audit_passed'] and read(regression_source / 'default-regression/manifest.json')['boot_restore'] is False
    error_regression = audit_case(regression_source / 'default-error-regression')
    checks['default_rom_error_regression'] = error_regression['audit_passed'] and read(regression_source / 'default-error-regression/manifest.json')['boot_restore'] is False
    checks['regression_model_matches_writer'] = all((regression_source / name / 'model.cs').read_bytes()==(writer/'model.cs').read_bytes() for name in ('default-regression','default-error-regression'))
    result = dict(passed=all(checks.values()),checks=checks,restoration=restoration,regression=regression,error_regression=error_regression,regression_source=str(regression_source),virtual_full_stock_verified=all(checks.values()),physical_recovery_verified=False,natural_ota_verified=False,hardware_accessed=False)
    output.mkdir(parents=True,mode=0o700)
    shutil.copy2(__file__,output/'audit-source.py')
    result['frozen_support_sha256'] = {}
    for name in ('audit_stock_main_mram_probe.py','run_original_boot_screen.py','run_renode_m55_probe.py','check_virtual_restore.py'):
        source = Path(__file__).resolve().parent/name
        shutil.copy2(source,output/name);result['frozen_support_sha256'][name] = sha(source.read_bytes())
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),regression_checks=len(regression['checks'])+len(error_regression['checks']),failed=[key for key,value in checks.items() if not value])))
    if not result['passed']:raise ValueError('Main-driven boot restoration audit failed')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('experiment',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.experiment,a.output)
