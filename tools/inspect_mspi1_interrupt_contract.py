"""Verify public MSPI interrupt metadata and original ARM clear/readback sequence."""
import argparse,hashlib,json,re,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from inspect_mspi1_config_contract import collect
from native_replay import parse_log
from pinned_main import load_pinned_main
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 h,regs=collect(s);lookup={r['name']:r for r in regs};xml=ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot();per=next(x for x in xml.findall('./peripherals/peripheral') if x.findtext('name')=='MSPI0');metadata={x.findtext('name'):x for x in per.findall('./registers/register')}
 for name,offset in [('INTEN',0x200),('INTSTAT',0x204),('INTCLR',0x208),('INTSET',0x20c)]:
  r=lookup[name];check(name+' reset-mask-offset',r['reset']==0 and r['mask']==0x3fff and r['offset']==offset)
  bits=re.findall(r'#define MSPI0_'+name+r'_\w+_Pos\s+\((\d+)UL\)',h);check(name+' 14-fields',len(bits)==14 and {int(x) for x in bits}==set(range(14)))
 check('clear-semantics','Write a 1' in metadata['INTCLR'].findtext('description') and 'clear' in metadata['INTCLR'].findtext('description'))
 check('set-semantics','Write a 1' in metadata['INTSET'].findtext('description') and 'generate an interrupt' in metadata['INTSET'].findtext('description'))
 check('MSPI1-IRQ21',re.search(r'MSPI1_IRQn\s*=\s*21,',h) is not None)
 halpath=s/'mspi1-source-research-01/am_hal_mspi.c';raw=halpath.read_bytes();pin=next(f for f in json.loads((s/'mspi1-source-research-01/sources.json').read_text())['files'] if f['path'].endswith('am_hal_mspi.c'));check('HAL-pin',hashlib.sha256(raw).hexdigest()==pin['sha256']);hal=raw.decode()
 for name,text in [('enable-rmw','MSPIn(ui32Module)->INTEN |= ui32IntMask;'),('disable-rmw','MSPIn(ui32Module)->INTEN &= ~ui32IntMask;'),('enabled-only-status','*pui32Status = ui32RetVal & MSPIn(ui32Module)->INTEN;'),('clear-write','MSPIn(ui32Module)->INTCLR = ui32IntMask;'),('clear-status-readback','*(volatile uint32_t*)(&MSPIn(ui32Module)->INTSTAT);')]:check(name,text in hal)
 end=h.index('} MSPI0_Type;');start=h.rfind('typedef struct {',0,end);c='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+h[start:end]+'} MSPI0_Type;\n'
 for name,offset in [('INTEN',0x200),('INTSTAT',0x204),('INTCLR',0x208),('INTSET',0x20c)]:c+='_Static_assert(offsetof(MSPI0_Type,'+name+')=='+str(offset)+',"'+name+'");\n'
 (o/'layout.c').write_text(c);r=subprocess.run(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(o/'layout.c'),'-o',str(o/'layout.o')],capture_output=True,text=True,timeout=30);(o/'compiler.log').write_text(r.stdout+r.stderr);check('compiled-offsets',r.returncode==0)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);cases=[]
 for key,bundle,pc in [('stock24','stock-2.4.0.24.bin',0x4e8caa),('stock23','stock-2.3.0.24.bin',0x4db8d6),('cfw','faceclaw-38-research-only.bin',0x4db8d6)]:
  d=s/'mspi1-xip-guard-main-01'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+' main-bytes',raw==(d/'main.bin').read_bytes());v=parse_log((d/'renode.log').read_text());check(key+' saved-report',v==json.loads((d/'report.json').read_text())['observed']);ctx=v['register_context'];guard=[g for g in v['guards'] if g['accesses']]
  check(key+' clear-attempt',v['pc']==pc and ctx['r1']==0x1a80 and ctx['r3']==0x40061000 and len(guard)==1 and guard[0]['address']==0x40061208 and guard[0]['operation']=='write')
  ins=list(md.disasm(raw[pc-0x438000:pc-0x438000+14],pc));check(key+' clear-readback-code',[(x.mnemonic,x.op_str) for x in ins]==[('str.w','r1, [r3, #0x208]'),('adds.w','r2, r2, r0, lsl #12'),('ldr.w','r0, [r2, #0x204]'),('movs','r0, #0')])
  cases.append(dict(case=key,pc=pc,mask=0x1a80,instructions=[dict(address=x.address,mnemonic=x.mnemonic,operands=x.op_str) for x in ins],clear_write_completed_in_this_reference=False))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='pinned source and original clear attempt/readback code; not runtime ISR, engine event or physical proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
