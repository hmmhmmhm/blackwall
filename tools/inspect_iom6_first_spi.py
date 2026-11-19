"""Decode actual original-main first SPI request and replay its original CMD builder."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import cpu, WORK, STOP, SRAM, BASE


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior analysis')
    svd=a.simulator/'apollo-dfp-research-01/apollo510.svd';tree=ET.parse(svd)
    iom=next(p for p in tree.findall('.//peripheral') if p.findtext('name')=='IOM0')
    registers={r.findtext('name'):r for r in iom.findall('.//register')}
    fields={f.findtext('name'):f.findtext('bitRange') for f in registers['CMD'].findall('./fields/field')}
    if fields!={'OFFSETLO':'[31:24]','CMDSEL':'[21:20]','TSIZE':'[19:8]','CONT':'[7:7]','OFFSETCNT':'[6:4]','CMD':'[3:0]'}:raise ValueError('Changed CMD layout')
    fulldup=next(f for f in registers['MSPICFG'].findall('./fields/field') if f.findtext('name')=='FULLDUP')
    if fulldup.findtext('bitRange')!='[2:2]':raise ValueError('Changed FULLDUP field')
    rows=[]
    for case in ['stock24','stock23','cfw']:
        source=a.simulator/'iom6-full-duplex-main-01'/case;r=json.loads((source/'report.json').read_text());raw=(source/'main.bin').read_bytes()
        if not r['passed'] or not r['execution_passed'] or not r['semantic_validation']['passed']:raise ValueError('Unverified original main request')
        # The saved runner audit separately checks all input pins and native logs.
        original=a.simulator/'iom6-dcx-no-pins-main-01'/case
        if sha(source/'main.bin')!=sha(original/'main.bin'):raise ValueError('Original main altered')
        regs=r['observed']['register_context'];stack=r['observed']['stack_context'];sp=regs['r13']
        if sp!=stack['base']:raise ValueError('Stack base differs')
        stack_data=struct.pack('<'+'I'*len(stack['words']),*stack['words'])
        def stack_bytes(address,length):
            offset=address-sp
            if offset<0 or offset+length>len(stack_data):raise ValueError('Data outside captured original stack')
            return stack_data[offset:offset+length]
        command=regs['r2'];pc=regs['r15'];ins=decode(raw,pc,4)
        if len(ins)!=1 or (ins[0].mnemonic,ins[0].op_str)!=('str.w','r2, [r0, #0x120]') or regs['r0']!=0x40056000:raise ValueError('Not original IOM6 CMD store')
        diag=r['diagnostics']
        if (diag['commands'],diag['spi_config'],diag['dcx'])!=(0,4,16):raise ValueError('Preflight affected transfer state')
        decoded=dict(command=command&15,ce=(command>>20)&3,size=(command>>8)&0xfff,cont=(command>>7)&1,offset_count=(command>>4)&7,offset_low=command>>24)
        if decoded!=dict(command=1,ce=0,size=2,cont=0,offset_count=0,offset_low=0):raise ValueError('Different first SPI request')
        payload=stack_bytes(regs['r4'],decoded['size']);rx_before=stack_bytes(regs['r5'],4)
        if payload!=b'\x81\0' or rx_before!=b'\0'*4:raise ValueError('Unexpected captured header or RX initial state')
        # The producer's builder is a real BL 0x32 bytes before the CMD store.
        call=decode(raw,pc-0x32,4)
        if len(call)!=1 or call[0].mnemonic!='bl':raise ValueError('Missing original command builder')
        builder=call[0].operands[0].imm
        source_body=decode(raw,builder,0x46)
        if (source_body[0].mnemonic,source_body[0].op_str)!=('push','{r4, r5}') or source_body[-1].mnemonic!='bx':raise ValueError('Unknown builder boundary')
        # Args are derived from the unmodified caller stack and original load sequence.
        stack_args=stack_bytes(sp+0x20,8)+stack_bytes(sp+0x1c,4)+stack_bytes(sp+0xc,4)
        u=cpu(raw,b'\0'*0x80000,WORK+0xff00)
        u.mem_write(WORK+0xff00,stack_args)
        ce=struct.unpack('<I',stack_bytes(regs['r9'],4))[0]
        cont=regs['r10']
        if ce!=0 or cont!=0:raise ValueError('Unsupported current caller CE/CONT state')
        for n,v in enumerate([ce,struct.unpack('<I',stack_bytes(sp+0x18,4))[0],cont,0]):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),v)
        u.emu_start(builder|1,STOP,count=1000)
        if u.reg_read(arm.UC_ARM_REG_PC)!=STOP or u.reg_read(arm.UC_ARM_REG_R0)!=command:raise ValueError('Original builder differs from captured command')
        rows.append(dict(case=case,source_report_sha256=sha(source/'report.json'),raw_sha256=sha(source/'main.bin'),pc=pc,sp=sp,tx_pointer=regs['r4'],rx_pointer=regs['r5'],
                         tx_storage_word=stack_bytes(regs['r4'],4).hex(),wire_candidate=payload.hex(),rx_before=rx_before.hex(),decoded=decoded,
                         builder=builder,builder_return=u.reg_read(arm.UC_ARM_REG_R0),builder_stack_args=stack_args.hex(),caller_direction=struct.unpack('<I',stack_bytes(sp+0x18,4))[0],
                         actual_transfer_executed=False,actual_response_observed=False))
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'svd-extract.xml').write_text('\n'.join(ET.tostring(registers[n],encoding='unicode') for n in ['CMD','MSPICFG','FIFOPTR','OFFSETHI']))
    result=dict(passed=True,cases=rows,svd_sha256=sha(svd),full_duplex_description=fulldup.findtext('description'),
                replay='isolated original CMD builder on M7; no MMIO, branches or returns replaced',whole_main_replayed=False,hardware_accessed=False,
                upper_two_storage_bytes_are_padding=True,peer_response_not_modelled=True)
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),request='CMD=0x201, MOSI candidate=81 00',spi_transfers=0)))


if __name__=='__main__':main()
