"""Observe original IOM7 address/FIFO request without attaching a peer or modifying guest state."""
import argparse,json,hashlib,subprocess,sys
from pathlib import Path
import capstone
from native_replay import parse_log,boundary_state
from pinned_main import load_pinned_main
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Use a fresh evidence directory')
 o.mkdir(mode=0o700);prior=s/'jedec-main-comparison-01';rows=[];cs=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS)
 for name in ('stock24','stock23','cfw'):
  old=json.loads((prior/name/'report.json').read_text());v=old['observed'];pc=v['pc'];raw=(prior/name/'main.bin').read_bytes();points=[('iom7-address',pc-0x198,'str.w','r0, [r1, #0x2c4]'),('iom7-fifo',pc-0x18,'str.w','r1, [r3, #0x10c]'),('iom7-command',pc,'str.w','r2, [r0, #0x120]')]
  for label,address,mn,op in points:
   ins=list(cs.disasm(raw[address-0x438000:address-0x438000+4],address))
   if len(ins)!=1 or ins[0].mnemonic!=mn or ins[0].op_str!=op:raise ValueError('Original observation instruction differs: '+label)
  # Descriptor source and FIFO source are bounded hypotheses from the saved ARM stack/registers.
  descriptor=v['stack_context']['base']+80;buffer=v['register_context']['r4']-4
  cmd=json.loads((prior/(name+'-launcher.json')).read_text())['command'];cmd[3]=str(o/name)
  for label,address,_,_ in points:cmd+=['--observe-pc',label+':'+hex(address)]
  cmd+=['--observe-sram','iom7-address:'+hex(descriptor)+':12','--observe-sram','iom7-fifo:'+hex(buffer)+':2']
  launch=subprocess.run(cmd,capture_output=True,text=True);(o/(name+'-launcher.json')).write_text(json.dumps(dict(command=cmd,returncode=launch.returncode,stdout=launch.stdout,stderr=launch.stderr),indent=2)+'\n')
  if launch.returncode:raise ValueError('Original observation failed: '+name)
  d=o/name;r=json.loads((d/'report.json').read_text());now=parse_log((d/'renode.log').read_text())
  if now!=r['observed'] or boundary_state(now)!=boundary_state(v):raise ValueError('Read-only observation changed endpoint')
  _,pinned=load_pinned_main(Path(cmd[2]).read_bytes())
  if pinned!=(d/'main.bin').read_bytes():raise ValueError('Original input differs')
  obs=r['execution_observation'];pm={x['label']:x for x in obs['points']};ev={x['sequence']:x for x in obs['events']};events={label:ev[pm[label]['first_sequence']] for label,_,_,_ in points}
  if any(pm[label]['hits']!=1 for label,_,_,_ in points):raise ValueError('Expected one address/FIFO/CMD attempt')
  if events['iom7-address']['r0']!=0x6b or events['iom7-command']['r0']!=0x40057000 or events['iom7-command']['r2']!=0x201:raise ValueError('Actual IOM7 request differs')
  desc=pm['iom7-address']['snapshot'];buf=pm['iom7-fifo']['snapshot']
  if desc['words'][0]!=0x6b or desc['words'][4]!=2 or desc['words'][6]!=buffer:raise ValueError('Actual descriptor layout differs')
  if events['iom7-fifo']['sequence']<=events['iom7-address']['sequence'] or events['iom7-command']['sequence']<=events['iom7-fifo']['sequence']:raise ValueError('Request observation order differs')
  iom=next(i for i in now['ioms'] if i['module']==7)
  if iom['commands']!=0 or iom['peer_attached'] or any(r[k] for k in ('installable','hardware_validated','boot_verified')):raise ValueError('Unexpected execution or completion claim')
  row=dict(name=name,points=[dict(label=l,address=hex(ad),instruction=mn+' '+op) for l,ad,mn,op in points],events=events,descriptor=desc,fifo_source=buf,fifo_available_bytes=events['iom7-fifo']['r0'],note='FIFO store operand is R1; current generic observer exposes R0/R2 only, payload bytes must be established from source RAM/decode')
  rows.append(row);print(json.dumps(row),flush=True)
 source=o/'source';source.mkdir(mode=0o700);data=Path(__file__).read_bytes();(source/Path(__file__).name).write_bytes(data)
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,source_sha256=hashlib.sha256(data).hexdigest(),scope='original address/FIFO/CMD attempt under existing mock personality; no peer response or physical device identity'),indent=2)+'\n')
if __name__=='__main__':main()
