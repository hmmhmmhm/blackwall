"""Audit original PIO reset request, call chain, pinned HAL and flash engine limitations."""
import argparse,hashlib,json,struct,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from pypdf import PdfReader
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main
from inspect_mspi1_config_contract import collect

def sha(b):return hashlib.sha256(b).hexdigest()
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);checks=[];research=s/'mspi1-pio-research-01'
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 pins=json.loads((s/'mspi1-source-research-01/sources.json').read_text());hal={}
 for name in ['am_hal_mspi.c','am_hal_mspi.h']:
  raw=(s/'mspi1-source-research-01'/name).read_bytes();pin=next(x for x in pins['files'] if x['path'].endswith('/'+name));check(name+'-SHA',sha(raw)==pin['sha256']);check(name+'-gitblob',blob(raw)==pin['git_blob']);hal[name]=raw.decode()
 c=hal['am_hal_mspi.c'];start=c.index('am_hal_mspi_blocking_transfer(');end=c.index('am_hal_mspi_nonblocking_transfer(',start);f=c[start:end]
 for name,needle in [('start','ui32Control |= _VAL2FLD(MSPI0_CTRL_START, 1);'),('instruction','_VAL2FLD(MSPI0_INSTR_INSTR, pTransaction->ui16DeviceInstr);'),('length','_VAL2FLD(MSPI0_CTRL_XFERBYTES, pTransaction->ui32NumBytes);'),('submit','MSPIn(ui32Module)->CTRL = ui32Control;'),('completion','MSPI0_CTRL_STATUS_Msk,'),('restore-interrupts','MSPIn(ui32Module)->INTEN = intMask;')]:check('HAL-'+name,needle in f)
 h,_=collect(s);root=ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot();per=next(x for x in root.findall('./peripherals/peripheral') if x.findtext('name')=='MSPI0');ctrl=next(x for x in per.findall('./registers/register') if x.findtext('name')=='CTRL');fields={x.findtext('name'):x for x in ctrl.findall('./fields/field')};check('CTRL-offset-reset',int(ctrl.findtext('addressOffset'),0)==0 and int(ctrl.findtext('resetValue'),0)==0)
 for n,r in [('START','[0:0]'),('STATUS','[1:1]'),('BUSY','[2:2]'),('SENDI','[6:6]'),('TXRX','[7:7]'),('XFERBYTES','[31:16]')]:check('CTRL-'+n,fields[n].findtext('bitRange')==r)
 check('status-W1C-source','Cleared by writing 1' in fields['STATUS'].findtext('description'))
 for pin in json.loads((research/'renode-sources.json').read_text())['files']:
  raw=(research/Path(pin['path']).name).read_bytes();check(Path(pin['path']).name+'-SHA',sha(raw)==pin['sha256']);check(Path(pin['path']).name+'-blob',blob(raw)==pin['git_blob'])
 engine=(research/'GenericSpiFlash.cs').read_text();a0=engine.index('case (byte)Commands.ResetEnable:');b0=engine.index('default:',a0);check('upstream-reset-unimplemented','Commands.ResetMemory' in engine[a0:b0] and 'Unhandled parameterless command' in engine[a0:b0]);check('upstream-backing-fill','underlyingMemory.ResetByte = EmptySegment;' in engine)
 pin=json.loads((research/'datasheet-source.json').read_text());raw=(research/'mx25u25643g-v1.1.pdf').read_bytes();check('datasheet-preserved',raw.startswith(b'%PDF') and sha(raw)==pin['sha256'] and len(raw)==pin['size']);pdf=PdfReader(research/'mx25u25643g-v1.1.pdf');text=pdf.pages[89].extract_text();check('datasheet-page90-match',text==(research/'datasheet-page-90.txt').read_text());check('datasheet-reset-prerequisite','Reset-Enable (RSTEN)' in text and 'must be executed first' in text);check('datasheet-interruption-invalidates','Reset-Enable will' in text and 'be invalid' in text);check('datasheet-recovery-varies','reset time is different depending on the last operation' in text)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);cases=[]
 def instructions(raw,pc,length):return list(md.disasm(raw[pc-0x438000:pc-0x438000+length],pc))
 for key,bundle,pio,wrapper,reset,pc in [('stock24','stock-2.4.0.24.bin',0x4e8944,0x47b694,0x47b3d4,0x4e8a46),('stock23','stock-2.3.0.24.bin',0x4db570,0x47697c,0x4766bc,0x4db672),('cfw','faceclaw-38-research-only.bin',0x4db570,0x47697c,0x4766bc,0x4db672)]:
  d=s/'mspi1-clear-all-main-01'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-original-bytes',raw==(d/'main.bin').read_bytes());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);log=(d/'renode.log').read_text();v=parse_log(log);check(key+'-saved-report',v==json.loads((d/'report.json').read_text())['observed']);check(key+'-PIO-start',v['pc']==pc and v['register_context']['r14']==0xc1)
  st=v['stack_context'];data=struct.pack('<32I',*st['words']);offset=v['register_context']['r1']-st['base'];check(key+'-live-descriptor-bound',offset==36 and len(data)>=offset+24);desc=data[offset:offset+24];check(key+'-live-descriptor',desc==bytes.fromhex('000000000000010000000000010066000000000000000000'))
  entry=instructions(raw,pio,4)[0];pop=instructions(raw,pio+0x168,4)[0];check(key+'-frame-layout',entry.mnemonic=='push.w' and entry.op_str=='{r2, r3, r4, r5, r6, r7, r8, lr}' and pop.mnemonic=='pop.w' and pop.op_str=='{r1, r2, r4, r5, r6, r7, r8, pc}')
  frame=instructions(raw,wrapper,6);endframe=instructions(raw,wrapper+0xaa,6);check(key+'-wrapper-frame',[(x.mnemonic,x.op_str) for x in frame]==[('push.w','{r4, r5, r6, r7, r8, sb, lr}'),('sub','sp, #0x1c')] and [(x.mnemonic,x.op_str) for x in endframe]==[('add','sp, #0x1c'),('pop.w','{r4, r5, r6, r7, r8, sb, pc}')])
  ret=st['words'][7]&~1;call=instructions(raw,ret-4,4)[0];check(key+'-caller-BL',call.mnemonic=='bl' and call.op_str==hex(pio).replace('0x','#0x'));outer=st['words'][21]&~1;call=instructions(raw,outer-4,4)[0];check(key+'-reset-caller-BL',call.mnemonic=='bl' and call.op_str=='#'+hex(wrapper));check(key+'-reset-frame-return',outer==reset+0x12)
  seq=instructions(raw,reset,0x70);pairs=[(x.mnemonic,x.op_str) for x in seq];check(key+'-reset-enable-then-reset',('movs','r0, #0x66') in pairs and ('movs','r0, #0x99') in pairs and pairs.index(('movs','r0, #0x66'))<pairs.index(('movs','r0, #0x99')))
  wait=instructions(raw,pio+0x146,0x16);wpairs=[(x.mnemonic,x.op_str) for x in wait];check(key+'-status-mask2-call',('movs','r3, #2') in wpairs and ('movs','r2, #2') in wpairs and any(x.mnemonic=='bl' for x in wait))
  target=int(next(x.op_str[1:] for x in wait if x.mnemonic=='bl'),0);helper=instructions(raw,target,0x44);hp=[(x.mnemonic,x.op_str) for x in helper];check(key+'-polling-helper',('ldr','r0, [r6]') in hp and ('ands','r0, r7') in hp and ('cmp','r0, r8') in hp and ('movs','r0, #4') in hp and any(x.mnemonic=='bne' and int(x.op_str[1:],0)<x.address for x in helper))
  cfg=json.loads(next(x.split(' ',1)[1] for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_CONFIG ')))['registers'];check(key+'-instruction-config',cfg['12']==0x66 and cfg['132']==0x1410061)
  cases.append(dict(case=key,pc=pc,descriptor=desc.hex(),pio_entry=pio,wrapper_entry=wrapper,reset_entry=reset,saved_return=ret,outer_return=outer,reset_code=[dict(address=x.address,mnemonic=x.mnemonic,operands=x.op_str) for x in seq],scope='descriptor and first66 attempt observed; later99 path is static only'))
 (o/'report.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks,cases=cases,hardware_validated=False,PIO_executed=False,boot_verified=False,scope='stored original ARM and primary sources; no new guest execution, wire transmission, reset completion, or backing'),indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))
if __name__=='__main__':main()
