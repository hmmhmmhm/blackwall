"""Check pinned HAL clear-all API and original ARM all-clear store against source metadata."""
import argparse,hashlib,json,re
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
 root=s/'mspi1-source-research-01';pins=json.loads((root/'sources.json').read_text());text={}
 for name in ['am_hal_mspi.c','am_hal_mspi.h']:
  pin=next(x for x in pins['files'] if x['path'].endswith('/'+name));raw=(root/name).read_bytes();check(name+'-SHA',hashlib.sha256(raw).hexdigest()==pin['sha256']);check(name+'-blob',hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==pin['git_blob']);text[name]=raw.decode()
 check('HAL-INT-ALL-FFFFFFFF',re.search(r'#define AM_HAL_MSPI_INT_ALL\s+0xFFFFFFFF\b',text['am_hal_mspi.h']) is not None)
 c=text['am_hal_mspi.c'];body=c[c.index('am_hal_mspi_interrupt_clear(void'):c.index('// MSPI interrupt service routine')];check('clear-write-readback','MSPIn(ui32Module)->INTCLR = ui32IntMask;' in body and '*(volatile uint32_t*)(&MSPIn(ui32Module)->INTSTAT);' in body);check('HAL-all-clear-used',c.count('MSPIn(ui32Module)->INTCLR = AM_HAL_MSPI_INT_ALL;')>=3)
 _,regs=collect(s)
 for n in ['INTEN','INTSTAT','INTCLR','INTSET']:
  r=next(x for x in regs if x['name']==n);check(n+'-implemented-mask',r['mask']==0x3fff and r['reset']==0)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);cases=[]
 for key,bundle,pc in [('stock24','stock-2.4.0.24.bin',0x4e8a3e),('stock23','stock-2.3.0.24.bin',0x4db66a),('cfw','faceclaw-38-research-only.bin',0x4db66a)]:
  d=s/'timer14-main-01'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-original-main',raw==(d/'main.bin').read_bytes());v=parse_log((d/'renode.log').read_text());g=[x for x in v['guards'] if x['accesses']];check(key+'-all-clear-attempt',v['pc']==pc and len(g)==1 and g[0]['address']==0x40061208 and g[0]['operation']=='write' and g[0]['value']==0xffffffff);ins=list(md.disasm(raw[pc-0x438000:pc-0x438000+8],pc));check(key+'-store-code',ins[0].mnemonic=='str.w' and '#0x208]' in ins[0].op_str);cases.append(dict(case=key,pc=pc,code=[dict(address=x.address,mnemonic=x.mnemonic,operands=x.op_str) for x in ins]))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='HAL all-clear contract and original store attempt, not measured reserved-bit hardware behavior'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
