"""Original ARM HCI status/LE-public-key events on validated native SRAM."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import unicorn.arm_const as arm
from inspect_application_vendor_address import call, sha
from inspect_nema_blocking_wait import cpu, WORK
from inspect_privacy_length_contract import queued
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal

# Public P-256 generator; a deterministic test point, not a device identity.
GX = int('6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296',16)
GY = int('4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5',16)
POINT = GX.to_bytes(32,'little') + GY.to_bytes(32,'little')
STATUS = bytes.fromhex('040f0400012520')
COMPLETE = bytes.fromhex('043e420800') + POINT


def inspect(s, case, output):
    folder=s/('privacy-length-main-01' if case=='stock24' else 'privacy-length-main-02/'+case)
    audit_path=s/'privacy-length-saved-audit-01'/case/'report.json'
    audit=json.loads(audit_path.read_text())
    if not audit['passed'] or audit['hardware_accessed']:
        raise ValueError('Unverified native source')
    for name,digest in audit['capture_hashes'].items():
        if sha(folder/name)!=digest:raise ValueError('Changed capture: '+name)
    raw=(folder/'main.bin').read_bytes();ram=(folder/'exports/sram-full.bin').read_bytes()
    path=s/'application-hci-transaction-source-02/report.json'
    pin=json.loads((s/'application-hci-reset-verification-01/manifest.json').read_text())['retained_source_sha256']
    if sha(path)!=pin:raise ValueError('Changed parser callbacks')
    ctx=next(r for r in json.loads(path.read_text())['cases'] if r['case']==case)
    path=s/'application-hci-source-01/report.json'
    pin=json.loads((s/'application-hci-idle-verification-01/manifest.json').read_text())['source_report_sha256']
    if sha(path)!=pin:raise ValueError('Changed ring metadata')
    ring=next(r for r in json.loads(path.read_text())['cases'] if r['case']==case)['tx_ring']
    candidates=[]
    for instruction in decode(raw,ctx['upper_handler'],0xa0):
        if instruction.mnemonic!='bl':continue
        target=instruction.operands[0].imm
        if any(i.mnemonic=='cmp' and i.op_str=='r2, #0x3e' for i in decode(raw,target,0xa0)):
            candidates.append(target)
    if len(candidates)!=1:raise ValueError('Ambiguous original HCI event dispatcher')
    dispatcher=candidates[0]
    callbacks=literal(raw,decode(raw,dispatcher+8,4)[0])
    word=lambda address:struct.unpack_from('<I',ram,address-0x20000000)[0]
    crypto=word(callbacks+12)&~1
    instructions=decode(raw,crypto,0x120)
    branch=next(instructions[n+1] for n,i in enumerate(instructions[:-1]) if i.mnemonic=='cmp' and i.op_str=='r0, #0x25')
    if branch.mnemonic!='beq':raise ValueError('Changed public-key event branch')
    block=decode(raw,branch.operands[0].imm,16)
    pending_queue=literal(raw,next(i for i in block if i.mnemonic.startswith('ldr') and '[pc,' in i.op_str))
    pop_instruction=next(i for i in block if i.mnemonic=='bl')
    pop=pop_instruction.operands[0].imm
    probe=cpu(raw,ram,WORK+0xf000);pending_pop=call(probe,pop,(pending_queue,WORK+0x200))
    request=probe.reg_read(arm.UC_ARM_REG_R0)
    if request!=word(pending_queue)+8:raise ValueError('Different original allocation/payload relation')
    state=ram[request-0x20000000+0x34]
    indirect=next(i for i in instructions if i.mnemonic=='blx' and i.op_str=='r3')
    table=literal(raw,[i for i in instructions if i.address<indirect.address and i.mnemonic.startswith('ldr') and i.op_str.startswith('r3, [pc,')][-1])
    consumer=word(table+0x3c+state*4)&~1
    send=[i for i in decode(raw,consumer,0x36) if i.mnemonic=='bl'][2].operands[0].imm
    send_calls=[i for i in decode(raw,send,0x24) if i.mnemonic=='bl']
    if not any(i.mnemonic=='bl' and i.operands[0].imm==send-0xa
               for i in decode(raw,ctx['upper_handler'],0xa0)):
        raise ValueError('Message free entry differs from original HCI consumer')
    getter=send_calls[0].operands[0].imm
    message_queue=literal(raw,decode(raw,getter,4)[0])
    ready=send_calls[2].operands[0].imm
    registry=literal(raw,next(i for i in decode(raw,ready,16) if i.mnemonic.startswith('ldr') and '[pc,' in i.op_str))
    if state!=2 or decode(raw,consumer+8,4)[0].mnemonic!='ldrb':
        raise ValueError('Changed original public-key consumer')
    scenarios=[('no-event',[]),('status-only',[STATUS]),
        ('status-error',[bytes.fromhex('040f0401012520')]),
        ('status-then-public-point',[STATUS,COMPLETE]),
        ('completion-error',[STATUS,bytes.fromhex('043e420801')+bytes(64)]),
        ('completion-without-status',[COMPLETE]),
        ('wire-truncated',[STATUS,COMPLETE[:-1]]),
        ('wrong-command-complete',[bytes.fromhex('040e0401252000')])]
    rows=[]
    for name,events in scenarios:
        u=cpu(raw,ram,WORK+0xf000)
        if queued(u,ring)[0]!=bytes.fromhex('01252000'):raise ValueError('Different initial public-key command')
        phases=[];error=None
        try:
            phases.append(call(u,ctx['ring_pop'],(ring,0,1)))
            for event in events:
                u.mem_write(WORK+0x100,event)
                phases.append(call(u,ctx['application_parser'],(WORK+0x100,len(event))))
                phases.append(call(u,ctx['upper_handler'],(1,0)))
            if not events:phases.append(call(u,ctx['upper_handler'],(1,0)))
            next_packet,fields=queued(u,ring)
        except Exception as exc:
            error=dict(type=type(exc).__name__,message=str(exc)[:150],pc=u.reg_read(arm.UC_ARM_REG_PC))
            next_packet=None;fields=list(struct.unpack('<6I',bytes(u.mem_read(ring,24))))
        after=bytes(u.mem_read(0x20000000,len(ram)))
        if name in ['status-then-public-point','status-only']:
            (output/(case+'-'+name+'-sram.bin')).write_bytes(after)
            (output/(case+'-'+name+'-work.bin')).write_bytes(bytes(u.mem_read(WORK,0x10000)))
        positions=[];offset=0
        while True:
            offset=after.find(POINT,offset)
            if offset<0:break
            positions.append(0x20000000+offset);offset+=len(POINT)
        request_offset=request-0x20000000
        consumed=(after[request_offset+4:request_offset+36]==GX.to_bytes(32,'big') and
                  after[request_offset+36:request_offset+68]==GY.to_bytes(32,'big'))
        owner_phases=[];owner_messages=[];owner_error=None
        try:
            for _ in range(8):
                owner_phases.append(call(u,pop,(message_queue,WORK+0x200)))
                message=u.reg_read(arm.UC_ARM_REG_R0)
                if not message:break
                owner=bytes(u.mem_read(WORK+0x200,1))[0]
                if owner>=10:raise ValueError('Unrecognized WSF owner')
                handler=word(registry+owner*4)&~1
                owner_messages.append(dict(pointer=message,owner=owner,handler=handler,
                    event=bytes(u.mem_read(message+2,1))[0]))
                owner_phases.append(call(u,handler,(0,message)))
                # The original WSF dispatch loop frees each delivered message.
                owner_phases.append(call(u,send-0xa,(message,)))
            next_after_owner,_=queued(u,ring)
        except Exception as exc:
            owner_error=dict(type=type(exc).__name__,message=str(exc)[:150],pc=u.reg_read(arm.UC_ARM_REG_PC))
            next_after_owner=None
        if name=='status-then-public-point' and owner_error is None:
            (output/(case+'-owner-sram.bin')).write_bytes(bytes(u.mem_read(0x20000000,len(ram))))
            (output/(case+'-owner-work.bin')).write_bytes(bytes(u.mem_read(WORK,0x10000)))
        rows.append(dict(scenario=name,event_lengths=[len(x) for x in events],
            executions=phases,error=error,ring_words=fields,
            next_header=next_packet[:4].hex() if next_packet else None,
            next_length=len(next_packet) if next_packet else 0,
            next_sha256=hashlib.sha256(next_packet).hexdigest() if next_packet else None,
            public_point_copies=positions,request_big_endian_coordinates_match=consumed,
            request_status=after[request_offset+3],
            owner_messages=owner_messages,owner_executions=owner_phases,owner_error=owner_error,
            next_after_owner_header=next_after_owner[:4].hex() if next_after_owner else None,
            next_after_owner_length=len(next_after_owner) if next_after_owner else 0,
            next_after_owner_sha256=hashlib.sha256(next_after_owner).hexdigest() if next_after_owner else None,
            sram_after_sha256=hashlib.sha256(after).hexdigest()))
        if error or owner_error:raise ValueError('Original event/owner execution failed: '+name)
        if consumed!=(name in ['status-then-public-point','completion-without-status']):
            raise ValueError('Different original coordinate consumption: '+name)
        owners=[(m['owner'],m['event']) for m in owner_messages]
        if owners!=([(1,0x41),(6,0x34)] if name in ['status-then-public-point','completion-error','completion-without-status'] else []):
            raise ValueError('Different original WSF message routing: '+name)
        expected=bytes.fromhex('01172020') if name in ['status-then-public-point','completion-error'] else None
        if (next_after_owner[:4] if next_after_owner else None)!=expected:
            raise ValueError('Different next original HCI command: '+name)
    return dict(case=case,raw_sha256=sha(folder/'main.bin'),sram_sha256=sha(folder/'exports/sram-full.bin'),
        source_audit_sha256=sha(audit_path),contract=dict(dispatcher=dispatcher,crypto_callback=crypto,
            pending_queue=pending_queue,original_queue_pop=pop,request=request,request_state=state,
            public_key_consumer=consumer,message_send=send,message_queue=message_queue,
            owner_registry=registry,pending_pop_execution=pending_pop),samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve private evidence outside Git')
    prime=0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff
    coefficient=int('5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b',16)
    if (GY*GY-GX*GX*GX+3*GX-coefficient)%prime:
        raise ValueError('Public test point is not on the P-256 curve')
    a.output.mkdir()
    rows=[inspect(a.simulator,c,a.output) for c in ['stock24','stock23','cfw']]
    (a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,software_scenarios=24,
        engine='Original ARM on Unicorn M7, synthetic calls/stack/registers, validated full native SRAM',
        native_executions=0,hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    for row in rows:
        print(row['case'],[(r['scenario'],r['request_big_endian_coordinates_match'],r['next_after_owner_header'],r['owner_error']['type'] if r['owner_error'] else None) for r in row['samples']])


if __name__=='__main__':main()
