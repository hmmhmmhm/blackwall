"""Verify Timer14 source metadata, C layout, pinned engine and original ARM read boundary."""
import argparse,hashlib,json,re,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from analyze_adc_metadata import SVD_SHA,HEADER_SHA
from native_replay import parse_log
from pinned_main import load_pinned_main
from timer14_engine_source import load_engine

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 svd=(s/'apollo-dfp-research-01/apollo510.svd').read_bytes();h=(s/'timer-source-research-01/apollo510.h').read_bytes()
 check('SVD-pin',hashlib.sha256(svd).hexdigest()==SVD_SHA);check('header-pin',hashlib.sha256(h).hexdigest()==HEADER_SHA);h=h.decode()
 per=next(x for x in ET.fromstring(svd).findall('./peripherals/peripheral') if x.findtext('name')=='TIMER');check('base',int(per.findtext('baseAddress'),0)==0x40008000);regs={x.findtext('name'):x for x in per.findall('./registers/register')}
 expected={'GLOBEN':(0x10,0xffff,0xe000ffff),'INTEN':(0x60,0,0xffffffff),'INTSTAT':(0x64,0,0xffffffff),'INTCLR':(0x68,0,0xffffffff),'INTSET':(0x6c,0,0xffffffff),'CTRL14':(0x3c0,0,0xff07ffff),'TIMER14':(0x3c4,0,0xffffffff),'TMR14CMP0':(0x3c8,0,0xffffffff),'TMR14CMP1':(0x3cc,0,0xffffffff),'MODE14':(0x3d0,0,0x1ff00)}
 for n,want in expected.items():check(n+'-layout',tuple(int(regs[n].findtext(k),0) for k in ['addressOffset','resetValue','resetMask'])==want)
 for n,f,rng in [('CTRL14','TMR14CLK','[16:8]'),('CTRL14','TMR14TMODE','[18:17]'),('MODE14','TMR14TRIGSEL','[16:8]'),('INTEN','TMR140INT','[28:28]'),('INTEN','TMR141INT','[29:29]')]:check(f+'-range',next(x for x in regs[n].findall('./fields/field') if x.findtext('name')==f).findtext('bitRange')==rng)
 check('Timer14-IRQ81',re.search(r'TIMER14_IRQn\s*=\s*81,',h,re.I) is not None)
 end=h.index('} TIMER_Type;');start=h.rfind('typedef struct {',0,end);c='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+h[start:end]+'} TIMER_Type;\n'
 for n,(off,_,_) in expected.items():c+='_Static_assert(offsetof(TIMER_Type,'+n+')=='+str(off)+',"'+n+'");\n'
 (o/'layout.c').write_text(c);r=subprocess.run(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(o/'layout.c'),'-o',str(o/'layout.o')],capture_output=True,text=True,timeout=30);(o/'compiler.log').write_text(r.stdout+r.stderr);check('compiled-offsets',r.returncode==0)
 research=s/'timer14-research-01';load_engine(s);check('engine-and-license-pin',True)
 for meta in ['source.json','comparing-source.json','clock-source.json']:
  items=json.loads((research/meta).read_text());items=items if isinstance(items,list) else [items]
  for pin in items:
   name=Path(pin['path']).name;raw=(research/name).read_bytes();check(name+'-SHA',hashlib.sha256(raw).hexdigest()==pin['sha256']);check(name+'-gitblob',hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==pin['git_blob'])
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);cases=[]
 for key,bundle,pc in [('stock24','stock-2.4.0.24.bin',0x5070d4),('stock23','stock-2.3.0.24.bin',0x4e8848),('cfw','faceclaw-38-research-only.bin',0x4e8848)]:
  d=s/'mspi1-interrupts-main-01'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-main-pin',raw==(d/'main.bin').read_bytes());v=parse_log((d/'renode.log').read_text());g=[x for x in v['guards'] if x['accesses']];check(key+'-read-attempt',v['pc']==pc and len(g)==1 and g[0]['address']==0x400083c0 and g[0]['operation']=='read');ins=list(md.disasm(raw[pc-0x438000:pc-0x438000+10],pc));check(key+'-disable-sequence',[(x.mnemonic,x.op_str) for x in ins[:4]]==[('ldr','r1, [r0]'),('lsrs','r1, r1, #1'),('lsls','r1, r1, #1'),('str','r1, [r0]')]);cases.append(dict(case=key,pc=pc,instructions=[dict(address=x.address,mnemonic=x.mnemonic,operands=x.op_str) for x in ins]))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,hardware_validated=False,scope='source layout and original read attempt; timing and ISR not proven'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
