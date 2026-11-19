"""Run immutable original ARM with optional STIMER interrupt storage; no counter/IRQ or device access."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
PLANS=[('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-no-stimer','stock24',False)]
MARKER="    stimer=m['sysbus.guard'].Stimer\n    stimer_state=dict(enabled=False) if stimer is None else dict(enabled=True,enable=int(stimer.Enable),status=int(stimer.Status),pending=bool(stimer.Pending),reads=int(stimer.Reads),writes=int(stimer.Writes))\n    Console.WriteLine('BLACKWALL_STIMER_INTERRUPT '+json.dumps(stimer_state))\n"
def board_for(board,enabled):
 needle='    rtc: rtc_model\n'
 if board.count(needle)!=1 or 'stimer_model:' in board:raise ValueError('Unexpected STIMER attachment')
 return board if not enabled else board.replace(needle,needle+'    stimer: stimer_model\n')+'\nstimer_model: Miscellaneous.BlackwallStimerInterruptStorage @ none\n    profile: "source-reset-storage"\n'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh output required')
 o.mkdir(mode=0o700);base=s/'pmic-ldsw-main-01';old=(s/'source-backup-stimer-base.cs').read_bytes();core=(ROOT/'tools/renode-strict-mmio.cs').read_bytes();addon=(ROOT/'tools/renode-stimer-interrupt-probe.cs').read_bytes()
 for name,data in [('runner.py',Path(__file__).read_bytes()),('old-core.cs',old),('core.cs',core),('addon.cs',addon)]: (o/name).write_bytes(data)
 rows=[]
 for name,key,enabled in PLANS:
  src=base/key;before=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text());bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived'])
  if raw!=(src/'main.bin').read_bytes() or v0!=before['observed']:raise ValueError('Frozen original differs')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(src/f) for f in FILES}
  for f in FILES:shutil.copyfile(src/f,d/f)
  strict=(d/'strict.cs').read_bytes()
  if not strict.startswith(old):raise ValueError('Frozen core differs')
  (d/'strict.cs').write_bytes(core+strict[len(old):]+b'\n'+addon);(d/'board.repl').write_text(board_for((d/'board.repl').read_text(),enabled))
  runtime=(d/'run.py').read_text();needle='except Exception as error:\n'
  if runtime.count(needle)!=1:raise ValueError('Runtime boundary differs')
  runtime=runtime.replace(needle,MARKER+needle);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,stimer_enabled=enabled),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(n):
   x=[json.loads(row.split(n+' ',1)[1]) for row in log.splitlines() if row.startswith(n+' ')]
   if len(x)!=1:raise ValueError('Missing '+n)
   return x[0]
  stimer=marker('BLACKWALL_STIMER_INTERRUPT');report=dict(name=name,observed=v,stimer=stimer,image_id=IMAGE,ldsw=marker('BLACKWALL_PMIC_LDSW'),buck=marker('BLACKWALL_PMIC_BUCK'),queued=marker('BLACKWALL_PMIC_QUEUED'),timer=marker('BLACKWALL_PMIC_TIMER'),selected_hypotheses=before['selected_hypotheses'],additional_hypotheses=before['additional_hypotheses']+[dict(stimer_interrupt_storage=enabled,counter=False,nvic_delivery=False)],boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  if enabled and (not stimer['enabled'] or stimer['reads']<1):raise ValueError('STIMER access not observed')
  if not enabled and (stimer['enabled'] or boundary_state(v)!=boundary_state(v0)):raise ValueError('Default boundary changed')
  row=dict(name=name,pc=hex(v['pc']),stimer=stimer,guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['board.repl','strict.cs','result.py','probe.resc']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW models differ')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='original ARM with interrupt storage subset; no counter/NVIC/full boot/device proof'),indent=2)+'\n')
if __name__=='__main__':main()
