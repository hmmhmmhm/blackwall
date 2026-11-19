"""Original TX queue and application H4 receive fragments; no controller response injection."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import unicorn.arm_const as arm
from inspect_nema_blocking_wait import cpu, WORK, STOP
from inspect_keydb_record_load import run
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target(raw, pc):
    ins = decode(raw, pc, 4)[0]
    if ins.mnemonic != 'bl':
        raise ValueError('Expected original direct call')
    return ins.operands[0].imm


def inspect(simulator, case):
    folder = simulator / 'application-hci-idle-main-01' / case
    audit_path = simulator / 'application-hci-idle-saved-audit-01' / case / 'report.json'
    audit = json.loads(audit_path.read_text())
    if not audit['passed']:
        raise ValueError('Unverified native source')
    for name, digest in audit['capture_hashes'].items():
        if sha(folder / name) != digest:
            raise ValueError('Changed source ' + name)
    source = json.loads((simulator / 'application-hci-source-01/report.json').read_text())
    entry = next(row for row in source['cases'] if row['case'] == case)
    raw = (folder / 'main.bin').read_bytes()
    ram = (folder / 'exports/sram-full.bin').read_bytes()
    pc, ring = entry['gpio_pc'], entry['tx_ring']
    pop = target(raw, pc - 0x1e)
    parser = target(raw, pc + 0x8a)
    body = decode(raw, parser, 0x220)
    calls = [i for i in body if i.mnemonic == 'bl']
    # In 2.4 an added reset prelude can free an old packet before dispatch.
    dispatch_call = calls[1] if case == 'stock24' else calls[0]
    dispatch = dispatch_call.operands[0].imm
    dispatch_body = decode(raw, dispatch, 0x2a)
    if not any(i.mnemonic == 'bl' for i in dispatch_body):
        raise ValueError('Missing original upper transport queue calls')
    rows = []
    for result in [0, 8]:
        u = cpu(raw, ram, WORK + 0xf000)
        u.mem_write(WORK + 0xf000, struct.pack('<I', entry['queued_pointer'] - 4))
        u.reg_write(arm.UC_ARM_REG_R0, result)
        u.reg_write(arm.UC_ARM_REG_R10, 0)
        t = run(u, pc + 0x122, [pc - 0x38, pc - 0x12])
        if t['stop'] != (pc - 0x38 if result == 0 else pc - 0x12):
            raise ValueError('Different write status branch')
        rows.append(dict(kind='write-return',status=result,queue_consume_path=result == 0,execution=t))
    for count, head in [(0, 0), (1, 0), (2, 0), (1, 1820)]:
        data = bytearray(ram)
        struct.pack_into('<I', data, ring - 0x20000000 + 4, head)
        u = cpu(raw, bytes(data), WORK + 0xf000)
        for n, value in [(0, ring), (1, 0), (2, count)]:
            u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), value)
        t = run(u, pop, [])
        fields = list(struct.unpack('<6I', bytes(u.mem_read(ring, 24))))
        success = count <= 1
        expected_head = (head + 260 * count) % 2080 if success else head
        expected_used = 260 - count * 260 if success else 260
        if t['stop'] != STOP or u.reg_read(arm.UC_ARM_REG_R0) != int(success) or fields[1:3] != [expected_head, expected_used]:
            raise ValueError('Original ring pop result differs')
        if fields[0] != 260 or fields[3:] != entry['ring_words'][3:]:
            raise ValueError('Original pop changed write offset/stride/capacity/buffer')
        rows.append(dict(kind='ring-pop',records=count,head_before=head,head_after=fields[1],used_after=fields[2],success=success,execution=t))
    packets = [(bytes.fromhex(h), None) for h in ['040e0401030c00','040e0401030c01','040e0401040c00']]
    packets += [(bytes.fromhex('040e0401030c00'), split) for split in [1,2,3,6]]
    packets += [(bytes.fromhex('040e0401030c'), None)]
    for packet, split in packets:
        u = cpu(raw, ram, WORK + 0xf000)
        u.mem_write(WORK + 0x100, packet)
        traces = []
        chunks = [(0, len(packet))] if split is None else [(0, split), (split, len(packet)-split)]
        for offset, size in chunks:
            u.reg_write(arm.UC_ARM_REG_R0, WORK + 0x100 + offset)
            u.reg_write(arm.UC_ARM_REG_R1, size)
            u.reg_write(arm.UC_ARM_REG_LR, STOP | 1)
            traces.append(run(u, parser, [dispatch]))
        complete = len(packet) == 7
        if traces[-1]['stop'] != (dispatch if complete else STOP):
            raise ValueError('Original H4 parser framing differs')
        copied = None
        if complete:
            pointer = u.reg_read(arm.UC_ARM_REG_R1)
            copied = bytes(u.mem_read(pointer, 6)).hex()
            if u.reg_read(arm.UC_ARM_REG_R0) != 4 or copied != packet[1:].hex():
                raise ValueError('Original allocation/copy/type differs')
        rows.append(dict(kind='H4-framing',packet=packet.hex(),split=split,dispatched=complete,upper_packet=copied,executions=traces,opcode_or_status_semantics_verified=False))
    handler = dispatch + 0x2a
    if decode(raw, handler, 2)[0].mnemonic != 'push':
        raise ValueError('Unidentified application HCI event handler')
    next_packets = []
    for packet_hex in [None, '040e0401030c00', '040e0401030c01', '040e0401040c00']:
        u = cpu(raw, ram, WORK + 0xf000)
        phases = [(pop, (ring, 0, 1))]
        if packet_hex is not None:
            u.mem_write(WORK + 0x100, bytes.fromhex(packet_hex))
            phases.append((parser, (WORK + 0x100, 7)))
        phases.append((handler, (1, 0)))
        traces = []
        for address, args in phases:
            for n, value in enumerate(args):
                u.reg_write(getattr(arm, 'UC_ARM_REG_R' + str(n)), value)
            u.reg_write(arm.UC_ARM_REG_LR, STOP | 1)
            traces.append(run(u, address, []))
            if traces[-1]['stop'] != STOP:
                raise ValueError('Original software transaction did not return')
        fields = list(struct.unpack('<6I', bytes(u.mem_read(ring, 24))))
        packet = None
        if packet_hex is None:
            if fields[:5] != [260,260,0,2080,260]:
                raise ValueError('No-event control unexpectedly queued a command')
        else:
            if fields[:5] != [520,260,260,2080,260]:
                raise ValueError('Different next command ring transaction')
            pointer = fields[5] + fields[1]
            size = struct.unpack('<I', bytes(u.mem_read(pointer, 4)))[0]
            packet = bytes(u.mem_read(pointer + 4, size)).hex()
            if size != 10 or not packet.startswith('0143fc06'):
                raise ValueError('Unknown follow-up command')
            next_packets.append(packet)
        rows.append(dict(kind='software-event-pipeline',input_event=packet_hex,synthetic_sequence=['pop-one-record','optional-original-parser','original-upper-handler-event-mask1'],next_packet=packet,ring_words=fields,executions=traces,natural_main_transaction=False))
    if len(set(next_packets)) != 1:
        raise ValueError('Status/opcode controls changed the observed next packet')
    # Prove the descriptor meaning from both original producer and consumer.
    producer = target(raw, pc - 0x1e) - 0x5e
    pb = decode(raw, producer, 0x5e)
    cb = decode(raw, pop, 0x5a)
    if not any(i.mnemonic == 'ldr' and i.op_str == 'r0, [r5, #0x10]' for i in pb) or not any(i.mnemonic == 'str' and i.op_str == 'r1, [r5]' for i in pb):
        raise ValueError('Unverified ring producer field layout')
    if not any(i.mnemonic == 'ldr' and i.op_str == 'r0, [r5, #0x10]' for i in cb) or not any(i.mnemonic == 'str' and i.op_str == 'r1, [r5, #4]' for i in cb):
        raise ValueError('Unverified ring consumer field layout')
    return dict(case=case,raw_sha256=sha(folder/'main.bin'),sram_sha256=sha(folder/'exports/sram-full.bin'),audit_sha256=sha(audit_path),ring_pop=pop,ring_producer=producer,application_parser=parser,upper_dispatch=dispatch,upper_handler=handler,status_and_wrong_opcode_controls_queue_same_followup=True,ring_fields=['write_offset','read_offset','used_bytes','capacity_bytes','record_stride','buffer'],samples=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Preserve prior evidence')
    rows = [inspect(a.simulator, c) for c in ['stock24','stock23','cfw']]
    count = sum(len(row['samples']) for row in rows)
    a.output.mkdir(parents=True)
    (a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_scenarios=count,fragment_engine='Unicorn M7; original ARM, synthetic entry/registers/stack, validated full native SRAM; original allocator; no stubbed calls',native_main_rerun=False,hardware_accessed=False,controller_response_injected=False,upper_hci_reset_completion_verified=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('application HCI transaction:',count,'original ARM scenarios passed; upper dispatch only')


if __name__ == '__main__':
    main()
