"""Original public-address constructor/setter and hypothetical completion pipeline."""
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


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def call(u,entry,args,ends=()):
    for n,value in enumerate(args):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),value)
    u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
    return run(u,entry,list(ends))


def inspect(simulator,case):
    capture=simulator/('application-hci-reset-main-02' if case=='stock24' else 'application-hci-reset-main-01')/case
    audit_path=simulator/('application-hci-reset-saved-audit-02' if case=='stock24' else 'application-hci-reset-saved-audit-01')/case/'report.json'
    audit=json.loads(audit_path.read_text());report=json.loads((capture/'report.json').read_text())
    if not audit['passed'] or not report['passed'] or report['hardware_accessed']:raise ValueError('Unverified native source')
    for name,digest in audit['capture_hashes'].items():
        if sha(capture/name)!=digest:raise ValueError('Changed native source '+name)
    raw=(capture/'main.bin').read_bytes();ram=(capture/'exports/sram-full.bin').read_bytes()
    needle=bytes.fromhex('4ff64340');hits=[0x438000+x for x in range(0,len(raw)-3,2) if raw[x:x+4]==needle]
    if len(hits)!=1:raise ValueError('Ambiguous public-address opcode constructor')
    opcode_pc=hits[0];ctor=opcode_pc-6;setter=ctor-0x36
    slot=literal(raw,decode(raw,ctor+2,4)[0]);b=decode(raw,ctor,16)
    if not 0x20000000<=slot<=0x20380000-6:raise ValueError('Address global outside captured SRAM')
    if [(i.mnemonic,i.op_str) for i in b[:4]]!=[('push','{r7, lr}'),('ldr',b[1].op_str),('movs','r1, #6'),('movw','r0, #0xfc43')]:raise ValueError('Unknown constructor shape')
    if b[1].op_str.split(',')[0]!='r2' or b[4].mnemonic!='bl':raise ValueError('Unknown constructor arguments')
    regs=report['observed']['register_context'];pointer=regs['r10'];packet=ram[pointer-0x20000000:pointer-0x20000000+10]
    address=ram[slot-0x20000000:slot-0x20000000+6]
    if len(address)!=6 or packet!=bytes.fromhex('0143fc06')+address:raise ValueError('Native queued address does not match original global')
    previous_path=simulator/'application-hci-transaction-source-02/report.json'
    previous_pin=json.loads((simulator/'application-hci-reset-verification-01/manifest.json').read_text())['retained_source_sha256']
    if sha(previous_path)!=previous_pin:raise ValueError('Changed preceding original software analysis')
    previous=json.loads(previous_path.read_text())
    context=next(row for row in previous['cases'] if row['case']==case)
    ring_path=simulator/'application-hci-source-01/report.json'
    ring_pin=json.loads((simulator/'application-hci-idle-verification-01/manifest.json').read_text())['source_report_sha256']
    if sha(ring_path)!=ring_pin:raise ValueError('Changed preceding original ring analysis')
    ring=next(row for row in json.loads(ring_path.read_text())['cases'] if row['case']==case)['tx_ring']
    rows=[]
    for name,value in [('native',address),('ascending',bytes(range(1,7))),('descending',bytes(range(6,0,-1)))]:
        data=bytearray(ram);data[slot-0x20000000:slot-0x20000000+6]=value
        u=cpu(raw,bytes(data),WORK+0xf000);t=call(u,ctor,(),[ctor+10]);args=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(3)]
        if args!=[0xfc43,6,slot] or bytes(u.mem_read(slot,6))!=value:raise ValueError('Original constructor did not preserve address order')
        rows.append(dict(kind='constructor',profile=name,arguments=args,data_sha256=hashlib.sha256(value).hexdigest(),execution=t))
    for name,value in [('null',None),('all-zero',bytes(6)),('nonzero',bytes(range(1,7)))]:
        u=cpu(raw,ram,WORK+0xf000)
        if value is not None:u.mem_write(WORK+0x100,value)
        t=call(u,setter,(0 if value is None else WORK+0x100,))
        expected=int(value is not None and any(value))
        if t['stop']!=STOP or u.reg_read(arm.UC_ARM_REG_R0)!=expected or bytes(u.mem_read(slot,6))!=(value if expected else address):raise ValueError('Original address setter differs')
        rows.append(dict(kind='RAM-setter',profile=name,accepted=bool(expected),execution=t,persistent_write_executed=False))
    for event in [None,'040e040143fc00','040e040143fc01','040e040144fc00']:
        u=cpu(raw,ram,WORK+0xf000);traces=[call(u,context['ring_pop'],(ring,0,1))]
        if event:
            u.mem_write(WORK+0x100,bytes.fromhex(event));traces.append(call(u,context['application_parser'],(WORK+0x100,7)))
        traces.append(call(u,context['upper_handler'],(1,0)))
        fields=list(struct.unpack('<6I',bytes(u.mem_read(ring,24))));next_packet=None
        if event:
            if fields[:5]!=[780,520,260,2080,260]:raise ValueError('Different next queue state')
            ptr=fields[5]+fields[1];length=struct.unpack('<I',bytes(u.mem_read(ptr,4)))[0];next_packet=bytes(u.mem_read(ptr+4,length))
            if length!=12 or next_packet[:4]!=bytes.fromhex('01f2ff08'):raise ValueError('Different follow-up command')
        elif fields[:5]!=[520,520,0,2080,260]:raise ValueError('No-event control queued a command')
        rows.append(dict(kind='hypothetical-completion',event=event,next_packet=next_packet.hex() if next_packet else None,ring_words=fields,executions=traces,controller_behavior_verified=False))
    # A second explicitly hypothetical completion exposes the next dependency;
    # this is host software exploration, not evidence of either controller command.
    u=cpu(raw,ram,WORK+0xf000);traces=[]
    for opcode in [0xfc43,0xfff2]:
        traces.append(call(u,context['ring_pop'],(ring,0,1)))
        u.mem_write(WORK+0x100,bytes([4,14,4,1,opcode&255,opcode>>8,0]))
        traces.append(call(u,context['application_parser'],(WORK+0x100,7)));traces.append(call(u,context['upper_handler'],(1,0)))
    fields=list(struct.unpack('<6I',bytes(u.mem_read(ring,24))));ptr=fields[5]+fields[1];length=struct.unpack('<I',bytes(u.mem_read(ptr,4)))[0];next_packet=bytes(u.mem_read(ptr+4,length))
    if fields[:5]!=[1040,780,260,2080,260] or length!=5 or next_packet[:4]!=bytes.fromhex('01c4fc01'):raise ValueError('Different second hypothetical follow-up')
    rows.append(dict(kind='two-hypothetical-completions',next_packet=next_packet.hex(),executions=traces,controller_behavior_verified=False))
    return dict(case=case,raw_sha256=sha(capture/'main.bin'),sram_sha256=sha(capture/'exports/sram-full.bin'),audit_sha256=sha(audit_path),constructor=ctor,RAM_setter=setter,address_slot=slot,address_sha256=hashlib.sha256(address).hexdigest(),queued_packet_sha256=hashlib.sha256(packet).hexdigest(),generic_command_call=b[4].operands[0].imm,samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];count=sum(len(row['samples']) for row in rows)
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_scenarios=count,engine='Unicorn M7 original ARM; synthetic calls/registers/stack; validated full native SRAM; no function stubs',native_main_rerun=False,peripheral_model_changed=False,controller_fc43_or_fff2_executed=False,controller_persistence_or_reset_known=False,hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('vendor address source:',count,'original ARM scenarios passed; controller side effects unknown')


if __name__=='__main__':main()
