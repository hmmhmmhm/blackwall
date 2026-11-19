"""Isolated original ARM display queue36 transactions; no full-main wake or pixels."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_INVALID, UcError
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import cpu, WORK, STOP, SRAM, BASE
from probe_ui_queue_producer import discover, literal, word, execute

SIGNATURE = bytes.fromhex('2de9f0478cb004000d0016001f00ddf85080')
UI_PREFIX = bytes.fromhex('f8b586b005000e0014000c21002203af3800')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def arguments(u):
    sp = u.reg_read(arm.UC_ARM_REG_SP)
    return [u.reg_read(getattr(arm, 'UC_ARM_REG_R'+str(k))) for k in range(4)] + list(struct.unpack('<II', u.mem_read(sp, 8)))


def prepare(raw, ram, args):
    sp = WORK+0xf000
    u = cpu(raw, ram, sp)
    for k, value in enumerate(args[:4]):
        u.reg_write(getattr(arm, 'UC_ARM_REG_R'+str(k)), value)
    u.mem_write(sp, struct.pack('<II', *args[4:]))
    return u


def state(u, size):
    return dict(ram=bytes(u.mem_read(SRAM, size)), work=bytes(u.mem_read(WORK, 0x10000)),
                scs=bytes(u.mem_read(0xe000e000, 0x2000)),
                registers=[u.reg_read(getattr(arm, 'UC_ARM_REG_R'+str(k))) for k in range(13)] +
                [u.reg_read(r) for r in [arm.UC_ARM_REG_SP, arm.UC_ARM_REG_LR, arm.UC_ARM_REG_PC, arm.UC_ARM_REG_XPSR]])


def producer(raw, ram, contract, args, observe, message_bytes=36, payload=b'', allow_peripheral_boundary=False):
    u = prepare(raw, ram, args)
    if payload:
        u.mem_write(WORK+0x100, payload)
    seen = []
    trace = []
    if observe:
        def code(c, pc, size, user):
            trace.append(pc)
            if pc == contract['put_call']:
                regs = arguments(c)[:4]
                seen.append(dict(arguments=regs, message=bytes(c.mem_read(regs[1], message_bytes)).hex()))
        u.hook_add(UC_HOOK_CODE, code)
    try:
        u.emu_start(contract['producer'] | 1, STOP, count=200000)
    except UcError as error:
        if not allow_peripheral_boundary or 'UC_ERR_READ_UNMAPPED' not in str(error):
            raise
        result = state(u, len(ram))
        result['peripheral_boundary_pc'] = u.reg_read(arm.UC_ARM_REG_PC)
        return result, seen, trace
    assert u.reg_read(arm.UC_ARM_REG_PC) == STOP
    assert u.reg_read(arm.UC_ARM_REG_SP) == WORK+0xf000
    return state(u, len(ram)), seen, trace


def binding(raw, ram, task, get):
    sp = task['saved_sp']
    w = lambda address: word(ram, address)
    exc = w(sp+4)
    extended = exc & 16 == 0
    core = sp+40+(64 if extended else 0)
    xpsr = w(core+28)
    caller = core+32+(72 if extended else 0)+(4 if xpsr & 0x200 else 0)
    matches = []
    for k in range(32):
        ret = w(caller+k*4)
        if ret & 1 == 0 or not BASE+4 <= ret < BASE+len(raw):
            continue
        ins = decode(raw, (ret & ~1)-4, 4)
        if len(ins) == 1 and ins[0].mnemonic == 'bl' and ins[0].operands[0].imm == get:
            matches.append((caller+k*4+4, ret & ~1))
    assert len(matches) == 1
    app_sp, ret = matches[0]
    assert raw[get-BASE:get-BASE+10] == bytes.fromhex('f8b506000d001c000027')
    # Suspended CPU r6/r7 hold queue/message; wrapper's pushed registers are
    # its caller's older values, not the live registers at the blocking point.
    assert w(sp+20) == app_sp+12
    load = decode(raw, ret-10, 4)[0]
    context = literal(raw, load)
    assert decode(raw, ret-6, 2)[0].op_str == 'r0, [r0, #0xc]'
    q = w(context+12)
    assert q == w(sp+16) and w(context+8) == task['tcb']
    return dict(context=context, queue=q, consumer_return=ret, saved_app_sp=app_sp)


def contract(raw, ram, task):
    apis = discover(raw)
    c = binding(raw, ram, task, apis['get'])
    assert raw.count(SIGNATURE) == 1
    entry = BASE+raw.index(SIGNATURE)
    b = {i.address-entry: i for i in decode(raw, entry, 0xb0)}
    assert b[0x44].mnemonic == 'bl' and b[0x44].operands[0].imm == apis['put']
    assert literal(raw, b[0x40]) == c['context']
    for off, op in [(0x24, 'r0, #3'), (0x26, 'r0, [sp, #0xc]'), (0x28, 'r4, [sp, #0x10]'),
                    (0x2a, 'r5, [sp, #0x14]'), (0x2c, 'r6, [sp, #0x18]'), (0x2e, 'r7, [sp, #0x1c]')]:
        assert b[off].op_str == op, (off, b[off].op_str)
    ret = c['consumer_return']
    prefix = decode(raw, ret, 0x4c)
    calls = [i.operands[0].imm for i in prefix if i.mnemonic == 'bl']
    assert len(calls) == 4
    by = {i.address-ret: i for i in prefix}
    assert by[0x34].op_str == 'r0, #3' and by[0x36].mnemonic == 'beq'
    switch = by[0x36].operands[0].imm
    block = {i.address-switch: i for i in decode(raw, switch, 0x20)}
    mode_slot = literal(raw, block[0])
    assert block[6].op_str == 'r0, #1' and block[8].mnemonic == 'bne'
    assert block[26].mnemonic == 'bl'
    wrapper = block[26].operands[0].imm
    assert raw[wrapper-BASE:wrapper-BASE+2] == bytes.fromhex('3eb5')
    slot = literal(raw, decode(raw, wrapper+2, 2)[0])
    table = word(ram, slot)
    assert BASE <= table < BASE+len(raw)-44
    callback = struct.unpack_from('<I', raw, table+40-BASE)[0]
    assert callback & 1 and BASE <= callback-1 < BASE+len(raw)
    return dict(**c, producer=entry, put=apis['put'], get=apis['get'], put_call=entry+0x44,
                consumer_helpers=calls, suppressed=by[0x22].operands[0].imm,
                mode_slot=mode_slot, mode_actual=word(ram, mode_slot), mode_skip=block[8].operands[0].imm,
                wrapper=wrapper, vtable_slot=slot, vtable=table, callback=callback & ~1)


def consumer(raw, ram, c, message, policy, mode):
    # Explicit ABI diagnostic: start after queue-get, stub preparation/policy.
    u = prepare(raw, ram, [0]*6)
    sp = u.reg_read(arm.UC_ARM_REG_SP)
    u.mem_write(sp+12, message)
    u.mem_write(c['mode_slot'], struct.pack('<I', mode))
    seen = []
    stop = None
    def code(v, pc, size, user):
        nonlocal stop
        if pc in c['consumer_helpers']:
            seen.append(pc)
            v.reg_write(arm.UC_ARM_REG_R0, policy if pc == c['consumer_helpers'][-1] else 0)
            v.reg_write(arm.UC_ARM_REG_PC, v.reg_read(arm.UC_ARM_REG_LR))
        elif pc in [c['suppressed'], c['mode_skip'], c['wrapper']]:
            stop = pc
            v.emu_stop()
    u.hook_add(UC_HOOK_CODE, code)
    u.emu_start(c['consumer_return'] | 1, STOP, count=2000)
    assert seen == c['consumer_helpers']
    expected = c['suppressed'] if policy == 0 else c['mode_skip'] if mode != 1 else c['wrapper']
    assert stop == expected, (stop, expected)
    forwarded = arguments(u) if stop == c['wrapper'] else None
    if forwarded is not None:
        assert forwarded == list(struct.unpack('<9I', message))[1:7]
    return dict(policy_fixture=policy, mode_fixture=mode, stop=stop, forwarded=forwarded,
                helpers_stubbed=seen, actual_snapshot_mode=c['mode_actual'])


def activation_contract(raw, ram, mapped, display):
    api = discover(raw)
    task = next(t for t in mapped['graph']['tasks'] if t['name'] == 'ui_task')
    sp = task['saved_sp']
    extended = word(ram, sp+4) & 16 == 0
    core = sp+40+(64 if extended else 0)
    caller = core+32+(72 if extended else 0)+(4 if word(ram, core+28) & 0x200 else 0)
    frames = []
    for k in range(32):
        ret = word(ram, caller+k*4)
        if ret & 1 == 0 or not BASE+4 <= ret < BASE+len(raw):
            continue
        b = decode(raw, (ret & ~1)-4, 4)
        if len(b) == 1 and b[0].mnemonic == 'bl' and b[0].operands[0].imm == api['get']:
            frames.append((caller+k*4+4, ret & ~1))
    assert len(frames) == 1
    app_sp, ret = frames[0]
    assert raw[api['get']-BASE:api['get']-BASE+10] == bytes.fromhex('f8b506000d001c000027')
    # Wrapper pushes r3-r7/lr before changing them. Recover the app's registers,
    # rather than confusing its live kernel r4-r7 with the caller's values.
    app_regs = [word(ram, app_sp-20+4*k) for k in range(4)]
    state_slot, table_slot, _, message_buffer = app_regs
    q = word(ram, api['queue_slot'])
    assert q == word(ram, sp+16) and message_buffer == word(ram, sp+20)
    assert [word(ram, q+off) for off in [0x24, 0x38, 0x3c, 0x40]] == [1, 0, 96, 12]
    table = word(ram, table_slot)
    assert BASE <= table < BASE+len(raw)-24 and struct.unpack_from('<I', raw, table-BASE)[0] == 1
    on = struct.unpack_from('<I', raw, table+8-BASE)[0]
    assert on & 1
    on &= ~1
    on_body = {i.address-on: i for i in decode(raw, on, 0x24)}
    assert on_body[0x10].op_str == 'r0, #1' and on_body[0x20].mnemonic == 'bl'
    assert on_body[0x20].operands[0].imm == api['put']
    assert literal(raw, on_body[0x1c]) == display['context']
    body = {i.address-ret: i for i in decode(raw, ret, 0x96)}
    for off, op in [(0x4c, 'r0, [r4]'), (0x6e, 'r0, [r7]'), (0x70, 'r0, #2'),
                    (0x78, 'r0, #1'), (0x7a, 'r0, [r4]'), (0x84, 'r0, [r5]'),
                    (0x86, 'r0, [r0, #0xc]'), (0x8a, 'r0, [r5]'), (0x8c, 'r0, [r0, #8]')]:
        assert body[off].op_str == op
    assert body[0x8e].mnemonic == 'blx' and body[0x8e].op_str == 'r0'
    candidates = []
    start = 0
    while True:
        offset = raw.find(UI_PREFIX, start)
        if offset < 0:
            break
        start = offset+1
        entry = BASE+offset
        b = {i.address-entry: i for i in decode(raw, entry, 0xb4)}
        if b.get(0x7a) and b[0x7a].op_str == 'r0, #2':
            assert b[0xac].mnemonic == 'bl' and b[0xac].operands[0].imm == api['put']
            assert literal(raw, b[0xa8]) == api['queue_slot']
            candidates.append(entry)
    assert len(candidates) == 1
    return dict(ui_tcb=task['tcb'], app_sp=app_sp, app_r4_r7=app_regs, queue=q,
                return_pc=ret, state_slot=state_slot, actual_state=ram[state_slot-SRAM],
                table_slot=table_slot, table=table, display_on_producer=on,
                display_on_indirect_call=ret+0x8e, message_buffer=message_buffer,
                ui_producer=candidates[0], ui_put_call=candidates[0]+0xac,
                preparation_helpers=[body[k].operands[0].imm for k in [0x48, 0x74, 0x7c, 0x80]],
                get=api['get'], ring=api['ring'])


def activation_prefix(raw, ram, c, get_registers, observe):
    u = cpu(raw, ram, c['app_sp'])
    for k, value in enumerate(get_registers[:13]):
        u.reg_write(getattr(arm, 'UC_ARM_REG_R'+str(k)), value)
    for k, value in enumerate(c['app_r4_r7'], 4):
        u.reg_write(getattr(arm, 'UC_ARM_REG_R'+str(k)), value)
    seen = []
    faults = []
    trace = []
    if observe:
        def code(v, pc, size, user):
            trace.append(pc)
            if pc in c['preparation_helpers']+[c['display_on_producer']]:
                seen.append(pc)
        def invalid(v, kind, address, size, value, user):
            faults.append(dict(pc=v.reg_read(arm.UC_ARM_REG_PC), address=address, size=size, kind=kind,
                               r4=v.reg_read(arm.UC_ARM_REG_R4)))
            return False
        u.hook_add(UC_HOOK_CODE, code)
        u.hook_add(UC_HOOK_MEM_INVALID, invalid)
    try:
        u.emu_start(c['return_pc'] | 1, STOP, count=200000)
    except UcError as error:
        # An unmapped device in this isolated M7 fixture is a declared boundary,
        # not an initialization success or a Renode model failure.
        if 'UC_ERR_READ_UNMAPPED' not in str(error):
            raise
    else:
        raise AssertionError('Expected explicit peripheral boundary, not a return/budget limit')
    return state(u, len(ram)), seen, faults, trace


def activation_case(raw, ram, mapped, display):
    c = activation_contract(raw, ram, mapped, display)
    assert c['actual_state'] == 0
    samples = []
    for app, payload in [(0x10b, b''), (0x10b, bytes.fromhex('12345678')), (0x110, bytes(range(16))),
                         (0x10b, bytes((k*31+7) & 255 for k in range(0x2800)))]:
        # Original API input. It is not an on-air phone packet or a claimed
        # natural task resume. Keep pointed input separate from queue words.
        pointer = WORK+0x100
        ingress = dict(producer=c['ui_producer'], put_call=c['ui_put_call'])
        args = [app, pointer, len(payload), 0, 0, 0]
        sent, seen, trace = producer(raw, ram, ingress, args, True, 12, payload)
        plain, _, _ = producer(raw, ram, ingress, args, False, 12, payload)
        assert sent == plain and sent['registers'][0] == 0 and len(seen) == 1
        message = struct.pack('<III', 2, app, len(payload))
        assert bytes.fromhex(seen[0]['message']) == message and seen[0]['arguments'][0] == c['queue']
        assert word(sent['ram'], c['queue']+0x38) == 1 and word(sent['ram'], c['ui_tcb']+40) == 0
        received, _, _ = execute(raw, sent['ram'], c['get'], [c['queue'], c['message_buffer'], 0, 0])
        off = c['message_buffer']-SRAM
        assert received['ram'][off:off+12] == message and word(received['ram'], c['queue']+0x38) == 0
        after, helpers, faults, path = activation_prefix(raw, received['ram'], c, received['registers'], True)
        plain_after, _, _, _ = activation_prefix(raw, received['ram'], c, received['registers'], False)
        assert after == plain_after and len(faults) == 1
        assert helpers == c['preparation_helpers'][:3] and faults[0]['address'] == 0x40021004 and faults[0]['size'] == 4
        assert after['ram'][c['state_slot']-SRAM] == 1
        assert word(after['ram'], display['queue']+0x38) == 0
        ring = c['ring']
        assert word(after['ram'], ring+8) == len(payload) and word(after['ram'], ring+12) == len(payload)
        # UI's original ring read staged the exact payload before preparation.
        staging_load = next(i for i in decode(raw, c['return_pc'], 0x30) if i.mnemonic == 'ldr.w' and i.op_str.startswith('r8, [pc,'))
        staging = literal(raw, staging_load)
        assert after['ram'][staging-SRAM:staging-SRAM+len(payload)] == payload
        samples.append(dict(app_argument=app,payload=payload.hex(),message=message.hex(),producer_return=0,
                            original_ui_state_before=0,original_ui_state_after=1,preparation_helpers_entered=helpers,
                            fault=faults[0],display_on_producer_reached=False,display_queue_messages=0,
                            producer_observer_control_exact=True,prefix_observer_control_exact=True,
                            ui_payload_staging=staging,ring_read_cursor=len(payload),ring_write_cursor=len(payload),
                            producer_instructions=len(trace),prefix_instructions=len(path),
                            prefix_trace_sha256=sha(struct.pack('<'+'I'*len(path),*path))))
    rejected, seen, _ = producer(raw, ram, ingress, [0x10b, WORK+0x100, 0x2801, 0, 0, 0], True, 12, allow_peripheral_boundary=True)
    rejected_control, _, _ = producer(raw, ram, ingress, [0x10b, WORK+0x100, 0x2801, 0, 0, 0], False, 12, allow_peripheral_boundary=True)
    assert rejected == rejected_control and rejected.get('peripheral_boundary_pc') and not seen
    assert word(rejected['ram'], c['queue']+0x38) == 0
    on_path = activation_display_path(raw, ram, c, display)
    return dict(contract=c,samples=samples,display_on_path=on_path,callees_stubbed=False,original_queue_api_executed=True,
                oversize_input_guard=dict(size=0x2801,return_verified=False,queue_messages=0,observer_control_exact=True,
                                          diagnostic_path_boundary_pc=rejected['peripheral_boundary_pc']),
                caller_context_synthetic=True,natural_task_resume=False,peripheral_boundary_is_isolated_fixture=True)


def activation_display_path(raw, ram, ui, c):
    ingress = dict(producer=ui['display_on_producer'], put_call=ui['display_on_producer']+0x20)
    sent, seen, _ = producer(raw, ram, ingress, [0]*6, True)
    plain, _, _ = producer(raw, ram, ingress, [0]*6, False)
    message = struct.pack('<9I', 1, *([0]*8))
    assert sent == plain and len(seen) == 1 and bytes.fromhex(seen[0]['message']) == message
    assert sent['registers'][0] == 0 and word(sent['ram'], c['queue']+0x38) == 1
    received, _, _ = execute(raw, sent['ram'], c['get'], [c['queue'], c['saved_app_sp']+12, 0, 0])
    off = c['saved_app_sp']+12-SRAM
    assert received['ram'][off:off+36] == message and word(received['ram'], c['queue']+0x38) == 0
    on_call = decode(raw, c['consumer_return']+0x6c, 4)[0]
    assert on_call.mnemonic == 'bl'
    wrapper = on_call.operands[0].imm
    assert literal(raw, decode(raw, wrapper+2, 4)[0]) == c['vtable_slot']
    callback = struct.unpack_from('<I', raw, c['vtable']+12-BASE)[0]
    assert callback & 1 and BASE <= callback-1 < BASE+len(raw)
    def run(observe):
        u = cpu(raw, received['ram'], c['saved_app_sp'])
        for k, value in enumerate(received['registers'][:13]):
            u.reg_write(getattr(arm, 'UC_ARM_REG_R'+str(k)), value)
        # Original app r4-r7 are in the get wrapper's pushed caller frame.
        for k in range(4, 8):
            u.reg_write(getattr(arm, 'UC_ARM_REG_R'+str(k)), word(ram, c['saved_app_sp']-20+(k-4)*4))
        seen = []
        faults = []
        if observe:
            def code(v, pc, size, user):
                if pc in c['consumer_helpers']+[wrapper, callback & ~1]:
                    seen.append(pc)
            def invalid(v, kind, address, size, value, user):
                faults.append(dict(pc=v.reg_read(arm.UC_ARM_REG_PC), address=address, size=size, kind=kind))
                return False
            u.hook_add(UC_HOOK_CODE, code)
            u.hook_add(UC_HOOK_MEM_INVALID, invalid)
        try:
            u.emu_start(c['consumer_return'] | 1, STOP, count=200000)
        except UcError as error:
            if 'UC_ERR_READ_UNMAPPED' not in str(error):
                raise
        else:
            raise AssertionError('Expected isolated peripheral boundary')
        return state(u, len(ram)), seen, faults
    result, helpers, faults = run(True)
    control, _, _ = run(False)
    assert result == control and len(faults) == 1
    assert helpers == [c['consumer_helpers'][0], c['consumer_helpers'][3], wrapper, callback & ~1]
    assert faults[0]['address'] == 0x400083c0 and faults[0]['size'] == 4
    assert word(result['ram'], c['mode_slot']) == c['mode_actual'] == 0
    return dict(message=message.hex(), producer_observer_control_exact=True, prefix_observer_control_exact=True,
                original_eligibility_allowed=True, actual_mode_before=0, actual_mode_after=0,
                original_callees_entered=helpers, wrapper=wrapper, callback=callback & ~1,
                fault=faults[0], callback_returned=False, mode_write_reached=False,
                producer_to_ui_to_display_is_one_scheduled_run=False)



def sync_contract(raw, ram, ui):
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
    signature = bytes.fromhex('3eb50c00a0680028')
    candidates = []
    start = 0
    while True:
        start = raw.find(signature, start)
        if start < 0:
            break
        entry = BASE + start
        call = decode(raw, entry + 0x124, 4)
        if len(call) == 1 and call[0].mnemonic == 'bl' and call[0].operands[0].imm == ui['ui_producer']:
            candidates.append(entry)
        start += 1
    assert len(candidates) == 1
    master = candidates[0]
    slave_sig = bytes.fromhex('2de9f84199b004000e00b568')
    assert raw.count(slave_sig) == 1
    slave = BASE + raw.index(slave_sig)
    call = decode(raw, slave + 0x104, 4)[0]
    assert call.mnemonic == 'bl' and call.operands[0].imm == ui['ui_producer']
    # Bind the original channel-2 registration and its actual context slot.
    cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    cs.detail = True
    loads = []
    registrations = []
    for address in range(master, min(master + 0xe00, BASE + len(raw) - 4), 2):
        ins = next(cs.disasm(raw[address-BASE:address-BASE+4], address, count=1), None)
        if ins is None:
            continue
        try:
            value = literal(raw, ins)
        except ValueError:
            continue
        if ins.op_str.startswith('r4,') and SRAM <= value < SRAM + len(ram) - 4:
            loads.append((address, value))
        if value == slave | 1:
            after = decode(raw, address + ins.size, 10)
            assert [(x.mnemonic, x.op_str) for x in after[:2]] == [('movs', 'r1, #2'), ('ldr', 'r0, [r4]')]
            assert after[2].mnemonic == 'bl'
            registrations.append((address, after[2].operands[0].imm))
    assert len(registrations) == 1
    registration, register_api = registrations[0]
    slot = max((x for x in loads if x[0] < registration), key=lambda x: x[0])[1]
    context = word(ram, slot)
    assert SRAM <= context and context + 0x715b <= SRAM + len(ram)
    pending_count, callback_count = ram[context+0x7158-SRAM:context+0x715a-SRAM]
    assert pending_count <= 32 and callback_count <= 32
    listeners = [dict(channel=word(ram, context+0x7030+8*k) & 0xffff,
                      callback=word(ram, context+0x7034+8*k)) for k in range(callback_count)]
    pending = [dict(id=word(ram, context+0x6430+24*k) & 0xffff,
                    callback=word(ram, context+0x6434+24*k)) for k in range(pending_count)]
    assert not any(x['callback'] == slave | 1 for x in listeners)
    assert not any(x['callback'] == master | 1 for x in pending)
    return dict(master_reply=master, slave_receive=slave, slave_channel=2,
                registration=registration, register_api=register_api, context_slot=slot,
                context=context, listeners=listeners, pending=pending,
                actual_slave_listener_registered=False, actual_display_reply_pending=False)


def sync_reply_case(raw, ram, mapped, display):
    c = activation_contract(raw, ram, mapped, display)
    sync = sync_contract(raw, ram, c)
    api = discover(raw)
    entry, end = sync['master_reply'], sync['master_reply'] + 0x128
    # Every accepted input comes from the original retained request, not reply data.
    expected = [('ldr', 'r5, [r4, #0x10]'), ('ldr', 'r1, [r5, #8]'),
                ('ldrh', 'r0, [r1, #2]'), ('ldrh', 'r2, [r1, #6]'),
                ('adds', 'r1, #8'), ('uxth', 'r0, r0')]
    assert [(i.mnemonic, i.op_str) for i in decode(raw, entry+0x118, 12)] == expected
    samples = []
    descriptor, reply, retained, packet = [WORK + x for x in (0x100, 0x200, 0x300, 0x1000)]
    for app, payload in [(0x10b, b''), (0x10b, bytes.fromhex('12345678')), (0x110, bytes(range(16)))]:
        states = []
        seen = []
        for observe in (False, True):
            u = cpu(raw, ram, WORK+0xf000)
            u.mem_write(descriptor, struct.pack('<6I', 0, 0, reply, 0, retained, 0))
            # Extra reply bytes intentionally differ from the outgoing payload.
            u.mem_write(reply, b'\x02REPLY-IS-NOT-CONTENT')
            u.mem_write(retained, struct.pack('<3I', 0, 0, packet))
            u.mem_write(packet, struct.pack('<4H', 0x100, app, 0, len(payload)) + payload)
            u.reg_write(arm.UC_ARM_REG_R1, descriptor)
            observations = []
            if observe:
                def hook(machine, pc, size, user):
                    if pc == c['ui_producer']:
                        observations.append([machine.reg_read(getattr(arm, 'UC_ARM_REG_R'+str(k))) for k in range(3)])
                u.hook_add(UC_HOOK_CODE, hook)
            u.emu_start(entry | 1, end, count=200000)
            assert u.reg_read(arm.UC_ARM_REG_PC) == end
            states.append(state(u, len(ram)))
            if observe:
                seen = observations
        assert states[0] == states[1] and seen == [[app, packet+8, len(payload)]]
        sent = states[0]
        message = struct.pack('<III', 2, app, len(payload))
        assert word(sent['ram'], c['queue']+0x38) == 1
        assert word(sent['ram'], c['ui_tcb']+40) == 0
        dst = word(ram, c['queue']+4)
        assert sent['ram'][dst-SRAM:dst-SRAM+12] == message
        received, _, _ = execute(raw, sent['ram'], c['get'], [c['queue'], WORK+0x800, 0, 0])
        assert received['work'][0x800:0x80c] == message and word(received['ram'], c['queue']+0x38) == 0
        drained, _, _ = execute(raw, received['ram'], api['reader'], [c['ring'], WORK+0x800, len(payload)])
        assert drained['work'][0x800:0x800+len(payload)] == payload
        assert word(drained['ram'], c['ring']+8) == word(drained['ram'], c['ring']+12) == len(payload)
        samples.append(dict(app=app, payload=payload.hex(), observed_api_arguments=seen[0], message=message.hex(),
                            queue_send_receive_and_ring_read_verified=True, observer_on_off_final_state_exact=True,
                            final_ram_sha256=sha(sent['ram']), stopped_after_ui_producer_return=True))
    negatives = []
    # Stop at the original guard/other-handler boundary; do not fabricate their return.
    for code, have_request in [(0, True), (1, True), (3, True), (255, True), (2, False)]:
        u = cpu(raw, ram, WORK+0xf000)
        u.mem_write(descriptor, struct.pack('<6I', 0, 0, reply, 0, retained if have_request else 0, 0))
        u.mem_write(reply, bytes([code]))
        u.reg_write(arm.UC_ARM_REG_R1, descriptor)
        default_branch = decode(raw, entry+0xca, 2)[0]
        assert default_branch.mnemonic == 'b'
        boundary = default_branch.operands[0].imm if have_request else entry+0xd2
        try:
            u.emu_start(entry | 1, boundary, count=200000)
        except UcError as error:
            raise ValueError('Reply guard frontier: entry=%x code=%x retained=%s pc=%x' % (entry, code, have_request, u.reg_read(arm.UC_ARM_REG_PC))) from error
        assert u.reg_read(arm.UC_ARM_REG_PC) == boundary
        assert word(bytes(u.mem_read(SRAM, len(ram))), c['queue']+0x38) == 0
        negatives.append(dict(reply_byte=code, retained_request_present=have_request,
                              stop=boundary, ui_message_sent=False, error_handler_return_verified=False))
    return dict(contract=sync, samples=samples, negative_boundaries=negatives,
                callback_context_synthetic=True, delay_or_io_helpers_stubbed=False,
                peer_transport_not_executed=True, callback_final_return_not_executed=True,
                legitimate_pending_request_creation_not_executed=True,
                original_ui_producer_and_queue_executed=True, native_main=False)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--activation', action='store_true', help='Trace original type2 UI ingress/preparation without helper stubs')
    p.add_argument('--sync-ingress', action='store_true', help='Bound original peer reply callback to actual UI queue/ring; no wire input')
    p.add_argument('--sync-roundtrip', action='store_true', help='Original request APIs and sync receive byte parser; isolated ARM only')
    a = p.parse_args()
    if sum((a.activation, a.sync_ingress, a.sync_roundtrip)) > 1:
        p.error('Select one diagnostic contract')
    if (a.sync_ingress or a.sync_roundtrip) and (not a.output.resolve().is_relative_to(a.simulator.resolve()) or a.simulator.resolve().is_relative_to(Path(__file__).resolve().parents[1])):
        p.error('Sync ingress evidence must use a fresh private simulator output')
    assert not a.output.exists(), 'Preserve previous evidence'
    a.output.mkdir(parents=True)
    (a.output/'probe.py').write_bytes(Path(__file__).read_bytes())
    s = a.simulator
    manifest_path = s/'imu-powersave-verification-01/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    waits_path = s/'imu-ui-dependency-source-02/report.json'
    waits_manifest_path = s/'imu-ui-dependency-verification-01/manifest.json'
    waits_manifest = json.loads(waits_manifest_path.read_text())
    waits = json.loads(waits_path.read_text())
    assert manifest['passed'] and waits['passed'] and waits_manifest['passed']
    assert sha(waits_path.read_bytes()) == waits_manifest['files'][str(waits_path.relative_to(s))]
    rows = []
    for case in ['stock24', 'stock23', 'cfw']:
        ap = s/'imu-powersave-saved-audit-01'/case/'report.json'
        assert sha(ap.read_bytes()) == manifest['files'][str(ap.relative_to(s))]
        audit = json.loads(ap.read_text())
        source = Path(audit['capture'])
        for name, pin in audit['capture_hashes'].items():
            assert sha((source/name).read_bytes()) == pin
        raw = (source/'main.bin').read_bytes()
        ram = (source/'exports/sram-full.bin').read_bytes()
        mapped = next(x for x in waits['cases'] if x['case'] == case)
        assert mapped['source_audit_sha256'] == sha(ap.read_bytes())
        task = next(x for x in mapped['graph']['tasks'] if x['name'] == 'displaydrv_mgr_task')
        c = contract(raw, ram, task)
        if a.sync_roundtrip:
            from sync_peer_roundtrip import run_case
            ui = activation_contract(raw, ram, mapped, c)
            rows.append(dict(case=case, raw_sha256=sha(raw), source_audit_sha256=sha(ap.read_bytes()), sync_roundtrip=run_case(raw, ram, ui, sync_contract(raw, ram, ui))))
            continue
        if a.sync_ingress:
            rows.append(dict(case=case, raw_sha256=sha(raw), source_audit_sha256=sha(ap.read_bytes()), sync_ingress=sync_reply_case(raw, ram, mapped, c)))
            continue
        if a.activation:
            rows.append(dict(case=case, raw_sha256=sha(raw), source_audit_sha256=sha(ap.read_bytes()),
                             activation=activation_case(raw, ram, mapped, c)))
            continue
        q = c['queue']
        assert [word(ram, q+off) for off in [0x24, 0x38, 0x3c, 0x40]] == [1, 0, 96, 36]
        samples = []
        for args in [[0, 0, 0, 0, 576, 288], [0x12345678, 0x89abcdef, 3, 4, 5, 6], [0xffffffff, 0x20000100, 0, 0x80000000, 639, 479]]:
            emitted, seen, trace = producer(raw, ram, c, args, True)
            plain, _, _ = producer(raw, ram, c, args, False)
            assert emitted == plain and len(seen) == 1
            message = struct.pack('<9I', 3, *args, 0, 0)
            assert seen[0]['arguments'][0] == q and seen[0]['arguments'][2:] == [0, 1000]
            assert bytes.fromhex(seen[0]['message']) == message
            after = emitted['ram']
            destination = word(ram, q+4)
            assert emitted['registers'][0] == 0
            assert [word(after, q+off) for off in [0x24, 0x38]] == [0, 1]
            assert word(after, task['tcb']+40) == 0 and word(after, q+4) == destination+36
            assert after[destination-SRAM:destination-SRAM+36] == message
            u = prepare(raw, after, [q, WORK+0x100, 0, 0, 0, 0])
            u.emu_start(c['get'] | 1, STOP, count=200000)
            assert u.reg_read(arm.UC_ARM_REG_PC) == STOP and u.reg_read(arm.UC_ARM_REG_R0) == 0
            received = bytes(u.mem_read(WORK+0x100, 36))
            assert received == message and struct.unpack('<I', u.mem_read(q+0x38, 4))[0] == 0
            branches = [consumer(raw, ram, c, received, policy, mode) for policy in [0, 1] for mode in [0, 1]]
            v = prepare(raw, ram, args)
            v.hook_add(UC_HOOK_CODE, lambda u, pc, n, user: u.emu_stop() if pc == c['callback'] else None)
            v.emu_start(c['wrapper'] | 1, STOP, count=2000)
            assert v.reg_read(arm.UC_ARM_REG_PC) == c['callback'] and arguments(v) == args
            samples.append(dict(arguments=args, message=message.hex(), producer_return=0,
                                observer_on_off_final_state_exact=True, queue_messages_after_send=1,
                                queue_messages_after_receive=0, receiver_waiters_after_send=0,
                                receiver_event_container_after_send=0, consumer_diagnostics=branches,
                                driver_callback_arguments=arguments(v), driver_callback_executed=False,
                                producer_instructions=len(trace), producer_trace_sha256=sha(struct.pack('<'+'I'*len(trace), *trace))))
        rows.append(dict(case=case, raw_sha256=sha(raw), source_audit_sha256=sha(ap.read_bytes()), contract=c, samples=samples))
    result = dict(passed=True, cases=rows, source_manifest_sha256=sha(manifest_path.read_bytes()),
                  wait_map_sha256=sha(waits_path.read_bytes()), wait_manifest_sha256=sha(waits_manifest_path.read_bytes()), original_arm_scenarios=72,
                  engine='Unicorn 2.1.4 Cortex-M7 isolated ARM functions', producer_internal_calls_skipped=False,
                  consumer_helpers_stubbed=True, consumer_mode_and_policy_synthetic=True,
                  hardware_accessed=False, native_main_resumed=False, nvic_or_pendsv_executed=False,
                  boot_verified=False, display_pixels_verified=False)
    if a.activation:
        result.update(original_arm_scenarios=81,consumer_helpers_stubbed=False,
                      consumer_mode_and_policy_synthetic=False,activation_complete=False,
                      current_ui_state_changed_by_original_code=True)
    if a.sync_ingress:
        result.update(original_arm_scenarios=51,consumer_helpers_stubbed=False,consumer_mode_and_policy_synthetic=False,callback_context_synthetic=True,peer_transport_executed=False,app_start_verified=False)
    if a.sync_roundtrip:
        result.pop('original_arm_scenarios')
        result.update(consumer_helpers_stubbed=False,consumer_mode_and_policy_synthetic=False,synthetic_api_caller=True,request_reply_scenarios=sum(len(x['sync_roundtrip']['positives'])+len(x['sync_roundtrip']['failure_and_routing_cases']) for x in rows),native_main=False,physical_transport_executed=False,app_start_verified=False)
    (a.output/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=3, samples=12 if a.activation else 9, original_arm_scenarios=result.get('original_arm_scenarios'), request_reply_scenarios=result.get('request_reply_scenarios'))))


if __name__ == '__main__':
    main()
