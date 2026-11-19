"""Original ARM HCI AES completions with exact host-calculated controller results."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import unicorn.arm_const as arm
from unicorn import UC_HOOK_MEM_INVALID
from inspect_application_vendor_address import call, sha
from inspect_nema_blocking_wait import cpu, WORK
from inspect_privacy_length_contract import queued
from bt_crypto_vectors import hci_encrypt, cmac_blocks_be
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal


def inspect(s, case, output):
    folder=s/'p256-peer-main-01'/case;audit_path=s/'p256-peer-saved-audit-01'/case/'report.json'
    audit=json.loads(audit_path.read_text())
    if not audit['passed'] or audit['hardware_accessed']:raise ValueError('Unverified native source')
    for name,digest in audit['capture_hashes'].items():
        if sha(folder/name)!=digest:raise ValueError('Changed native capture: '+name)
    raw=(folder/'main.bin').read_bytes();ram=(folder/'exports/sram-full.bin').read_bytes()
    source=s/'p256-event-source-06/report.json'
    pin=json.loads((s/'p256-event-verification-01/manifest.json').read_text())['source_sha256']
    if sha(source)!=pin:raise ValueError('Changed original WSF contract')
    contract=next(c for c in json.loads(source.read_text())['cases'] if c['case']==case)['contract']
    source=s/'application-hci-transaction-source-02/report.json'
    pin=json.loads((s/'application-hci-reset-verification-01/manifest.json').read_text())['retained_source_sha256']
    if sha(source)!=pin:raise ValueError('Changed parser/ring callbacks')
    ctx=next(c for c in json.loads(source.read_text())['cases'] if c['case']==case)
    ring=0x20076304 if case=='stock24' else 0x20076cbc
    registry=contract['owner_registry'];pop=contract['original_queue_pop'];send=contract['message_send'];q=contract['message_queue']
    word=lambda address:struct.unpack_from('<I',ram,address-0x20000000)[0]
    instructions=decode(raw,contract['crypto_callback'],0x120)
    branch=next(instructions[n+1] for n,i in enumerate(instructions[:-1]) if i.mnemonic=='cmp' and i.op_str=='r0, #0x1b')
    block=decode(raw,branch.operands[0].imm,16)
    aes_queue=literal(raw,next(i for i in block if i.mnemonic.startswith('ldr') and '[pc,' in i.op_str))
    probe=cpu(raw,ram,WORK+0xf000);pending_pop=call(probe,pop,(aes_queue,WORK+0x200))
    request=probe.reg_read(arm.UC_ARM_REG_R0)
    if ram[request-0x20000000+0x34]!=1:raise ValueError('Different original CMAC request state')
    descriptor=word(request+0x30);pointer=word(descriptor)
    consumed,length=struct.unpack_from('<2h',ram,descriptor-0x20000000+0x24)
    if consumed!=0 or not 0<length<=4096 or not 0x20000000<=pointer<=0x20380000-length:
        raise ValueError('CMAC descriptor outside bounded native source')
    cmac_message=ram[pointer-0x20000000:pointer-0x20000000+length]
    initial=queued(cpu(raw,ram,WORK+0xf000),ring)[0]
    key=initial[4:20][::-1];reference=cmac_blocks_be(key,cmac_message)
    rows=[]
    for scenario in ['exact-chain','no-event','error-status','wrong-opcode','wire-truncated','zero-return']:
        u=cpu(raw,ram,WORK+0xf000);stages=[];error=None;faults=[]
        def invalid(c,operation,address,size,value,user):
            faults.append(dict(operation=operation,address=address,size=size,pc=c.reg_read(arm.UC_ARM_REG_PC),
                registers=[c.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(13)]))
            return False
        u.hook_add(UC_HOOK_MEM_INVALID,invalid)
        for stage in range(64 if scenario=='exact-chain' else 1):
            packet,fields=queued(u,ring)
            if packet is None or packet[:4]!=bytes.fromhex('01172020'):break
            encrypted=hci_encrypt(packet[4:20],packet[20:36])
            if scenario=='exact-chain' and (stage>=len(reference) or packet[4:20][::-1]!=key or
                    packet[20:36][::-1]!=reference[stage][0] or encrypted[::-1]!=reference[stage][1]):
                raise ValueError('Original AES sequence differs from independent CMAC reference')
            reply=bytes.fromhex('040e1401172000')+encrypted
            if scenario=='error-status':reply=reply[:6]+bytes([1])+reply[7:]
            if scenario=='wrong-opcode':reply=reply[:4]+bytes.fromhex('1620')+reply[6:]
            if scenario=='wire-truncated':reply=reply[:-1]
            if scenario=='zero-return':reply=reply[:7]+bytes(16)
            executions=[];owners=[]
            try:
                executions.append(call(u,ctx['ring_pop'],(ring,0,1)))
                if scenario!='no-event':
                    u.mem_write(WORK+0x100,reply)
                    executions.append(call(u,ctx['application_parser'],(WORK+0x100,len(reply))))
                executions.append(call(u,ctx['upper_handler'],(1,0)))
                for _ in range(16):
                    executions.append(call(u,pop,(q,WORK+0x200)))
                    message=u.reg_read(arm.UC_ARM_REG_R0)
                    if not message:break
                    owner=bytes(u.mem_read(WORK+0x200,1))[0]
                    if owner>=10:raise ValueError('Unrecognized WSF message owner')
                    handler=struct.unpack('<I',bytes(u.mem_read(registry+owner*4,4)))[0]&~1
                    owners.append(dict(owner=owner,event=bytes(u.mem_read(message+2,1))[0],handler=handler,pointer=message))
                    executions.append(call(u,handler,(0,message)))
                    executions.append(call(u,send-0xa,(message,)))
                else:raise ValueError('Original WSF owner queue exceeded the bounded drain')
                successor,after=queued(u,ring)
            except Exception as exc:
                error=dict(type=type(exc).__name__,message=str(exc)[:150],pc=u.reg_read(arm.UC_ARM_REG_PC))
                successor=None;after=list(struct.unpack('<6I',bytes(u.mem_read(ring,24))))
            stages.append(dict(command_sha256=hashlib.sha256(packet).hexdigest(),reply_sha256=hashlib.sha256(reply).hexdigest(),
                encrypted_sha256=hashlib.sha256(encrypted).hexdigest(),command=packet.hex(),reply=reply.hex(),
                executions=executions,owners=owners,next_header=successor[:4].hex() if successor else None,
                next_length=len(successor) if successor else 0,
                next_sha256=hashlib.sha256(successor).hexdigest() if successor else None,ring_words=after,error=error))
            if error or successor is None or successor[:4]!=bytes.fromhex('01172020'):break
        after=bytes(u.mem_read(0x20000000,len(ram)))
        (output/(case+'-'+scenario+'-sram.bin')).write_bytes(after)
        (output/(case+'-'+scenario+'-work.bin')).write_bytes(bytes(u.mem_read(WORK,0x10000)))
        rows.append(dict(scenario=scenario,stages=stages,error=error,invalid_memory=faults,sram_after_sha256=hashlib.sha256(after).hexdigest()))
        if scenario=='exact-chain':
            if len(stages)!=len(reference) or len(reference)!=32 or length!=494 or not error or len(faults)!=1:
                raise ValueError('Different bounded CMAC completion/frontier')
            if faults[0]['address']!=0x4003a018 or faults[0]['size']!=4 or faults[0]['pc']!=(0x5ae038 if case=='stock24' else 0x5ad92c):
                raise ValueError('Different original UART1 read frontier')
            if [(m['owner'],m['event']) for m in stages[-1]['owners']]!=[(3,0x24)]:
                raise ValueError('Different original CMAC completion owner')
        elif error or faults:raise ValueError('Unexpected negative-control execution failure')
        elif stages[-1]['next_header']!=('01172020' if scenario in ['error-status','zero-return'] else None):
            raise ValueError('Different negative-control successor')
    return dict(case=case,main_sha256=sha(folder/'main.bin'),sram_sha256=sha(folder/'exports/sram-full.bin'),
        source_audit_sha256=sha(audit_path),cmac_contract=dict(pending_queue=aes_queue,request=request,
            descriptor=descriptor,message_pointer=pointer,message_length=length,message_sha256=hashlib.sha256(cmac_message).hexdigest(),
            reference_aes_blocks=len(reference),reference_tag_sha256=hashlib.sha256(reference[-1][1]).hexdigest(),
            pending_pop_execution=pending_pop),samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Preserve firmware-derived evidence outside Git')
    a.output.mkdir();rows=[inspect(a.simulator,c,a.output) for c in ['stock24','stock23','cfw']]
    (a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,software_scenarios=18,
        host_crypto='macOS CommonCrypto AES-128 ECB, HCI byte order',
        engine='Original Apollo ARM on Unicorn M7; synthetic calls/stack/registers and validated native SRAM',
        native_executions=0,hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    for row in rows:
        print(row['case'],[(r['scenario'],len(r['stages']),r['stages'][-1]['next_header'],r['error']) for r in row['samples']])


if __name__=='__main__':main()
