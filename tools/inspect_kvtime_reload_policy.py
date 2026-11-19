"""Execute the original kvTime reload policy with explicit storage ABI fixtures.

This isolates policy, not FlashDB, NOR durability, or natural startup.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct

from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import cpu, WORK, STOP
from kvtime_layout import discover, literal
from pinned_main import MAIN_LAYOUT
from runtime_firmware_candidate import PROFILES
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm


def schema_contract(raw, layout):
    entry=layout['producer']-0x12c
    log=decode(raw,entry+0x1c,12)
    if [(i.mnemonic,i.op_str) for i in log[:4]]!=[
            ('movs','r0, #3'),('str','r0, [sp, #0xc]'),
            ('ldrb.w','r0, [sp, #0x10]'),('str','r0, [sp, #8]')]:
        raise ValueError('Unknown actual/expected version arguments')
    fmt=literal(raw,log[4])
    if raw[fmt-0x438000:fmt-0x438000+15]!=b'version %d(%d)\x00':
        raise ValueError('Missing original version log string')
    gate=decode(raw,layout['producer']-0x26,10)
    if [(i.mnemonic,i.op_str) for i in gate[:2]]!=[
            ('ldrb.w','r1, [sp, #0x10]'),('cmp','r1, #3')] or gate[2].mnemonic!='bge':
        raise ValueError('Unknown schema upgrade gate')
    if gate[2].operands[0].imm!=layout['producer']-6:
        raise ValueError('Unknown version gate destination')
    return dict(version_byte=0,expected_version=3,read_buffer_stack_offset=16,
                original_log='version %d(%d)',format_address=fmt,log_argument_pc=entry+0x1c,
                version_gate_pc=gate[1].address,version_ge3_skips_rewrite=True)


def inspect_case(source, schema_matrix=False):
    pins = json.loads((source / 'capture-files.json').read_text())['files']
    for name in ('main.bin', 'connection-profile.json', 'exports/sram-full.bin'):
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != pins[name]:
            raise ValueError('Changed source input: ' + name)
    raw = (source / 'main.bin').read_bytes()
    profile = json.loads((source / 'connection-profile.json').read_text())
    if hashlib.sha256(raw).hexdigest() != MAIN_LAYOUT[PROFILES[profile['case']]][3]:
        raise ValueError('Not an original image')
    layout = discover(raw, profile)
    entry = layout['producer'] - 0x12c
    body = decode(raw, entry, 0x12c)
    if raw[entry-0x438000:entry-0x438000+10] != bytes.fromhex('00b587b00c2204a97548'):
        raise ValueError('Unknown reload prologue')
    calls = [i.operands[0].imm for i in body if i.mnemonic == 'bl']
    read = calls[0]
    logging = calls[1]
    if calls[-2:] != [layout['producer'], layout['producer']]:
        raise ValueError('Unknown rewrite branches')
    if [(i.mnemonic, i.op_str) for i in body[-3:]] != [
            ('movs', 'r0, #0'), ('add', 'sp, #0x1c'), ('pop', '{pc}')]:
        raise ValueError('Unknown return policy')
    producer = decode(raw, layout['producer'], 0x1c)
    crc = next(i.operands[0].imm for i in producer if i.mnemonic == 'bl')
    ram = (source / 'exports/sram-full.bin').read_bytes()
    offset = layout['record'] - 0x20000000
    initial = ram[offset:offset+12]
    if len(initial) != 12:
        raise ValueError('Missing complete source record')
    matching = bytearray(initial)
    matching[0] = 3
    mismatching = bytearray(initial)
    mismatching[10] ^= 1
    fixtures = [
        ('read-minus-one', -1, b'', True),
        ('read-zero', 0, b'', True),
        ('equal-crc-current', 12, bytes(matching), False),
        ('short-positive-current', 1, b'\x03', False),
    ]
    for version, expected in [(2, True), (3, False), (4, False)]:
        value = bytearray(mismatching)
        value[0] = version
        fixtures.append(('different-crc-type-' + str(version), 12, bytes(value), expected))
    value = bytearray(matching)
    value[0] = 2
    fixtures.append(('equal-crc-old-type', 12, bytes(value), False))
    contract=schema_contract(raw,layout) if schema_matrix else None
    if schema_matrix:
        fixtures=[]
        for version in (0,1,2,3,4,255):
            for crc_mode in ('equal','different','valid'):
                value=bytearray(initial);value[0]=version
                if crc_mode=='different':value[10]^=1
                if crc_mode=='valid':struct.pack_into('<H',value,10,binascii.crc_hqx(value[:10],0xffff))
                fixtures.append(('schema-'+str(version)+'-crc-field-'+crc_mode,
                    12,bytes(value),version<3 and value[10:12]!=initial[10:12]))
    rows = []
    for name, read_status, payload, rewrite in fixtures:
        for store_status in (0, 7):
            machine = cpu(raw, ram, WORK + 0xf000)
            machine.mem_write(WORK, b'\xa5' * 0x10000)
            trace, stores, reads, crc_calls = [], [], [], []

            def abi(core, pc, size, user):
                trace.append(pc)
                if pc == crc:
                    crc_calls.append(pc)
                if pc not in (read, logging, layout['store']):
                    return
                if pc == read:
                    key, target, capacity = [core.reg_read(getattr(arm, 'UC_ARM_REG_R'+str(n))) for n in range(3)]
                    if key != layout['key'] or capacity != 12 or len(payload) > capacity:
                        raise ValueError('Unexpected storage read ABI')
                    if payload:
                        core.mem_write(target, payload)
                    reads.append(dict(status=read_status, copied=len(payload)))
                    result = read_status
                elif pc == layout['store']:
                    if core.reg_read(arm.UC_ARM_REG_R1) != layout['record'] or core.reg_read(arm.UC_ARM_REG_R2) != 12:
                        raise ValueError('Unexpected storage write ABI')
                    stores.append(bytes(core.mem_read(layout['record'], 12)).hex())
                    result = store_status
                else:
                    result = 0
                core.reg_write(arm.UC_ARM_REG_R0, result & 0xffffffff)
                core.reg_write(arm.UC_ARM_REG_PC, core.reg_read(arm.UC_ARM_REG_LR))

            machine.hook_add(UC_HOOK_CODE, abi)
            machine.emu_start(entry | 1, STOP, count=20000)
            final = bytes(machine.mem_read(layout['record'], 12))
            expected = bytearray(initial)
            if rewrite:
                expected[0] = 3
                struct.pack_into('<H', expected, 10, binascii.crc_hqx(expected[:10], 0xffff))
            checks = dict(returned_to_caller=machine.reg_read(arm.UC_ARM_REG_PC) == STOP,
                          stack_restored=machine.reg_read(arm.UC_ARM_REG_SP) == WORK + 0xf000,
                          returned_zero=machine.reg_read(arm.UC_ARM_REG_R0) == 0,
                          read_once=len(reads) == 1, rewrite_count=len(stores) == int(rewrite),
                          original_crc_only_on_rewrite=len(crc_calls) == int(rewrite),
                          global_not_replaced_by_read_payload=final == bytes(expected),
                          rewritten_payload=stores == ([bytes(expected).hex()] if rewrite else []))
            if not all(checks.values()):
                raise ValueError((name, store_status, checks))
            rows.append(dict(fixture=name, read_status=read_status, read_payload=payload.hex(),
                             store_status=store_status, stores=stores, crc_calls=len(crc_calls),
                             returned=0, checks=checks, trace_sha256=hashlib.sha256(
                                 b''.join(struct.pack('<I', pc) for pc in trace)).hexdigest()))
            if schema_matrix:
                rows[-1].update(stored_version=payload[0],crc_field_equals_current=payload[10:12]==initial[10:12],
                    payload_crc16_valid=struct.unpack_from('<H',payload,10)[0]==binascii.crc_hqx(payload[:10],0xffff))
    report=dict(case=profile['case'], passed=True, layout=layout, entry=entry,
                read_api=read, logging_flag_api=logging, crc=crc,
                initial_record=initial.hex(), scenarios=rows,
                source_capture_sha256=hashlib.sha256((source/'capture-files.json').read_bytes()).hexdigest())
    if schema_matrix:report['schema_contract']=contract
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--schema-matrix',action='store_true')
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Preserve previous evidence')
    cases = [inspect_case(a.simulator/'runtime-kv-commit-native-01'/name,a.schema_matrix)
             for name in ('stock24', 'stock23', 'cfw')]
    a.output.mkdir(mode=0o700, parents=True)
    report = dict(passed=True, cases=cases, engine='isolated original ARM on Unicorn M7',
                  storage_read_and_write_abi_stubbed=True, logging_disabled_by_abi=True,
                  natural_boot_verified=False, hardware_accessed=False, e08_complete=False)
    (a.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, images=len(cases), scenarios=sum(len(c['scenarios']) for c in cases))))


if __name__ == '__main__':
    main()
