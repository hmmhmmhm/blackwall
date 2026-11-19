"""Original sync request APIs and byte-stream receive callback, isolated ARM only."""
import struct
from collections import Counter
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_INVALID, UC_MEM_READ_UNMAPPED, UcError
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import cpu, WORK, STOP, SRAM, BASE
from probe_ui_queue_producer import literal, word, discover, execute, sha


def crc16(data):
    value = 0
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xa001 if value & 1 else 0)
    return value


def frame(identifier, channel, payload):
    header = b'\x01' + struct.pack('>HHH', identifier, len(payload), channel)
    return header + struct.pack('>H', crc16(header)) + payload + (struct.pack('>H', crc16(payload)) if payload else b'')


def locations(raw, signature):
    start = 0
    while True:
        start = raw.find(signature, start)
        if start < 0:
            return
        yield BASE + start
        start += 1


def bl_references(raw, target):
    refs = []
    for offset in range(0, len(raw)-3, 2):
        high, low = struct.unpack_from('<HH', raw, offset)
        if high & 0xf800 != 0xf000 or low & 0xd000 != 0xd000:
            continue
        sign = high >> 10 & 1
        imm = (sign << 24) | ((1 ^ (low >> 13 & 1) ^ sign) << 23) | ((1 ^ (low >> 11 & 1) ^ sign) << 22) | ((high & 0x3ff) << 12) | ((low & 0x7ff) << 1)
        if sign:
            imm -= 1 << 25
        if BASE + offset + 4 + imm == target:
            decoded = decode(raw, BASE + offset, 4)
            if len(decoded) == 1 and decoded[0].mnemonic == 'bl':
                refs.append(BASE + offset)
    return refs


def contract(raw, sync):
    cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    cs.detail = True
    setters = []
    for pc in range(sync['master_reply'], sync['master_reply']+0xe00, 2):
        ins = next(cs.disasm(raw[pc-BASE:pc-BASE+4], pc, count=1), None)
        if ins is None or not ins.op_str.startswith('r2,'):
            continue
        try:
            value = literal(raw, ins)
        except ValueError:
            continue
        if value != sync['master_reply'] | 1:
            continue
        after = decode(raw, pc+ins.size, 20)
        assert after[0].op_str.startswith('r3,') and literal(raw, after[1]) == sync['context_slot']
        assert after[-1].mnemonic == 'bl'
        setters.append((after[-1].operands[0].imm, literal(raw, after[0])))
    assert len(setters) == 1
    start, timeout = setters[0]
    chunk, finish, tick = start+0x12, start+0x1a, start+0x22
    for address in (chunk, finish):
        code = decode(raw, address, 8)
        assert [(i.mnemonic, i.op_str) for i in (code[0], code[2])] == [('push', '{r7, lr}'), ('pop', '{r0, pc}')]
        assert code[1].mnemonic == 'bl'
    finish_core = decode(raw, finish+2, 4)[0].operands[0].imm
    calls = [i.operands[0].imm for i in decode(raw, finish_core, 0x68) if i.mnemonic == 'bl']
    transport = [target for target, count in Counter(calls).items() if count == 2]
    assert len(transport) == 1
    malloc_sites = list(locations(raw, bytes.fromhex('47f26010')))
    assert len(malloc_sites) == 1
    alloc = decode(raw, malloc_sites[0]+4, 4)[0]
    assert alloc.mnemonic == 'bl'
    byte_sites = list(locations(raw, bytes.fromhex('feb504000d00608a642824db')))
    assert len(byte_sites) == 1
    feeds = []
    for candidate in locations(raw, bytes.fromhex('f8b504000d001600002704e0')):
        ins = decode(raw, candidate+0x10, 4)[0]
        if ins.mnemonic == 'bl' and ins.operands[0].imm == byte_sites[0]:
            feeds.append(candidate)
    assert len(feeds) == 1
    refs = bl_references(raw, feeds[0])
    assert len(refs) == 1
    receiver = []
    for pc in range(refs[0]-128, refs[0], 2):
        ins = decode(raw, pc, 2)
        if len(ins) != 1 or (ins[0].mnemonic, ins[0].op_str) != ('push', '{r5, r6, r7, lr}'):
            continue
        ins = decode(raw, pc+2, 4)[0]
        if ins.op_str.startswith('r3,') and literal(raw, ins) == sync['context_slot']:
            receiver.append(pc)
    assert len(receiver) == 1
    free_call = decode(raw, sync['master_reply']+0xa2, 4)[0]
    assert free_call.mnemonic == 'bl'
    return dict(start=start, chunk=chunk, finish=finish, tick=tick, timeout_callback=timeout, deallocator=free_call.operands[0].imm,
                allocator=alloc.operands[0].imm, transport=transport[0], receive=receiver[0],
                feed=feeds[0], byte_parser=byte_sites[0])


def invoke(machine, entry, args, end=STOP, stack_args=()):
    sp = WORK+0xf000
    machine.reg_write(arm.UC_ARM_REG_SP, sp)
    machine.reg_write(arm.UC_ARM_REG_LR, STOP | 1)
    for k, value in enumerate(args):
        machine.reg_write(getattr(arm, 'UC_ARM_REG_R'+str(k)), value)
    for k, value in enumerate(stack_args):
        machine.mem_write(sp+4*k, struct.pack('<I', value))
    machine.emu_start(entry | 1, end, count=400000)
    assert machine.reg_read(arm.UC_ARM_REG_PC) == end
    return machine.reg_read(arm.UC_ARM_REG_R0)


def snapshot(machine, size):
    return dict(ram=bytes(machine.mem_read(SRAM, size)), work=bytes(machine.mem_read(WORK, 0x10000)),
                scs=bytes(machine.mem_read(0xe000e000, 0x2000)),
                regs=[machine.reg_read(getattr(arm, 'UC_ARM_REG_R'+str(k))) for k in range(13)] +
                     [machine.reg_read(x) for x in (arm.UC_ARM_REG_SP, arm.UC_ARM_REG_LR, arm.UC_ARM_REG_PC, arm.UC_ARM_REG_XPSR)])


def replay(raw, saved):
    machine = cpu(raw, saved['ram'], WORK+0xf000)
    machine.mem_write(WORK, saved['work'])
    machine.mem_write(0xe000e000, saved['scs'])
    return machine


def run_case(raw, ram, ui, sync):
    c = contract(raw, sync)
    context = sync['context']
    ring_api = discover(raw)
    positives, negatives = [], []
    for app, payload in [(0x10b, b''), (0x10b, b'BWL!'), (0x110, bytes(range(16)))]:
        machine = cpu(raw, ram, WORK+0xf000)
        node = invoke(machine, c['allocator'], [12])
        body = struct.pack('<4H', 0x100, app, 0, len(payload)) + payload
        packet = invoke(machine, c['allocator'], [len(body)])
        assert SRAM <= node < SRAM+len(ram) and SRAM <= packet < SRAM+len(ram)
        machine.mem_write(packet, body)
        machine.mem_write(node, struct.pack('<3I', 0, 0, packet))
        descriptor = WORK+0x100
        machine.mem_write(descriptor, struct.pack('<HBBH2xIH2xII', 0, 0, 0, 2, 0, len(body), node, 0))
        assert invoke(machine, c['start'], [context, descriptor, sync['master_reply'] | 1, c['timeout_callback']], stack_args=[50]) == 1
        identifier = struct.unpack('<H', machine.mem_read(descriptor, 2))[0]
        size = machine.mem_read(context+0x7158, 1)[0]
        records = [context+0x6430+24*k for k in range(size)]
        record = [p for p in records if int.from_bytes(machine.mem_read(p, 2), 'little') == identifier]
        assert len(record) == 1
        record = record[0]
        assert int.from_bytes(machine.mem_read(record+4, 4), 'little') == sync['master_reply'] | 1
        assert int.from_bytes(machine.mem_read(record+0x10, 4), 'little') == node
        invoke(machine, c['chunk'], [context, packet, len(body)])
        invoke(machine, c['finish'], [context], end=c['transport'])
        pointer, count = [machine.reg_read(getattr(arm, 'UC_ARM_REG_R'+str(k))) for k in (1, 2)]
        outgoing = bytes(machine.mem_read(pointer, count))
        assert outgoing == frame(identifier, 2, body)
        saved = snapshot(machine, len(ram))
        reply = frame(identifier, 2, b'\x02')
        for mode in ('one-chunk', 'bytewise', 'split-header'):
            states, observations = [], []
            for observe in (False, True):
                received = replay(raw, saved)
                seen, freed = [], []
                if observe:
                    def observe_api(m, pc, width, user):
                        if pc == ui['ui_producer']:
                            seen.append([m.reg_read(getattr(arm, 'UC_ARM_REG_R'+str(k))) for k in range(3)])
                        if pc == c['deallocator']:
                            freed.append(m.reg_read(arm.UC_ARM_REG_R0))
                    received.hook_add(UC_HOOK_CODE, observe_api)
                chunks = [reply] if mode == 'one-chunk' else [bytes([b]) for b in reply] if mode == 'bytewise' else [reply[:4], reply[4:9], reply[9:]]
                for index, chunk in enumerate(chunks):
                    received.mem_write(WORK+0x2000, chunk)
                    invoke(received, c['receive'], [WORK+0x2000, len(chunk)])
                    if index < len(chunks)-1:
                        assert word(bytes(received.mem_read(SRAM, len(ram))), ui['queue']+0x38) == 0
                done = snapshot(received, len(ram))
                assert word(done['ram'], ui['queue']+0x38) == 1
                assert word(done['ram'], record+4) == 0
                assert done['ram'][context+0x10-SRAM] == 0
                if observe:
                    assert seen == [[app, packet+8, len(payload)]] and freed == [packet, node]
                states.append(done)
                observations = seen
            assert states[0] == states[1]
            after = states[0]
            message = struct.pack('<III', 2, app, len(payload))
            drained, _, _ = execute(raw, after['ram'], ui['get'], [ui['queue'], WORK+0x800, 0, 0])
            assert drained['work'][0x800:0x80c] == message
            drained, _, _ = execute(raw, drained['ram'], ring_api['reader'], [ui['ring'], WORK+0x800, len(payload)])
            assert drained['work'][0x800:0x800+len(payload)] == payload
            positives.append(dict(app=app, payload=payload.hex(), mode=mode, identifier=identifier,
                                  outgoing=outgoing.hex(), reply=reply.hex(), api_arguments=observations,
                                  full_receive_and_callback_return=True, original_pending_record_removed=True,
                                  original_heap_objects_freed=True, deallocator_arguments=[packet, node], observer_on_off_final_state_exact=True,
                                  ram_sha256=sha(after['ram'])))
        for variant in ('header-crc', 'payload-crc', 'unknown-id', 'same-id-other-channel', 'duplicate'):
            received = replay(raw, saved)
            candidate = bytearray(reply)
            if variant == 'header-crc': candidate[8] ^= 1
            if variant == 'payload-crc': candidate[-1] ^= 1
            if variant == 'unknown-id': candidate = frame(identifier ^ 0x4000, 2, b'\x02')
            if variant == 'same-id-other-channel': candidate = frame(identifier, 3, b'\x02')
            received.mem_write(WORK+0x2000, bytes(candidate))
            faults = []
            def missing(m, access, address, width, value, user):
                faults.append(dict(access=access, address=address, width=width, pc=m.reg_read(arm.UC_ARM_REG_PC)))
                return False
            received.hook_add(UC_HOOK_MEM_INVALID, missing)
            try:
                invoke(received, c['receive'], [WORK+0x2000, len(candidate)])
            except UcError:
                assert faults and all(x['access'] == UC_MEM_READ_UNMAPPED and x['address'] == 0x400083c0 and x['width'] == 4 for x in faults)
            accepted = variant in ('same-id-other-channel', 'duplicate')
            state = bytes(received.mem_read(SRAM, len(ram)))
            assert word(state, ui['queue']+0x38) == int(accepted)
            assert (word(state, record+4) == 0) == accepted
            assert bool(faults) == (not accepted)
            if variant == 'duplicate':
                received.mem_write(WORK+0x2000, reply)
                try:
                    invoke(received, c['receive'], [WORK+0x2000, len(reply)])
                except UcError:
                    assert faults and all(x['address'] == 0x400083c0 and x['width'] == 4 for x in faults)
                assert faults
                state = bytes(received.mem_read(SRAM, len(ram)))
                assert word(state, ui['queue']+0x38) == 1 and word(state, record+4) == 0
            negatives.append(dict(app=app, payload_bytes=len(payload), variant=variant,
                                  initial_accepted=accepted, final_ui_messages=int(accepted),
                                  error_logging_frontiers=faults, error_handler_return_verified=False,
                                  recovery_after_bad_frame_verified=False,
                                  same_id_other_channel_is_accepted_by_original=variant == 'same-id-other-channel'))
        expired = replay(raw, saved)
        faults = []
        def missing_tick(m, access, address, width, value, user):
            faults.append(dict(access=access, address=address, width=width, pc=m.reg_read(arm.UC_ARM_REG_PC)))
            return False
        expired.hook_add(UC_HOOK_MEM_INVALID, missing_tick)
        complete_ticks = 0
        try:
            for _ in range(50):
                invoke(expired, c['tick'], [context])
                complete_ticks += 1
        except UcError:
            assert faults and all(x['access'] == UC_MEM_READ_UNMAPPED and x['address'] == 0x400083c0 and x['width'] == 4 for x in faults)
        assert complete_ticks == 49 and faults
        state = bytes(expired.mem_read(SRAM, len(ram)))
        assert word(state, ui['queue']+0x38) == 0
        negatives.append(dict(app=app, payload_bytes=len(payload), variant='timeout-log-frontier',
                              original_tick_calls_completed=complete_ticks, next_tick_entered=50,
                              physical_duration_verified=False, final_ui_messages=0,
                              timeout_cleanup_verified=False, error_logging_frontiers=faults))
    return dict(contract=c, positives=positives, failure_and_routing_cases=negatives,
                host_inserted_pending_record=False, host_called_reply_callback=False,
                original_allocator_and_free_executed=True, receive_api_return_verified=True,
                failure_handlers_completed=False,
                outgoing_transport_leaf_not_executed=True, sender_final_return_not_executed=True,
                synthetic_api_caller=True, physical_uart_or_ble_executed=False, native_main=False)
