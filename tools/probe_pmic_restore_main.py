"""Run original PMIC restore under a declared seven-byte read-only startup fixture."""
import argparse,json,hashlib,shutil,struct
from pathlib import Path
import capstone
from native_replay import FILES,IMAGE,digest,validate_assets,parse_log
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def sites(raw,signature):
 off=raw.find(signature)
 if off<0 or raw.find(signature,off+1)>=0:raise ValueError('Core init prefix not unique')
 entry=off+0x438000;c=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS);c.detail=True
 instructions=list(c.disasm(raw[off:off+800],entry));ret=next(i for i in instructions if i.mnemonic=='pop.w')
 if ret.op_str!='{r4, r5, r6, r7, r8, sb, sl, pc}':raise ValueError('Core init return differs')
 calls=[]
 for x in range(0,len(raw)-4,2):
  a,b=struct.unpack_from('<HH',raw,x)
  if a&0xf800!=0xf000 or b&0xd000!=0xd000:continue
  s=(a>>10)&1;i1=1^((b>>13)&1)^s;i2=1^((b>>11)&1)^s;imm=s<<24|i1<<23|i2<<22|(a&1023)<<12|(b&2047)<<1
  if imm&(1<<24):imm-=1<<25
  if 0x438000+x+4+imm==entry:calls.append(0x438000+x)
 if len(calls)!=1:raise ValueError('Core init caller not unique')
 call=calls[0];load=next(c.disasm(raw[call-10-0x438000:call-6-0x438000],call-10))
 if load.mnemonic!='ldr.w' or load.reg_name(load.operands[0].reg)!='r4' or load.reg_name(load.operands[1].mem.base)!='pc':raise ValueError('Caller PMIC instance literal differs')
 address=((load.address+4)&~3)+load.operands[1].mem.disp;instance=struct.unpack_from('<I',raw,address-0x438000)[0]
 if not 0x20000000<=instance<=0x20380000-0xd0:raise ValueError('Instance not mapped G2 SRAM')
 ldr=next(i for i in instructions if i.address==ret.address-4)
 if ldr.mnemonic!='ldr' or ldr.reg_name(ldr.operands[0].reg)!='r0' or ldr.reg_name(ldr.operands[1].mem.base)!='pc':raise ValueError('Init success literal differs')
 lit=((ldr.address+4)&~3)+ldr.operands[1].mem.disp;success=struct.unpack_from('<I',raw,lit-0x438000)[0]
 return dict(entry=entry,ret=ret.address,caller=call+4,instance=instance,success=success,instructions=[dict(address=hex(i.address),bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str) for i in instructions if i.address<=ret.address])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Use fresh evidence directory')
 base=s/'iom7-pointer-main-02';o.mkdir(mode=0o700);peer=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();(o/'peer.cs').write_bytes(peer);(o/'runner.py').write_bytes(Path(__file__).read_bytes());raw24=(base/'stock24/main.bin').read_bytes();sig=raw24[0x57fdae-0x438000:0x57fdbc-0x438000];rows=[]
 for name in ('stock24','stock23','cfw'):
  src=base/name;prior=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text());raw=(src/'main.bin').read_bytes();points=sites(raw,sig)
  file={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[name];_,pinned=load_pinned_main((s/'inputs/verified-01'/file).read_bytes())
  if pinned!=raw or prior['observed']!=v0 or prior['image_id']!=IMAGE:raise ValueError('Frozen source differs')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(src/f) for f in FILES}
  for f in FILES:shutil.copyfile(src/f,d/f)
  validate_assets(d,original);(d/'strict.cs').write_bytes((d/'strict.cs').read_bytes()+b'\n'+peer)
  text=(d/'board.repl').read_text();old='pointerProbe: Miscellaneous.BlackwallI2cPointerProbe @ iom7 0x6b\n'
  if text.count(old)!=1:raise ValueError('Pointer attachment differs')
  (d/'board.repl').write_text(text.replace(old,'pointerProbe: Miscellaneous.BlackwallPmicRestoreProbe @ iom7 0x6b\n    profile: "source-reset-readonly"\n'))
  text=(d/'run.py').read_text();needle='    e.StartAll()';setup=''
  for label,key in [('pmic-init-entry','entry'),('pmic-init-return','ret'),('pmic-init-caller','caller')]:setup+="    observer.AddPoint('"+label+"',"+str(points[key])+')\n'
  setup+="    observer.CaptureSram(m,'pmic-init-return',"+str(points['instance']+8)+",3)\n    observer.CaptureSram(m,'pmic-init-caller',"+str(points['instance']+0xc0)+",4)\n"
  if text.count(needle)!=1:raise ValueError('Observer boundary differs')
  text=text.replace(needle,setup+needle);lines=text.splitlines();marker=[n for n,l in enumerate(lines) if "Console.WriteLine('BLACKWALL_POINTER " in l]
  if len(marker)!=1:raise ValueError('Peer diagnostic differs')
  lines[marker[0]]="    Console.WriteLine('BLACKWALL_PMIC_RESTORE '+json.dumps(dict(pointer=int(peer.Pointer),pointer_writes=int(peer.PointerWrites),data_reads=int(peer.DataReads),returned_bytes=int(peer.ReturnedBytes),finishes=int(peer.Finishes),blocked=int(peer.AccessCount),operation=str(peer.LastOperation),requested_length=int(peer.LastWidth),requested_value=int(peer.LastValue),read_addresses=[int(v) for v in peer.ReadAddresses],read_values=[int(v) for v in peer.ReadValues])))"
  text='\n'.join(lines)+'\n';compile(text,'run.py','exec');(d/'run.py').write_text(text);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,profile='source-reset-readonly',points=points),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(name):
   records=[json.loads(x.split(name+' ',1)[1]) for x in log.splitlines() if x.startswith(name+' ')]
   if len(records)!=1:raise ValueError('Missing '+name)
   return records[0]
  state=marker('BLACKWALL_PMIC_RESTORE');obs=marker('BLACKWALL_OBSERVATION');pm={p['label']:p for p in obs['points']};ev={e['sequence']:e for e in obs['events']};report=dict(name=name,profile='source-reset-readonly',observed=v,peer=state,observation=obs,points=points,image_id=IMAGE,raw_main_sha256=digest(d/'main.bin'),selected_hypotheses=prior['selected_hypotheses'],boot_verified=False,hardware_validated=False,installable=False)
  (d/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  if state['read_addresses']!=[0x509,0x50a,0x308,0x30a,0xb04] or state['read_values']!=[0,1,8,0x1cf,3]:raise ValueError('Original restore requests differ')
  if any(pm[l]['hits']!=1 for l in ['pmic-init-entry','pmic-init-return','pmic-init-caller']):raise ValueError('Full original init did not return')
  if ev[pm['pmic-init-caller']['first_sequence']]['r0']!=points['success'] or (pm['pmic-init-caller']['snapshot']['words'][3]>>8)&255!=1:raise ValueError('Original return status or restored flag differs')
  row=dict(name=name,pc=hex(v['pc']),peer=state,init_success=hex(points['success']),init_return_observed=True,adc_cache_snapshot=pm['pmic-init-return']['snapshot'],restore_flag_snapshot=pm['pmic-init-caller']['snapshot']);rows.append(row);print(json.dumps(row),flush=True)
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='original PMIC restore init under declared seven-byte read-only fixture; not full boot or physical device'),indent=2)+'\n')
if __name__=='__main__':main()
