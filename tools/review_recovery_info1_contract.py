"""Derive recovery initialization inputs and a bounded B0 alternative from pinned sources."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
def read(p):return json.loads(p.read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def body(s,token):
 st=s.index(token);a=s.index('{',st);end=a+1;n=1
 while n:n+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[a:end]

def run(output):
 output=Path(output).resolve()
 if output.exists() or not output.is_relative_to(PRIVATE):raise ValueError('Fresh private analysis output required')
 s=PRIVATE/'simulator';hal=s/'upstream/hal-ambiq-61b293a';info=s/'info-read-copy-research-01';research=s/'recovery-info1-research-bw575-01';tree_path=s/'gaf-delay-clock-research-01/upstream-tree.json';tree=read(tree_path);blobs={r['path']:r['sha'] for r in tree['tree']};checks={};sources={}
 selected={**{f'mcu/apollo510/hal/{n}':hal/n for n in ('am_hal_spotmgr.c','am_hal_spotmgr.h','am_hal_spotmgr_pcm2_1.c','am_hal_spotmgr_pcm2_2.c')},'mcu/apollo510/hal/mcu/am_hal_mcuctrl.h':research/'am_hal_mcuctrl.h','mcu/apollo510/hal/am_hal_spotmgr_pcm0_7.c':research/'am_hal_spotmgr_pcm0_7.c',**{f'mcu/apollo510/regs/{n}':info/n for n in ('am_mcu_apollo510_mraminfo1.h','am_mcu_apollo510_otpinfo1.h')}}
 for path,f in selected.items():
  b=f.read_bytes();blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();checks[path+'_blob']=blob==blobs[path];sources[path]=dict(local=str(f),sha256=sha(b),blob_sha1=blob)
 mram=(info/'am_mcu_apollo510_mraminfo1.h').read_text();otp=(info/'am_mcu_apollo510_otpinfo1.h').read_text();info_c=(info/'am_hal_info.c').read_text();offsets={k:int(v,16) for k,v in re.findall(r'#define AM_REG_INFO1_(\w+)_O\s+(0x\w+)',mram)};addresses={k:int(v,16) for k,v in re.findall(r'#define AM_REG_INFO1_(\w+)_ADDR\s+(0x\w+)',mram)};otp_offsets={k:int(v,16) for k,v in re.findall(r'#define AM_REG_OTP_INFO1_(\w+)_O\s+(0x\w+)',otp)}
 checks['info_offset_translation']= 'ui32wordOffset + (0xA00 / 4)' in info_c and all(offsets[k]==otp_offsets[k]+0xa00 and addresses[k]==0x42002000+offsets[k] for k in ('POWERSTATE0','L_TRIMCODE','E_TRIMCODE','GPUVDDCTON','MEMLDOCONFIG'))
 layouts={}
 for pcm,total in [('2_1',23),('2_2',28)]:
  text=(hal/f'am_hal_spotmgr_pcm{pcm}.c').read_text();init=body(text,f'am_hal_spotmgr_pcm{pcm}_init(void)');calls=re.findall(r'RD_INFO1\(AM_HAL_INFO_INFOSPACE_CURRENT_INFO1,\s*\(AM_REG_OTP_INFO1_(\w+)_O\s*/\s*4\),\s*(\d+)',init)
  layouts[pcm]=[dict(name=name,address=hex(addresses[name]),words=int(n),bytes=int(n)*4) for name,n in calls];checks[pcm+'_source_reads']=len(calls)==5 and sum(int(n) for _,n in calls)==total
 native={}
 for trim in (1,2):
  d=s/f'upstream23-current-trim{trim}-native-bw559-01';r=read(d/'report.json');m=read(d/'manifest.json');regs=r['registers'];g=next(x for x in r['guards'] if x['accesses'])
  checks[f'trim{trim}_actual_first_request']=r['pc']==0x48 and regs[:3]==[0x42003370,0x20026ba4,16 if trim==1 else 20] and g['address']==0x42003370 and g['operation']=='read' and g['width']==4 and r['cfsr']==r['hfsr']==r['policy']==0
  checks[f'trim{trim}_frozen_sources']=all(sha((d/n).read_bytes())==h for n,h in m['components'].items())
  native[str(trim)]=dict(source=hex(regs[0]),destination=hex(regs[1]),remaining_words=regs[2],first_read_width=g['width'],report_sha256=sha((d/'report.json').read_bytes()),full_table_read_completed=False)
 checks['powerstate_request_lengths_match_source']=all(layouts['2_'+str(t)][0]['words']==native[str(t)]['remaining_words'] for t in (1,2))
 zero=(research/'am_hal_spotmgr_pcm0_7.c').read_text();init=body(zero,'am_hal_spotmgr_pcm0_7_init(void)');update=body(zero,'am_hal_spotmgr_pcm0_7_ton_config_update(bool');spot=(hal/'am_hal_spotmgr.c').read_text();block=body(spot,'else if (APOLLO5_B0_PCM0P7)')
 checks['b0_init_no_calibration_reads']='return AM_HAL_STATUS_SUCCESS;' in init and 'am_hal_info1_read' not in init
 checks['b0_tempco_slots_unassigned']='pfnSpotMgrTempcoPostponeSet' not in block and 'pfnSpotMgrTempcoPendingHandle' not in block and 'pfnSpotmgrInit = am_hal_spotmgr_pcm0_7_init;' in block
 html_path=hal/'mcuctrl_regs.html';html=html_path.read_text();header=(hal/'apollo510.h').read_text();registers={}
 for reg in ('SIMOBUCK1','SIMOBUCK2','SIMOBUCK4','SIMOBUCK6','SIMOBUCK7'):
  at=html.index('<h3 id="'+reg+'"');end=html.find('<h3 id=',at+1);text=html[at:end];reset=0;fields={}
  for name,value in re.findall(r'colspan="\d+">([A-Z0-9_]+)\s*<br>(0x[0-9a-fA-F]+)',text):
   if name.startswith('RSVD') or name.startswith('RESVD'):continue
   if int(value,16)==0:continue
   prefix='MCUCTRL_'+reg+'_'+name;position=int(re.search(r'#define '+prefix+r'_Pos\s+\((\d+)UL\)',header).group(1));mask=int(re.search(r'#define '+prefix+r'_Msk\s+\((0x\w+)UL\)',header).group(1),16);value=int(value,16)<<position
   if value&~mask:raise ValueError('Invalid public reset field')
   reset|=value
  for field in re.findall(r'MCUCTRL->'+reg+r'_b\.(\w+)\s*=',update):fields[field]=hex(int(re.search(r'#define MCUCTRL_'+reg+'_'+field+r'_Msk\s+\((0x\w+)UL\)',header).group(1),16))
  registers[reg]=dict(address=re.search(r'0x4002[0-9a-fA-F]{4}',text).group(0),source_reset=hex(reset),source_written_field_masks=fields)
 checks['b0_ton_behavior_group']=registers['SIMOBUCK1']['source_reset']=='0x400000' and sum(len(v['source_written_field_masks']) for v in registers.values())==7
 d=s/'upstream23-b0-pcm07-native-bw575-01';r=read(d/'report.json');m=read(d/'manifest.json');guards=[g for g in r['guards'] if g['accesses']]
 checks['b0_actual_frontier']=m['synthetic_chip_revision']==0x21 and m['synthetic_trim']==1 and not m['physical_chip_revision_observed'] and r['pc']==0x42f878 and len(guards)==1 and guards[0]['address']==0x40020340 and guards[0]['operation']=='read' and r['images_unchanged'] and not r['scope']['worker_entered'] and r['cfsr']==r['hfsr']==r['policy']==0
 checks['b0_sources_pinned']=all(sha((d/n).read_bytes())==h for n,h in m['components'].items())
 old=s/'upstream23-current-trim1-native-bw559-01';checks['b0_input_only_revision_delta']=(d/'strict.cs').read_bytes()==(old/'strict.cs').read_bytes() and (d/'run.py').read_bytes()==(old/'run.py').read_bytes() and (d/'board.repl').read_text()==(old/'board.repl').read_text().replace('    chipRevision: 35\n','    chipRevision: 33\n')
 boot=PRIVATE/'recovery/boot-2-4-analysis/boot-2.3.2.14.bin';b=boot.read_bytes();decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);witness=[dict(pc=hex(i.address),mnemonic=i.mnemonic,operands=i.op_str,bytes=bytes(i.bytes).hex()) for i in decoder.disasm(b[0x42f878-0x410000:0x42f880-0x410000],0x42f878)]
 checks['b0_original_hp_gate_witness']=[(i['mnemonic'],i['operands']) for i in witness]==[('ldr','r3, [r2]'),('orrs','r3, r3, #0x80000000'),('str','r3, [r2]')]
 result=dict(passed=all(checks.values()),checks=checks,source_commit='61b293a49db34030c545f99101f7ebf6a3050314',sources=sources,cached_tree_sha256=sha(tree_path.read_bytes()),public_info1_requests=layouts,original_first_requests=native,actual_calibration_values_available=False,source_layout_is_not_binary_abi_proof=True,b0_ton_contract=registers,b0_original_witness=witness,b0_worker_entered=False,hardware_compatibility_verified=False,authentication_verified=False,scope='Source contract and one new synthetic B0/trim1 original boot frontier; no NVM fill or callback/code rewrite')
 output.mkdir(parents=True,mode=0o700);shutil.copy2(__file__,output/'audit-source.py');(output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('INFO1/source contract review failed')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();run(a.output)
