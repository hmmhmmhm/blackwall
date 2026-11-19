"""Inspect pinned MSPI metadata; select configuration storage, keeping execution controls strict."""
import argparse,hashlib,json,re,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from analyze_adc_metadata import SVD_SHA,HEADER_SHA
ROOT=Path(__file__).resolve().parents[1]
NAMES=['CTRL1','ADDR','INSTR','THRESHOLD','MSPICFG','PADOUTEN','PADOVEREN','PADOVER','DEV0AXI','DEV0CFG','DEV0DDR','DEV0CFG1','DEV0XIP','DEV0INSTR','DEV0BOUNDARY','DEV0SCRAMBLING','DEV0XIPMISC','DEV0XIPCPURQ','DEV0DDRDLYEXT','DMACFG','DMATARGADDR','DMADEVADDR','DMATOTCOUNT','DMABCOUNT','DMATHRESH']
def collect(s):
 svd=(s/'apollo-dfp-research-01/apollo510.svd').read_bytes();h=(s/'mspi1-source-research-01/apollo510.h').read_bytes()
 if hashlib.sha256(svd).hexdigest()!=SVD_SHA or hashlib.sha256(h).hexdigest()!=HEADER_SHA:raise ValueError('Source pins differ')
 root=ET.fromstring(svd);p=next(x for x in root.findall('./peripherals/peripheral') if x.findtext('name')=='MSPI0');registers=[]
 instance=next(x for x in root.findall('./peripherals/peripheral') if x.findtext('name')=='MSPI1')
 if instance.get('derivedFrom')!='MSPI0' or int(instance.findtext('baseAddress'),0)!=0x40061000 or instance.find('registers') is not None:raise ValueError('MSPI1 inheritance differs')
 for x in p.findall('./registers/register'):
  name=x.findtext('name');mask=0
  for field in x.findall('./fields/field'):
   high,low=map(int,re.fullmatch(r'\[(\d+):(\d+)\]',field.findtext('bitRange')).groups());m=((1<<(high-low+1))-1)<<low;macro=re.search(r'#define MSPI0_'+name+'_'+field.findtext('name')+r'_Msk\s+\((0x[0-9a-f]+)UL\)',h.decode())
   if not macro or int(macro.group(1),0)!=m or mask&m:raise ValueError('Field mismatch '+name)
   mask|=m
  if mask!=int(x.findtext('resetMask'),0):raise ValueError('Register mask mismatch '+name)
  registers.append(dict(name=name,offset=int(x.findtext('addressOffset'),0),reset=int(x.findtext('resetValue'),0),mask=mask,selected=name in NAMES,access=x.findtext('access')))
 if len(registers)!=43 or sum(x['selected'] for x in registers)!=len(NAMES):raise ValueError('Register coverage differs')
 return h.decode(),registers
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();h,regs=collect(a.simulator);o=a.output;o.mkdir(mode=0o700)
 (o/'base-core.cs').write_bytes((ROOT/'tools/renode-strict-mmio.cs').read_bytes())
 end=h.index('} MSPI0_Type;');start=h.rfind('typedef struct {',0,end);c='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+h[start:end]+'} MSPI0_Type;\n'
 for r in regs:c+='_Static_assert(offsetof(MSPI0_Type,'+r['name']+')=='+str(r['offset'])+',"'+r['name']+'");\n'
 (o/'layout.c').write_text(c);x=subprocess.run(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(o/'layout.c'),'-o',str(o/'layout.o')],capture_output=True,text=True,timeout=30);(o/'compiler.log').write_text(x.stdout+x.stderr)
 if x.returncode:raise ValueError('Layout compile failed')
 (o/'report.json').write_text(json.dumps(dict(passed=True,registers=regs,compiled_offsets=len(regs),selected_count=len(NAMES),policy='Only selected config storage; MSPICFG reset controls preserve C0000000; XIPEN,SCRENABLE,DMAEN must remain zero; CTRL/FIFO/status/IRQ/CQ strict',hardware_validated=False),indent=2)+'\n');print(json.dumps(dict(passed=True,registers=len(regs),selected=len(NAMES))))
if __name__=='__main__':main()
