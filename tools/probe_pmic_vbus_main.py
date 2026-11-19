"""Replay immutable original ARM startup with optional VBUS storage, without physical devices."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence directory required')
 o.mkdir(mode=0o700);base=s/'pmic-timed-main-03';old=(base/'root.cs').read_bytes()+b'\n'+(base/'timed.cs').read_bytes();root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes()
 for n,b in [('runner.py',Path(__file__).read_bytes()),('root.cs',root),('timed.cs',timed)]: (o/n).write_bytes(b)
 rows=[]
 for name,key,enabled in [('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-no-vbus','stock24',False)]:
  src=base/key;before=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text());bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  if raw!=(src/'main.bin').read_bytes() or before['observed']!=v0 or before['image_id']!=IMAGE:raise ValueError('Frozen input differs')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(src/f) for f in FILES}
  for f in FILES:shutil.copyfile(src/f,d/f)
  validate_assets(d,original);strict=(d/'strict.cs').read_bytes()
  if not strict.endswith(old):raise ValueError('Frozen PMIC source differs')
  (d/'strict.cs').write_bytes(strict[:-len(old)]+root+b'\n'+timed)
  board=(d/'board.repl').read_text();needle='    timerProfile: "fast-reset-stopped"\n'
  if board.count(needle)!=1:raise ValueError('Timer attachment differs')
  if enabled:(d/'board.repl').write_text(board.replace(needle,needle+'    vbusState: "guest-storage"\n'))
  text=(d/'run.py').read_text();needle='except Exception as error:\n'
  if text.count(needle)!=1:raise ValueError('Runtime boundary differs')
  extra="    Console.WriteLine('BLACKWALL_PMIC_VBUS '+json.dumps(dict(enabled=bool(peer.GuestVbusStorage),current_known=bool(peer.VbusCurrentKnown),current=int(peer.VbusCurrent),suspend_known=bool(peer.VbusSuspendKnown),suspend=int(peer.VbusSuspend),writes=int(peer.VbusWrites),apply_requests=int(peer.VbusApplyRequests))))\n"
  text=text.replace(needle,extra+needle);compile(text,'run.py','exec');(d/'run.py').write_text(text);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,vbus_state='guest-storage' if enabled else None),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(name):
   matches=[json.loads(x.split(name+' ',1)[1]) for x in log.splitlines() if x.startswith(name+' ')]
   if len(matches)!=1:raise ValueError('Missing '+name)
   return matches[0]
  state=marker('BLACKWALL_PMIC_RESTORE');timer=marker('BLACKWALL_PMIC_TIMER');vbus=marker('BLACKWALL_PMIC_VBUS');r=dict(name=name,observed=v,peer=state,timer=timer,vbus=vbus,image_id=IMAGE,raw_main_sha256=digest(d/'main.bin'),boot_verified=False,hardware_validated=False,installable=False,selected_hypotheses=before['selected_hypotheses']);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n')
  if enabled:
   if not vbus['current_known'] or vbus['writes']<1:raise ValueError('VBUS setup did not complete')
  elif boundary_state(v)!=boundary_state(v0):raise ValueError('Default VBUS strict boundary changed')
  row=dict(name=name,pc=hex(v['pc']),vbus=vbus,timer=timer,guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['board.repl','strict.cs','result.py','probe.resc']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW models differ')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='guest VBUS config and apply request storage only; no analog/status/power behavior'),indent=2)+'\n')
if __name__=='__main__':main()
