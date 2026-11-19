"""Compare original interrupt initialization using explicit idle event-register banks."""
import argparse,json,hashlib,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets,boundary_state
ROOT=Path(__file__).resolve().parents[1]
from run_renode_m55_probe import execute
from pinned_main import load_pinned_main

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Use fresh evidence directory')
 o.mkdir(mode=0o700);base=s/'pmic-restore-main-01';old=(s/'pmic-restore-unit-01/peer.cs').read_bytes();peer=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();(o/'peer.cs').write_bytes(peer);(o/'runner.py').write_bytes(Path(__file__).read_bytes());rows=[]
 for name,key,enabled in [('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-no-irqs','stock24',False)]:
  src=base/key;prior=json.loads((src/'report.json').read_text());before=parse_log((src/'renode.log').read_text());filename={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
  if before!=prior['observed'] or raw!=(src/'main.bin').read_bytes() or prior['image_id']!=IMAGE:raise ValueError('Frozen source differs')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(src/f) for f in FILES}
  for f in FILES:shutil.copyfile(src/f,d/f)
  validate_assets(d,original);text=(d/'strict.cs').read_bytes()
  if not text.endswith(old):raise ValueError('Old model suffix differs')
  (d/'strict.cs').write_bytes(text[:-len(old)]+peer)
  if enabled:(d/'board.repl').write_text((d/'board.repl').read_text()+'    interruptState: "explicit-idle"\n')
  text=(d/'run.py').read_text();needle='pointer=int(peer.Pointer),pointer_writes=int(peer.PointerWrites)'
  if text.count(needle)!=1:raise ValueError('Peer report differs')
  replacement='interrupt_registers=bool(peer.InterruptRegistersEnabled),register_writes=int(peer.RegisterWrites),digital_irq_pending=bool(peer.DigitalIrqPending),event_state=[int(v) for v in peer.EventState],enable_state=[int(v) for v in peer.EnableState],write_addresses=[int(v) for v in peer.WriteAddresses],write_values=[int(v) for v in peer.WriteValues],'+needle
  text=text.replace(needle,replacement);compile(text,'run.py','exec');(d/'run.py').write_text(text);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,interrupt_state='explicit-idle' if enabled else None,model_sha256=hashlib.sha256(peer).hexdigest()),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(name):
   records=[json.loads(x.split(name+' ',1)[1]) for x in log.splitlines() if x.startswith(name+' ')]
   if len(records)!=1:raise ValueError('Missing '+name)
   return records[0]
  state=marker('BLACKWALL_PMIC_RESTORE');obs=marker('BLACKWALL_OBSERVATION');guards=[g for g in v['guards'] if g['accesses']];r=dict(name=name,observed=v,peer=state,observation=obs,image_id=IMAGE,raw_main_sha256=digest(d/'main.bin'),selected_hypotheses=prior['selected_hypotheses'],additional_hypothesis=dict(interrupt_state='explicit-idle' if enabled else None,gpio_connected=False,physical_interrupts=False),boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n')
  if enabled:
   expected=[addr for base in [2,6,10,14,18,22,26,34] for addr in [base+3,base+1]]
   if state['write_addresses'][:16]!=expected or state['write_values'][:16]!=[255]*16:raise ValueError('Original disable/clear sequence differs')
  elif state['register_writes'] or boundary_state(v)!=boundary_state(before):raise ValueError('Unknown default changed')
  row=dict(name=name,pc=hex(v['pc']),peer=state,guards=guards);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['strict.cs','board.repl','probe.resc','result.py']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW model differs')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='original digital event-register initialization with explicit idle events; no GPIO, physical events or full boot'),indent=2)+'\n')
if __name__=='__main__':main()
