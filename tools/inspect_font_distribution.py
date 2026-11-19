"""Audit downloaded official package data without executing packages; compare metrics to pinned ARM."""
import argparse
import base64
import hashlib
import json
import struct
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from native_replay import digest, parse_log, validate_assets
from pinned_main import load_pinned_main


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    a.output.mkdir(mode=0o700)
    source = a.simulator/'font-distribution-research-01'
    manifest = json.loads((source/'sources.json').read_text())
    checks = []
    def check(label, ok):
        if not ok:
            raise ValueError(label)
        checks.append(label)
    check('no-package-execution', manifest['packages_executed'] is False)
    packages = {}
    for item in manifest['packages']:
        name = item['name'].split('/')[-1]
        directory = source/name
        metadata_bytes = (directory/'registry.json').read_bytes()
        check(name+'-metadata', hashlib.sha256(metadata_bytes).hexdigest() == item['metadata_sha256'])
        metadata = json.loads(metadata_bytes)
        check(name+'-version', metadata['version'] == item['version'] and metadata['dist'] == item['dist'])
        data = (directory/'package.tgz').read_bytes()
        check(name+'-tarball', hashlib.sha256(data).hexdigest() == item['tarball_sha256']
              and hashlib.sha1(data).hexdigest() == metadata['dist']['shasum']
              and 'sha512-'+base64.b64encode(hashlib.sha512(data).digest()).decode() == metadata['dist']['integrity'])
        for f in item['files']:
            raw = (directory/f['path']).read_bytes()
            check(name+'-'+f['path'], len(raw) == f['bytes'] and hashlib.sha256(raw).hexdigest() == f['sha256'])
        packages[name] = dict(version=item['version'], license_declared=item['license_declared'],
                              files=[f['path'] for f in item['files']])
    js = (source/'pretext/package/dist/font_measure.js').read_text()
    prefix = 'const fontData = '
    check('JSON-prefix', js.startswith(prefix))
    # Decode the JSON literal only. Never evaluate the surrounding JavaScript.
    data, end = json.JSONDecoder().raw_decode(js[len(prefix):])
    check('JSON-terminator', js[len(prefix)+end:].lstrip().startswith(';'))
    check('four-font-metric-records', [f['name'] for f in data['fonts']] == ['evenroster', 'evenroster_crylgrek', 'cn', 'evenemoji'])
    cn = data['fonts'][2]
    check('CJK-metrics-only', 'glyphs' not in cn and cn['default_adv_w'] == 320 and len(cn['ranges']) == 2120 and len(cn['exceptions']) == 2887)
    samples = []
    for character in [0x4E2D, 0xAC00, 0xD55C]:
        present = any(lo <= character <= hi for lo,hi in cn['ranges'])
        check('CJK-metric-'+hex(character), present)
        samples.append(dict(character=character, raw_advance=cn['exceptions'].get(str(character), cn['default_adv_w'])))
    upstream = source/'official-lvgl'
    tree = json.loads((upstream/'tree.json').read_text())
    pin = '14b6eae3dca058153d993628cc23c152e0d8eac8'
    check('official-binding-pin', tree['sha'] == pin and tree['truncated'] is False)
    for path in ['.gitmodules', 'build.rs', 'Cargo.toml']:
        raw = (upstream/path).read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        check('official-binding-'+path, blob == next(x['sha'] for x in tree['tree'] if x['path'] == path))
    check('official-LVGL-submodule', next(x['sha'] for x in tree['tree'] if x['path'] == 'vendor/lvgl') == 'c033a98afddd65aaafeebea625382a94020fe4a7')
    build = (upstream/'build.rs').read_text()
    check('external-font-source-input', 'LVGL_FONTS_DIR' in build and 'current_dir.join("fonts")' in build)
    check('no-font-directory-in-binding-tree', not any(x['path'].startswith('fonts/') for x in tree['tree']))
    binary = (source/'sim-darwin-arm64/package/bin/evenhub-simulator').read_bytes()
    check('simulator-Mach-O-not-bank', binary[:4] == b'\xcf\xfa\xed\xfe')
    check('binary-binding-build-path', b'lvgl-sys-v9-9161286feb5e521f/14b6eae/vendor/lvgl/' in binary)
    cases = []
    for key, filename in [('stock24', 'stock-2.4.0.24.bin'), ('stock23', 'stock-2.3.0.24.bin'), ('cfw', 'faceclaw-38-research-only.bin')]:
        directory = a.simulator/'builtin-font-memory-main-01'/key
        report = json.loads((directory/'report.json').read_text())
        validate_assets(directory, json.loads((directory/'derived-inputs.json').read_text())['derived'])
        check(key+'-native', report['passed'] and parse_log((directory/'renode.log').read_text()) == report['observed'])
        _, raw = load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes())
        check(key+'-original-main', raw == (directory/'main.bin').read_bytes())
        ram = (directory/'low-sram.bin').read_bytes()
        check(key+'-RAM-hash', report['sram']['sha256'] == digest(directory/'low-sram.bin') and len(ram) == 0x6000)
        u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        size = (len(raw)+4095) & ~4095
        u.mem_map(0x438000, size)
        u.mem_write(0x438000, raw)
        u.mem_protect(0x438000, size, UC_PROT_READ | UC_PROT_EXEC)
        u.mem_map(0x20000000, len(ram))
        u.mem_map(0x21000000, 0x3000)
        u.mem_map(0x10000000, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
        fonts = []
        for address_hex, metric in zip(report['configs'][0]['pointers'][:2], data['fonts'][:2]):
            address = int(address_hex, 0)
            font = report['fonts'][address_hex]
            check(key+'-'+metric['name']+'-RAM-font', struct.pack('<9I', *font) == ram[address-0x20000000:address-0x20000000+36])
            glyphs = struct.unpack_from('<I', raw, font[6]-0x438000+4)[0]
            same, mismatch, absent = [], [], []
            for codepoint, width in metric['glyphs'].items():
                u.mem_write(0x20000000, ram)
                u.mem_write(0x21000000, b'\0'*0x3000)
                for register,value in [(UC_ARM_REG_R0,address), (UC_ARM_REG_R1,0x21001000), (UC_ARM_REG_R2,int(codepoint)), (UC_ARM_REG_R3,0), (UC_ARM_REG_SP,0x21002F00), (UC_ARM_REG_LR,0x10000001)]:
                    u.reg_write(register,value)
                u.emu_start(font[0],0x10000000,count=20000)
                if u.reg_read(UC_ARM_REG_PC) != 0x10000000 or u.reg_read(UC_ARM_REG_SP) != 0x21002F00:
                    raise ValueError('Original glyph callback did not return')
                if not u.reg_read(UC_ARM_REG_R0):
                    absent.append(int(codepoint))
                    continue
                glyph_id = struct.unpack('<I',u.mem_read(0x21001018,4))[0]
                offset = glyphs-0x438000+16*glyph_id+4
                if not 0 <= offset <= len(raw)-4:
                    raise ValueError('Original glyph metadata outside ROM')
                advance = struct.unpack_from('<I',raw,offset)[0]
                (same if advance == width else mismatch).append(int(codepoint))
            check(key+'-'+metric['name']+'-shared-widths', not mismatch)
            check(key+'-'+metric['name']+'-coverage-difference', len(same) == (399 if metric['name'] == 'evenroster' else 299)
                  and len(absent) == (16 if metric['name'] == 'evenroster' else 0))
            fonts.append(dict(name=metric['name'], declared_metrics=len(metric['glyphs']), shared_exact_advances=len(same),
                              missing_in_original=absent, raw_advance_mismatch=mismatch))
        cases.append(dict(case=key, fonts=fonts))
    result = dict(passed=True, count=len(checks), checks=checks, packages=packages,
                  binding_commit=pin, cases=cases, CJK_metric_samples=samples,
                  original_callback_calls=sum(f['declared_metrics'] for c in cases for f in c['fonts']),
                  package_code_executed=False, simulator_binary_executed=False,
                  firmware_font_bank_obtained=False, stock_font_asset_compatibility_verified=False,
                  hardware_accessed=False,
                  scope='Registry integrity/file hashes, official binding source and metrics compared with pinned original ARM; metrics and simulator binary are not verified stock XIP assets')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,count=len(checks),original_callback_calls=result['original_callback_calls'],stock_font_bank=False)))


if __name__ == '__main__':
    main()
