"""Replay pinned original ARM with optional LDSW register storage; no physical operations."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
PLANS=[('stock24','stock24','source-reset-storage'),('stock23','stock23','source-reset-storage'),('cfw','cfw','source-reset-storage'),('stock24-ldsw-unknown','stock24','guest-storage'),('stock24-no-ldsw','stock24',None)]
MARKER="    Console.WriteLine('BLACKWALL_PMIC_LDSW '+json.dumps(dict(profile=None if peer.LdswState is None else str(peer.LdswState),addresses=[int(x) for x in peer.LdswKnownAddresses],values=[int(x) for x in peer.LdswKnownValues],config_writes=int(peer.LdswConfigWrites),task_writes=int(peer.LdswTaskWrites),task_requests=[int(x) for x in peer.LdswTaskRequests])))\n"
def ldsw_board(board,profile):
 if profile not in (None,'source-reset-storage','guest-storage'):raise ValueError('Invalid LDSW profile')
 needle='    timerProfile: "fast-reset-stopped"\n'
 if board.count(needle)!=1 or 'ldswState:' in board:raise ValueError('Unexpected LDSW attachment')
 return board if profile is None else board.replace(needle,needle+'    ldswState: "'+profile+'"\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',action='append',dest='cases');p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if a.cases and set(a.cases)-{x[0] for x in PLANS}:raise ValueError('Unknown replay case')
 plans=[x for x in PLANS if not a.cases or x[0] in a.cases]
 if o.exists():raise ValueError('Fresh output required')
 o.mkdir(mode=0o700);base=s/'pmic-buck-main-01';old=(base/'root.cs').read_bytes()+b'\n'+(base/'timed.cs').read_bytes();root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes()
 for name,data in [('runner.py',Path(__file__).read_bytes()),('root.cs',root),('timed.cs',timed)]: (o/name).write_bytes(data)
 rows=[]
 for name,key,profile in plans:
  src=base/key;before=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text());bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived'])
  if raw!=(src/'main.bin').read_bytes() or before['observed']!=v0 or before['image_id']!=IMAGE:raise ValueError('Frozen original differs')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(src/f) for f in FILES}
  for f in FILES:shutil.copyfile(src/f,d/f)
  strict=(d/'strict.cs').read_bytes()
  if not strict.endswith(old):raise ValueError('Frozen PMIC suffix differs')
  (d/'strict.cs').write_bytes(strict[:-len(old)]+root+b'\n'+timed);(d/'board.repl').write_text(ldsw_board((d/'board.repl').read_text(),profile))
  runtime=(d/'run.py').read_text();needle='except Exception as error:\n'
  if runtime.count(needle)!=1:raise ValueError('Runtime boundary differs')
  runtime=runtime.replace(needle,MARKER+needle);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime)
  derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,ldsw_state=profile),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
  log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(n):
   found=[json.loads(x.split(n+' ',1)[1]) for x in log.splitlines() if x.startswith(n+' ')]
   if len(found)!=1:raise ValueError('Missing '+n)
   return found[0]
  ldsw=marker('BLACKWALL_PMIC_LDSW');report=dict(name=name,observed=v,ldsw=ldsw,buck=marker('BLACKWALL_PMIC_BUCK'),queued=marker('BLACKWALL_PMIC_QUEUED'),charger_status=marker('BLACKWALL_PMIC_CHARGER_STATUS'),timer=marker('BLACKWALL_PMIC_TIMER'),peer=marker('BLACKWALL_PMIC_RESTORE'),image_id=IMAGE,raw_main_sha256=digest(d/'main.bin'),selected_hypotheses=before['selected_hypotheses'],additional_hypotheses=before['additional_hypotheses']+[dict(ldsw_state=profile,rail_response=False,gpio_or_vset_response=False)],boot_verified=False,hardware_validated=False,installable=False)
  (d/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  if ldsw['profile']!=profile:raise ValueError('Wrong LDSW profile')
  if profile!='source-reset-storage' and boundary_state(v)!=boundary_state(v0):raise ValueError('Default/unknown LDSW boundary changed')
  if profile=='source-reset-storage' and not ldsw['addresses']:raise ValueError('No LDSW reset storage')
  row=dict(name=name,pc=hex(v['pc']),ldsw=ldsw,guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 compared={'stock23','cfw'}.issubset({x[0] for x in plans})
 if compared:
  for f in ['board.repl','strict.cs','result.py','probe.resc']:
   if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW models differ')
  if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,stock_cfw_compared=compared,scope='original ARM/configuration/task request subset; no physical rail/FSM/full boot proof'),indent=2)+'\n')
if __name__=='__main__':main()
