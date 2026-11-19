"""Verify source-supported XIP mixed-mode field and original ARM write request."""
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
 root=ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot();p=next(x for x in root.findall('./peripherals/peripheral') if x.findtext('name')=='MSPI0');reg=next(x for x in p.findall('./registers/register') if x.findtext('name')=='DEV0XIP');fields={x.findtext('name'):x for x in reg.findall('./fields/field')};check('mixed-range',fields['XIPMIXED0'].findtext('bitRange')=='[11:8]');values={x.findtext('name'):int(x.findtext('value'),0) for x in fields['XIPMIXED0'].findall('./enumeratedValues/enumeratedValue')};check('documented-modes',values==dict(NORMAL=0,D2=1,AD2=3,D4=5,AD4=7,D8=9,AD8=11));check('delta-only-mixed',(0x205ed^0x200ed)==0x500 and ((0x205ed>>8)&15)==5 and ((0x200ed>>8)&15)==0)
 root=s/'mspi1-source-research-01';raw=(root/'am_hal_mspi.c').read_bytes();pin=next(x for x in json.loads((root/'sources.json').read_text())['files'] if x['path'].endswith('/am_hal_mspi.c'));check('HAL-SHA',hashlib.sha256(raw).hexdigest()==pin['sha256']);check('HAL-blob',hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==pin['git_blob']);c=raw.decode()
 for n,t in [('NORMAL-config-path','MSPIn(ui32Module)->DEV0XIP_b.XIPMIXED0    = MSPI0_CTRL1_PIOMIXED_NORMAL;'),('D4-config-path','MSPIn(ui32Module)->DEV0XIP_b.XIPMIXED0    = MSPI0_CTRL1_PIOMIXED_D4;'),('serial-device-path','case AM_HAL_MSPI_FLASH_SERIAL_CE0:')]:check(n,t in c)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);cases=[]
 for key,bundle,pc in [('stock24','stock-2.4.0.24.bin',0x4e683a),('stock23','stock-2.3.0.24.bin',0x4d9466),('cfw','faceclaw-38-research-only.bin',0x4d9466)]:
  d=s/'mspi1-xip-turnaround-main-01'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-main-pin',raw==(d/'main.bin').read_bytes());log=(d/'renode.log').read_text();v=parse_log(log);check(key+'-saved-report',v==json.loads((d/'report.json').read_text())['observed']);g=[x for x in v['guards'] if x['accesses']];check(key+'-write-attempt',v['pc']==pc and len(g)==1 and g[0]['address']==0x40061090 and g[0]['value']==0x200ed and g[0]['operation']=='write' and v['register_context']['r4']==0x200ed)
  cfg=json.loads(next(x.split(' ',1)[1] for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_CONFIG ')))['registers'];check(key+'-prior-control',cfg['144']==0x205ed and cfg['128']==0x19);ins=list(md.disasm(raw[pc-0x438000-6:pc-0x438000+2],pc-6));check(key+'-store-instruction',[(x.mnemonic,x.op_str) for x in ins]==[('ldr','r4, [r3]'),('bics','r4, r4, #0xf00'),('str','r4, [r3]')]);cases.append(dict(case=key,pc=pc,prior=0x205ed,requested=0x200ed,previous_mode=5,requested_mode=0))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='metadata and original field write only; no XIP data, physical latency, flash or compatibility proof'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
