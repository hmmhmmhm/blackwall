"""Inspect saved post-scan RX3 requests and zero-turnaround configuration without replay."""
import argparse,hashlib,json,re,struct,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from pypdf import PdfReader
from inspect_mspi1_config_contract import collect
from native_replay import parse_log
from pinned_main import load_pinned_main
CASES=[('stock24','stock-2.4.0.24.bin','mspi1-ideal-sampling-main-01',0),('stock23','stock-2.3.0.24.bin','mspi1-ideal-sampling-main-04',0x4d18),('cfw','faceclaw-38-research-only.bin','mspi1-ideal-sampling-main-04',0x4d18)]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[];rows=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 collect(s)
 root=ET.fromstring((s/'apollo-dfp-research-01/apollo510.svd').read_bytes());per=next(x for x in root.findall('./peripherals/peripheral') if x.findtext('name')=='MSPI0');reg=next(x for x in per.findall('./registers/register') if x.findtext('name')=='DEV0CFG')
 fields={}
 for f in reg.findall('./fields/field'):
  high,low=map(int,re.fullmatch(r'\[(\d+):(\d+)\]',f.findtext('bitRange')).groups());fields[f.findtext('name')]=(low,((1<<(high-low+1))-1)<<low)
 check('turnaround-layout',fields['TURNAROUND0']==(8,0x3f00))
 before=0x3010861;after=0x3010061
 check('configuration-delta-only-turnaround',before^after==0x800 and ((before&0x3f00)>>8)==8 and (after&0x3f00)==0)
 research=s/'mspi1-pio-research-01';pin=json.loads((research/'datasheet-source.json').read_text());pdf=research/'mx25u25643g-v1.1.pdf';check('manufacturer-PDF-pin',hashlib.sha256(pdf.read_bytes()).hexdigest()==pin['sha256']);text=PdfReader(pdf).pages[26].extract_text();check('RDID-text-preserved',text==(research/'datasheet-page-27.txt').read_text());flat=' '.join(text.split());check('manufacturer-RDID-immediate-ID-sequence','sending RDID instruction code→24-bits ID data out' in flat and 'SPI mode only' in flat)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
 for key,bundle,folder,delta in CASES:
  d=s/folder/key;log=(d/'renode.log').read_text();r=json.loads((d/'report.json').read_text());v=parse_log(log);check(key+'-saved-report',r['passed'] and v==r['observed']);_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-original-main',raw==(d/'main.bin').read_bytes());q=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_CONFIG ')];check(key+'-config-marker',len(q)==1);cfg=q[0]['registers'];check(key+'-post-scan-configuration',cfg['132']==after and cfg['12']==0x9f and cfg['144']==0xed and cfg['4']==0)
  g=[x for x in v['guards'] if x['accesses']];check(key+'-strict-RX3-request',len(g)==1 and g[0]['address']==0x40061000 and g[0]['value']==0x30441 and g[0]['operation']=='write' and v['pc']==0x4e8a46-(0 if key=='stock24' else 0xd3d4))
  st=v['stack_context'];stack=struct.pack('<32I',*st['words']);offset=v['register_context']['r1']-st['base'];check(key+'-descriptor-bounds',offset==36 and len(stack)>=offset+24);desc=stack[offset:offset+24];prior=json.loads((s/'mspi1-xip-mixed-main-01'/key/'report.json').read_text())['observed'];ps=prior['stack_context'];pb=struct.pack('<32I',*ps['words']);po=prior['register_context']['r1']-ps['base'];check(key+'-same-descriptor-contract',desc[:20]==pb[po:po+20]);check(key+'-RX3-instruction-no-address',struct.unpack_from('<I',desc)[0]==3 and desc[6]==0 and desc[7]==0 and desc[12]==1 and struct.unpack_from('<H',desc,14)[0]==0x9f and desc[16]==1);buffer=struct.unpack_from('<I',desc,20)[0];check(key+'-bounded-RX-buffer',buffer%4==0 and st['base']<=buffer<=st['base']+124)
  points={x['label']:x for x in r['selected_observation']['points']};ev=[x for x in r['selected_observation']['events'] if x['label']=='scan-return'];check(key+'-native-scan-return',len(ev)==1 and ev[0]['r0']==0 and points['scan-return']['hits']==1 and r['selection']=='010000010e20' and r['sampling']['id_frames']==1152)
  entry=0x47b5e0-delta;ret=0x47b66c-delta;code={x.address:(x.mnemonic,x.op_str) for x in md.disasm(raw[entry-0x438000:ret+2-0x438000],entry)};check(key+'-descriptor-function-entry',code.get(entry)==('push.w','{r3, r4, r5, r6, r7, r8, lr}') and code.get(entry+4)==('sub','sp, #0x1c'));check(key+'-descriptor-call-site',code.get(ret-4)==('bl','#'+hex(0x4e8944-(0 if key=='stock24' else 0xd3d4))) and st['words'][7]==ret+1)
  rows.append(dict(case=key,configuration=hex(after),decoded_fields={name:(after&mask)>>low for name,(low,mask) in fields.items()},descriptor=desc.hex(),buffer=hex(buffer),RX_attempted=True,RX_completed=False,physical_validated=False))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=rows,scope='saved original post-scan RDID request and manufacturer protocol; no new native execution, physical timing or full boot proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
