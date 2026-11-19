"""Locate original draw-unit registration/evaluation and plan read-only main capture."""
import argparse,json,struct,hashlib
from pathlib import Path
from inspect_ambiq_target import decode,BASE
from font_wrapper_contract import direct_call_candidates
from pinned_main import load_pinned_main
from native_replay import IMAGE


def sha(data):return hashlib.sha256(data).hexdigest()


def inspect(raw):
    signature=bytes.fromhex('38b50c002079012817d00228');assert raw.count(signature)==1
    evaluate=BASE+raw.index(signature)
    registrations=[]
    for address in range(evaluate-0x200,evaluate,2):
        block=decode(raw,address,12)
        if len(block)<3 or block[0].mnemonic!='addw' or block[0].op_str.split(',')[0]!='r0':continue
        i=block[0]
        if ((address+4)&~3)+i.operands[2].imm==evaluate|1 and block[2].op_str=='r0, [r1, #0x10]':registrations.append(address)
    assert len(registrations)==1;adr=registrations[0]
    creator_call=decode(raw,adr-14,4)[0];assert creator_call.mnemonic=='bl';creator=creator_call.operands[0].imm
    creator_body=decode(raw,creator,0x56)
    index=next(j for j,i in enumerate(creator_body) if i.op_str=='r2, [r1, #0x13c]')
    load=creator_body[index-1];assert load.mnemonic=='ldr.w'
    literal=((load.address+4)&~3)+load.operands[1].mem.disp
    global_base=struct.unpack_from('<I',raw,literal-BASE)[0]
    unitload=decode(raw,adr-20,4)[0];assert unitload.op_str.startswith('r4, [pc, #')
    unit_slot=struct.unpack_from('<I',raw,((unitload.address+4)&~3)+unitload.operands[1].mem.disp-BASE)[0]
    dispatch_adr=decode(raw,adr-8,4)[0];assert dispatch_adr.mnemonic=='addw'
    dispatch=(((dispatch_adr.address+4)&~3)+dispatch_adr.operands[2].imm)&~1
    dispatch_body=decode(raw,dispatch,0x56)
    available=next(i.operands[0].imm for i in dispatch_body if i.mnemonic=='bl')
    available_body=decode(raw,available,0x1c)
    assert available_body[2].op_str=='r3, [r3, #0x140]' and available_body[3].op_str=='r3, #1'
    fast=next(i.operands[0].imm for i in available_body if i.mnemonic=='bl')
    return dict(evaluate=evaluate,dispatch=dispatch,creator=creator,creator_calls=direct_call_candidates(raw,creator),
        registration=adr,global_base=global_base,unit_slot=unit_slot,available=available,fast=fast,
        fast_body=[dict(pc=i.address,text=i.mnemonic+' '+i.op_str,bytes=i.bytes.hex()) for i in decode(raw,fast,18)],
        evaluate_body=[dict(pc=i.address,text=i.mnemonic+' '+i.op_str,bytes=i.bytes.hex()) for i in decode(raw,evaluate,0x15e)])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
    if any((v/'.git').exists() for v in [out,*out.parents]):raise ValueError('Private output required')
    out.mkdir(mode=0o700);cases=[]
    for case,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        _,raw=load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes());cases.append(dict(case=case,raw_sha256=sha(raw),contract=inspect(raw)))
    bases=sorted({c['contract']['global_base'] for c in cases});slots=sorted({c['contract']['unit_slot'] for c in cases})
    read='int(m.SystemBus.ReadDoubleWord(a+0x13c))'
    diagnostics='dict(paused=bool(m.IsPaused),slots={str(a):int(m.SystemBus.ReadDoubleWord(a)) for a in '+repr(slots)+'},roots={str(a):dict(head='+read+',count=int(m.SystemBus.ReadDoubleWord(a+0x140)),words=([int(m.SystemBus.ReadDoubleWord('+read+'+4*i)) for i in range(57)] if 0x20000000<='+read+'<=0x20380000-228 else None)) for a in '+repr(bases)+'})'
    plan=dict(schema=2,id='draw-unit-state-v1',image_id=IMAGE,source_root='em9305-reset-main-01',cases={'stock24':'stock_current','stock23':'stock_base','cfw':'cfw'},components=[],board_edits=[],board_append='',runtime_edits=[dict(before='    while not m.IsPaused and live_seconds<45:\n',after='    while not m.IsPaused and live_seconds<90:\n')],diagnostics=diagnostics,semantics={})
    for case in plan['cases']:
        old=json.loads((a.simulator/'em9305-reset-main-01'/case/'plan.json').read_text())
        spec=dict(boundary=old['semantics'][case]['candidate']['boundary'],comparison=dict(policy='exact',path=['observed']),checks=[dict(path=['selected_observation'],eq_source=['selected_observation']),dict(path=['diagnostics','paused'],eq=True)],allowed_differences=['Host observation window 90 seconds, post-pause read-only draw-unit fields only'],unresolved_differences=['Diagnostic missing font banks and synthetic peripheral readiness; no main UI draw reached'])
        plan['semantics'][case]=dict(candidate=spec,control=spec)
    (out/'report.json').write_text(json.dumps(dict(passed=True,cases=cases,source_sha256=sha(Path(__file__).read_bytes())),indent=2)+'\n');(out/'candidate.json').write_text(json.dumps(plan,indent=2)+'\n');(out/'inspector.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(passed=True,cases=[dict(case=c['case'],**{k:hex(c['contract'][k]) for k in ['evaluate','available','global_base','unit_slot']}) for c in cases])))


if __name__=='__main__':main()
