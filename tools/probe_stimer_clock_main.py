"""Replay immutable G2 ARM with explicit nominal STIMER clocks and connected interrupt lines."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from stimer_engine_source import load_engine
ROOT=Path(__file__).resolve().parents[1]
PLANS=[('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-no-clock','stock24',False)]
MARKER="    clock=m['sysbus.guard'].Stimer\n    clock_state=dict(enabled=False) if not hasattr(clock,'Counter') else dict(enabled=True,config=int(clock.Config),counter=int(clock.Counter),frequency=int(clock.Frequency),enable=int(clock.Enable),status=int(clock.Status),pending=bool(clock.Pending),reads=int(clock.Reads),writes=int(clock.Writes),irq=[bool(getattr(clock,'IRQ'+c).IsSet) for c in 'ABCDEFGHI'])\n    Console.WriteLine('BLACKWALL_STIMER_CLOCK '+json.dumps(clock_state))\n"
def board_for(board,enabled):
 old='stimer_model: Miscellaneous.BlackwallStimerInterruptStorage @ none\n    profile: "source-reset-storage"\n'
 if board.count(old)!=1:raise ValueError('Frozen interrupt adapter differs')
 new='stimer_model: Miscellaneous.BlackwallStimerClockCounter @ none\n    profile: "nominal-source-clocks"\n'+''.join('    IRQ'+c+' -> nvic@'+str(32+i)+'\n' for i,c in enumerate('ABCDEFGHI'))
 return board.replace(old,new) if enabled else board
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh output required')
 o.mkdir(mode=0o700);base=s/'stimer-interrupt-main-03';engine=load_engine(s).encode();addon=(ROOT/'tools/renode-stimer-clock-probe.cs').read_bytes()
 for name,data in [('runner.py',Path(__file__).read_bytes()),('engine.cs',engine),('addon.cs',addon),('loader.py',(ROOT/'tools/stimer_engine_source.py').read_bytes())]: (o/name).write_bytes(data)
 rows=[]
 for name,key,enabled in PLANS:
  src=base/key;before=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text());bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived'])
  if raw!=(src/'main.bin').read_bytes() or v0!=before['observed'] or before['image_id']!=IMAGE:raise ValueError('Frozen original differs')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(src/f) for f in FILES}
  for f in FILES:shutil.copyfile(src/f,d/f)
  (d/'strict.cs').write_bytes((d/'strict.cs').read_bytes()+b'\n'+engine+b'\n'+addon);(d/'board.repl').write_text(board_for((d/'board.repl').read_text(),enabled));runtime=(d/'run.py').read_text();needle='except Exception as error:\n'
  if runtime.count(needle)!=1:raise ValueError('Runtime boundary differs')
  runtime=runtime.replace(needle,MARKER+needle);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,nominal_stimer=enabled,compare_timing='immediate-relative-write' if enabled else None,nvic_connected=enabled),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(n):
   found=[json.loads(x.split(n+' ',1)[1]) for x in log.splitlines() if x.startswith(n+' ')]
   if len(found)!=1:raise ValueError('Missing '+n)
   return found[0]
  clock=marker('BLACKWALL_STIMER_CLOCK');r=dict(name=name,observed=v,clock=clock,image_id=IMAGE,stimer=marker('BLACKWALL_STIMER_INTERRUPT'),ldsw=marker('BLACKWALL_PMIC_LDSW'),buck=marker('BLACKWALL_PMIC_BUCK'),queued=marker('BLACKWALL_PMIC_QUEUED'),selected_hypotheses=before['selected_hypotheses'],additional_hypotheses=before['additional_hypotheses']+[dict(nominal_stimer=enabled,compare_timing='immediate-relative-write' if enabled else None,nvic_connected=enabled,physical_clock=False)],boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n')
  if clock['enabled']!=enabled:raise ValueError('Wrong clock adapter selected')
  if not enabled and boundary_state(v)!=boundary_state(v0):raise ValueError('Default clock boundary changed')
  row=dict(name=name,pc=hex(v['pc']),clock=clock,guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for file in ['board.repl','strict.cs','result.py','probe.resc']:
  if (o/'stock23'/file).read_bytes()!=(o/'cfw'/file).read_bytes():raise ValueError('Stock/CFW models differ')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='original ARM with nominal source clocks/relative immediate compare/NVIC lines; no physical timing, full boot or main ISR proof'),indent=2)+'\n')
if __name__=='__main__':main()
