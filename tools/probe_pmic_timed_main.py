"""Run pinned original startup with an explicit virtual stopped PMIC watchdog, without hardware."""
import argparse,json,shutil,hashlib
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Use fresh evidence directory')
 o.mkdir(mode=0o700);base=s/'pmic-charger-main-01';old=(s/'pmic-charger-unit-01/peer.cs').read_bytes();root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes();(o/'runner.py').write_bytes(Path(__file__).read_bytes());(o/'root.cs').write_bytes(root);(o/'timed.cs').write_bytes(timed);rows=[]
 for name,key,enabled in [('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-no-timer','stock24',False)]:
  src=base/key;before=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text());file={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes())
  if raw!=(src/'main.bin').read_bytes() or v0!=before['observed'] or before['image_id']!=IMAGE:raise ValueError('Frozen source differs')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(src/f) for f in FILES}
  for f in FILES:shutil.copyfile(src/f,d/f)
  validate_assets(d,original);data=(d/'strict.cs').read_bytes()
  if not data.endswith(old):raise ValueError('Root suffix differs')
  (d/'strict.cs').write_bytes(data[:-len(old)]+root+b'\n'+timed)
  board=(d/'board.repl').read_text();node='pointerProbe: Miscellaneous.BlackwallPmicRestoreProbe @ iom7 0x6b\n    profile: "source-reset-readonly"\n    interruptState: "explicit-idle"\n    gpioState: "guest-storage"\n    chargerState: "guest-storage"\n'
  if board.count(node)!=1:raise ValueError('PMIC attachment differs')
  if enabled:(d/'board.repl').write_text(board.replace(node,'pointerProbe: Miscellaneous.BlackwallPmicTimedProbe @ iom7 0x6b\n    timerProfile: "fast-reset-stopped"\n'))
  text=(d/'run.py').read_text();needle="    peer=m['sysbus.iom7.pointerProbe']\n"
  if text.count(needle)!=1:raise ValueError('Peer report differs')
  if enabled:
   text=text.replace(needle,needle.rstrip()+'.Inner\n')
   extra="    timed_peer=m['sysbus.iom7.pointerProbe']\n    wt=timed_peer.Timer\n    Console.WriteLine('BLACKWALL_PMIC_TIMER '+json.dumps(dict(config_known=bool(wt.ConfigKnown),config=int(wt.Config),target_known=bool(wt.TargetKnown),target=int(wt.Target),running=bool(wt.Running),starts=int(wt.Starts),stops=int(wt.Stops),kicks=int(wt.Kicks),strobes=int(wt.Strobes),warnings=int(wt.Warnings),reset_requested=bool(wt.ResetRequested),reset_requests=int(wt.ResetRequests),timer_writes=int(timed_peer.TimerWrites),timer_reads=int(timed_peer.TimerReads),repeated_start_attempts=int(timed_peer.RepeatedStarts),read_hole_mock=int(timed_peer.RecoveryReadHoleMock))))\n"
   if text.count('except Exception as error:\n')!=1:raise ValueError('Runtime boundary differs')
   text=text.replace('except Exception as error:\n',extra+'except Exception as error:\n')
  compile(text,'run.py','exec');(d/'run.py').write_text(text);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,timer_profile='fast-reset-stopped' if enabled else None,read_hole_mock=None),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(name):
   records=[json.loads(x.split(name+' ',1)[1]) for x in log.splitlines() if x.startswith(name+' ')]
   if len(records)!=1:raise ValueError('Missing '+name)
   return records[0]
  state=marker('BLACKWALL_PMIC_RESTORE');obs=marker('BLACKWALL_OBSERVATION');timer=marker('BLACKWALL_PMIC_TIMER') if enabled else None;r=dict(name=name,observed=v,peer=state,timer=timer,observation=obs,image_id=IMAGE,raw_main_sha256=digest(d/'main.bin'),selected_hypotheses=before['selected_hypotheses'],additional_hypothesis=dict(timer_profile='fast-reset-stopped' if enabled else None,clock='virtual-500hz' if enabled else None,read_holes='unsupported',physical_reset=False,gpio_connected=False),boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n')
  if enabled:
   if not timer['config_known'] or timer['config']!=10 or not timer['target_known'] or timer['target']!=0x3c00 or timer['strobes']!=1:raise ValueError('Original timer setup did not complete')
  elif boundary_state(v)!=boundary_state(v0):raise ValueError('Default timer boundary changed')
  row=dict(name=name,pc=hex(v['pc']),timer=timer,guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['board.repl','strict.cs','result.py','probe.resc']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW model differs')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='original timer setup under explicit virtual stopped state; no physical watchdog, reset or full boot'),indent=2)+'\n')
if __name__=='__main__':main()
