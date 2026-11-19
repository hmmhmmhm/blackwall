"""Inspect original NOR/XIP caller, packed ABI and source aperture without running guest or hardware."""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 research=s/'mspi1-xip-research-01';manifest=json.loads((research/'sources.json').read_text());tree=json.loads((s/'timer-source-research-01/tree.json').read_text())['tree']
 check('public-commit',manifest['commit']=='61b293a49db34030c545f99101f7ebf6a3050314')
 for f in manifest['files']:
  raw=(research/Path(f['path']).name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();check(f['path']+' pin',hashlib.sha256(raw).hexdigest()==f['sha256'] and blob==f['git_blob']==next(x['sha'] for x in tree if x['path']==f['path']))
 for f in json.loads((s/'mspi1-source-research-01/sources.json').read_text())['files']:
  raw=(s/'mspi1-source-research-01'/Path(f['path']).name).read_bytes();check(f['path']+' existing-pin',hashlib.sha256(raw).hexdigest()==f['sha256'])
 bases=(research/'am_reg_base_addresses.h').read_text();header=(s/'mspi1-source-research-01/am_hal_mspi.h').read_text()
 def macro(name):return int(re.search(r'#define '+name+r'\s+\((0x[0-9a-fA-F]+)UL\)',bases).group(1),0)
 check('module-window',macro('MSPI1_APERTURE_START_ADDR')==0x80000000 and macro('MSPI1_APERTURE_END_ADDR')==0x84000000)
 snippets=[]
 for name in ['am_hal_mspi_ap_e','am_hal_mspi_ap_size_e','am_hal_mspi_xip_config_t']:
  end=re.search(r'}\s+'+name+r';',header).end();start=header.rfind('typedef ',0,end);snippets.append(header[start:end])
 prefix='#include <stdint.h>\n#include <stddef.h>\n'+'\n'.join(snippets)+'\n_Static_assert(AM_HAL_MSPI_AP_SIZE32M==9,"size enum");\n'
 for name,flags,size,size_offset in [('default',[],20,16),('short',['-fshort-enums'],16,13)]:
  c=prefix+f'_Static_assert(sizeof(am_hal_mspi_xip_config_t)=={size},"struct size");\n_Static_assert(offsetof(am_hal_mspi_xip_config_t,eAPMode)==12,"mode");\n_Static_assert(offsetof(am_hal_mspi_xip_config_t,eAPSize)=={size_offset},"size");\n';(o/(name+'.c')).write_text(c);cmd=['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11']+flags+['-c',str(o/(name+'.c')),'-o',str(o/(name+'.o'))];r=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(o/(name+'.log')).write_text(r.stdout+r.stderr);check(name+'-compiled-layout',r.returncode==0)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);cases=[]
 def instructions(raw,pc,length):return list(md.disasm(raw[pc-0x438000:pc-0x438000+length],pc))
 def literal(raw,pc):
  ins=instructions(raw,pc,4)[0];match=re.fullmatch(r'r\d+, \[pc, #(0x[0-9a-f]+|\d+)\]',ins.op_str)
  if not ins.mnemonic.startswith('ldr') or not match:raise ValueError('Unexpected literal instruction')
  at=((pc+4)&~3)+int(match.group(1),0);return struct.unpack_from('<I',raw,at-0x438000)[0]
 for key,bundle,copy_pc,request_pc,field_pc,pc,lr in [('stock24','stock-2.4.0.24.bin',0x47b0a6,0x47b0c4,0x4e7e28,0x4e7ec0,0x47b0ce),('stock23','stock-2.3.0.24.bin',0x47638e,0x4763ac,0x4daa54,0x4daaec,0x4763b6),('cfw','faceclaw-38-research-only.bin',0x47638e,0x4763ac,0x4daa54,0x4daaec,0x4763b6)]:
  d=s/'mspi1-cq-init-main-01'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+' original-main',raw==(d/'main.bin').read_bytes());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);checks.append(key+' saved-asset-hashes');v=parse_log((d/'renode.log').read_text());check(key+' saved-report',v==json.loads((d/'report.json').read_text())['observed'])
  context=v['register_context'];guards=[g for g in v['guards'] if g['accesses']];check(key+' original-stop',v['pc']==pc and context['r0']==0x40061090 and context['r1']==0x5ed and context['r6']==1 and (context['r14']&~1)==lr and len(guards)==1 and guards[0]['operation']=='write' and guards[0]['value']==0x5ed)
  callee=0x4e7824 if key=='stock24' else 0x4da450
  check(key+' caller-direct-bl',[(i.mnemonic,i.op_str) for i in instructions(raw,lr-4,4)]==[('bl','#'+hex(callee))])
  check(key+' request-number',[(i.mnemonic,i.op_str) for i in instructions(raw,request_pc,2)]==[('movs','r1, #0x15')])
  check(key+' natural-enable-rmw',[(i.mnemonic,i.op_str) for i in instructions(raw,pc-6,8)]==[('ldr','r1, [r0]'),('orrs','r1, r1, #1'),('str','r1, [r0]')])
  pointer=literal(raw,copy_pc);config=raw[pointer-0x438000:pointer-0x438000+16];check(key+' fixed-config-object',config==bytes.fromhex('00000000000000000000008001090000'))
  check(key+' copy-length16',[(i.mnemonic,i.op_str) for i in instructions(raw,copy_pc+4,2)]==[('movs','r2, #0x10')])
  field_ops=[(i.mnemonic,i.op_str) for i in instructions(raw,field_pc,14)];check(key+' byte-mode-size-access',field_ops[0]==('ldrb','r0, [r2, #0xc]') and ('ldrb','r0, [r2, #0xd]') in field_ops)
  range_code=instructions(raw,field_pc-0x3e,14)
  check(key+' original-module1-range-check',[(i.mnemonic,i.op_str) for i in range_code[:3]]==[('ldr','r0, [r2, #8]'),('adds.w','r0, r0, #-0x80000000'),('cmp.w','r0, #0x4000000')])
  def cstring(at):return raw[at-0x438000:at-0x438000+180].split(b'\0',1)[0].decode('ascii')
  path=cstring(literal(raw,copy_pc+0x68));function=cstring(literal(raw,copy_pc+0x64));check(key+' NOR-caller-labels',path.endswith('drv_mx25u25643g.c') and function=='am_devices_norflash_qspi_init')
  lines=(d/'renode.log').read_text().splitlines();cfgs=[json.loads(x.split('BLACKWALL_MSPI1_CONFIG ',1)[1]) for x in lines if x.startswith('BLACKWALL_MSPI1_CONFIG ')];check(key+' config-marker',len(cfgs)==1);regs=cfgs[0]['registers'];check(key+' readonly32m-register',regs['128']==0x19 and regs['144']==0x5ec and regs['148']==0x6b0002)
  base=struct.unpack_from('<I',config,8)[0];size=65536<<config[13];check(key+' window-match',base==0x80000000 and size==0x2000000 and config[12]==1 and base+size<=macro('MSPI1_APERTURE_END_ADDR'))
  cases.append(dict(case=key,stop_pc=pc,caller_return=lr,config_address=pointer,config_hex=config.hex(),mode_offset=12,size_offset=13,NOR_source_label=path,NOR_function_label=function,base=base,size=size,end_exclusive=base+size,readonly=True,physical_chip_identified=False,range_instructions=[dict(address=i.address,mnemonic=i.mnemonic,operands=i.op_str) for i in range_code]))
 check('current-model-unchanged',(s/'mspi1-cq-init-main-01/stock24/strict.cs').read_bytes().count((ROOT/'tools/renode-mspi1-config.cs').read_bytes())==1)
 result=dict(passed=True,count=len(checks),checks=checks,cases=cases,backing_data_proven=False,physical_validated=False,boot_verified=False,installable=False,abi_note='Original reads enum fields as bytes12/13; public default C layout differs. short-enum compile reproduces layout but does not prove original compiler flags.',legacy_base_macro=macro('MSPI1_XIP_BASEADDR'),policy='No register enable, flash bytes or address mapping added; preserve strict guard until explicit backing/unknown-read policy is implemented')
 (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');(o/'required-backing.json').write_text(json.dumps(dict(base=0x80000000,size=0x2000000,end_exclusive=0x82000000,readonly=True,known_ranges=[],unknown_ranges=[dict(offset=0,length=0x2000000)],source_image=None,source_sha256=None,unknown_read_policy='must-stop-not-zero-fill',physical_chip_identified=False),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),base='0x80000000',size=0x2000000,backing_data_proven=False)))
if __name__=='__main__':main()
