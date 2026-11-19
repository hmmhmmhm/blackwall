"""Test one lost command completion through actual Renode peer transactions."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from hci_response_loss_model import compose
from native_replay import IMAGE
from run_renode_m55_probe import execute


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--disabled',action='store_true');a=p.parse_args()
    s=a.simulator;ref=s/'runtime-reconnect-model-unit-03';pins=json.loads((s/'runtime-readvertise-reconnect-research-01/manifest.json').read_text())['files']
    a.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    for n in ('strict.cs','board.repl','probe.resc','test.py'):
        pin=pins[str((ref/n).relative_to(s))]
        if hashlib.sha256((ref/n).read_bytes()).hexdigest()!=pin['sha256']:raise ValueError('Changed device test reference')
        shutil.copy2(ref/n,a.output/n)
    path=a.output/'strict.cs';path.write_text(compose(path.read_text()))
    path=a.output/'board.repl';path.write_text(path.read_text().replace('    runtimeReadvertise: true\n','    runtimeReadvertise: true\n    runtimeDropFirstReadvertisingReply: '+str(not a.disabled).lower()+'\n'))
    if not a.disabled:
        path=a.output/'test.py';prefix=path.read_text().split('for n,index in enumerate((1,4)):')[0]
        suffix='''
dropped=[]
p.ReadvertisingReplyDropped+=Action(lambda:dropped.append(True))
check('selected-loss',p.DropFirstReadvertisingReply)
send(list(bytearray.fromhex(commands[1])))
check('one-completion-lost',p.ReadvertisingCommands==1 and p.ReadvertisingReplies==0 and p.ReadvertisingRepliesDropped==1)
check('no-reply-event',not p.RuntimeEventPending and p.ReadyLevel==0 and str(p.State)=='Complete')
check('no-completed-advertising',completed==[] and dropped==[True])
check('no-reconnect-after-loss',not p.TryQueueRuntimeReconnection())
check('startup-unchanged',(int(p.CommandsAccepted),int(p.Replies))==baseline)
check('no-extra-ready-edge',q.RisingEdges==8)
check('no-fake-receive',not p.CanReceive(7))
g.Reset();check('loss-reset',p.ReadvertisingCommands==p.ReadvertisingReplies==p.ReadvertisingRepliesDropped==0 and not p.RuntimeEventPending)
try:BlackwallEm9305EventPeer('04ff0101',runtimeDropFirstReadvertisingReply=True)
except Exception:check('loss-without-readvertise-denied',True)
else:raise ValueError('Invalid loss option accepted')
Console.WriteLine('BLACKWALL_RUNTIME_ATT_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_firmware_executed=False)))
'''
        path.write_text(prefix+suffix)
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=90)
    rows=[json.loads(l.split('BLACKWALL_RUNTIME_ATT_UNIT ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_RUNTIME_ATT_UNIT ')]
    if len(rows)!=1:raise ValueError(log[-1800:])
    (a.output/'unit-report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],checks=rows[0]['count'],loss_enabled=not a.disabled)))


if __name__=='__main__':main()
