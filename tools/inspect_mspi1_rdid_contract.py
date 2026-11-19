"""Verify manufacturer RDID data, MSPI FIFO layout and original three-byte RX path."""
import argparse,hashlib,json,struct,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from pypdf import PdfReader
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from inspect_mspi1_config_contract import collect
from pinned_main import load_pinned_main
from native_replay import parse_log

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 research=s/'mspi1-pio-research-01';pin=json.loads((research/'datasheet-source.json').read_text());raw=(research/'mx25u25643g-v1.1.pdf').read_bytes();check('manufacturer-PDF-pin',hashlib.sha256(raw).hexdigest()==pin['sha256']);pdf=PdfReader(research/'mx25u25643g-v1.1.pdf');text=pdf.pages[30].extract_text();check('ID-table-text-preserved',text==(research/'datasheet-page-31.txt').read_text());check('RDID-three-primary-bytes','RDID 9Fh Manufacturer ID Memory type Memory density C2 25 39' in ' '.join(text.split()));check('visual-table-image-preserved',(research/'datasheet-page-31.png').read_bytes().startswith(b'\x89PNG'))
 h,regs=collect(s)
 for n,off,mask in [('RXFIFO',0x14,0xffffffff),('RXENTRIES',0x1c,0x3f)]:
  r=next(x for x in regs if x['name']==n);check(n+'-layout',r['offset']==off and r['mask']==mask and r['reset']==0)
 end=h.index('} MSPI0_Type;');start=h.rfind('typedef struct {',0,end);c='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+h[start:end]+'} MSPI0_Type;\n_Static_assert(offsetof(MSPI0_Type,RXFIFO)==0x14,"FIFO");\n_Static_assert(offsetof(MSPI0_Type,RXENTRIES)==0x1c,"entries");\n';(o/'layout.c').write_text(c);r=subprocess.run(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-c',str(o/'layout.c'),'-o',str(o/'layout.o')],capture_output=True,text=True,timeout=30);(o/'compiler.log').write_text(r.stdout+r.stderr);check('compiled-FIFO-offsets',r.returncode==0)
 root=s/'mspi1-source-research-01';raw=(root/'am_hal_mspi.c').read_bytes();pin=next(x for x in json.loads((root/'sources.json').read_text())['files'] if x['path'].endswith('/am_hal_mspi.c'));check('HAL-pin',hashlib.sha256(raw).hexdigest()==pin['sha256']);hal=raw.decode();body=hal[hal.index('mspi_fifo_read(uint32_t'):hal.index('//! @brief Initialize MSPI command queue.')]
 for n,needle in [('whole-words','ui32NumWords = ui32NumBytes / 4;'),('entries-poll','MSPI0_RXENTRIES_RXENTRIES_Msk,'),('tail-word','sTempBuffer.words[0] = MSPIn(ui32Module)->RXFIFO;'),('tail-bytes','pui8Data[j] = sTempBuffer.bytes[j];')]:check('HAL-'+n,needle in body)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);cases=[]
 for key,bundle,pc,fifo,ret in [('stock24','stock-2.4.0.24.bin',0x4e8a46,0x4e6468,0x4e8a5e),('stock23','stock-2.3.0.24.bin',0x4db672,0x4d9094,0x4db68a),('cfw','faceclaw-38-research-only.bin',0x4db672,0x4d9094,0x4db68a)]:
  d=s/'mspi1-xip-mixed-main-01'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-original-bytes',raw==(d/'main.bin').read_bytes());v=parse_log((d/'renode.log').read_text());check(key+'-saved-report',v==json.loads((d/'report.json').read_text())['observed']);g=[x for x in v['guards'] if x['accesses']];check(key+'-RX3-attempt',v['pc']==pc and len(g)==1 and g[0]['address']==0x40061000 and g[0]['value']==0x30441)
  st=v['stack_context'];stack=struct.pack('<32I',*st['words']);offset=v['register_context']['r1']-st['base'];check(key+'-descriptor-bounds',offset==36 and len(stack)>=offset+24);desc=stack[offset:offset+24];check(key+'-descriptor-fields',struct.unpack_from('<I',desc)[0]==3 and desc[6]==0 and desc[12]==1 and struct.unpack_from('<H',desc,14)[0]==0x9f and desc[16]==1);buf=struct.unpack_from('<I',desc,20)[0];check(key+'-buffer-snapshot-bounds',st['base']<=buf<=st['base']+124 and buf%4==0);before=struct.unpack_from('<I',stack,buf-st['base'])[0]
  code=list(md.disasm(raw[fifo-0x438000:fifo-0x438000+0x9e],fifo));pairs=[(x.mnemonic,x.op_str) for x in code];check(key+'-FIFO-word-read',('ldr.w','r0, [r8, #0x14]') in pairs);check(key+'-entries-poll-address',('adds.w','r1, r0, #0x1c') in pairs and ('movs','r2, #0x3f') in pairs);check(key+'-three-byte-copy-loop',('ldrb','r2, [r2, r1]') in pairs and ('strb','r2, [r0, r1]') in pairs and ('cmp','r1, r4') in pairs and any(x.mnemonic=='blo' and int(x.op_str[1:],0)<x.address for x in code));call=list(md.disasm(raw[ret-4-0x438000:ret-0x438000],ret-4));check(key+'-FIFO-call-return',len(call)==1 and call[0].mnemonic=='bl' and call[0].op_str=='#'+hex(fifo));cases.append(dict(case=key,descriptor=desc.hex(),buffer=buf,before_word=before,FIFO_return=ret,expected_profile_id='c22539',expected_fourth_byte=(before>>24)&255,hardware_identity_confirmed=False))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='manufacturer model contract and saved original request; actual device identity and RX execution unverified'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
