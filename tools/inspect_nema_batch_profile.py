"""Inventory saved original-ARM draw batches; does not execute GPU commands."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(simulator, batch_root='nema-state-batch-m55-01'):
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'docs/data/gpu-extension-upstream-snapshot.json').read_text())
    headers = simulator / 'gpu-extension-research-01/headers'
    sources = []
    for name in ('nema_regs.h', 'nema_programHW.h'):
        record = next(x for x in manifest['sources'] if x['path'].endswith('/' + name))
        path = headers / 'NemaGFX/Nema' / name
        if digest(path) != record['sha256']:
            raise ValueError('Pinned header differs: ' + name)
        sources.append(record)
    registers = (headers / 'NemaGFX/Nema/nema_regs.h').read_text()
    names = {}
    for name, value in re.findall(r'#define\s+(NEMA_\w+)\s+\(\s*(0x[0-9a-fA-F]+)U?\s*\)', registers):
        names.setdefault(int(value, 16), []).append(name)
    blender = simulator / 'draw-command-batch-source-01/nema_blender.h'
    provenance = json.loads((blender.parent / 'sources.json').read_text())
    # The source file is recorded as URL/file/SHA by the preceding research task.
    records = provenance if isinstance(provenance, list) else provenance['sources']
    blend_pin = next(x for x in records if x.get('file', '').endswith('nema_blender.h'))
    if digest(blender) != blend_pin['sha256']:
        raise ValueError('Pinned blender header differs')
    text = blender.read_text()
    for definition in ('NEMA_BF_SRCALPHA     (0x4U)', 'NEMA_BF_INVSRCALPHA  (0x5U)'):
        if definition not in text:
            raise ValueError('Unexpected blend factors')
    profiles = {}
    for case in ('stock24', 'stock23', 'cfw'):
        folder = simulator / batch_root / (case + '-full-letter')
        report = json.loads((folder / 'report.json').read_text())
        snapshot = json.loads((folder / 'snapshot.json').read_text())
        work_path = folder / 'result/final-work.bin'
        work = work_path.read_bytes()
        words = report['actual']['words']
        if not report['passed'] or len(words) % 2:
            raise ValueError('Invalid saved batch: ' + case)
        if digest(work_path) != report['final_hashes']['work']:
            raise ValueError('Saved memory differs: ' + case)
        if words != snapshot['batch']['words']:
            raise ValueError('Reference differs: ' + case)
        if list(struct.unpack_from('<' + 'I' * len(words), work, 0x4000)) != words:
            raise ValueError('Actual RAM differs: ' + case)
        trace = []
        for index in range(0, len(words), 2):
            command, value = words[index:index + 2]
            offset = command & ~0xff000000
            if offset not in names:
                raise ValueError('Uncatalogued register: ' + hex(command))
            trace.append(dict(word=index, command=hex(command), register=names[offset],
                              value=hex(value), hold=bool(command & 0xff000000)))
        profiles[case] = dict(trace=trace, report_sha256=digest(folder / 'report.json'),
                              work_sha256=digest(work_path),
                              shader_upload_words=[hex(words[i + 1]) for i in range(0, len(words), 2)
                                                   if words[i] in (0xc8, 0xcc)],
                              codeptr=[hex(words[i + 1]) for i in range(0, len(words), 2)
                                       if words[i] == 0x11c],
                              rop_mode=[hex(words[i + 1]) for i in range(0, len(words), 2)
                                        if words[i] == 0x1d0])
    return dict(sources=sources, blender_source=blend_pin, batch_root=batch_root, profiles=profiles,
                gpu_commands_executed=False, pixels_generated=False,
                finding='0x504 factors: source-alpha / inverse-source-alpha; not SRC_OVER 0x501',
                unresolved=['fragment instruction ISA', 'CODEPTR packed fields and ROM shader semantics',
                            'A4 sampling order and L8 conversion', 'blend rounding and clip coverage',
                            'ring submission, completion IRQ, integrated main rendering'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--batch-root', default='nema-state-batch-m55-01',
                        help='Saved native batch directory; legacy bw254 is draw-command-batch-m55-04')
    args = parser.parse_args()
    result = inspect(args.simulator, args.batch_root)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'profiles': len(result['profiles']), 'pixels_generated': False}))
