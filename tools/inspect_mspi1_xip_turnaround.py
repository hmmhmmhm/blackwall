"""Verify source-supported XIP turnaround field and original ARM write request."""
import argparse,hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import parse_log
from pinned_main import load_pinned_main
from inspect_mspi1_config_contract import collect

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 h,regs=collect(s);r=next(x for x in regs if x['name']=='DEV0XIP');check('register-metadata',r['offset']==0x90 and r['mask']==0x3fffffd and r['reset']==0)
 root=ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot();p=next(x for x in root.findall('./peripherals/peripheral') if x.findtext('name')=='MSPI0');reg=next(x for x in p.findall('./registers/register') if x.findtext('name')=='DEV0XIP');fields={x.findtext('name'):x for x in reg.findall('./fields/field')};check('turnaround-range',fields['XIPTURNAROUND0'].findtext('bitRange')=='[19:14]');check('turnaround-qualified', 'XIPENTURN' in fields['XIPTURNAROUND0'].findtext('description'));check('delta-only-turnaround',(0x205ed^0x5ed)==(8<<14) and ((0x205ed>>14)&63)==8)
 root=s/'mspi1-source-research-01';raw=(root/'am_hal_mspi.c').read_bytes();pin=next(x for x in json.loads((root/'sources.json').read_text())['files'] if x['path'].endswith('/am_hal_mspi.c'));check('HAL-SHA',hashlib.sha256(raw).hexdigest()==pin['sha256']);check('HAL-blob',hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==pin['git_blob']);c=raw.decode()
 for n,t in [('mask-field','MSPI0_DEV0XIP_XIPTURNAROUND0_Msk'),('write-field','ui32Config |= _VAL2FLD(MSPI0_DEV0XIP_XIPTURNAROUND0, pConfig->ui8TurnAround);'),('write-register','MSPIn(ui32Module)->DEV0XIP = ui32Config;')]:check(n,t in c)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);cases=[]
 for key,bundle,pc in [('stock24','stock-2.4.0.24.bin',0x4e75d6),('stock23','stock-2.3.0.24.bin',0x4da202),('cfw','faceclaw-38-research-only.bin',0x4da202)]:
  d=s/'mspi1-pio-main-02'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-main-pin',raw==(d/'main.bin').read_bytes());log=(d/'renode.log').read_text();v=parse_log(log);check(key+'-saved-report',v==json.loads((d/'report.json').read_text())['observed']);g=[x for x in v['guards'] if x['accesses']];check(key+'-write-attempt',v['pc']==pc and len(g)==1 and g[0]['address']==0x40061090 and g[0]['value']==0x205ed and g[0]['operation']=='write' and v['register_context']['r2']==0x205ed)
  cfg=json.loads(next(x.split(' ',1)[1] for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_CONFIG ')))['registers'];check(key+'-prior-control',cfg['144']==0x5ed and cfg['128']==0x19);ins=list(md.disasm(raw[pc-0x438000:pc-0x438000+4],pc));check(key+'-store-instruction',len(ins)==1 and ins[0].mnemonic=='str.w' and ins[0].op_str=='r2, [r0, #0x90]');cases.append(dict(case=key,pc=pc,prior=0x5ed,requested=0x205ed,turnaround=8))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='metadata and original field write only; no XIP data, physical latency, flash or compatibility proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
