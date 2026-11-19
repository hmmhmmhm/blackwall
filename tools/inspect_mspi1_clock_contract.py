"""Check pinned public MSPI clock metadata and saved original ARM read contexts."""
import argparse,hashlib,json,re,struct,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from pinned_main import load_pinned_main
from native_replay import parse_log
from analyze_adc_metadata import SVD_SHA,HEADER_SHA
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 svd=(s/'apollo-dfp-research-01/apollo510.svd').read_bytes();h=(s/'mspi1-source-research-01/apollo510.h').read_bytes()
 check('pinned-svd',hashlib.sha256(svd).hexdigest()==SVD_SHA);check('pinned-header',hashlib.sha256(h).hexdigest()==HEADER_SHA)
 xml=ET.fromstring(svd);per=next(x for x in xml.findall('./peripherals/peripheral') if x.findtext('name')=='CLKGEN');reg=next(x for x in per.findall('./registers/register') if x.findtext('name')=='MSPIIOCLKCTRL')
 check('source-address',int(per.findtext('baseAddress'),0)+int(reg.findtext('addressOffset'),0)==0x40004110)
 check('source-reset',int(reg.findtext('resetValue'),0)==0xa4214 and int(reg.findtext('resetMask'),0)==0xfffff)
 header=h.decode();fields=[]
 for f in reg.findall('./fields/field'):
  name=f.findtext('name');hi,lo=map(int,re.fullmatch(r'\[(\d+):(\d+)\]',f.findtext('bitRange')).groups());mask=((1<<(hi-lo+1))-1)<<lo
  macro=re.search(r'#define CLKGEN_MSPIIOCLKCTRL_'+name+r'_Msk\s+\((0x[0-9a-f]+)UL\)',header)
  check(name+'-mask',macro is not None and int(macro.group(1),0)==mask)
  enums=[dict(name=x.findtext('name'),value=int(x.findtext('value'),0)) for x in f.findall('./enumeratedValues/enumeratedValue')]
  fields.append(dict(name=name,mask=mask,enums=enums))
 check('mspi1-selection-7-8',[x['value'] for x in next(x for x in fields if x['name']=='MSPI1IOCLKSEL')['enums']]==[7,8])
 end=header.index('} CLKGEN_Type;');start=header.rfind('typedef struct {',0,end)
 c='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+header[start:end]+'} CLKGEN_Type;\n_Static_assert(offsetof(CLKGEN_Type,MSPIIOCLKCTRL)==0x110,"clock layout");\n'
 o.mkdir(mode=0o700);(o/'layout.c').write_text(c);r=subprocess.run(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(o/'layout.c'),'-o',str(o/'layout.o')],capture_output=True,text=True,timeout=30);(o/'compiler.log').write_text(r.stdout+r.stderr);check('compiled-offset',r.returncode==0)
 cases=[];md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
 for key,bundle,pc in [('stock24','stock-2.4.0.24.bin',0x4e7024),('stock23','stock-2.3.0.24.bin',0x4d9c50),('cfw','faceclaw-38-research-only.bin',0x4d9c50)]:
  d=s/'mspi1-power-main-01'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-original-bytes',raw==(d/'main.bin').read_bytes());v=parse_log((d/'renode.log').read_text());ctx=v['register_context']
  check(key+'-context',v['pc']==pc and ctx['r1']==0x40004110 and ctx['r4']==1 and ctx['r5']==8 and ctx['r7']==1)
  ins=list(md.disasm(raw[pc-4-0x438000:pc+58-0x438000],pc-4));check(key+'-read',ins[1].address==pc and ins[1].mnemonic=='ldr' and ins[1].op_str=='r0, [r1]')
  literal=((pc-4+4)&~3)+0x7e8;check(key+'-literal',struct.unpack_from('<I',raw,literal-0x438000)[0]==0x40004110)
  cases.append(dict(case=key,read_pc=pc,module=1,selection=8,instructions=[dict(address=x.address,mnemonic=x.mnemonic,operands=x.op_str) for x in ins]))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,fields=fields,cases=cases,reset=0xa4214,physical_validated=False,scope='pinned public metadata and static original ARM context; not completed clock write'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
