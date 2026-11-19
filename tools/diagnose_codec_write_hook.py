"""Reproduce the Unicorn write-hook discrepancy from an archived original probe."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import unicorn
from unicorn import Uc, UC_HOOK_MEM_WRITE
from audit_assets import PINS
from blackwall_package import parse_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('original_probe', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = args.bundle.read_bytes()
    if hashlib.sha256(data).hexdigest() != PINS['stock_base']:
        raise ValueError('Pinned stock 2.3 bundle required')
    raw = next(c for c in parse_bundle(data) if c.type_id == 0).payload[32:]
    spec = importlib.util.spec_from_file_location('original_codec_probe', args.original_probe)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = {}
    for mode in ('disabled', 'empty', 'normal'):
        observed = dict(write_hook_registered=False, calls=0)

        def factory(*params):
            cpu = Uc(*params)
            add = cpu.hook_add

            def hook_add(kind, callback, *params, **kwargs):
                if kind == UC_HOOK_MEM_WRITE:
                    if mode == 'disabled':
                        return None
                    observed['write_hook_registered'] = True
                    original = callback

                    def callback(*params):
                        observed['calls'] += 1
                        if mode == 'normal':
                            original(*params)

                return add(kind, callback, *params, **kwargs)

            cpu.hook_add = hook_add
            return cpu

        module.Uc = factory
        try:
            result = module.execute(raw, 'stock_base', 0, 2)
            results[mode] = dict(passed=True, result=result, controls=observed)
        except ValueError as error:
            results[mode] = dict(passed=False, error=str(error), controls=observed)
    reproduced = (results['disabled']['passed'] and not results['disabled']['controls']['write_hook_registered']
                  and all(not results[k]['passed'] and results[k]['controls']['write_hook_registered']
                          and results[k]['controls']['calls'] > 0 for k in ('empty', 'normal')))
    report = dict(unicorn_version=unicorn.__version__, results=results, discrepancy_reproduced=reproduced,
                  source_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (Path(__file__), args.original_probe)},
                  bundle_sha256=hashlib.sha256(data).hexdigest(),
                  hardware_validated=False, full_boot_verified=False,
                  limitations=['Disabled-write-hook run is a diagnostic control, not compatibility evidence',
                               'Does not establish the internal CPU engine bug mechanism'])
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    if not reproduced:
        raise SystemExit('Discrepancy no longer matches; inspect new evidence')
    print('Discrepancy reproduced: disabled hook passes, empty/normal write hooks diverge')


if __name__ == '__main__':
    main()
