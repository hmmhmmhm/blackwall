"""Check paused main font-chain state and run original resolver/getter/setter prefixes."""
import argparse
import hashlib
import json
import struct
import re
from pathlib import Path

from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from inspect_ambiq_target import BASE,WORK,STOP,SRAM
from pinned_main import load_pinned_main
from native_replay import parse_log,validate_assets


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('contract',type=Path);p.add_argument('native',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--case-source',action='append',default=[],help='CASE=private capture directory; preserves independent failed/prior captures')
    a=p.parse_args();sources={}
    for value in a.case_source:
        case,separator,path=value.partition('=')
        if not separator or case not in ['stock24','stock23','cfw'] or case in sources:raise ValueError('Invalid case source')
        sources[case]=Path(path).resolve()
    out=a.output.resolve()
    if any((v/'.git').exists() for v in [out,*out.parents]):raise ValueError('Private output required')
    out.mkdir(mode=0o700);static=json.loads((a.contract/'report.json').read_text());results=[];pins={}
    reference=a.simulator/'ui-font-source-research-01'
    metadata=json.loads((reference/'source.json').read_text());header=(reference/'lv_style.h').read_bytes()
    assert sha(header)==metadata['sha256'] and re.search(rb'LV_STYLE_TEXT_FONT\s*=\s*90,',header)
    for path in [reference/'source.json',reference/'lv_style.h']:pins[str(path.relative_to(a.simulator))]=sha(path.read_bytes())
    for row,filename in zip(static['cases'],['stock-2.4.0.24.bin','stock-2.3.0.24.bin','faceclaw-38-research-only.bin']):
        case=row['case'];c=row['contract'];folder=sources.get(case,a.native/case)
        if not folder.resolve().is_relative_to(a.simulator.resolve()):raise ValueError('Native source outside private simulator root')
        report=json.loads((folder/'report.json').read_text());before=json.loads((a.simulator/'em9305-reset-main-01'/case/'report.json').read_text())
        manifest=json.loads((folder/'derived-inputs.json').read_text());validate_assets(folder,manifest['derived'])
        assert report['case']==case and report['passed'] and report['execution_passed'] and report['semantic_validation']['passed']
        assert parse_log((folder/'renode.log').read_text())==report['observed']==before['observed'] and report['selected_observation']==before['selected_observation']
        d=report['diagnostics'];assert d['paused']
        _,raw=load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes());assert sha(raw)==row['raw_sha256']
        old=json.loads((a.simulator/'builtin-font-memory-main-01'/case/'report.json').read_text())
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);size=(len(raw)+4095)&~4095
        u.mem_map(BASE,size);u.mem_write(BASE,raw);u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
        u.mem_map(SRAM,0x380000);u.mem_map(WORK,0x2000);u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        def put(address,words):u.mem_write(address,struct.pack('<'+'I'*len(words),*words))
        font_changes=[]
        for address,prior in old['fonts'].items():
            now=d['fonts'][str(int(address,0))]
            assert now[:7]==prior[:7] and now[8:]==prior[8:]
            put(int(address,0),now);font_changes.append(dict(address=address,callback_words=now[:3],fallback_before=prior[7],fallback_after=now[7],descriptor=now[6]))
        for chain in c['chains']:
            config=d['configs'][str(chain['config'])];assert config[::3]==[0]*4
            put(chain['config'],config)
            owner=d['slots'][str(chain['owner_slot'])];record=d['owners'][str(chain['owner_slot'])]
            assert 0x20000000<=owner<0x2037fff4 and record is not None and record[2]&255==4
            put(owner,record)
        u.mem_protect(SRAM,0x380000,UC_PROT_READ)
        def call(entry,args,until=STOP):
            for reg,value in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(reg,value)
            u.reg_write(UC_ARM_REG_SP,WORK+0x1f00);u.reg_write(UC_ARM_REG_LR,STOP|1)
            u.emu_start(entry|1,until,count=10000)
            assert u.reg_read(UC_ARM_REG_PC)==until
            if until==STOP:assert u.reg_read(UC_ARM_REG_SP)==WORK+0x1f00
            return u.reg_read(UC_ARM_REG_R0)
        chains=[]
        for chain in c['chains']:
            config=d['configs'][str(chain['config'])];pointers=config[1::3]
            for index,pointer in enumerate(pointers):assert call(c['resolver'],[chain['config']+index*12])==pointer
            owner=d['slots'][str(chain['owner_slot'])];head=d['slots'][str(chain['head_slot'])]
            assert call(c['getter'],[owner])==head==pointers[0]
            for index,pointer in enumerate(pointers):
                assert d['fonts'][str(pointer)][7]==(pointers[index+1] if index<3 else 0)
            call(c['style_setter'],[WORK+0x100,head,0],until=c['style_target'])
            assert [u.reg_read(reg) for reg in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]]==[WORK+0x100,90,head,0]
            chains.append(dict(config=chain['config'],owner=owner,head_slot=chain['head_slot'],head=head,font_pointers=pointers,
                head_bitmap_callback=d['fonts'][str(head)][1],external_descriptor=d['fonts'][str(pointers[2])][6],
                original_type0_resolver_preserves_pointer=True,original_getter_returns_first_font=True,original_style_prefix_property=90))
        results.append(dict(case=case,chains=chains,font_changes=font_changes,ui_setter_candidates=len(c['ui_setter_candidates']),
            main_observed_unchanged=True,diagnostic_invalid_font_banks=True,actual_render_unit_selection_verified=False))
        for path in [folder/'report.json',folder/'renode.log',folder/'derived-inputs.json',a.contract/'report.json']:
            pins[str(path.relative_to(a.simulator))]=sha(path.read_bytes())
    tool_hashes={}
    for name in ['verify_ui_font_state.py','inspect_ui_font_selection.py','inspect_ambiq_target.py','font_wrapper_contract.py','pinned_main.py','native_replay.py','run_renode_m55_probe.py','blackwall_package.py','revalidate_research_assets.py']:
        data=Path(__file__).with_name(name).read_bytes();(out/name).write_bytes(data);tool_hashes[name]=sha(data)
    (out/'report.json').write_text(json.dumps(dict(passed=True,cases=results,source_hashes=pins,tool_hashes=tool_hashes,original_function_calls=36,
        full_main_rendered=False,callback_words_changed_between_snapshots=False,hardware_accessed=False),indent=2)+'\n')
    (out/'report.json').chmod(0o600)
    print(json.dumps(dict(passed=True,original_function_calls=36,callback_words_changed_between_snapshots=False,full_main_rendered=False)))


if __name__=='__main__':main()
