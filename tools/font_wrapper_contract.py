"""Locate source-supported font wrapper/caller candidates in pinned main bytes."""
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS

BASE = 0x438000
SIGNATURES = {
    'bitmap': bytes.fromhex('feb505000e002c68002c10d1'),
    'descriptor': bytes.fromhex('2de9fe4f070091469846002f'),
    'release': bytes.fromhex('7fb50500002d10d1'),
    'letter': bytes.fromhex('2de9f8418fb004000d0016001f00ddf85880'),
    'reshape': bytes.fromhex('2de9f0410400884617001e00'),
    'ambiq_letter': bytes.fromhex('2de9fc4fa7b006000c00f06c'),
}


def discover_wrappers(raw):
    entries = {}
    for name, signature in SIGNATURES.items():
        offsets = []
        start = 0
        while True:
            offset = raw.find(signature, start)
            if offset < 0:
                break
            if offset % 2 == 0:
                offsets.append(offset)
            start = offset + 1
        if len(offsets) != 1:
            raise ValueError('Missing or ambiguous original ' + name + ' wrapper')
        entries[name] = BASE + offsets[0]
    return entries


def direct_call_candidates(raw, target):
    from blackwall_package import branch_target

    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    result = []
    for offset in range(0, len(raw) - 3, 2):
        first, second = struct.unpack_from('<HH', raw, offset)
        if first & 0xf800 != 0xf000 or second & 0xd000 != 0xd000:
            continue
        if branch_target(BASE + offset, raw[offset:offset + 4]) != target:
            continue
        instruction = next(decoder.disasm(raw[offset:offset + 4], BASE + offset), None)
        if instruction is not None and instruction.mnemonic == 'bl' and instruction.op_str == '#'+hex(target):
            result.append(BASE + offset)
    return result


def static_contract(raw, entries):
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    decoder.detail = True
    body = []
    for instruction in decoder.disasm(raw[entries['letter']-BASE:entries['letter']-BASE+0x280], entries['letter']):
        body.append(instruction)
        if instruction.mnemonic.startswith('pop') and 'pc' in instruction.op_str:
            break
    sites = {name: direct_call_candidates(raw, entries[name]) for name in ['descriptor', 'bitmap', 'release', 'letter']}
    if len(sites['letter'])!=1:raise ValueError('Expected one direct generic letter caller')
    calls = {name: [pc for pc in sites[name] if entries['letter'] <= pc <= body[-1].address] for name in ['descriptor', 'bitmap', 'release']}
    if not body or any(len(calls[name]) != 1 for name in calls) or not calls['descriptor'][0] < calls['bitmap'][0] < calls['release'][0]:
        raise ValueError('Original letter wrapper call ordering differs')
    indirect = [i.address for i in body if i.mnemonic == 'blx']
    if len(indirect) != 1 or not calls['bitmap'][0] < indirect[0] < calls['release'][0]:
        raise ValueError('Backend callback lifetime boundary differs')
    registrations=[]
    for address in range(entries['ambiq_letter']-0x400,entries['ambiq_letter'],2):
        pair=list(decoder.disasm(raw[address-BASE:address-BASE+8],address))[:2]
        if len(pair)!=2 or pair[0].mnemonic!='addw' or not pair[0].op_str.startswith('r3, pc, #') or pair[1].mnemonic!='bl':continue
        if ((address+4)&~3)+pair[0].operands[2].imm!=entries['ambiq_letter']|1:continue
        target=pair[1].operands[0].imm
        if all(target<=site<target+0x1000 for site in sites['letter']):registrations.append(dict(callback_adr=hex(address),iterator_call=hex(pair[1].address),iterator=hex(target)))
    if len(registrations)!=1:raise ValueError('Ambiq callback registration differs')
    filename=b'lv_draw_ambiq_letter.c\0';offset=raw.find(filename)
    if offset<0 or raw.count(filename)!=1:raise ValueError('Ambiq source filename missing or ambiguous')
    start=raw.rfind(b'\0',0,offset)+1;pointer=struct.pack('<I',BASE+start)
    pools=[BASE+index for index in range(entries['ambiq_letter']-BASE,entries['ambiq_letter']-BASE+0x400,4) if raw[index:index+4]==pointer]
    if len(pools)!=1:raise ValueError('Ambiq filename reference outside callback context')
    return dict(entries={k: hex(v) for k,v in entries.items()}, direct_call_candidates={k:[hex(v) for v in values] for k,values in sites.items()},
                letter_body=[dict(pc=hex(i.address),instruction=i.mnemonic+' '+i.op_str,bytes=i.bytes.hex()) for i in body],
                ordered_calls={k:hex(v[0]) for k,v in calls.items()}, backend_callback=hex(indirect[0]),
                ambiq_backend=dict(registration=registrations[0],source_file='lv_draw_ambiq_letter.c',filename_literal=hex(pools[0]),bitmap_call_candidates=[hex(pc) for pc in sites['bitmap'] if entries['ambiq_letter']<=pc<entries['ambiq_letter']+0x400]),
                scope='Direct BL candidates and local decoded ordering only, not full reachability or natural rendering')
