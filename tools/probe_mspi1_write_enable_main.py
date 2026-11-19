"""Run original WREN caller under opt-in idle latch and retain disabled control."""
import argparse,json,shutil
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute
PLANS=[('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-disabled','stock24',False)]
LATCH_MARKER="    q=m['sysbus.guard'].Mspi1Config.Pio\n    Console.WriteLine('BLACKWALL_NOR_LATCH '+json.dumps(dict(enabled=bool(q.EmulateWriteEnableLatch),seed=int(q.StatusByte),current=int(q.CurrentStatusByte),wel=bool(q.WriteEnabled),WREN_completed=int(q.WriteEnableTransfers))))\n"
def board(text,enabled):
 if not enabled:return text
 needle='    profile: "idle-nor-reset"\n'
 if text.count(needle)!=1:raise ValueError('Unexpected NOR owner')
 return text.replace(needle,needle+'    emulateWriteEnableLatch: true\n')
def instrument(runtime,raw,key):
 delta=0 if key=='stock24' else 0x4d18;entry=0x47bbc0-delta;ret=0x47bc1a-delta;caller=0x47ba04-delta;after=0x47ba68-delta;md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);code={x.address:(x.mnemonic,x.op_str) for x in md.disasm(raw[entry-0x438000:ret+2-0x438000],entry)}
 if code.get(entry)!=('push','{r2, r3, r4, lr}') or code.get(ret-2)!=('movs','r0, r4') or code.get(ret)!=('pop','{r1, r2, r4, pc}'):raise ValueError('Original WREN wrapper differs')
 cc={x.address:(x.mnemonic,x.op_str) for x in md.disasm(raw[caller-0x438000:caller+0xc2-0x438000],caller)}
 if cc.get(after-4)!=('bl','#'+hex(entry)) or cc.get(after)!=('movs','r4, r0') or cc.get(after+4)!=('beq','#'+hex(caller+0xb2)) or cc.get(caller+0xbc)!=('movs','r0, #0xb7'):raise ValueError('Original WREN caller differs')
 extra="    observer.AddPoint('wren-wrapper-return',"+str(ret)+")\n    observer.AddPoint('wren-caller-return',"+str(after)+")\n"
 if runtime.count('    e.StartAll()\n')!=1 or runtime.count('except Exception as error:\n')!=1:raise ValueError('Runtime insertion differs')
 return runtime.replace('    e.StartAll()\n',extra+'    e.StartAll()\n').replace('except Exception as error:\n',LATCH_MARKER+'except Exception as error:\n'),dict(wrapper=entry,return_point=ret,caller_return=after)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);rows=[]
 for name,key,enabled in PLANS:
  src=s/'mspi1-status-main-01'/(key+'-idle');prior=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text())
  if v0!=prior['observed']:raise ValueError('Saved base differs')
  validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived']);bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  if raw!=(src/'main.bin').read_bytes():raise ValueError('Original main differs')
  d=o/name;d.mkdir(mode=0o700)
  for f in FILES:shutil.copyfile(src/f,d/f)
  (d/'strict.cs').write_bytes(models(s));(d/'board.repl').write_text(board((src/'board.repl').read_text(),enabled));runtime,meta=instrument((src/'run.py').read_text(),raw,key);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base={f:digest(src/f) for f in FILES},derived=derived,latch_enabled=enabled,observation=meta),indent=2)+'\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],d,'renode',timeout=None);v=parse_log(log);validate_assets(d,derived)
  def marker(tag):
   z=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
   if len(z)!=1:raise ValueError(tag)
   return z[0]
  latch=marker('BLACKWALL_NOR_LATCH');ob=marker('BLACKWALL_OBSERVATION');q=marker('BLACKWALL_MSPI1_SAMPLING');status=marker('BLACKWALL_NOR_STATUS')
  if ob['dropped_events'] or len(ob['events'])!=ob['sequence']:raise ValueError('Selected observation overflow')
  if not enabled and boundary_state(v)!=boundary_state(v0):raise ValueError('Disabled latch changed prior boundary')
  r=dict(passed=True,name=name,observed=v,latch=latch,sampling=q,nor_status=status,selected_observation=ob,observation=meta,selected_hypotheses=prior['selected_hypotheses'],additional_hypotheses=prior['additional_hypotheses']+[dict(idle_WEL_latch=enabled,physical_NOR_state_known=False)],WEL_read_after_WREN_observed=False,boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n');row=dict(name=name,pc=hex(v['pc']),latch=latch,sampling=q,events=ob['sequence'],guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW dependencies differ')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='opt-in idle WEL in original ARM main; no original WEL readback, NV writes, full boot or display proof'),indent=2)+'\n')
if __name__=='__main__':main()
