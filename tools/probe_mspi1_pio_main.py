"""Replay pinned original ARM with virtual-time PIO NOR reset; no hardware access."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,parse_log,digest,validate_assets,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import board,models
MARKER="    q=m['sysbus.guard'].Mspi1Config.Pio\n    pio_state=dict(selected=False) if q is None else dict(selected=True,control=int(q.Control),busy=bool(q.Busy),starts=int(q.Starts),completions=int(q.Completions),armed=bool(q.ResetArmed),recovering=bool(q.Recovering),resets=int(q.Resets),ignored_resets=int(q.IgnoredResets),aborted=int(q.Aborted),reads=int(q.Reads),writes=int(q.Writes))\n    Console.WriteLine('BLACKWALL_MSPI1_PIO '+json.dumps(pio_state))\n"
PLANS=[('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-no-pio','stock24',False)]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700);rows=[]
 for name,key,enabled in PLANS:
  src=s/'mspi1-clear-all-main-01'/key;prior=parse_log((src/'renode.log').read_text());prior_report=json.loads((src/'report.json').read_text());check_key='stock24' if key.startswith('stock24') else key
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[check_key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  if raw!=(src/'main.bin').read_bytes() or prior!=prior_report['observed']:raise ValueError('Frozen original differs')
  validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived']);d=o/name;d.mkdir(mode=0o700)
  for f in FILES:shutil.copyfile(src/f,d/f)
  (d/'strict.cs').write_bytes(models(s));(d/'board.repl').write_text(board((src/'board.repl').read_text(),enabled));runtime=(src/'run.py').read_text();needle='except Exception as error:\n'
  if runtime.count(needle)!=1:raise ValueError('Unexpected runtime')
  runtime=runtime.replace(needle,MARKER+needle);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime)
  derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base={f:digest(src/f) for f in FILES},derived=derived,pio=enabled,backing=False),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(tag):
   data=[json.loads(x.split(tag+' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
   if len(data)!=1:raise ValueError('Missing '+tag)
   return data[0]
  pio=marker('BLACKWALL_MSPI1_PIO');power=marker('BLACKWALL_MSPI1_POWER')
  if not enabled and (pio['selected'] or boundary_state(v)!=boundary_state(prior)):raise ValueError('Default boundary changed')
  r=dict(name=name,observed=v,pio=pio,power=power,image_id=IMAGE,selected_hypotheses=prior_report['selected_hypotheses'],additional_hypotheses=prior_report['additional_hypotheses']+[dict(pio=enabled,idle_NOR_reset=True,controller_us=10,recovery_us=100,physical_timing=False,identity_backing=False)],boot_verified=False,hardware_validated=False,installable=False)
  (d/'report.json').write_text(json.dumps(r,indent=2)+'\n');row=dict(name=name,pc=hex(v['pc']),pio=pio,power=power,guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW models differ')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='virtual PIO command and idle NOR reset hypotheses; full boot/display/physical unverified'),indent=2)+'\n')
if __name__=='__main__':main()
