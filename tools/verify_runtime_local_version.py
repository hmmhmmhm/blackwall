"""Exercise an explicit controller version response through SPI and GPIO, no guest firmware."""
import argparse,ast,json
from pathlib import Path
from run_renode_m55_probe import execute
from reset_restart_profiles import RENODE_IMAGE

IDENTITY='0d34120d5a007856'
REPLY='040e0c01011000'+IDENTITY

def constant(name,file):
 for node in ast.parse(file.read_text()).body:
  if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):return ast.literal_eval(node.value)
 raise ValueError('Missing fixture constant '+name)

def main():
 q=argparse.ArgumentParser(description=__doc__);q.add_argument('simulator',type=Path);q.add_argument('output',type=Path);q.add_argument('--baseline',action='store_true');q.add_argument('--disabled',action='store_true');q.add_argument('--split-chunks',action='store_true');q.add_argument('--limit',type=int,default=2);a=q.parse_args();s=a.simulator;o=a.output
 if not 1<=a.limit<=32:raise ValueError('Query limit1..32 required')
 if o.exists() or not o.resolve().is_relative_to(s.resolve()):raise ValueError('Fresh private output required')
 root=Path(__file__).parent;ref=s/'gaf-natural-timeout-native-03';model=(ref/'strict.cs').read_text();board=(ref/'board.repl').read_text()
 if not a.baseline:
  from runtime_local_version_model import compose
  model=compose(model)
  if not a.disabled:board=board.replace('    runtimeConnectionEventHex:','    runtimeLocalVersionHex: "'+IDENTITY+'"\n    runtimeLocalVersionLimit: '+str(a.limit)+'\n    runtimeConnectionEventHex:')
 if a.split_chunks:
  if board.count('    writeCapacity: 9\n')!=1:raise ValueError('Unknown write capacity')
  board=board.replace('    writeCapacity: 9\n','    writeCapacity: 2\n')
 o.mkdir(mode=0o700,parents=True);(o/'strict.cs').write_text(model);(o/'board.repl').write_text(board)
 prefix=constant('SCRIPT',root/'verify_runtime_event_gpio.py').split("check('runtime-opt-in'")[0]
 test=constant('TEST',root/'verify_runtime_att_workflow.py')
 extra='''
cfg(117,0x53);cs(False);check('version-wrong-pin-profile-denied',not p.CanBegin(2));cs(True);cfg(117,0x93)
for query in range(LIMIT):
 data=list(bytearray.fromhex('01011000'));offset=0
 while offset<len(data):
  cs(False);check('version-header-supported',p.CanBegin(2))
  if query==0 and offset==0:
   check('version-profile-explicit',p.RuntimeLocalVersionLimit==LIMIT)
   check('version-not-yet-sent',p.LocalVersionCommands==p.LocalVersionReplies==0)
  p.BeginTransaction(2);p.Transmit(0x42);capacity=int(p.Transmit(0));p.FinishTransmission()
  n=min(capacity,len(data)-offset)
  check('wrong-write-length-'+str(query)+'-'+str(offset),not p.CanBegin(n+1))
  p.BeginTransaction(n)
  for value in data[offset:offset+n]:
   check('wrong-command-byte-'+str(query)+'-'+str(offset)+'-'+str(value),not p.CanExchange(value^1,1))
   p.Transmit(value)
  check('query-not-committed-before-cs-'+str(query)+'-'+str(offset),p.LocalVersionCommands==query)
  p.FinishTransmission();cs(True);offset+=n
  if offset<len(data):check('partial-query-no-reply-'+str(query)+'-'+str(offset),p.LocalVersionCommands==query and not p.RuntimeEventPending)
 check('version-pending-'+str(query),p.LocalVersionCommands==query+1 and p.LocalVersionReplies==query and p.RuntimeEventPending and p.ReadyLevel==1)
 cs(False);p.BeginTransaction(2);check('write-while-reply-pending-denied-'+str(query),not p.CanExchange(0x42,1));p.Transmit(0x81);cs(True)
 check('aborted-reply-header-retained-'+str(query),p.RuntimeEventPending and p.LocalVersionReplies==query)
 check('version-exact-'+str(query),drain()==list(bytearray.fromhex(REPLY)))
 check('version-consumed-'+str(query),p.LocalVersionReplies==query+1 and not p.RuntimeEventPending and p.ReadyLevel==0 and not q.IRQ.IsSet)
check('version-startup-preserved',(int(p.CommandsAccepted),int(p.Replies))==baseline)
check('version-events-preserved',p.RuntimeEventsConsumed==3 and p.RuntimeRemoteRepliesConsumed==2)
check('version-counter-and-edge',p.LocalVersionCommands==p.LocalVersionReplies==LIMIT and q.RisingEdges==7+LIMIT)
for limit in (-1,1,33):
 try:BlackwallEm9305EventPeer('04ff0101',runtimeLocalVersionLimit=limit)
 except Exception as error:check('version-invalid-limit-'+str(limit),'Local version limit/profile mismatch' in str(error))
 else:raise Exception('Invalid local version profile accepted')
try:BlackwallEm9305EventPeer('04ff0101',runtimeLocalVersionHex=IDENTITY,runtimeLocalVersionLimit=1)
except Exception as error:check('version-missing-att-profile','Local version requires' in str(error))
else:raise Exception('Local version without ATT accepted')
'''.replace('REPLY',repr(REPLY)).replace('IDENTITY',repr(IDENTITY)).replace('LIMIT',str(a.limit))
 if a.disabled:extra="check('version-default-off',p.RuntimeLocalVersionLimit==0 and p.LocalVersionCommands==p.LocalVersionReplies==0)\n"
 test=test.replace("check('no-replay',",extra+"check('no-replay',")
 test=test.replace("Console.WriteLine('BLACKWALL_RUNTIME_ATT_UNIT '","check('version-reset',p.LocalVersionCommands==p.LocalVersionReplies==0 and not p.RuntimeEventPending)\nConsole.WriteLine('BLACKWALL_RUNTIME_ATT_UNIT '") if not a.baseline else test
 profile=json.loads((ref/'connection-profile.json').read_text());packets=profile['att_packets'] if 'att_packets' in profile else None
 if packets is None:
  import re
  packets=re.search(r'runtimeAttPacketsHex: "([^"]+)"',board)[1].split(';')
 prefix=prefix.replace(' p.BeginReceive(n);data='," if getattr(p,'LocalVersionCommands',0)>getattr(p,'LocalVersionReplies',0):\n  check('version-short-receive-denied',not p.CanReceive(n-1))\n  check('version-long-receive-denied',not p.CanReceive(n+1))\n p.BeginReceive(n);data=")
 code=prefix+'packets='+repr(packets)+'\n'+test
 code='try:\n'+''.join(' '+line+'\n' for line in code.splitlines())+"except Exception as error:\n from System import Console\n Console.WriteLine('BLACKWALL_VERSION_UNIT_FAILURE '+json.dumps(dict(error=str(error),state=str(p.State),headers=int(p.WriteHeaders),commands=int(p.CommandsAccepted),checks=checks)))\n raise\n"
 compile(code,'generated-test.py','exec');(o/'test.py').write_text(code)
 (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "version-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=90)
 rows=[json.loads(l.split('BLACKWALL_RUNTIME_ATT_UNIT ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_RUNTIME_ATT_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing unit result; inspect '+str(o/'renode.log'))
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],checks=rows[0]['count'])))
if __name__=='__main__':main()
