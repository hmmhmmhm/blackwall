"""Observe original timer config arguments without accepting any PMIC timer command."""
import argparse,json,hashlib,struct,shutil
from pathlib import Path
import capstone
from native_replay import FILES,IMAGE,digest,validate_assets,parse_log,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def layout(raw,signature):
 off=raw.find(signature)
 if off<0 or raw.find(signature,off+1)>=0:raise ValueError('Timer config prefix not unique')
 entry=0x438000+off;c=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS);c.detail=True;calls=[]
 for x in range(0,len(raw)-4,2):
  a,b=struct.unpack_from('<HH',raw,x)
  if a&0xf800!=0xf000 or b&0xd000!=0xd000:continue
  s=(a>>10)&1;i1=1^((b>>13)&1)^s;i2=1^((b>>11)&1)^s;imm=s<<24|i1<<23|i2<<22|(a&1023)<<12|(b&2047)<<1
  if imm&(1<<24):imm-=1<<25
  if x+0x438004+imm==entry:calls.append(x+0x438000)
 if len(calls)!=1:raise ValueError('Timer config caller not unique')
 call=calls[0];ins=list(c.disasm(raw[call-18-0x438000:call+4-0x438000],call-18));expected=[('add','r0, sp, #0x14'),('ldr.w',None),('ldm.w','r1, {r2, r3, ip}'),('stm.w','r0, {r2, r3, ip}'),('add','r1, sp, #0x14'),('mov','r0, sb'),('bl',None)]
 if len(ins)!=len(expected) or any(i.mnemonic!=m or (op is not None and i.op_str!=op) for i,(m,op) in zip(ins,expected)):raise ValueError('Original profile copy/call differs')
 load=ins[1]
 if load.reg_name(load.operands[0].reg)!='r1' or load.reg_name(load.operands[1].mem.base)!='pc':raise ValueError('Profile literal differs')
 literal=((load.address+4)&~3)+load.operands[1].mem.disp;address=struct.unpack_from('<I',raw,literal-0x438000)[0]
 if not 0x438000<=address<=0x438000+len(raw)-12:raise ValueError('Profile not in pinned original')
 profile=list(struct.unpack_from('<III',raw,address-0x438000))
 return dict(entry=entry,caller=call,profile_address=address,profile=profile,call_instructions=[dict(address=hex(i.address),bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str) for i in ins],config_instructions=[dict(address=hex(i.address),bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str) for i in c.disasm(raw[off:off+0x66],entry)])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Use fresh evidence directory')
 o.mkdir(mode=0o700);base=s/'pmic-charger-main-01';raw24=(base/'stock24/main.bin').read_bytes();signature=raw24[0x580680-0x438000:0x58069e-0x438000];rows=[];(o/'runner.py').write_bytes(Path(__file__).read_bytes())
 for name in ['stock24','stock23','cfw']:
  src=base/name;prior=json.loads((src/'report.json').read_text());old=parse_log((src/'renode.log').read_text());raw=(src/'main.bin').read_bytes();sites=layout(raw,signature)
  file={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[name];_,pinned=load_pinned_main((s/'inputs/verified-01'/file).read_bytes())
  if pinned!=raw or old!=prior['observed'] or prior['image_id']!=IMAGE:raise ValueError('Frozen base differs')
  # Prior endpoint window contains the target at its first word. Verify the full live struct at entry.
  address=old['sram_windows'][0]['base']-8
  if not 0x20000000<=address<=0x20380000-12:raise ValueError('Argument snapshot outside SRAM')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(src/f) for f in FILES}
  for f in FILES:shutil.copyfile(src/f,d/f)
  validate_assets(d,original);text=(d/'run.py').read_text();needle='    e.StartAll()';setup="    observer.AddPoint('pmic-timer-config-entry',"+str(sites['entry'])+")\n    observer.CaptureSram(m,'pmic-timer-config-entry',"+str(address)+",3)\n"
  if text.count(needle)!=1:raise ValueError('Observer attachment differs')
  text=text.replace(needle,setup+needle);compile(text,'run.py','exec');(d/'run.py').write_text(text);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,sites=sites,snapshot_address=address),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived);obsrows=[json.loads(x.split('BLACKWALL_OBSERVATION ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_OBSERVATION ')]
  if len(obsrows)!=1:raise ValueError('Missing observation')
  obs=obsrows[0];point=next(x for x in obs['points'] if x['label']=='pmic-timer-config-entry')
  report=dict(name=name,observed=v,observation=obs,sites=sites,profile_snapshot=point['snapshot'],image_id=IMAGE,raw_main_sha256=digest(d/'main.bin'),physical_clock_verified=False,watchdog_started_observed=False,boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  if boundary_state(v)!=boundary_state(old) or point['hits']!=1 or point['snapshot']['words']!=sites['profile'] or sites['profile']!=[2,1,0x3c00]:raise ValueError('Original timer arguments or unchanged endpoint differ')
  row=dict(name=name,entry=hex(sites['entry']),profile=sites['profile'],live_profile=point['snapshot']['words'],candidate_timeout_ms=0x3c00*2,pc=hex(v['pc']));rows.append(row);print(json.dumps(row),flush=True)
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='original intended timer arguments/live stack, no timer command accepted or physical clock proof'),indent=2)+'\n')
if __name__=='__main__':main()
