"""Replay pinned original ARM with optional MSPI1 configuration storage; no bus engine."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,parse_log,digest,validate_assets,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from verify_mspi1_config import board,models
MARKER="    config=m['sysbus.guard'].Mspi1Config\n    config_state=dict(enabled=False) if config is None else dict(enabled=True,reads=int(config.Reads),writes=int(config.Writes),registers=dict((str(int(x.Key)),int(x.Value)) for x in config.Values))\n    Console.WriteLine('BLACKWALL_MSPI1_CONFIG '+json.dumps(config_state))\n"
PLANS=[('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-no-config','stock24',False),('stock24-stuck-off','stock24-stuck-off',True)]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700);rows=[]
 for name,key,enabled in PLANS:
  src=s/'mspi1-clock-main-01'/key;prior=parse_log((src/'renode.log').read_text());prior_report=json.loads((src/'report.json').read_text());check_key='stock24' if key.startswith('stock24') else key
  bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[check_key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  if raw!=(src/'main.bin').read_bytes() or prior!=prior_report['observed']:raise ValueError('Frozen original differs')
  validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived']);d=o/name;d.mkdir(mode=0o700)
  for f in FILES:shutil.copyfile(src/f,d/f)
  (d/'strict.cs').write_bytes(models(s));(d/'board.repl').write_text(board((src/'board.repl').read_text(),enabled));runtime=(src/'run.py').read_text();needle='except Exception as error:\n'
  if runtime.count(needle)!=1:raise ValueError('Unexpected runtime')
  runtime=runtime.replace(needle,MARKER+needle);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime)
  derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base={f:digest(src/f) for f in FILES},derived=derived,config_profile='source-reset-config' if enabled else None,bus_engine=False),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(tag):
   data=[json.loads(x.split(tag+' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
   if len(data)!=1:raise ValueError('Missing '+tag)
   return data[0]
  config=marker('BLACKWALL_MSPI1_CONFIG');power=marker('BLACKWALL_MSPI1_POWER')
  if not enabled and (config['enabled'] or boundary_state(v)!=boundary_state(prior)):raise ValueError('Default boundary changed')
  r=dict(name=name,observed=v,config=config,power=power,image_id=IMAGE,selected_hypotheses=prior_report['selected_hypotheses'],additional_hypotheses=prior_report['additional_hypotheses']+[dict(mspi1_config_storage=enabled,source_reset_registers=True,clock_engine=False,bus_engine=False)],boot_verified=False,hardware_validated=False,installable=False)
  (d/'report.json').write_text(json.dumps(r,indent=2)+'\n');row=dict(name=name,pc=hex(v['pc']),config=config,power=power,guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW models differ')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='source-reset config register storage only; full boot/display/physical unverified'),indent=2)+'\n')
if __name__=='__main__':main()
