"""Audit saved original-setter traces without pretending to execute EDMP code."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(simulator):
    inputs = {}

    def read(relative):
        path = simulator / relative
        inputs[relative] = digest(path)
        return json.loads(path.read_text())

    verified = read('imu-parameter-full-setter-01/verification-report.json')
    saved = read('imu-parameter-full-setter-01/report.json')
    report_path = simulator / 'imu-parameter-full-setter-01/report.json'
    assert verified['passed'] and saved['passed']
    assert verified['source_files'][str(report_path)] == digest(report_path)
    assert saved['source_io_abi_stubbed'] and saved['synthetic_bus_registers_and_rom']
    assert not saved['native_main'] and not saved['hardware_accessed']
    source_manifest = read('imu-edmp-init-research-01/source-manifest.json')
    tree = read('iom4-command-source-research-01/tdk-tree.json')
    assert source_manifest['commit'] == tree['sha'] == '646f55a6ec119b59d9ebce47af660842b53e5506'
    assert not tree.get('truncated', False)
    blobs = {entry['path']: entry['sha'] for entry in tree['tree']}
    for source in source_manifest['files']:
        path = simulator / 'imu-edmp-init-research-01' / Path(source['path']).name
        raw = path.read_bytes()
        assert digest(path) == source['sha256']
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        assert blob == source['blob'] == blobs[source['path']]
        inputs[str(path.relative_to(simulator))] = digest(path)
    for relative, public in [
        ('imu-parameter-full-setter-01/inv_imu_edmp_memmap.h', 'src/imu/inv_imu_edmp_memmap.h'),
        ('iom4-command-source-research-01/tdk/src/imu/inv_imu_edmp_defs.h', 'src/imu/inv_imu_edmp_defs.h'),
    ]:
        path = simulator / relative
        raw = path.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == blobs[public]
        inputs[relative] = digest(path)

    cases = []
    for case in saved['cases']:
        main = simulator / 'imu-clock-variation-main-01' / case['case'] / 'main.bin'
        assert digest(main) == case['main_sha256']
        inputs[str(main.relative_to(simulator))] = digest(main)
        runs = []
        for run in case['cases']:
            transactions = run['requests']
            request_indices = [index for index, tx in enumerate(transactions)
                               if tx['kind'] == 'write-sram' and tx['address'] == 4]
            assert len(request_indices) == 2
            assert [transactions[index]['data'] for index in request_indices] == ['02', '04']
            assert run['returned'] == 0 and run['ready']
            first, second = request_indices
            assert not any(tx['kind'] == 'read-sram' for tx in transactions[first:second])
            reads = [tx for tx in transactions[second:] if tx['kind'] == 'read-sram']
            assert len(reads) == 1 and reads[0]['address'] == 0x5bc
            assert len(bytes.fromhex(reads[0]['data'])) == 4
            tail = transactions[second:]
            assert int.from_bytes(bytes.fromhex(reads[0]['data']), 'little') == run['romword']
            temperatures = [tx['data'] for tx in tail
                            if tx['kind'] == 'write-sram' and tx['address'] == 0x6a0]
            assert temperatures == (['0000effe'] if run['romword'] == 0 else [])
            patch = next(tx for tx in tail if tx['kind'] == 'write-sram' and tx['address'] == 0xc80)
            assert len(bytes.fromhex(patch['data'])) == 125
            runs.append(dict(rate=run['rate'], gyro=run['gyro'], romword=run['romword'],
                             requests=[2, 4], post_request_sram_reads=reads,
                             temperature_initialized=run['romword'] == 0,
                             post_request_patch_bytes=125,
                             computed_edmp_outputs_observed=False))
        cases.append(dict(case=case['case'], main_sha256=case['main_sha256'], runs=runs))
    assert len(cases) == 3 and sum(len(case['runs']) for case in cases) == 48
    return dict(passed=True, scope='saved isolated host-driver transaction evidence only',
                source_commit=tree['sha'], cases=cases, reused_original_arm_scenarios=48,
                new_arm_executions=0, hardware_accessed=False,
                host_setter_reads_complex_parameters=False,
                only_post_request_sram_read=dict(address=0x5bc, width=4,
                                                name='EDMP_GAF_SAVED_GYR_ACCURACY'),
                read_values_are_synthetic=True,
                computation_reconstruction_supported=False,
                evidence_gap='EDMP request2/4 internal output map, computation and independent expected values',
                fifo_decode_is_not_fusion_implementation=True,
                automatic_ready_authorized=False, files=inputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new output directory; saved evidence is immutable')
    report = inspect(args.simulator.resolve())
    args.output.mkdir(mode=0o700, parents=True)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('48 saved setter traces verified; computed EDMP effects remain unsupported')


if __name__ == '__main__':
    main()
