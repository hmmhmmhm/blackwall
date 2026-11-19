"""Observe original WRDI wrapper and completion of the address-mode parent helper."""
import argparse,json,shutil
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute
PLANS=[('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-disabled','stock24',False)]
WRDI_MARKER="    q=m['sysbus.guard'].Mspi1Config.Pio\n    Console.WriteLine('BLACKWALL_NOR_WRDI '+json.dumps(dict(completed=int(q.WriteDisableTransfers),wel=bool(q.WriteEnabled),current_status=int(q.CurrentStatusByte),current_configuration=int(q.CurrentConfigurationByte))))\n"
def board(text,enabled):
 if enabled:return text
 needle='    emulateWriteEnableLatch: true\n'
 if text.count(needle)!=1:raise ValueError('Unexpected latch selection')
 return text.replace(needle,'    emulateWriteEnableLatch: false\n')
def instrument(runtime,raw,key):
 delta=0 if key=='stock24' else 0x4d18;entry=0x47bc28-delta;ret=0x47bc82-delta;caller=0x47bb6a-delta;parent=0x47ba04-delta;parent_return=0x47bbb6-delta;md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);code={x.address:(x.mnemonic,x.op_str) for x in md.disasm(raw[entry-0x438000:ret+2-0x438000],entry)};expected={0:('push','{r2, r3, r4, lr}'),2:('movs','r0, #0'),4:('str','r0, [sp]'),6:('movs','r3, #0'),8:('movs','r2, #0'),0xa:('movs','r1, #0'),0xc:('movs','r0, #4'),0xe:('bl','#'+hex(0x47b694-delta)),0x12:('movs','r4, r0'),0x14:('cmp','r4, #0'),0x16:('beq','#'+hex(entry+0x58)),0x58:('movs','r0, r4'),0x5a:('pop','{r1, r2, r4, pc}')}
 if any(code.get(entry+n)!=pair for n,pair in expected.items()):raise ValueError('Original WRDI wrapper differs')
 pc={x.address:(x.mnemonic,x.op_str) for x in md.disasm(raw[parent-0x438000:parent_return+2-0x438000],parent)}
 if pc.get(caller-4)!=('bl','#'+hex(entry)) or pc.get(caller)!=('movs','r4, r0') or pc.get(caller+4)!=('beq','#'+hex(parent_return-2)) or pc.get(parent_return-2)!=('movs','r0, #0') or pc.get(parent_return)!=('pop','{r1, r2, r4, pc}'):raise ValueError('Original WRDI parent differs')
 points=[('WRDI-wrapper-return',ret),('WRDI-caller-return',caller),('address-mode-parent-return',parent_return)];extra=''.join("    observer.AddPoint('"+n+"',"+str(addr)+")\n" for n,addr in points)
 if runtime.count('    e.StartAll()\n')!=1 or runtime.count('except Exception as error:\n')!=1:raise ValueError('Runtime insertion differs')
 return runtime.replace('    e.StartAll()\n',extra+'    e.StartAll()\n').replace('except Exception as error:\n',WRDI_MARKER+'except Exception as error:\n'),dict(wrapper=entry,points=dict(points))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);rows=[]
 for name,key,enabled in PLANS:
  src=s/'mspi1-address-mode-main-01'/key;prior=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text())
  if v0!=prior['observed']:raise ValueError('Saved base report differs')
  validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived']);bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  if raw!=(src/'main.bin').read_bytes():raise ValueError('Original main differs')
  d=o/name;d.mkdir(mode=0o700)
  for f in FILES:shutil.copyfile(src/f,d/f)
  (d/'strict.cs').write_bytes(models(s));(d/'board.repl').write_text(board((src/'board.repl').read_text(),enabled));runtime,meta=instrument((src/'run.py').read_text(),raw,key);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base={f:digest(src/f) for f in FILES},derived=derived,latch_enabled=enabled,observation=meta),indent=2)+'\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],d,'renode',timeout=None);v=parse_log(log);validate_assets(d,derived)
  def marker(tag):
   z=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
   if len(z)!=1:raise ValueError(tag)
   return z[0]
  wrdi=marker('BLACKWALL_NOR_WRDI');ob=marker('BLACKWALL_OBSERVATION');q=marker('BLACKWALL_MSPI1_SAMPLING');address=marker('BLACKWALL_NOR_ADDRESS');latch=marker('BLACKWALL_NOR_LATCH');status=marker('BLACKWALL_NOR_STATUS')
  if ob['dropped_events'] or len(ob['events'])!=ob['sequence']:raise ValueError('Selected event loss')
  if not enabled:
   old=json.loads((s/'mspi1-write-enable-main-01/stock24-disabled/report.json').read_text())
   if boundary_state(v)!=boundary_state(old['observed']):raise ValueError('Disabled latch changed default WREN boundary')
  r=dict(passed=True,name=name,observed=v,wrdi=wrdi,address_mode=address,latch=latch,sampling=q,nor_status=status,selected_observation=ob,observation=meta,selected_hypotheses=prior['selected_hypotheses'],additional_hypotheses=prior['additional_hypotheses'],wrapper_checks_WEL=False,array_addressing_verified=False,boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n');row=dict(name=name,pc=hex(v['pc']),wrdi=wrdi,address_mode=address,sampling=q,events=ob['sequence'],guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW dependency differs')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='original WRDI/address-helper completion; no WEL readback by wrapper, array or NV writes, full boot/display proof'),indent=2)+'\n')
if __name__=='__main__':main()
