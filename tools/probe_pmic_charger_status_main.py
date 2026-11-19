"""Replay pinned original ARM with explicit static charger snapshots, without physical devices."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
PLANS=[('stock24','stock24','source-reset-snapshot'),('stock23','stock23','source-reset-snapshot'),
       ('cfw','cfw','source-reset-snapshot'),('stock24-battery-detected','stock24','battery-detected-idle-snapshot'),
       ('stock24-status-unknown','stock24',None)]
MARKER="    Console.WriteLine('BLACKWALL_PMIC_CHARGER_STATUS '+json.dumps(dict(profile=None if peer.ChargerStatusProfile is None else str(peer.ChargerStatusProfile),addresses=[int(x) for x in peer.ChargerStatusAddresses],values=[int(x) for x in peer.ChargerStatusValues],reads=int(peer.ChargerStatusReads),bytes=int(peer.ChargerStatusBytes),read_addresses=[int(x) for x in peer.ChargerStatusReadAddresses],read_payloads=[str(x) for x in peer.ChargerStatusReadPayloads])))\n"

def status_board(board,profile):
 if profile not in (None,'source-reset-snapshot','battery-detected-idle-snapshot'):raise ValueError('Unknown status snapshot')
 needle='    timerProfile: "fast-reset-stopped"\n'
 if board.count(needle)!=1 or 'chargerStatusProfile:' in board:raise ValueError('Unexpected PMIC status attachment')
 return board if profile is None else board.replace(needle,needle+'    chargerStatusProfile: "'+profile+'"\n')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',action='append',dest='cases');p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 plans=[x for x in PLANS if not a.cases or x[0] in a.cases]
 if a.cases and set(a.cases)-{x[0] for x in PLANS}:raise ValueError('Unknown case')
 if o.exists():raise ValueError('Fresh output required')
 o.mkdir(mode=0o700);base=s/'pmic-queued-main-01';old=(base/'root.cs').read_bytes()+b'\n'+(base/'timed.cs').read_bytes();root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes()
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
  (d/'strict.cs').write_bytes(strict[:-len(old)]+root+b'\n'+timed)
  (d/'board.repl').write_text(status_board((d/'board.repl').read_text(),profile))
  runtime=(d/'run.py').read_text();needle='except Exception as error:\n'
  if runtime.count(needle)!=1:raise ValueError('Runtime boundary differs')
  runtime=runtime.replace(needle,MARKER+needle);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime)
  derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,charger_status_profile=profile,static_snapshot=True if profile else None),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
  log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(n):
   found=[json.loads(x.split(n+' ',1)[1]) for x in log.splitlines() if x.startswith(n+' ')]
   if len(found)!=1:raise ValueError('Missing '+n)
   return found[0]
  status=marker('BLACKWALL_PMIC_CHARGER_STATUS');queue=marker('BLACKWALL_PMIC_QUEUED');timer=marker('BLACKWALL_PMIC_TIMER');peer=marker('BLACKWALL_PMIC_RESTORE')
  report=dict(name=name,observed=v,charger_status=status,queued=queue,timer=timer,peer=peer,image_id=IMAGE,raw_main_sha256=digest(d/'main.bin'),selected_hypotheses=before['selected_hypotheses'],additional_hypothesis=dict(charger_status_profile=profile,static_snapshot=profile is not None,charging_fsm=False),boot_verified=False,hardware_validated=False,installable=False)
  (d/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  if status['profile']!=profile:raise ValueError('Wrong selected snapshot')
  if profile is None:
   if status['reads']!=0 or boundary_state(v)!=boundary_state(v0):raise ValueError('Default status boundary changed')
  elif not status['reads'] or 0x334 not in status['read_addresses']:raise ValueError('No original status read')
  row=dict(name=name,pc=hex(v['pc']),charger_status=status,guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 compared={'stock23','cfw'}.issubset({x[0] for x in plans})
 if compared:
  for f in ['board.repl','strict.cs','result.py','probe.resc']:
   if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW models differ')
  if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,stock_cfw_compared=compared,scope='original ARM with optional fixed digital status snapshot; no physical/FSM/full boot proof'),indent=2)+'\n')
if __name__=='__main__':main()
