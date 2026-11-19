"""Verify public STIMER interrupt offsets and the pinned original ARM access; no guest replay."""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import parse_log
from pinned_main import load_pinned_main
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output
 if o.exists():raise ValueError('Fresh evidence output required')
 checks=[]
 def check(name,ok):
  if not ok:raise ValueError(name)
  checks.append(name)
 src=s/'timer-source-research-01';manifest=json.loads((src/'sources.json').read_text());tree=json.loads((src/'tree.json').read_text())
 check('pinned-public-commit',manifest['commit']==tree['sha']=='61b293a49db34030c545f99101f7ebf6a3050314')
 for item in manifest['files']:
  data=(src/Path(item['path']).name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  check(item['path']+'-pin',hashlib.sha256(data).hexdigest()==item['sha256'] and blob==item['git_blob']==next(x['sha'] for x in tree['tree'] if x['path']==item['path']))
 header=(src/'apollo510.h').read_text();hal=(src/'am_hal_stimer.c').read_text();doc=(src/'stimer_regs.html').read_text();c='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'
 check('stimer-base',bool(re.search(r'#define STIMER_BASE\s+0x40008800UL',header)))
 for typename in ['STIMER','TIMER']:
  end=header.index('} '+typename+'_Type;');start=header.rfind('typedef struct {',0,end);c+=header[start:end]+'} '+typename+'_Type;\n'
 for name,offset in [('STMINTEN',0x100),('STMINTSTAT',0x104),('STMINTCLR',0x108),('STMINTSET',0x10c)]:
  c+='_Static_assert(offsetof(STIMER_Type,'+name+')=='+str(offset)+',"'+name+'");\n'
  fields=re.findall(r'#define STIMER_'+name+r'_(\w+)_Pos\s+\((\d+)UL\)',header)
  check(name+'-13-bit-fields',len(fields)==13 and {int(x[1]) for x in fields}==set(range(13)))
  begin=doc.index('id="'+name+'"');end=doc.find('<h3 ',begin+1);section=doc[begin:end]
  check(name+'-document-address',hex(0x40008800+offset).upper().replace('0X','0x') in section)
 c+='_Static_assert(offsetof(TIMER_Type,INTEN)==0x60,"separate TIMER bank");\n'
 check('hal-enable-rmw','STIMER->STMINTEN |= ui32Interrupt;' in hal)
 check('hal-set-clear','STIMER->STMINTSET = ui32Interrupt;' in hal and 'STIMER->STMINTCLR = ui32Interrupt;' in hal)
 o.mkdir(mode=0o700);(o/'layout.c').write_text(c);cmd=['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(o/'layout.c'),'-o',str(o/'layout.o')];r=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(o/'compiler.log').write_text(r.stdout+r.stderr);check('compiled-offsets',r.returncode==0)
 decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);cases=[]
 for key,bundle,pc in [('stock24','stock-2.4.0.24.bin',0x4a2d9a),('stock23','stock-2.3.0.24.bin',0x49d1d2),('cfw','faceclaw-38-research-only.bin',0x49d1d2)]:
  d=s/'pmic-ldsw-main-01'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-immutable-main',raw==(d/'main.bin').read_bytes())
  v=parse_log((d/'renode.log').read_text());check(key+'-saved-report',v==json.loads((d/'report.json').read_text())['observed']);ctx=v['register_context'];active=[x for x in v['guards'] if x['accesses']]
  check(key+'-attempted-enable-read',v['pc']==pc and ctx['r0']==1 and ctx['r1']==0x40008900 and len(active)==1 and active[0]['address']==0x40008900 and active[0]['operation']=='read' and active[0]['width']==4)
  start=pc-2;instructions=list(decoder.disasm(raw[start-0x438000:start-0x438000+10],start));check(key+'-rmw-instructions',[(x.mnemonic,x.op_str) for x in instructions]==[('ldr','r1, [pc, #0x30]'),('ldr','r2, [r1]'),('orrs','r0, r2'),('str','r0, [r1]'),('bx','lr')])
  literal=((start+4)&~3)+0x30;check(key+'-literal-address',struct.unpack_from('<I',raw,literal-0x438000)[0]==0x40008900)
  cases.append(dict(case=key,pc=pc,requested_mask=1,address=0x40008900,attempted_read_only=True,enable_write_observed=False,instructions=[dict(address=x.address,mnemonic=x.mnemonic,operands=x.op_str) for x in instructions]))
 (o/'inspector.py').write_bytes(Path(__file__).read_bytes());(o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,source_manifest=manifest,cases=cases,hardware_validated=False,boot_verified=False,scope='compiled public offset checks and saved original ARM read attempt; no guest/device execution or completed enable write'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
