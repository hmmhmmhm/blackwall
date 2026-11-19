"""Observe original EN4B completion and actual indirect RDCR/bit5 verification."""
import argparse,json,shutil
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute
PLANS=[('stock24','stock24',0),('stock23','stock23',0),('cfw','cfw',0),('stock24-unknown','stock24',None)]
ADDRESS_MARKER="    q=m['sysbus.guard'].Mspi1Config.Pio\n    Console.WriteLine('BLACKWALL_NOR_ADDRESS '+json.dumps(dict(seed=int(q.ConfigurationByte),current=int(q.CurrentConfigurationByte),four_byte=bool(q.FourByteAddressMode),EN4B_completed=int(q.Enter4ByteTransfers),RDCR_completed=int(q.ConfigurationReadTransfers))))\n"
def board(text,seed):
 if seed is None:return text
 needle='    profile: "idle-nor-reset"\n'
 if text.count(needle)!=1:raise ValueError('Unexpected NOR owner')
 return text.replace(needle,needle+'    configurationByte: '+str(seed)+'\n')
def instrument(runtime,raw,key):
 delta=0 if key=='stock24' else 0x4d18;parent=0x47ba04-delta;helper=0x47b83e-delta;md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);code={x.address:(x.mnemonic,x.op_str) for x in md.disasm(raw[parent-0x438000:parent+0x1b4-0x438000],parent)};expected={0:('push','{r2, r3, r4, lr}'),0xbe:('bl','#'+hex(0x47b694-delta)),0xc2:('movs','r4, r0'),0x118:('blx','r0'),0x11a:('cmp','r0, #0'),0x11c:('bne','#'+hex(parent+0x162))}
 if any(code.get(parent+n)!=pair for n,pair in expected.items()):raise ValueError('Original EN4B caller differs')
 hc={x.address:(x.mnemonic,x.op_str) for x in md.disasm(raw[helper-0x438000:helper+0xc0-0x438000],helper)};expectedh={0:('push','{r0, r1, r2, r3, r4, lr}'),0x6a:('ldrb.w','r0, [sp, #8]'),0x6e:('lsls','r0, r0, #0x1a'),0x70:('bpl','#'+hex(helper+0x76)),0x72:('movs','r0, #1'),0xbc:('add','sp, #0x10'),0xbe:('pop','{r4, pc}')}
 if any(hc.get(helper+n)!=pair for n,pair in expectedh.items()):raise ValueError('Original RDCR/bit5 helper differs')
 points=[('EN4B-caller-return',parent+0xc2),('address-indirect-call',parent+0x118),('configuration-helper-entry',helper),('configuration-byte',helper+0x6e),('configuration-result',helper+0xbc),('address-check-caller',parent+0x11a)];extra=''.join("    observer.AddPoint('"+label+"',"+str(address)+")\n" for label,address in points)
 if runtime.count('    e.StartAll()\n')!=1 or runtime.count('except Exception as error:\n')!=1:raise ValueError('Runtime insertion differs')
 return runtime.replace('    e.StartAll()\n',extra+'    e.StartAll()\n').replace('except Exception as error:\n',ADDRESS_MARKER+'except Exception as error:\n'),dict(parent=parent,helper=helper,points=dict(points))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);rows=[]
 for name,key,seed in PLANS:
  src=s/'mspi1-write-enable-main-01'/key;prior=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text())
  if v0!=prior['observed']:raise ValueError('Saved base report differs')
  validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived']);bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  if raw!=(src/'main.bin').read_bytes():raise ValueError('Original main differs')
  d=o/name;d.mkdir(mode=0o700)
  for f in FILES:shutil.copyfile(src/f,d/f)
  (d/'strict.cs').write_bytes(models(s));(d/'board.repl').write_text(board((src/'board.repl').read_text(),seed));runtime,meta=instrument((src/'run.py').read_text(),raw,key);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base={f:digest(src/f) for f in FILES},derived=derived,configuration_seed=seed,observation=meta),indent=2)+'\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],d,'renode',timeout=None);v=parse_log(log);validate_assets(d,derived)
  def marker(tag):
   z=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
   if len(z)!=1:raise ValueError(tag)
   return z[0]
  address=marker('BLACKWALL_NOR_ADDRESS');ob=marker('BLACKWALL_OBSERVATION');q=marker('BLACKWALL_MSPI1_SAMPLING');latch=marker('BLACKWALL_NOR_LATCH');status=marker('BLACKWALL_NOR_STATUS')
  if ob['dropped_events'] or len(ob['events'])!=ob['sequence']:raise ValueError('Selected event loss')
  if seed is None and boundary_state(v)!=boundary_state(v0):raise ValueError('Unknown configuration changed base boundary')
  r=dict(passed=True,name=name,observed=v,address_mode=address,latch=latch,sampling=q,nor_status=status,selected_observation=ob,observation=meta,selected_hypotheses=prior['selected_hypotheses'],additional_hypotheses=prior['additional_hypotheses']+[dict(reset_configuration_seed=seed,physical_configuration_known=False)],array_addressing_verified=False,boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n');row=dict(name=name,pc=hex(v['pc']),address_mode=address,latch=latch,sampling=q,events=ob['sequence'],guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW dependency differs')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='reset configuration and original EN4B/RDCR verification; no array addressing, NV writes, full boot or display proof'),indent=2)+'\n')
if __name__=='__main__':main()
