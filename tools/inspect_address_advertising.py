"""Original ARM random-address and bounded advertising initialization contracts."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
import unicorn.arm_const as arm
from unicorn import UC_HOOK_MEM_INVALID
from inspect_application_vendor_address import call, sha
from inspect_nema_blocking_wait import cpu, WORK
from inspect_privacy_length_contract import queued
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal

WRITE_LENGTHS={0x2005:6,0x2006:15,0x2008:32,0x2009:32,0x200a:1}


def inspect(s,case,out):
    f=s/'aes-peer-main-01'/case;audit_path=s/'aes-peer-saved-audit-01'/case/'report.json'
    audit=json.loads(audit_path.read_text())
    if not audit['passed'] or audit['hardware_accessed']:raise ValueError('Unverified native source')
    for n,h in audit['capture_hashes'].items():
        if sha(f/n)!=h:raise ValueError('Changed native capture: '+n)
    raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes()
    p=s/'p256-event-source-06/report.json';pin=json.loads((s/'p256-event-verification-01/manifest.json').read_text())['source_sha256']
    if sha(p)!=pin:raise ValueError('Changed WSF contract')
    contract=next(c for c in json.loads(p.read_text())['cases'] if c['case']==case)['contract']
    p=s/'application-hci-transaction-source-02/report.json';pin=json.loads((s/'application-hci-reset-verification-01/manifest.json').read_text())['retained_source_sha256']
    if sha(p)!=pin:raise ValueError('Changed original parser/ring callbacks')
    ctx=next(c for c in json.loads(p.read_text())['cases'] if c['case']==case)
    ring=0x20076304 if case=='stock24' else 0x20076cbc
    initial=queued(cpu(raw,ram,WORK+0xf000),ring)[0]
    if initial[:4]!=bytes.fromhex('01052006'):raise ValueError('Different initial address request')
    address=initial[4:];vendor=bytes.fromhex(re.search(r'vendorStartupHex: "([0-9a-f]+)"',(f/'board.repl').read_text()).group(1))[4:10]
    needle=bytes.fromhex('42f20500');sites=[0x438000+n for n in range(0,len(raw)-3,2) if raw[n:n+4]==needle]
    if len(sites)!=1:raise ValueError('Ambiguous original Set Random Address constructor')
    constructor=sites[0]-6
    if decode(raw,constructor,2)[0].mnemonic!='push':raise ValueError('Changed original constructor')
    constructor_samples=[]
    for value in [address,bytes(range(1,7)),bytes(range(6,0,-1))]:
        u=cpu(raw,ram,WORK+0xf000);phases=[call(u,ctx['ring_pop'],(ring,0,1))]
        u.mem_write(WORK+0x500,value)
        if decode(raw,constructor+0x1a,4)[0].mnemonic!='bl':raise ValueError('Changed address copy call')
        phases.append(call(u,constructor,(WORK+0x500,),[constructor+0x1e]))
        allocation=u.reg_read(arm.UC_ARM_REG_R5)
        if bytes(u.mem_read(allocation,9))!=bytes.fromhex('052006')+value:
            raise ValueError('Original constructor changed address byte order')
        constructor_samples.append(dict(input_sha256=hashlib.sha256(value).hexdigest(),executions=phases))
    complete_candidates=[]
    for i in decode(raw,contract['dispatcher'],0xc0):
        if i.mnemonic=='bl' and any(x.mnemonic.startswith('ldrb') and x.op_str=='r8, [r0]' for x in decode(raw,i.operands[0].imm,0x30)):
            complete_candidates.append(i.operands[0].imm)
    if len(complete_candidates)!=1:raise ValueError('Ambiguous original Command Complete consumer')
    helpers=[]
    for i in decode(raw,complete_candidates[0],0x204):
        if i.mnemonic!='bl':continue
        body=decode(raw,i.operands[0].imm,0x20)
        stores=[x for x in body if x.mnemonic.startswith('strb') and x.op_str in ['r0, [r4, #0x22]','r0, [r4, #0x1a]']]
        if stores:helpers.append((i.operands[0].imm,body,stores[0]))
    if len(helpers)!=1:raise ValueError('Ambiguous original command-ready helper')
    helper,body,store=helpers[0]
    if not any(i.address<store.address and i.mnemonic=='movs' and i.op_str=='r0, #1' for i in body):
        raise ValueError('Changed command-ready value')
    ready=literal(raw,next(i for i in body if i.mnemonic.startswith('ldr') and i.op_str.startswith('r4, [pc,')))+store.operands[1].mem.disp
    readiness=[]
    for credits in [0,1,7,255]:
        u=cpu(raw,ram,WORK+0xf000);execution=call(u,helper,(credits,),[store.address+store.size])
        value=bytes(u.mem_read(ready,1))[0]
        if value!=1:raise ValueError('Different original command-ready store')
        readiness.append(dict(input_credits=credits,stored_ready=value,execution=execution))
    rows=[]
    for scenario in ['write-chain','no-event','status-error','opcode-zero','unknown-opcode','zero-credit','credit-resume','wire-truncated']:
        u=cpu(raw,ram,WORK+0xf000);stages=[];faults=[];error=None
        def invalid(c,operation,address,size,value,user):
            faults.append(dict(operation=operation,address=address,size=size,pc=c.reg_read(arm.UC_ARM_REG_PC)))
            return False
        u.hook_add(UC_HOOK_MEM_INVALID,invalid)
        for step in range(12 if scenario=='write-chain' else 1):
            packet,fields=queued(u,ring)
            if not packet:break
            opcode=int.from_bytes(packet[1:3],'little')
            if opcode not in WRITE_LENGTHS:break
            if len(packet)!=4+WRITE_LENGTHS[opcode]:raise ValueError('Different original HCI write parameter length')
            reply=bytes([4,14,4,1,opcode&255,opcode>>8,1 if scenario=='status-error' else 0])
            if scenario=='opcode-zero':reply=bytes.fromhex('040e03010000')
            if scenario=='unknown-opcode':reply=reply[:4]+bytes.fromhex('fe7f')+reply[6:]
            if scenario in ['zero-credit','credit-resume']:reply=reply[:3]+bytes([0])+reply[4:]
            if scenario=='wire-truncated':reply=reply[:-1]
            events=[] if scenario=='no-event' else [reply]
            if scenario=='credit-resume':events.append(bytes.fromhex('040e03010000'))
            executions=[];owners=[];after_zero_credit=None
            try:
                executions.append(call(u,ctx['ring_pop'],(ring,0,1)))
                for event_index,event in enumerate(events):
                    u.mem_write(WORK+0x100,event);executions.append(call(u,ctx['application_parser'],(WORK+0x100,len(event))))
                    executions.append(call(u,ctx['upper_handler'],(1,0)))
                    if scenario=='credit-resume' and event_index==0:
                        pending,_=queued(u,ring);after_zero_credit=pending[:4].hex() if pending else None
                if not events:executions.append(call(u,ctx['upper_handler'],(1,0)))
                for _ in range(16):
                    executions.append(call(u,contract['original_queue_pop'],(contract['message_queue'],WORK+0x200)))
                    message=u.reg_read(arm.UC_ARM_REG_R0)
                    if not message:break
                    owner=bytes(u.mem_read(WORK+0x200,1))[0]
                    if owner>=10:raise ValueError('Unrecognized WSF owner')
                    handler=struct.unpack('<I',bytes(u.mem_read(contract['owner_registry']+owner*4,4)))[0]&~1
                    owners.append(dict(owner=owner,event=bytes(u.mem_read(message+2,1))[0],handler=handler))
                    executions.append(call(u,handler,(0,message)));executions.append(call(u,contract['message_send']-0xa,(message,)))
                else:raise ValueError('WSF drain exceeded bound')
                successor,after=queued(u,ring)
            except Exception as exc:
                error=dict(type=type(exc).__name__,message=str(exc)[:150],pc=u.reg_read(arm.UC_ARM_REG_PC));successor=None;after=None
            stages.append(dict(command=packet.hex(),reply_events=[e.hex() for e in events],executions=executions,owners=owners,
                next_header=successor[:4].hex() if successor else None,next_length=len(successor) if successor else 0,
                next_sha256=hashlib.sha256(successor).hexdigest() if successor else None,ring_words=after,
                after_zero_credit_header=after_zero_credit))
            if error or not successor or int.from_bytes(successor[1:3],'little') not in WRITE_LENGTHS:break
        after=bytes(u.mem_read(0x20000000,len(ram)));(out/(case+'-'+scenario+'-sram.bin')).write_bytes(after)
        rows.append(dict(scenario=scenario,stages=stages,error=error,invalid_memory=faults))
        if scenario=='write-chain':
            if [t['command'][:8] for t in stages]!=['01052006','0106200f','01082020','01092020','010a2001'] or not error:
                raise ValueError('Different original advertising initialization sequence')
            if len(faults)!=1 or faults[0]['address']!=0x4003a018:raise ValueError('Different advertising completion frontier')
        elif error or faults:raise ValueError('Unexpected control execution failure')
        elif stages[-1]['next_header']!=(None if scenario in ['no-event','wire-truncated'] else '0106200f'):
            raise ValueError('Different original response/control successor')
    return dict(case=case,main_sha256=sha(f/'main.bin'),sram_sha256=sha(f/'exports/sram-full.bin'),audit_sha256=sha(audit_path),
        address_sha256=hashlib.sha256(address).hexdigest(),address_top_two_bits=address[5]>>6,
        static_random_format_valid=(address[5]>>6)==3 and 0<(int.from_bytes(address,'little')&((1<<46)-1))<((1<<46)-1),
        address_equals_vendor_public=address==vendor,constructor=constructor,constructor_samples=constructor_samples,
        command_ready_helper=helper,command_ready_byte=ready,readiness_samples=readiness,samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Preserve private evidence outside Git')
    a.output.mkdir();rows=[inspect(a.simulator,c,a.output) for c in ['stock24','stock23','cfw']]
    (a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,software_scenarios=24,
        engine='Original ARM on Unicorn M7; synthetic calls/stack/registers; validated full native SRAM',native_executions=0,
        hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    for c in rows:print(c['case'],[(r['scenario'],[t['command'][:8] for t in r['stages']],r['stages'][-1]['next_header'],r['error']) for r in c['samples']])


if __name__=='__main__':main()
