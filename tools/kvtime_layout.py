"""Identify the original kvTime producer and database wrapper by instructions."""
import struct
from inspect_ambiq_target import decode


def literal(raw, instruction):
    address=((instruction.address+4)&~3)+instruction.operands[1].mem.disp
    return struct.unpack_from('<I',raw,address-0x438000)[0]


def discover(raw, profile):
    signature=bytes.fromhex('217260600320207000220a212000')
    hits=[0x438000+off-4 for off in range(4,len(raw)-len(signature),2)
          if raw[off:off+len(signature)]==signature and raw[off-4:off-2]==bytes.fromhex('1fb5')]
    if len(hits)!=1:raise ValueError('Ambiguous kvTime producer')
    entry=hits[0];body=decode(raw,entry,0xb0)
    if body[1].mnemonic!='ldr' or not body[1].op_str.startswith('r4, [pc,'):
        raise ValueError('Unknown record base load')
    record=literal(raw,body[1]);end=next(i.address for i in body if i.mnemonic=='pop')
    tail=decode(raw,end-12,12)
    if [(i.mnemonic,i.op_str) for i in tail[:2]]!=[('movs','r2, #0xc'),('movs','r1, r4')]:
        raise ValueError('Unknown record store size')
    key=literal(raw,tail[2]);store=tail[3].operands[0].imm
    if raw[key-0x438000:key-0x438000+7]!=b'kvTime\0':raise ValueError('Wrong record key')
    wrapper=decode(raw,store,0x12);calls=[i for i in wrapper if i.mnemonic=='bl']
    if len(calls)!=1:raise ValueError('Unknown database wrapper')
    setter=calls[0].operands[0].imm;core=decode(raw,setter,0x34)
    loads=[i for i in core if i.mnemonic.startswith('ldr') and i.op_str.startswith('r3, [pc,')]
    if len(loads)!=1 or not any(i.mnemonic=='movw' and i.op_str=='r0, #0x8ac' for i in core):
        raise ValueError('Unknown database table stride/base')
    database=literal(raw,loads[0])
    if not all(0x20000000<=x<0x20380000 for x in [record,database,profile['service']['state']]):
        raise ValueError('Storage layout outside SRAM')
    return dict(record=record,database=database,state=profile['service']['state'],
                producer=entry,key=key,store=store,setter=setter,database_stride=0x8ac)
