"""Check the original main's draw-unit registry and exercise original selection functions."""
import argparse,json,struct,hashlib
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC
import unicorn.arm_const as arm
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main

BASE,SRAM,WORK,STOP=0x438000,0x20000000,0x21000000,0x10000000


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('contract',type=Path);p.add_argument('native',type=Path);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
    if any((v/'.git').exists() for v in [out,*out.parents]):raise ValueError('Private output required')
    out.mkdir(mode=0o700);contract=json.loads((a.contract/'report.json').read_text());results=[];pins={};calls=0
    for row,filename in zip(contract['cases'],['stock-2.4.0.24.bin','stock-2.3.0.24.bin','faceclaw-38-research-only.bin']):
        case=row['case'];c=row['contract'];folder=a.native/case
        r=json.loads((folder/'report.json').read_text());prior=json.loads((a.simulator/'em9305-reset-main-01'/case/'report.json').read_text())
        validate_assets(folder,json.loads((folder/'derived-inputs.json').read_text())['derived'])
        assert r['passed'] and r['execution_passed'] and r['semantic_validation']['passed'] and r['diagnostics']['paused']
        assert parse_log((folder/'renode.log').read_text())==r['observed']==prior['observed'] and r['selected_observation']==prior['selected_observation']
        d=r['diagnostics'];root=d['roots'][str(c['global_base'])];unit=d['slots'][str(c['unit_slot'])];words=root['words']
        assert root['count']==1 and root['head']==unit and len(words)==57 and words[0]==0 and words[2]==1
        assert words[3]==c['dispatch']|1 and words[4]==c['evaluate']|1
        _,raw=load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes());assert sha(raw)==row['raw_sha256']
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);size=(len(raw)+4095)&~4095
        u.mem_map(BASE,size);u.mem_write(BASE,raw);u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
        u.mem_map(SRAM,0x380000);u.mem_map(WORK,0x10000);u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        u.mem_write(unit,struct.pack('<57I',*words));u.mem_write(c['global_base']+0x140,struct.pack('<I',root['count']));u.mem_protect(SRAM,0x380000,UC_PROT_READ)
        saved=[getattr(arm,'UC_ARM_REG_R'+str(i)) for i in range(4,12)]
        def call(entry,args,mutable=()):
            nonlocal calls
            for reg,value in zip([arm.UC_ARM_REG_R0,arm.UC_ARM_REG_R1,arm.UC_ARM_REG_R2,arm.UC_ARM_REG_R3],args):u.reg_write(reg,value)
            for i,reg in enumerate(saved):u.reg_write(reg,0x12340000+i)
            u.reg_write(arm.UC_ARM_REG_SP,WORK+0xff00);u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
            before=bytes(u.mem_read(WORK,0x10000));u.emu_start(entry|1,STOP,count=10000)
            assert u.reg_read(arm.UC_ARM_REG_PC)==STOP and u.reg_read(arm.UC_ARM_REG_SP)==WORK+0xff00
            assert [u.reg_read(reg) for reg in saved]==[0x12340000+i for i in range(8)]
            after=bytes(u.mem_read(WORK,0x10000));allowed=[(0xfc00,0xff00),*mutable]
            assert all(any(start<=i<end for start,end in allowed) for i,(x,y) in enumerate(zip(before,after)) if x!=y)
            calls+=1;return u.reg_read(arm.UC_ARM_REG_R0)
        task,layer=WORK+0x100,WORK+0x400;labels=[]
        for preferred in [0,1,9]:
            for score in [0,10,255]:
                for descriptor in [0,WORK+0x3000,0xfffffff0]:
                    u.mem_write(task,bytes(0x100));u.mem_write(task+4,b'\x05');u.mem_write(task+0x54,struct.pack('<I',descriptor));u.mem_write(task+0x58,bytes([preferred,score]))
                    value=call(c['evaluate'],[unit,task],[(0x158,0x15a)])
                    result=list(u.mem_read(task+0x58,2));assert value==0 and result==[9,10]
                    labels.append(dict(preferred_before=preferred,score_before=score,descriptor=descriptor,result=result,returned=value))
        for kind in [0,4,12]:
            u.mem_write(task,bytes(0x100));u.mem_write(task+4,bytes([kind]));u.mem_write(task+0x58,bytes([7,25]));call(c['evaluate'],[unit,task]);assert bytes(u.mem_read(task+0x58,2))==bytes([7,25])
        selected=[]
        for state in [0,1,2,3]:
            for unit_id in [0,9,99]:
                u.mem_write(layer,bytes(0x100));u.mem_write(task,bytes(0x100));u.mem_write(layer+0x44,struct.pack('<I',task));u.mem_write(task+0x50,struct.pack('<I',state))
                value=call(c['available'],[layer,0,unit_id]);assert value==(task if state==1 else 0)
                selected.append(dict(state=state,requested_unit_id=unit_id,selected=value==task))
        u.mem_write(layer,bytes(0x100));assert call(c['available'],[layer,0,9])==0
        results.append(dict(case=case,unit_address=unit,unit_count=root['count'],unit_words=words,evaluation=labels,unsupported_kinds=[0,4,12],selection=selected,
            actual_registry_is_ambiq=True,synthetic_tasks=True,main_state_unchanged=True,main_draw_executed=False))
        for path in [folder/'report.json',folder/'renode.log',folder/'derived-inputs.json',a.contract/'report.json']:pins[str(path.relative_to(a.simulator))]=sha(path.read_bytes())
    tools={}
    for name in ['verify_draw_unit_selection.py','inspect_draw_unit_selection.py','inspect_ambiq_target.py','font_wrapper_contract.py','pinned_main.py','native_replay.py','run_renode_m55_probe.py','blackwall_package.py','revalidate_research_assets.py']:
        data=Path(__file__).with_name(name).read_bytes();(out/name).write_bytes(data);tools[name]=sha(data)
    (out/'report.json').write_text(json.dumps(dict(passed=True,cases=results,original_function_calls=calls,source_hashes=pins,tool_hashes=tools,
        full_main_rendered=False,hardware_accessed=False),indent=2)+'\n');(out/'report.json').chmod(0o600)
    print(json.dumps(dict(passed=True,original_function_calls=calls,unit_counts=[r['unit_count'] for r in results],full_main_rendered=False)))


if __name__=='__main__':main()
