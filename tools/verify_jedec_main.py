"""Observe natural ARM getter/API returns under explicit mock IDs, with pre-return SRAM capture."""
import argparse,json,hashlib,subprocess,sys
from pathlib import Path
import capstone
from capstone.arm import ARM_OP_IMM
from native_replay import parse_log,boundary_state,IMAGE
from pinned_main import load_pinned_main
ROOT=Path(__file__).resolve().parents[1]

def checkpoints(s,base):
    previous=s/'chip-info-main-comparison-01'/base
    report=json.loads((previous/'report.json').read_text());v=report['observed'];raw=(previous/'main.bin').read_bytes();cs=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS);cs.detail=True
    catalog=json.loads((s/'chip-info-source-01/report.json').read_text());meta=next(x for x in catalog['cases'] if x['name']==base)
    entry=int(meta['candidate_entry'],0);ret=int(meta['instructions'][-1]['address'],0);cont=v['register_context']['r14']&~1;stack=v['stack_context']['words'];target=v['register_context']['r4']
    def decode(address,length):return list(cs.disasm(raw[address-0x438000:address-0x438000+length],address))
    if decode(entry,2)[0].op_str!='{r3, r4, r5, lr}' or decode(ret,2)[0].op_str!='{r0, r4, r5, pc}':raise ValueError('Candidate getter frame differs')
    if stack[3]&~1!=cont or not stack[5]&1:raise ValueError('Saved Thumb return frame differs')
    outer=stack[5]&~1;call=decode(outer-4,4)[0]
    if call.mnemonic!='bl' or call.operands[0].type!=ARM_OP_IMM:raise ValueError('Outer caller is not a verified BL')
    api_entry=call.operands[0].imm;push=decode(api_entry,2)[0]
    if push.mnemonic!='push' or len(push.operands)!=2 or 'lr' not in push.op_str:raise ValueError('API frame differs')
    branch=decode(cont,2)[0]
    if branch.mnemonic!='b' or branch.operands[0].type!=ARM_OP_IMM:raise ValueError('Getter continuation differs')
    success=decode(branch.operands[0].imm,4)
    if [i.mnemonic for i in success]!=['movs','pop'] or success[0].op_str!='r0, #0' or success[1].op_str!='{r1, pc}':raise ValueError('Original API success path differs')
    points=[dict(label='api-entry',address=api_entry),dict(label='info-entry',address=entry),dict(label='info-return',address=ret),dict(label='info-cont',address=cont),dict(label='api-return',address=success[1].address),dict(label='api-cont',address=outer)]
    return points,target

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
    if o.exists():raise ValueError('Use a fresh evidence directory')
    o.mkdir(mode=0o700);rows=[]
    plan=[('stock24','stock24',0,0),('stock23','stock23',0,0),('cfw','cfw',0,0),('stock24-alt','stock24',0xfff,0xb105100d),('stock24-unknown','stock24',None,None)]
    for name,base,part,cid in plan:
        prior=s/'chip-info-main-comparison-01';cmd=json.loads((prior/(base+'-launcher.json')).read_text())['command'];run=o/name;cmd[3]=str(run)
        points,target=checkpoints(s,base)
        for point in points:cmd+=['--observe-pc',point['label']+':'+hex(point['address'])]
        cmd+=['--observe-sram','info-return:'+hex(target)+':16']
        if part is not None:cmd+=['--jedec-mock-part',hex(part),'--jedec-mock-cid',hex(cid)]
        launch=subprocess.run(cmd,capture_output=True,text=True)
        (o/(name+'-launcher.json')).write_text(json.dumps(dict(command=cmd,returncode=launch.returncode,stdout=launch.stdout,stderr=launch.stderr),indent=2)+'\n')
        if launch.returncode:raise ValueError('Observed original run failed: '+name)
        report=json.loads((run/'report.json').read_text());v=parse_log((run/'renode.log').read_text());obs=report['execution_observation']
        if v!=report['observed'] or report['image_id']!=IMAGE:raise ValueError('Saved native/runtime mismatch')
        _,raw=load_pinned_main(Path(cmd[2]).read_bytes())
        if raw!=(run/'main.bin').read_bytes():raise ValueError('Original main differs')
        point_map={p['label']:p for p in obs['points']};events={e['sequence']:e for e in obs['events']}
        if len(point_map)!=6 or obs['dropped_events']!=0:raise ValueError('Missing bounded return observations')
        words=None;returned=False
        if part is not None:
            first=[point_map[p['label']]['first_sequence'] for p in points]
            if any(point_map[p['label']]['hits']<1 for p in points) or first!=sorted(set(first)):raise ValueError('Natural call/return order not observed')
            if events[point_map['info-entry']['first_sequence']]['r0']!=target or events[point_map['api-cont']['first_sequence']]['r0']!=0:raise ValueError('Getter destination or natural API return status differs')
            snap=point_map['info-return']['snapshot']
            if snap is None or snap['address']!=target or snap['sequence']!=point_map['info-return']['first_sequence']:raise ValueError('Missing pre-return structure')
            words=snap['words'];revision=report['selected_hypotheses']['chip_revision']
            if words[:7]!=[0x10320080,0,0,revision,0,0x2d480f,1] or words[8:12]!=[262144,524288,3145728,4194304] or words[12:16]!=[part,0x9b,revision,cid]:raise ValueError('Original completed device-info fields differ from declared mock')
            returned=True
        else:
            previous=json.loads((prior/base/'report.json').read_text())
            if boundary_state(v)!=boundary_state(previous['observed']) or point_map['info-return']['hits'] or point_map['api-cont']['hits'] or point_map['info-return']['snapshot'] is not None:raise ValueError('Unknown JEDEC boundary was bypassed')
        if any(report[k] for k in ('boot_verified','hardware_validated','installable')):raise ValueError('Unproven completion claim')
        row=dict(name=name,pc=hex(v['pc']),guard=[g for g in v['guards'] if g['accesses']],mock_part=part,mock_cid=cid,natural_api_return_observed=returned,pre_return_words=words,point_hits={k:p['hits'] for k,p in point_map.items()})
        rows.append(row);print(json.dumps(row),flush=True)
    left=o/'stock23';right=o/'cfw'
    for name in ('board.repl','strict.cs','result.py','probe.resc'):
        if (left/name).read_bytes()!=(right/name).read_bytes():raise ValueError('Stock/CFW config differs')
    if (left/'run.py').read_text().replace('3758688','3829832')!=(right/'run.py').read_text():raise ValueError('Stock/CFW runtime differs beyond size')
    backup=o/'source';backup.mkdir(mode=0o700);hashes={}
    for file in ('verify_jedec_main.py','run_renode_main_probe.py','renode-strict-mmio.cs','renode-execution-observer.cs','execution_observer.py'):
        data=(ROOT/'tools'/file).read_bytes();(backup/file).write_bytes(data);hashes[file]=hashlib.sha256(data).hexdigest()
    (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,source_sha256=hashes,physical_identity_verified=False,scope='original call/return and info output under explicit mock JEDEC IDs, not real hardware compatibility or full boot'),indent=2)+'\n')

if __name__=='__main__':main()
