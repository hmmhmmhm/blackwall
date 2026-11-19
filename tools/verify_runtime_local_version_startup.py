"""Reuse exact local-version SPI tests at completed startup, without synthetic ATT events."""
import argparse,ast,json
from pathlib import Path
from verify_runtime_local_version import constant,IDENTITY,REPLY
from runtime_local_version_model import component
from run_renode_m55_probe import execute
from native_replay import IMAGE


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');p.add_argument('--disabled',action='store_true');p.add_argument('--split-chunks',action='store_true');p.add_argument('--limit',type=int,default=2);a=p.parse_args();s=a.simulator;o=a.output
 if not 1<=a.limit<=32 or not o.resolve().is_relative_to(s.resolve()):raise ValueError('Private output and bounded query limit required')
 old,new=component() if a.baseline else component(completed_startup=True)
 if o.exists():raise ValueError('Preserve prior unit evidence')
 ref=s/'gaf-natural-timeout-native-03';model=(ref/'strict.cs').read_text();assert model.count(old)==1
 board=(ref/'board.repl').read_text()
 if not a.disabled:
  assert board.count('    runtimeConnectionEventHex:')==1
  board=board.replace('    runtimeConnectionEventHex:','    runtimeLocalVersionHex: "'+IDENTITY+'"\n    runtimeLocalVersionLimit: '+str(a.limit)+'\n    runtimeConnectionEventHex:')
 if a.split_chunks:
  assert board.count('    writeCapacity: 9\n')==1
  board=board.replace('    writeCapacity: 9\n','    writeCapacity: 2\n')
 root=Path(__file__).parent
 prefix=constant('SCRIPT',root/'verify_runtime_event_gpio.py').split("check('runtime-opt-in'")[0]
 prefix=prefix.replace(' p.BeginReceive(n);data='," if getattr(p,'LocalVersionCommands',0)>getattr(p,'LocalVersionReplies',0):\n  check('version-short-receive-denied',not p.CanReceive(n-1))\n  check('version-long-receive-denied',not p.CanReceive(n+1))\n p.BeginReceive(n);data=")
 definitions=constant('TEST',root/'verify_runtime_att_workflow.py').split('prime();baseline=')[0]
 nodes=[n.value for n in ast.walk(ast.parse((root/'verify_runtime_local_version.py').read_text())) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'version-wrong-pin-profile-denied' in n.value]
 assert len(nodes)==1
 extra=nodes[0].replace('p.RuntimeEventsConsumed==3 and p.RuntimeRemoteRepliesConsumed==2','p.RuntimeEventsConsumed==0 and p.RuntimeRemoteRepliesConsumed==0').replace('q.RisingEdges==7+LIMIT','q.RisingEdges==LIMIT')
 extra=extra.replace('REPLY',repr(REPLY)).replace('IDENTITY',repr(IDENTITY)).replace('LIMIT',str(a.limit))
 extra+="cs(False);check('startup-version-limit-exhausted',not p.CanBegin(2));cs(True)\n"
 if a.disabled:extra="cs(False);check('startup-version-default-off',not p.CanBegin(2));cs(True)\n"
 code=prefix+definitions+"prime();baseline=(int(p.CommandsAccepted),int(p.Replies))\ncheck('startup-only-prerequisites',baseline==(59,60) and p.RuntimeEventsConsumed==0 and p.RuntimeRemoteRepliesConsumed==0)\n"+extra+"p.Reset();check('startup-version-reset',p.LocalVersionCommands==p.LocalVersionReplies==0 and not p.RuntimeEventPending)\nConsole.WriteLine('BLACKWALL_STARTUP_VERSION_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,synthetic_att_events=False)))\n"
 compile(code,'unit','exec');o.mkdir(mode=0o700);(o/'exports').mkdir(mode=0o700)
 (o/'strict.cs').write_text(model.replace(old,new,1));(o/'board.repl').write_text(board);(o/'test.py').write_text(code)
 (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "startup-version"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=bind,source='+str(o)+',target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=90)
 rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_STARTUP_VERSION_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing startup version result')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,checks=rows[0]['count'])))

if __name__=='__main__':main()
