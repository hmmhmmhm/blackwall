"""Inspect saved WREN requests, manufacturer WEL rules and actual original caller sequence."""
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from pypdf import PdfReader
from pinned_main import load_pinned_main
from native_replay import parse_log

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[];cases=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 research=s/'mspi1-pio-research-01';pdf=research/'mx25u25643g-v1.1.pdf';pin=json.loads((research/'datasheet-source.json').read_text());check('manufacturer-source-pin',hashlib.sha256(pdf.read_bytes()).hexdigest()==pin['sha256']);r=PdfReader(pdf);texts={n:r.pages[n-1].extract_text() for n in [24,25,36,90]}
 for n,t in texts.items():(o/f'datasheet-page-{n}.txt').write_text(t)
 t=' '.join(texts[24].split());check('WREN-command-sets-WEL','06h' in t and 'for setting Write Enable Latch (WEL) bit' in t and 'CS# goes low→sending WREN instruction code→ CS# goes high' in t)
 t=' '.join(texts[25].split());check('WEL-clear-on-WRDI-and-softreset','WRDI command completion' in t and 'Softreset command completion' in t and 'Power-up' in t)
 t=' '.join(texts[90].split());check('softreset-clears-volatile-only','All the volatile bits and settings will be cleared' in t and 'any other command to interrupt' in t)
 t=' '.join(texts[36].split());check('WEL-volatile-and-QE-nonvolatile','WEL bit. The Write Enable Latch (WEL) bit is a volatile bit' in t and 'Quad Enable (QE) bit is a non-volatile bit' in t)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
 for key,bundle,delta in [('stock24','stock-2.4.0.24.bin',0),('stock23','stock-2.3.0.24.bin',0x4d18),('cfw','faceclaw-38-research-only.bin',0x4d18)]:
  d=s/'mspi1-status-main-01'/(key+'-idle');_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-original-main',raw==(d/'main.bin').read_bytes());log=(d/'renode.log').read_text();v=parse_log(log);check(key+'-raw-report',v==json.loads((d/'report.json').read_text())['observed']);g=[x for x in v['guards'] if x['accesses']];check(key+'-command-only-request',len(g)==1 and g[0]['address']==0x40061000 and g[0]['value']==0xc1 and g[0]['operation']=='write');cfg=[json.loads(x.split(' ',1)[1])['registers'] for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_CONFIG ')];check(key+'-observed-WREN-config',len(cfg)==1 and cfg[0]['12']==6 and cfg[0]['132']==0x3010061);st=v['stack_context'];b=struct.pack('<32I',*st['words']);off=v['register_context']['r1']-st['base'];check(key+'-WREN-descriptor',off==36 and b[off:off+24]==bytes.fromhex('000000000000010000000000010006000000000000000000'))
  entry=0x47bbc0-delta;end=0x47bc1c-delta;code=list(md.disasm(raw[entry-0x438000:end-0x438000],entry));m={x.address:(x.mnemonic,x.op_str) for x in code};expected={0:('push','{r2, r3, r4, lr}'),2:('movs','r0, #0'),4:('str','r0, [sp]'),6:('movs','r3, #0'),8:('movs','r2, #0'),0xa:('movs','r1, #0'),0xc:('movs','r0, #6'),0xe:('bl','#'+hex(0x47b694-delta)),0x12:('movs','r4, r0'),0x14:('cmp','r4, #0'),0x16:('beq','#'+hex(entry+0x58)),0x58:('movs','r0, r4'),0x5a:('pop','{r1, r2, r4, pc}')};check(key+'-WREN-wrapper-transfer-result',all(m.get(entry+x)==pair for x,pair in expected.items()));check(key+'-actual-wrapper-and-caller-returns',st['words'][7]==0x47b725-delta and st['words'][21]==entry+0x13 and st['words'][25]==0x47ba69-delta)
  parent=0x47ba04-delta;code2=list(md.disasm(raw[parent-0x438000:parent+0x1b4-0x438000],parent));m2={x.address:(x.mnemonic,x.op_str) for x in code2};expected2={0:('push','{r2, r3, r4, lr}'),0x60:('bl','#'+hex(entry)),0x64:('movs','r4, r0'),0x66:('cmp','r4, #0'),0x68:('beq','#'+hex(parent+0xb2)),0xb2:('movs','r0, #0'),0xb4:('str','r0, [sp]'),0xb6:('movs','r3, #0'),0xb8:('movs','r2, #0'),0xba:('movs','r1, #0'),0xbc:('movs','r0, #0xb7'),0xbe:('bl','#'+hex(0x47b694-delta))};check(key+'-next-direct-command-B7',all(m2.get(parent+x)==pair for x,pair in expected2.items()));check(key+'-no-WEL-read-on-success-path',not any(x.mnemonic in ('bl','blx') for x in code2 if parent+0xb2<=x.address<parent+0xbe));(o/(key+'-WREN-and-caller.asm')).write_text('\n'.join(hex(x.address)+' '+x.mnemonic+' '+x.op_str for x in code+code2)+'\n');cases.append(dict(case=key,wrapper=hex(entry),caller=hex(parent),next_command=0xb7,WREN_completed=False,WEL_read_after_WREN_observed=False))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='manufacturer WEL contract and static original WREN/caller sequence; no new guest execution or physical state'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
