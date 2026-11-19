"""Observe original sampling scan with frozen models; no new peripheral behavior or guest writes."""
import argparse,json,shutil,struct,hashlib
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_REG_PC,ARM_OP_MEM
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_LR,UC_ARM_REG_SP,UC_ARM_REG_PC
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute

def metadata(raw,delta):
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True;scan=0x47ab18-delta
 anchored=list(md.disasm(raw[scan-0x438000:scan-0x438000+0x270],scan));by_address={x.address:x for x in anchored}
 if (anchored[0].mnemonic,anchored[0].op_str)!=('push.w','{r3, r4, r5, r6, r7, r8, lr}'):raise ValueError('Scan entry differs')
 if any(scan+off not in by_address for off in [0,4,6,8,0x6e,0x90]):raise ValueError('Observer is not on an instruction boundary')
 if scan+0x86 in by_address or (by_address[scan+0x6c].mnemonic,by_address[scan+0x6c].op_str)!=('movs','r0, #6'):raise ValueError('Table stride must be decoded from function entry')
 expected={0x3e:('cmp','r0, #0'),0x40:('bne','#'+hex(scan+0x5c)),0x48:('cmp','r0, #2'),0x4a:('beq','#'+hex(scan+0x5c)),0x52:('movs','r2, #1'),0x54:('lsls','r2, r7'),0x56:('orrs','r1, r2'),0x58:('str.w','r1, [r0, r6, lsl #2]'),0xbc:('bl','#'+hex(0x47aa76-delta)),0x1e0:('bl','#'+hex(0x47aa8a-delta)),0x266:('movs','r0, #0')}
 if any(addr not in by_address or (by_address[addr].mnemonic,by_address[addr].op_str)!=pair for addr,pair in ((scan+off,pair) for off,pair in expected.items())):raise ValueError('Scan acceptance/selection/return code differs')
 ins=next(md.disasm(raw[scan+0x6e-0x438000:scan+0x6e-0x438000+4],scan+0x6e));operand=ins.operands[1]
 if operand.type!=ARM_OP_MEM or operand.mem.base!=ARM_REG_PC:raise ValueError('Expected table literal')
 literal=((ins.address+4)&~3)+operand.mem.disp;table=struct.unpack_from('<I',raw,literal-0x438000)[0]
 if not 0x20000000<=table<=0x20380000-216:raise ValueError('Table must be bounded RAM')
 classifier=0x47a846-delta
 classifier_code=list(md.disasm(raw[classifier-0x438000:classifier-0x438000+0x32],classifier));returns={x.address:x for x in classifier_code}
 if classifier+0x30 not in returns or (returns[classifier+0x30].mnemonic,returns[classifier+0x30].op_str)!=('bx','lr'):raise ValueError('Classifier result hook must be the actual return instruction')
 coarse=list(md.disasm(raw[scan+0x20-0x438000:scan+0x6a-0x438000],scan+0x20));pairs=[(x.mnemonic,x.op_str) for x in coarse]
 if ('movs','r5, #0x24') not in pairs or ('cmp','r0, #0x20') not in pairs:raise ValueError('Expected 36x32 scan limits')
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.mem_map(0x438000,(len(raw)+4095)&~4095);u.mem_write(0x438000,raw);u.mem_map(0x10000,0x1000);u.mem_map(0x20000000,0x1000);results=[]
 for value,expected in [(0xc22539,0),(0x123456,2),(0x3925c2,2),(0x253900,0)]:
  u.reg_write(UC_ARM_REG_R0,value);u.reg_write(UC_ARM_REG_LR,0x10001);u.reg_write(UC_ARM_REG_SP,0x20001000);u.emu_start(classifier|1,0x10000,count=1000);result=u.reg_read(UC_ARM_REG_R0)
  if result!=expected or u.reg_read(UC_ARM_REG_PC)!=0x10000:raise ValueError('Original classifier result differs')
  results.append(dict(input=value,result=result))
 return dict(scan=scan,table=table,classifier=classifier,classifier_return=0x47a876-delta,rxcap_observe=0x47aba8-delta,classifier_units=results)

def selection_helper(raw,delta):
 entry=0x47aa76-delta;md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);ins=list(md.disasm(raw[entry-0x438000:entry-0x438000+0x14],entry))
 expected=[('movs','r1, r0'),('movs','r0, #0'),('ldr','r1, [r1]'),('b','#'+hex(entry+14)),('ands.w','r1, r1, r1, lsl #1'),('adds','r0, r0, #1'),('cmp','r1, #0'),('bne','#'+hex(entry+8)),('bx','lr')]
 if [(x.mnemonic,x.op_str) for x in ins]!=expected:raise ValueError('Longest run helper body differs')
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.mem_map(0x438000,(len(raw)+4095)&~4095);u.mem_write(0x438000,raw);u.mem_map(0x10000,0x1000);u.mem_map(0x20000000,0x1000);cases=[]
 for mask,expected in [(0,0),(0xffffffff,32),(0x00ff0000,8)]:
  u.mem_write(0x20000000,struct.pack('<I',mask));u.reg_write(UC_ARM_REG_R0,0x20000000);u.reg_write(UC_ARM_REG_LR,0x10001);u.reg_write(UC_ARM_REG_SP,0x20001000);u.emu_start(entry|1,0x10000,count=1000);result=u.reg_read(UC_ARM_REG_R0)
  if result!=expected or u.reg_read(UC_ARM_REG_PC)!=0x10000:raise ValueError('Longest run result differs')
  cases.append(dict(mask=mask,result=result))
 return cases

def instrument(runtime,meta):
 needle="observer=BlackwallExecutionObserver(m['sysbus.cpu'],128)"
 if runtime.count(needle)!=1 or runtime.count('    e.StartAll()\n')!=1:raise ValueError('Unexpected observer source')
 runtime=runtime.replace(needle,"observer=BlackwallExecutionObserver(m['sysbus.cpu'],4096)");extra=''
 for n,(off,words) in enumerate([(0,16),(4,16),(6,16),(8,6)]):
  extra+="    observer.AddPoint('scan-table-"+str(n)+"',"+str(meta['scan']+off)+")\n    observer.CaptureSram(m,'scan-table-"+str(n)+"',"+str(meta['table']+n*64)+','+str(words)+')\n'
 for label,address in [('classifier-input',meta['classifier']),('classifier-result',meta['classifier_return']),('scan-rxcap-byte',meta['rxcap_observe'])]:extra+="    observer.AddPoint('"+label+"',"+str(address)+")\n"
 return runtime.replace('    e.StartAll()\n',extra+'    e.StartAll()\n')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);cases=[]
 for key,bundle,delta in [('stock24','stock-2.4.0.24.bin',0),('stock23','stock-2.3.0.24.bin',0x4d18),('cfw','faceclaw-38-research-only.bin',0x4d18)]:
  src=s/'mspi1-rdid-main-01'/key;_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());prior=parse_log((src/'renode.log').read_text())
  if raw!=(src/'main.bin').read_bytes() or prior!=json.loads((src/'report.json').read_text())['observed']:raise ValueError('Frozen input differs')
  validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived']);meta=metadata(raw,delta);d=o/key;d.mkdir(mode=0o700)
  for f in FILES:shutil.copyfile(src/f,d/f)
  runtime=instrument((src/'run.py').read_text(),meta);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base={f:digest(src/f) for f in FILES},derived=derived,observation_only=True),indent=2)+'\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],d,'renode');v=parse_log(log);validate_assets(d,derived)
  if boundary_state(v)!=boundary_state(prior):raise ValueError('Observation changed boundary')
  rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_OBSERVATION ')]
  if len(rows)!=1:raise ValueError('Missing observation')
  ob=rows[0]
  if ob['capacity']!=4096 or ob['dropped_events']!=0 or len(ob['events'])!=ob['sequence']:raise ValueError('Selected event stream incomplete')
  points={x['label']:x for x in ob['points']};words=[]
  for n in range(4):
   point=points['scan-table-'+str(n)]
   if point['hits']!=1 or point['snapshot']['address']!=meta['table']+n*64:raise ValueError('Missing RAM table tile')
   words+=point['snapshot']['words']
  table=struct.pack('<54I',*words);(d/'scan-table.bin').write_bytes(table)
  incoming=[x for x in ob['events'] if x['label']=='classifier-input'];result=[x for x in ob['events'] if x['label']=='classifier-result'];rxcap=[x['r2'] for x in ob['events'] if x['label']=='scan-rxcap-byte']
  if len(incoming)!=288 or len(result)!=288 or any(x['r0']!=0xc22539 for x in incoming) or any(x['r0']!=0 for x in result):raise ValueError('Unexpected native classifier path')
  r=dict(passed=True,case=key,metadata=meta,observed=v,selected_observation=ob,table_sha256=hashlib.sha256(table).hexdigest(),table_rows=[list(table[n*6:(n+1)*6]) for n in range(36)],rxcap_raw_prefix=rxcap,scope='original classifier and RAM table observation, not physical timing or calibration success',boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n');row=dict(case=key,classifications=len(incoming),selected_events=ob['sequence'],dropped=ob['dropped_events'],table=hex(meta['table']),rxcap_prefix=rxcap);cases.append(row);print(json.dumps(row),flush=True)
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=cases),indent=2)+'\n')
if __name__=='__main__':main()
