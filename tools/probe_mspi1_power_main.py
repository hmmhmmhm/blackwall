"""Replay original G2 ARM with optional source-masked MSPI1 power responses, no MSPI bus engine."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from mspi1_power_board import attach
ROOT=Path(__file__).resolve().parents[1]
PLANS=[('stock24','stock24','active'),('stock23','stock23','active'),('cfw','cfw','active'),('stock24-no-mspi1','stock24',None),('stock24-stuck-off','stock24','stuck-off')]
MARKER="    power=m['sysbus.guard'].Mspi1Power\n    power_state=dict(enabled=False) if power is None else dict(enabled=True,profile=int(power.Profile),mask=int(power.Mask),phase=str(power.Phase),request=int(power.RequestWord),status=int(power.StatusWord),requests=int(power.Requests),responses=int(power.Responses),off_requests=int(power.OffRequests))\n    Console.WriteLine('BLACKWALL_MSPI1_POWER '+json.dumps(power_state))\n"
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',action='append',dest='cases');p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if a.cases and set(a.cases)-{x[0] for x in PLANS}:raise ValueError('Unknown case')
 plans=[x for x in PLANS if x[0] in a.cases] if a.cases else PLANS[:4]
 if o.exists():raise ValueError('Fresh output required')
 o.mkdir(mode=0o700);base=s/'stimer-clock-main-01';old=(s/'mspi1-source-research-01/base-core.cs').read_bytes();core=(ROOT/'tools/renode-strict-mmio.cs').read_bytes()
 for name,data in [('runner.py',Path(__file__).read_bytes()),('core.cs',core),('old-core.cs',old)]: (o/name).write_bytes(data)
 rows=[]
 for name,key,profile in plans:
  src=base/key;before=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text());bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived'])
  if raw!=(src/'main.bin').read_bytes() or v0!=before['observed']:raise ValueError('Frozen original differs')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(src/f) for f in FILES}
  for f in FILES:shutil.copyfile(src/f,d/f)
  strict=(d/'strict.cs').read_bytes()
  if not strict.startswith(old):raise ValueError('Frozen power/core differs')
  (d/'strict.cs').write_bytes(core+strict[len(old):]);(d/'board.repl').write_text(attach((d/'board.repl').read_text(),profile));runtime=(d/'run.py').read_text();needle='except Exception as error:\n'
  if runtime.count(needle)!=1:raise ValueError('Runtime boundary differs')
  runtime=runtime.replace(needle,MARKER+needle);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,mspi1_power_profile=profile,off_response=None,bus_engine=False),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(n):
   found=[json.loads(x.split(n+' ',1)[1]) for x in log.splitlines() if x.startswith(n+' ')]
   if len(found)!=1:raise ValueError('Missing '+n)
   return found[0]
  power=marker('BLACKWALL_MSPI1_POWER');r=dict(name=name,observed=v,power=power,clock=marker('BLACKWALL_STIMER_CLOCK'),image_id=IMAGE,selected_hypotheses=before['selected_hypotheses'],additional_hypotheses=before['additional_hypotheses']+[dict(mspi1_power=profile,response='first-status-read' if profile else None,bus_engine=False,physical_power=False)],boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n')
  if profile is None and (power['enabled'] or boundary_state(v)!=boundary_state(v0)):raise ValueError('Default power guard changed')
  if profile and (not power['enabled'] or power['profile']!=int(profile=='active')):raise ValueError('Unexpected profile')
  row=dict(name=name,pc=hex(v['pc']),power=power,guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 compared={'stock23','cfw'}.issubset({x[0] for x in plans})
 if compared:
  for f in ['board.repl','strict.cs','result.py','probe.resc']:
   if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW models differ')
  if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,stock_cfw_compared=compared,scope='source-masked shared power/first-status-read response only, no bus/peer/physical/full boot proof'),indent=2)+'\n')
if __name__=='__main__':main()
