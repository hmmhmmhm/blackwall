"""Exercise exact optional re-advertising and reconnection in Renode, without firmware."""
import argparse
import json
from pathlib import Path
import re

from verify_runtime_event_gpio import build,SCRIPT
from verify_runtime_att_workflow import TEST
from run_runtime_connection_m55 import att_packets
from runtime_reconnect_model import compose
from run_renode_m55_probe import execute
from native_replay import IMAGE


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--disabled',action='store_true');a=p.parse_args()
    build(a.simulator,a.output)
    path=a.output/'strict.cs';path.write_text(compose(path.read_text()))
    path=a.output/'board.repl';board=path.read_text();anchor='    runtimeConnectionEventHex:'
    board=board.replace(anchor,'    runtimeReadvertise: '+str(not a.disabled).lower()+'\n    runtimeDisconnectEventHex: "04050400400013"\n    runtimeAttPacketsHex: "'+';'.join(att_packets())+'"\n    runtimeHostAclHex: "02400007000300040002f700"\n    runtimeRandHex: "0102030405060708"\n    runtimeRssi: -42\n    runtimeRemoteFeaturesHex: "0100000000000000"\n'+anchor);path.write_text(board)
    packed=bytes.fromhex(re.search(r'advertisingInitializationHex: "([^"]+)"',board)[1]);commands=[];replies=[];offset=0
    for size in (10,19,36,36,5):
        commands.append(packed[offset:offset+size].hex());offset+=size;replies.append(packed[offset:offset+7].hex());offset+=7
    extra='''
check('reconnect-before-close-denied',not p.TryQueueRuntimeReconnection())
check('disconnect-queued',p.TryQueueRuntimeDisconnect())
check('disconnect-exact',drain()==list(bytearray.fromhex('04050400400013')))
check('reconnect-before-advertising-denied',not p.TryQueueRuntimeReconnection())
completed=[]
from System import Action
p.ReadvertisingCompleted+=Action(lambda:completed.append(True))
for n,index in enumerate((1,4)):
 check('reconnect-before-reply-'+str(n),not p.TryQueueRuntimeReconnection())
 send(list(bytearray.fromhex(commands[index])))
 check('exact-rearm-reply-'+str(n),drain()==list(bytearray.fromhex(replies[index])))
 check('rearm-counter-'+str(n),p.ReadvertisingCommands==p.ReadvertisingReplies==n+1)
check('completion-once',completed==[True])
check('exact-rearm-commands',str(p.ReadvertisingAccepted)==';'.join((commands[1],commands[4])))
check('startup-counters-preserved',(int(p.CommandsAccepted),int(p.Replies))==baseline)
check('reconnect-queued',p.TryQueueRuntimeReconnection())
check('duplicate-reconnect-denied',not p.TryQueueRuntimeReconnection())
check('reconnect-event-exact',drain()==list(bytearray.fromhex('043e1301004000010011223344556618000000c80000')))
check('five-events',p.RuntimeEventsConsumed==5 and not p.RuntimeEventPending)
check('replay-reconnect-denied',not p.TryQueueRuntimeReconnection())
'''
    if a.disabled:
        extra='''
check('disabled',not p.RuntimeReadvertise)
check('disconnect-queued',p.TryQueueRuntimeDisconnect())
check('disconnect-exact',drain()==list(bytearray.fromhex('04050400400013')))
check('disabled-reconnect-denied',not p.TryQueueRuntimeReconnection())
cs(False);check('disabled-rearm-denied',not p.CanBegin(2));cs(True)
'''
    test=TEST.replace("check('no-replay',",extra+"check('no-replay',")
    test=test.replace('for value in data[offset:offset+n]:p.Transmit(value)',"for value in data[offset:offset+n]:\n   if p.RuntimeEventsConsumed==4:check('wrong-rearm-byte-'+str(len(checks)),not p.CanExchange(value^1,1))\n   p.Transmit(value)")
    test=test.replace("Console.WriteLine('BLACKWALL_RUNTIME_ATT_UNIT '","check('rearm-reset',p.ReadvertisingCommands==p.ReadvertisingReplies==0 and not p.TryQueueRuntimeReconnection())\nConsole.WriteLine('BLACKWALL_RUNTIME_ATT_UNIT '")
    prerequisite='''
try:BlackwallEm9305EventPeer('04ff0101',runtimeReadvertise=True)
except Exception:check('missing-disconnect-profile-rejected',True)
else:raise Exception('Readvertising without prerequisites accepted')
'''
    code=SCRIPT.split("check('runtime-opt-in'")[0]+prerequisite+'packets='+repr(att_packets())+'\ncommands='+repr(commands)+'\nreplies='+repr(replies)+'\n'+test
    compile(code,'test','exec');(a.output/'test.py').write_text(code)
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=90)
    rows=[json.loads(l.split('BLACKWALL_RUNTIME_ATT_UNIT ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_RUNTIME_ATT_UNIT ')]
    if len(rows)!=1:raise ValueError(log[-2000:])
    (a.output/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],checks=rows[0]['count'])))


if __name__=='__main__':main()
