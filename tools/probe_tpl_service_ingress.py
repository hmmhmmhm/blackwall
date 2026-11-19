"""Original TPL -> ble_msgrx queue -> protobuf time-state boundary; isolated ARM."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import UcError
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import BASE, SRAM, WORK, STOP
from probe_display_queue_producer import literal
from probe_display_root_ingress import invoke, packet
from sync_peer_roundtrip import invoke as call


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def varint(n):
    if n < 0:
        raise ValueError('Only explicit nonnegative fixture integers are supported')
    result = bytearray()
    while n > 127:
        result.append((n & 127) | 128)
        n >>= 7
    return bytes(result) + bytes([n])


def message(timestamp, zone, field=128):
    nested = b'\x08' + varint(timestamp) + b'\x10' + varint(zone)
    return b'\x08\x80\x01\x10\x01' + varint(field * 8 + 2) + varint(len(nested)) + nested


def contract(raw, ram, root):
    sig = bytes.fromhex('1fb500200290ffe70023002202a9')
    assert raw.count(sig) == 1
    consumer = BASE + raw.index(sig)
    load = decode(raw, consumer + 14, 4)[0]
    context = literal(raw, load)
    queue = struct.unpack_from('<I', ram, context + 12 - SRAM)[0]
    tcb = struct.unpack_from('<I', ram, context + 8 - SRAM)[0]
    assert ram[tcb + 52 - SRAM:tcb + 84 - SRAM].split(b'\0')[0] == b'ble_msgrx'
    # The original switch selects service 0x80 and calls the real decoder.
    code = decode(raw, consumer, 0x70)
    assert any(i.mnemonic == 'subs' and i.op_str == 'r0, #0x80' for i in code)
    dispatch = decode(raw, consumer + 0x5c, 4)[0]
    assert dispatch.mnemonic == 'bl'
    service = dispatch.operands[0].imm
    body = decode(raw, service, 0x800)
    choices = [body[k+1].operands[0].imm for k, i in enumerate(body[:-1])
               if i.mnemonic == 'cmp' and i.op_str == 'r0, #0x80' and body[k+1].mnemonic.startswith('beq')]
    assert len(choices) == 1
    branch = decode(raw, choices[0], 0x62)
    sites = [branch[k+1] for k, i in enumerate(branch[:-1])
             if i.mnemonic == 'ldrb' and i.op_str == 'r0, [r4, #2]' and branch[k+1].mnemonic == 'bl']
    assert len(sites) == 2
    handler = sites[0].operands[0].imm
    helper = decode(raw, handler, 0xf0)
    sets = [helper[k+1] for k, i in enumerate(helper[:-1])
            if i.mnemonic == 'ldr' and i.op_str == 'r0, [r4]' and helper[k+1].mnemonic == 'bl']
    assert len(sets) == 1
    boundary = sets[0].address
    loads = [i for i in helper if i.mnemonic.startswith('ldr') and i.op_str.startswith('r5,') and i.address < boundary]
    assert len(loads) == 1
    state = literal(raw, loads[0])
    assert SRAM <= state < SRAM + len(ram) - 8
    return dict(consumer=consumer, context=context, queue=queue, tcb=tcb,
                service=service, time_handler=handler, state=state,
                before_clock_apply=boundary, clock_apply=sets[0].operands[0].imm,
                tpl_local_callback=root['peer'])


def inspect(raw, ram, root, c):
    rows = []
    for kind, app, field, timestamp, zone in [
        ('time-a', 128, 128, 1700000000, 16),
        ('time-b', 128, 128, 1700000017, 24),
        ('wrong-nested-field', 128, 16, 1700000000, 16),
        ('unhandled-service', 11, 128, 1700000000, 16),
    ]:
        data = message(timestamp, zone, field)
        q = c['queue']
        count = struct.unpack_from('<I', ram, q + 0x38 - SRAM)[0]
        assert count == 0, 'Do not mix this fixture with existing queued messages'
        write_slot = struct.unpack_from('<I', ram, q + 4 - SRAM)[0]
        u, result = invoke(raw, ram, root, packet(app, data, both=False), end=STOP)
        assert result['pc'] == STOP and result['r0'] == 0 and not result['invalid'] and result['error'] is None
        assert struct.unpack('<I', u.mem_read(q + 0x38, 4))[0] == 1
        node = struct.unpack('<I', u.mem_read(write_slot, 4))[0]
        assert SRAM <= node < SRAM + len(ram) - 8 - len(data)
        assert bytes(u.mem_read(node, 8 + len(data))) == struct.pack('<II', app, len(data)) + data
        before = bytes(u.mem_read(c['state'], 8))
        end = STOP if app == 11 else c['before_clock_apply']
        call(u, c['consumer'], [], end=end)
        assert struct.unpack('<I', u.mem_read(q + 0x38, 4))[0] == 0
        after = bytes(u.mem_read(c['state'], 8))
        if app == 11:
            assert after == before
            args = None
        else:
            expected = (timestamp, zone) if field == 128 else (0, 0)
            args = [u.reg_read(arm.UC_ARM_REG_R0), u.reg_read(arm.UC_ARM_REG_R1)]
            assert args == list(expected)
            assert after[:5] == struct.pack('<IB', *expected)
            assert after[5:] == before[5:]
        rows.append(dict(kind=kind, app=app, nested_field=field, payload=data.hex(),
                         original_queued_node=True, consumer_executed=True, queue_delta_after_consume=0,
                         state_before=before.hex(), state_after=after.hex(), clock_arguments=args,
                         stopped_before_clock_apply=app != 11, pc=u.reg_read(arm.UC_ARM_REG_PC)))
    # Do not silently promote the state-write checkpoint to complete time sync.
    u, result = invoke(raw, ram, root, packet(128, message(1700000000, 16), both=False), end=STOP)
    assert result['pc'] == STOP and result['error'] is None and not result['invalid']
    try:
        call(u, c['consumer'], [], end=STOP)
    except UcError as exc:
        failure = str(exc)
    else:
        raise AssertionError('The isolated fixture unexpectedly completed RTC application')
    assert len(result['invalid']) == 1 and result['invalid'][0]['address'] == 0x40004800
    invalid = result['invalid'][0]
    assert invalid['pc'] == u.reg_read(arm.UC_ARM_REG_PC)
    assert bytes(u.mem_read(c['state'], 5)) == struct.pack('<IB', 1700000000, 16)
    rows.append(dict(kind='full-consumer-rtc-boundary', error=failure, invalid=invalid,
                     rtc_apply_completed=False, consumer_returned=False))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    s, out = a.simulator.resolve(), a.output.resolve()
    if not out.is_relative_to(s) or s.is_relative_to(Path(__file__).resolve().parents[1]):
        p.error('Use a fresh private simulator output')
    out.mkdir()
    root_report = s / 'display-root-source-05/report.json'
    root_manifest = json.loads((s / 'display-root-research-01/manifest.json').read_text())
    assert sha(root_report) == root_manifest['files'][str(root_report.relative_to(s))]
    roots = json.loads(root_report.read_text())
    pins = json.loads((s / 'tpl-request-research-01/manifest.json').read_text())
    cases = []
    for name in ['stock24', 'stock23', 'cfw']:
        src = s / 'tpl-request-native-02' / name
        capture = src / 'capture-files.json'
        assert sha(capture) == pins['files'][str(capture.relative_to(s))]
        files = json.loads(capture.read_text())['files']
        for f in ['main.bin', 'exports/sync-after-sram.bin']:
            assert sha(src / f) == files[f]
        raw = (src / 'main.bin').read_bytes()
        ram = (src / 'exports/sync-after-sram.bin').read_bytes()
        root = next(x['contract'] for x in roots['cases'] if x['case'] == name)
        c = contract(raw, ram, root)
        rows = inspect(raw, ram, root, c)
        cases.append(dict(case=name, main_sha256=files['main.bin'], ram_sha256=files['exports/sync-after-sram.bin'], contract=c, rows=rows))
        (out / 'partial.json').write_text(json.dumps(dict(cases=cases, complete=False), indent=2)+'\n')
    result = dict(passed=True, scenarios=sum(len(x['rows']) for x in cases), cases=cases,
                  layer='isolated original ARM API + original queue consumer; no scheduler replay',
                  native_main_complete=False, device_att_input=False, physical_hardware_access=False,
                  rtc_apply_executed=True, rtc_apply_completed=False, synthetic_consumer_call=True)
    (out / 'probe.py').write_bytes(Path(__file__).read_bytes())
    (out / 'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, scenarios=result['scenarios'])))


if __name__ == '__main__':
    main()
