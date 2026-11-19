"""Trace pinned font-head publication/UI setter references; plan paused state capture."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone.arm import ARM_OP_MEM, ARM_REG_PC
from inspect_ambiq_target import decode, BASE
from pinned_main import load_pinned_main
from native_replay import IMAGE


def sha(data):return hashlib.sha256(data).hexdigest()


def contract(raw,meta):
    def literal(i):
        assert i.mnemonic.startswith('ldr') and i.operands[1].type==ARM_OP_MEM and i.operands[1].mem.base==ARM_REG_PC
        return struct.unpack_from('<I',raw,((i.address+4)&~3)+i.operands[1].mem.disp-BASE)[0]
    body=decode(raw,int(meta['parent_call'],0),0x80);chains=[]
    for j,i in enumerate(body):
        if i.mnemonic=='bl' and i.operands[0].imm==int(meta['chain_builder'],0):
            assert body[j-2].op_str=='r1, #4' and body[j+1].op_str=='r0, [r4]' and body[j+6].mnemonic=='bl' and body[j+8].op_str=='r0, [r1]'
            chains.append(dict(owner_slot=literal(body[j-3]),config=literal(body[j-1]),head_slot=literal(body[j+7]),getter=body[j+6].operands[0].imm))
    assert len(chains)==2 and [hex(c['config']) for c in chains]==meta['chain_configs']
    setter_signature=bytes.fromhex('80b513000a005a21')
    assert raw.count(setter_signature)==1
    setter=BASE+raw.index(setter_signature);setter_body=decode(raw,setter,14)
    assert setter_body[4].mnemonic=='bl' and setter_body[-1].mnemonic=='pop'
    sites=[];pools={}
    for c in chains:
        pattern=struct.pack('<I',c['head_slot']);positions=[];start=0
        while True:
            o=raw.find(pattern,start)
            if o<0:break
            if o%4==0:positions.append(BASE+o)
            start=o+1
        pools[str(c['head_slot'])]=positions
        for pool in positions:
            for address in range(max(BASE,pool-0xffc),pool,2):
                first=decode(raw,address,4)
                if not first:continue
                i=first[0]
                if not i.mnemonic.startswith('ldr') or i.op_str.split(',')[0]!='r0' or len(i.operands)<2 or i.operands[1].type!=ARM_OP_MEM or i.operands[1].mem.base!=ARM_REG_PC:continue
                if ((address+4)&~3)+i.operands[1].mem.disp!=pool:continue
                block=decode(raw,address,16)
                if len(block)>=4 and block[1].mnemonic=='ldr' and block[1].op_str=='r1, [r0]' and block[3].mnemonic=='bl' and block[3].operands[0].imm==setter:
                    sites.append(dict(pc=address,head_slot=c['head_slot'],instructions=[dict(pc=q.address,text=q.mnemonic+' '+q.op_str,bytes=q.bytes.hex()) for q in block[:4]]))
    assert sites and len({s['head_slot'] for s in sites})==2
    getter=chains[0]['getter'];resolver=getter+0x50
    resolver_prefix=decode(raw,resolver,6)
    assert len(resolver_prefix)==3 and resolver_prefix[0].mnemonic=='push' and [(i.mnemonic,i.op_str) for i in resolver_prefix[1:]]==[('movs','r4, r0'),('cmp','r4, #0')]
    getter_tail=decode(raw,getter+0x4c,4)
    assert [(i.mnemonic,i.op_str) for i in getter_tail]==[('ldr','r0, [r0]'),('pop','{r1, r2, r3, pc}')]
    return dict(chains=chains,getter=getter,resolver=resolver,style_setter=setter,style_target=setter_body[4].operands[0].imm,
        property_id=90,head_literal_pools=pools,ui_setter_candidates=sites,scope='Static local source candidates, not screen reachability or main draw execution')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    out=a.output.resolve()
    if any((v/'.git').exists() for v in [out,*out.parents]):raise ValueError('Private output required')
    out.mkdir(mode=0o700);r=json.loads((a.simulator/'xip-font-contract-03/report.json').read_text())
    result=[];objects=set();slots=set();configs=set();owner_slots=set()
    for meta,filename in zip(r['cases'],['stock-2.4.0.24.bin','stock-2.3.0.24.bin','faceclaw-38-research-only.bin']):
        _,raw=load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes());assert sha(raw)==meta['raw_sha256']
        c=contract(raw,meta);result.append(dict(case=meta['case'],raw_sha256=sha(raw),contract=c))
        for chain in c['chains']:
            slots.update([chain['owner_slot'],chain['head_slot']]);owner_slots.add(chain['owner_slot']);configs.add(chain['config'])
        old=json.loads((a.simulator/'builtin-font-memory-main-01'/meta['case']/'report.json').read_text())
        objects.update(int(v,0) for v in old['fonts'])
    plan=dict(schema=2,id='ui-font-state-v1',image_id=IMAGE,source_root='em9305-reset-main-01',cases={'stock24':'stock_current','stock23':'stock_base','cfw':'cfw'},components=[],runtime_edits=[],board_edits=[],board_append='',semantics={})
    read='int(m.SystemBus.ReadDoubleWord(a))'
    # The validated main board has low SRAM plus system SRAM up to 0x20380000.
    # Its heap owner records are not restricted to the low 512 KiB snapshot.
    plan['diagnostics']='dict(paused=bool(m.IsPaused),fonts={str(a):[int(m.SystemBus.ReadDoubleWord(a+4*i)) for i in range(9)] for a in '+repr(sorted(objects))+'},slots={str(a):'+read+' for a in '+repr(sorted(slots))+'},configs={str(a):[int(m.SystemBus.ReadDoubleWord(a+4*i)) for i in range(12)] for a in '+repr(sorted(configs))+'},owners={str(a):([int(m.SystemBus.ReadDoubleWord('+read+'+4*i)) for i in range(3)] if 0x20000000<='+read+'<0x2037fff4 else None) for a in '+repr(sorted(owner_slots))+'})'
    for case in plan['cases']:
        old=json.loads((a.simulator/'em9305-reset-main-01'/case/'plan.json').read_text())
        spec=dict(boundary=old['semantics'][case]['candidate']['boundary'],comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','paused'],eq=True)],allowed_differences=['Read-only diagnostic fields after original pause only'],unresolved_differences=['Original main still stops at unsupported SPI DCX configuration; invalid-magic font-bank diagnostic scenario, not normal UI boot'])
        plan['semantics'][case]=dict(candidate=spec,control=spec)
    (out/'report.json').write_text(json.dumps(dict(passed=True,cases=result,source_sha256=sha(Path(__file__).read_bytes())),indent=2)+'\n')
    (out/'candidate.json').write_text(json.dumps(plan,indent=2)+'\n')
    (out/'inspector.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(passed=True,cases=3,ui_candidates={c['case']:len(c['contract']['ui_setter_candidates']) for c in result})))


if __name__=='__main__':main()
