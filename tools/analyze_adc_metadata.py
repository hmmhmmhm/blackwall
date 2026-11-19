"""Validate pinned Apollo510 ADC SVD metadata against the firmware-research header."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

SVD_SHA = 'a2390c3366450eaccc9d4531d26dc9d68488ec42de5795ee50ab45a266f28276'
HEADER_SHA = 'b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def number(text):
    if text is None:
        return None
    return int(text.strip(), 0)


def collect(svd_data, header_data):
    if digest(svd_data) != SVD_SHA or digest(header_data) != HEADER_SHA:
        raise ValueError('Input differs from pinned ADC research sources')
    root = ET.fromstring(svd_data)
    if root.findtext('name') != 'apollo510':
        raise ValueError('Unexpected device')
    candidates = [p for p in root.findall('./peripherals/peripheral') if p.findtext('name') == 'ADC']
    if len(candidates) != 1 or candidates[0].get('derivedFrom'):
        raise ValueError('Expected one direct ADC peripheral')
    adc = candidates[0]
    if number(adc.findtext('baseAddress')) != 0x40038000 or adc.findall('./registers/cluster'):
        raise ValueError('Unexpected ADC address or cluster layout')
    header = header_data.decode()
    registers = []
    for register in adc.findall('./registers/register'):
        if register.get('derivedFrom') or register.find('dim') is not None:
            raise ValueError('Register inheritance/arrays require explicit expansion')
        name = register.findtext('name')
        if not name or not re.fullmatch(r'[A-Z][A-Z0-9]*', name):
            raise ValueError('Unexpected ADC register name')
        reset_source = next((node for node in (register, adc, root) if node.find('resetValue') is not None), None)
        fields = []
        used_bits = 0
        for field in register.findall('./fields/field'):
            field_name = field.findtext('name')
            bits = re.fullmatch(r'\[(\d+):(\d+)\]', field.findtext('bitRange', ''))
            if not bits or not field_name or not re.fullmatch(r'[A-Z][A-Z0-9]*', field_name):
                raise ValueError('Unsupported field layout')
            high, low = map(int, bits.groups())
            if not 0 <= low <= high <= 31:
                raise ValueError('Field outside DWORD')
            mask = ((1 << (high-low+1))-1) << low
            if used_bits & mask:
                raise ValueError('Overlapping ADC fields')
            used_bits |= mask
            macro = 'ADC_'+name+'_'+field_name+'_Msk'
            found = re.search(r'^#define '+re.escape(macro)+r'\s+\((0x[0-9a-fA-F]+)UL\)', header, re.M)
            if not found or int(found.group(1), 16) != mask:
                raise ValueError('SVD/header mismatch: '+macro)
            enums = []
            for item in field.findall('./enumeratedValues/enumeratedValue'):
                value = number(item.findtext('value'))
                if value is None or not 0 <= value < 1 << (high-low+1):
                    raise ValueError('Enum outside field: '+macro)
                enums.append(dict(name=item.findtext('name'), value=value))
            fields.append(dict(name=field_name, low=low, high=high, mask=mask, enums=enums))
        registers.append(dict(name=name, offset=number(register.findtext('addressOffset')),
            reset_value=number(reset_source.findtext('resetValue')) if reset_source is not None else None,
            access_label=register.findtext('access'), field_mask=used_bits, fields=fields))
    if len(registers) != 30 or sum(len(r['fields']) for r in registers) != 140:
        raise ValueError('Pinned ADC register/field coverage changed')
    if len({r['offset'] for r in registers}) != 30:
        raise ValueError('ADC register addresses overlap')
    return header, registers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('svd', type=Path)
    parser.add_argument('header', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--clang', default='/opt/homebrew/opt/llvm@21/bin/clang')
    args = parser.parse_args()
    svd_data, header_data = args.svd.read_bytes(), args.header.read_bytes()
    header, registers = collect(svd_data, header_data)
    marker = header.index('/*!< ADC Structure')
    start = header.rfind('typedef struct', 0, marker)
    end = header.index('} ADC_Type;', marker)+len('} ADC_Type;')
    if start < 0:
        raise ValueError('ADC_Type missing')
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    source = '#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+header[start:end]+'\n'
    source += ''.join('_Static_assert(offsetof(ADC_Type,%s)==%d,"%s");\n' % (r['name'], r['offset'], r['name']) for r in registers)
    (output/'layout.c').write_text(source)
    result = subprocess.run([args.clang, '-std=c11', '-c', str(output/'layout.c'), '-o', str(output/'layout.o')], capture_output=True, text=True)
    (output/'layout.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise ValueError('ADC layout compile failed; inspect layout.log')
    report = dict(passed=True, svd_sha256=digest(svd_data), header_sha256=digest(header_data),
        device='apollo510', base_address=0x40038000, register_count=30, matched_field_masks=140,
        compiled_offset_assertions=30, registers=registers, hardware_validated=False,
        scope='source metadata only; access labels do not implement side effects or prove G2 reset state')
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','register_count','matched_field_masks','compiled_offset_assertions')}))


if __name__ == '__main__':
    main()
