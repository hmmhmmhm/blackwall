"""Compare all two-bit synthetic ADC configs in original ARM getters; unknown registers remain strict."""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
import capstone
from native_replay import FILES,IMAGE,digest,validate_assets,parse_log,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def getter_layout(raw,signature):
 offsets=[];start=0
 while True:
  off=raw.find(signature,start)
  if off<0:break
  offsets.append(off);start=off+1
 if len(offsets)!=1:raise ValueError('Getter prefix not unique')
 entry=0x438000+offsets[0];c=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS);c.detail=True
 points=[('adc-entry',0,'push','{r3, r4, r5, lr}'),('adc-auto-store',0x26,'strb','r0, [r5]'),('adc-burst-store',0x32,'strb','r0, [r5, #1]'),('adc-cache-store',0x36,'strb','r0, [r4, #4]'),('adc-return',0x3a,'pop','{r1, r4, r5, pc}')]
 for label,delta,mn,op in points:
  ins=next(c.disasm(raw[offsets[0]+delta:offsets[0]+delta+4],entry+delta))
  if (ins.mnemonic,ins.op_str)!=(mn,op):raise ValueError('Getter store/return differs: '+label)
 load=next(c.disasm(raw[offsets[0]+0x16:offsets[0]+0x1a],entry+0x16));literal=((load.address+4)&~3)+load.operands[1].mem.disp
 status=struct.unpack_from('<I',raw,literal-0x438000)[0]
 instructions=[dict(address=hex(i.address),mnemonic=i.mnemonic,operands=i.op_str) for i in c.disasm(raw[offsets[0]:offsets[0]+0x3c],entry)]
 return entry,points,status,instructions

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Use a fresh evidence directory')
 base=s/'iom7-pointer-main-02';o.mkdir(mode=0o700);peer=(ROOT/'tools/renode-i2c-pointer-probe.cs').read_bytes();oldpeer=(s/'i2c-pointer-unit-01/peer.cs').read_bytes();(o/'peer.cs').write_bytes(peer);(o/'runner.py').write_bytes(Path(__file__).read_bytes())
 raw24=(base/'stock24/main.bin').read_bytes();signature=raw24[0x58098e-0x438000:0x58099c-0x438000];rows=[]
 plan=[('stock24-'+str(v),'stock24',v) for v in range(4)]+[('stock23-0','stock23',0),('cfw-0','cfw',0),('stock24-unknown','stock24',None)]
 for name,key,initial in plan:
  source=base/key;prior=json.loads((source/'report.json').read_text());raw=(source/'main.bin').read_bytes();entry,points,status,instructions=getter_layout(raw,signature)
  old=parse_log((source/'renode.log').read_text());_,pinned=load_pinned_main((s/'inputs/verified-01'/dict(stock24='stock-2.4.0.24.bin',stock23='stock-2.3.0.24.bin',cfw='faceclaw-38-research-only.bin')[key]).read_bytes())
  if pinned!=raw or old!=prior['observed'] or prior['image_id']!=IMAGE:raise ValueError('Frozen original base differs')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(source/f) for f in FILES}
  for f in FILES:shutil.copyfile(source/f,d/f)
  validate_assets(d,original);text=(d/'strict.cs').read_bytes()
  if not text.endswith(oldpeer):raise ValueError('Frozen pointer source suffix differs')
  (d/'strict.cs').write_bytes(text[:-len(oldpeer)]+peer)
  if initial is not None:(d/'board.repl').write_text((d/'board.repl').read_text()+'    adcConfig: '+str(initial)+'\n')
  for file in ('run.py','result.py'):
   text=(d/file).read_text()
   if file=='run.py':
    needle='    e.StartAll()';setup=''.join("    observer.AddPoint('"+label+"',"+str(entry+delta)+')\n' for label,delta,_,_ in points)
    if text.count(needle)!=1:raise ValueError('Ambiguous observer attachment')
    text=text.replace(needle,setup+needle).replace('pointer=int(peer.Pointer),writes=int(peer.Writes)','initial_config=int(peer.InitialAdcConfig),returned_reads=int(peer.ReturnedReads),pointer=int(peer.Pointer),writes=int(peer.Writes)')
   compile(text,file,'exec');(d/file).write_text(text)
  derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,initial_config=initial,old_peer_sha256=hashlib.sha256(oldpeer).hexdigest(),new_peer_sha256=hashlib.sha256(peer).hexdigest(),getter_entry=entry,success_status=status,instructions=instructions),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
  log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(name):
   items=[json.loads(x.split(name+' ',1)[1]) for x in log.splitlines() if x.startswith(name+' ')]
   if len(items)!=1:raise ValueError('Missing '+name)
   return items[0]
  state=marker('BLACKWALL_POINTER');obs=marker('BLACKWALL_OBSERVATION');pm={p['label']:p for p in obs['points']};events={e['sequence']:e for e in obs['events']};guard=[g for g in v['guards'] if g['accesses']]
  report=dict(name=name,initial_config=initial,getter_entry=hex(entry),success_status=hex(status),pointer=state,observed=v,observation=obs,image_id=IMAGE,raw_main_sha256=hashlib.sha256(raw).hexdigest(),selected_hypotheses=prior['selected_hypotheses'],additional_hypothesis='explicit synthetic config 0..3 at0509, no PMIC write/other address support',boot_verified=False,hardware_validated=False,installable=False)
  (d/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  if initial is None:
   if boundary_state(v)!=boundary_state(old) or state['returned_reads']!=0 or pm['adc-return']['hits']!=0:raise ValueError('Unknown default changed')
  else:
   if state['returned_reads']!=1 or state['finishes']!=2 or len(guard)!=1 or guard[0]['operation']!='peer-write-unsupported' or guard[0]['value']!=0x50a:raise ValueError('Unexpected post-config boundary')
   if any(pm[label]['hits']!=1 for label,_,_,_ in points):raise ValueError('Original getter did not return exactly once')
   expected={'adc-auto-store':initial&1,'adc-burst-store':(initial>>1)&1,'adc-cache-store':(initial>>1)&1,'adc-return':status}
   if any(events[pm[label]['first_sequence']]['r0']!=value for label,value in expected.items()):raise ValueError('Original bit extraction/cache/status differs')
  row=dict(name=name,initial_config=initial,pc=hex(v['pc']),peer=state,guard=guard,getter_return_hits=pm['adc-return']['hits']);rows.append(row);print(json.dumps(row),flush=True)
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='original two-bit config decode and natural getter return under explicit values; next address strict; not physical PMIC or full boot'),indent=2)+'\n')
if __name__=='__main__':main()
