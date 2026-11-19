"""Correlate original partition tables and FlashDB header consumers with pinned public source."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from blackwall_package import parse_bundle
from native_replay import parse_log, validate_assets
from pinned_main import load_pinned_main

SOURCE_PINS = {
    'fal': ('aa0211218634a613d3638425a830854bd07a0b76', {
        'src/fal_partition.c': '9aee41e18ca465e4b46bab20b2ed77227aceeeda',
        'inc/fal_def.h': '18eee8e5e78121d13dee0cbcf5a7a32424ae276f',
        'LICENSE': '261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64'}),
    'FlashDB': ('360a68d0b1f9f02b0d597a9f08c141e28b332c1e', {
        'src/fdb_kvdb.c': '0406b2dd2472c6c0a513531737c8d78f55d33d4c',
        'inc/fdb_def.h': '473b4763dd1075f3d3fffd0096dae4d8d44e95f2',
        'LICENSE': '261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64'}),
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    s, out = a.simulator, a.output
    out.mkdir(mode=0o700)
    checks, rows = [], []
    def check(name, condition):
        if not condition:
            raise ValueError(name)
        checks.append(name)
    texts = {}
    for repo, (commit, files) in SOURCE_PINS.items():
        folder = s / 'nor-partition-source-01'
        manifest = json.loads((folder / (repo + '-sources.json')).read_text())
        check(repo + '-commit', manifest['commit'] == commit)
        for name, blob in files.items():
            data = (folder / repo / name).read_bytes()
            declared = next(f for f in manifest['files'] if f['path'] == name)
            check(repo + '-' + name + '-blob', hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == blob == declared['git_blob'])
            check(repo + '-' + name + '-sha256', hashlib.sha256(data).hexdigest() == declared['sha256'])
            texts[repo + '/' + name] = data.decode()
    header = texts['fal/inc/fal_def.h']
    check('FAL-24byte-names', '#define FAL_DEV_NAME_MAX 24' in header and 'char flash_name[FAL_DEV_NAME_MAX];' in header)
    fal = ' '.join(texts['fal/src/fal_partition.c'].split())
    check('FAL-relative-to-device-read', 'flash_dev->ops.read(part->offset + addr, buf, size)' in fal)
    fdb = texts['FlashDB/src/fdb_kvdb.c']
    check('FlashDB-header-magic-and-read', '#define SECTOR_MAGIC_WORD                        0x30424446' in fdb
          and '_fdb_flash_read((fdb_db_t)db, addr, (uint32_t *)&sec_hdr, sizeof(struct sector_hdr_data));' in fdb)
    check('FlashDB-invalid-header-is-init-failure', 'sector->magic != SECTOR_MAGIC_WORD' in fdb and 'return FDB_INIT_FAILED;' in fdb)
    base = 0x438000
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    for key, name in [('stock24', 'stock-2.4.0.24.bin'), ('stock23', 'stock-2.3.0.24.bin'), ('cfw', 'faceclaw-38-research-only.bin')]:
        bundle = (s / 'inputs/verified-01' / name).read_bytes()
        _, raw = load_pinned_main(bundle)
        d = s / 'nor-partition-stack-01' / key
        check(key + '-original-main', raw == (d / 'main.bin').read_bytes())
        validate_assets(d, json.loads((d / 'derived-inputs.json').read_text())['derived'])
        v = parse_log((d / 'renode.log').read_text())
        check(key + '-native-report', v == json.loads((d / 'report.json').read_text())['observed'])
        old = json.loads((s / 'mspi1-continuous-status-main-01' / key / 'report.json').read_text())['observed']
        check(key + '-same-execution', all(v[k] == old[k] for k in v if k != 'stack_context')
              and len(v['stack_context']['words']) == 96 and v['stack_context']['words'][:32] == old['stack_context']['words'])
        parts = []
        at = 0
        while True:
            at = raw.find(struct.pack('<I', 0x45503130), at)
            if at < 0:
                break
            data = raw[at:at + 64]
            if len(data) == 64 and data[28:37] == b'norflash\0':
                offset, size, reserved = struct.unpack_from('<III', data, 52)
                parts.append(dict(table=base + at, name=data[4:28].split(b'\0', 1)[0].decode('ascii'), offset=offset, size=size, reserved=reserved))
            at += 1
        kv = next(p for p in parts if p['name'] == 'kvdb')
        nv = next(p for p in parts if p['name'] == 'NVdb')
        check(key + '-exact-kv-NV-partitions', len(parts) == 2 and kv['offset'] == 0x1fc0000 and kv['size'] == 0x38000
              and nv['offset'] == kv['offset'] + kv['size'] == 0x1ff8000 and nv['size'] == 0x8000
              and nv['offset'] + nv['size'] == 0x2000000)
        stack = v['stack_context']['words']
        check(key + '-active-kv-partition-on-stack', kv['table'] in stack and 0x1fc0000 in stack and 16 in stack)
        needle = struct.pack('<I', 0x30424446)
        check(key + '-unique-sector-magic-literal', raw.count(needle) == 1)
        literal = base + raw.index(needle)
        loads = []
        for off in range(0, len(raw) - 4, 2):
            a1, a2 = struct.unpack_from('<HH', raw, off)
            if a1 == 0xf8df and a2 >> 12 == 1 and ((base + off + 4) & ~3) + (a2 & 0xfff) == literal:
                loads.append(base + off)
        check(key + '-unique-sector-magic-load', len(loads) == 1)
        load = loads[0]
        read = load - 0x16
        code = list(md.disasm(raw[read - 8 - base:load + 0x24 - base], read - 8))
        ins = {i.address: (i.mnemonic, i.op_str) for i in code}
        check(key + '-16byte-sector-header-read', ins.get(read - 8) == ('movs', 'r3, #0x10') and ins.get(read - 6) == ('mov', 'r2, sp')
              and ins.get(read, ('', ''))[0] == 'bl')
        check(key + '-header-read-return-on-native-stack', read + 5 in stack)
        check(key + '-checks-header-word1', ins.get(load - 6) == ('ldr', 'r0, [sp, #4]')
              and ins.get(load + 4) == ('cmp', 'r0, r1') and ins.get(load + 6) == ('bne', '#' + hex(load + 0x16)))
        check(key + '-invalid-header-sets8', ins.get(load + 0x20) == ('movs', 'r0, #8'))
        branch = ins.get(load + 0x22)
        check(key + '-invalid-header-branches-to-epilogue', branch is not None and branch[0] == 'b' and branch[1].startswith('#0x'))
        epilogue = int(branch[1][1:], 0)
        tail = list(md.disasm(raw[epilogue - base:epilogue + 6 - base], epilogue))
        check(key + '-return8-not-overwritten', [(i.mnemonic, i.op_str) for i in tail]
              == [('add', 'sp, #0x6c'), ('pop.w', '{r4, r5, r6, r7, r8, sb, pc}')])
        check(key + '-erased-header-is-not-valid', struct.unpack_from('<I', b'\xff' * 16, 4)[0] != 0x30424446)
        components = parse_bundle(bundle)
        check(key + '-six-OTA-components', {c.type_id for c in components} == {0, 1, 3, 4, 5, 6})
        check(key + '-no-named-KV-or-NOR-component', not any('kvdb' in c.name.lower() or 'norflash' in c.name.lower() for c in components))
        rows.append(dict(case=key, partitions=parts, header_read=hex(read), header_return_on_stack=hex(read + 5),
                         sector_magic=hex(0x30424446), erased_header_valid=False,
                         components=[dict(name=c.name, bytes=len(c.payload)) for c in components],
                         physical_NOR_contents_known=False, exact_FlashDB_version_known=False))
        (out / (key + '-header-check.asm')).write_text('\n'.join(f'{i.address:#x} {i.mnemonic} {i.op_str}' for i in code + tail) + '\n')
    (out / 'report.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks, cases=rows,
        scope='Partition and header-consumer correlation; no array bytes supplied, blank-state execution or formatting verified'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, count=len(checks))))


if __name__ == '__main__':
    main()
