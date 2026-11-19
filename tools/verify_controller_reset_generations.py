"""Exercise bounded controller generations using actual Renode transactions."""
import argparse
import json
from pathlib import Path
import shutil
from controller_reset_generation_model import compose
from run_runtime_connection_m55 import sha
from run_renode_m55_probe import execute
from native_replay import IMAGE

EXTRA='''
r=g.Em9305Reset
check('explicit-limit',p.ControllerResetLimit==1 and p.ControllerGeneration==0)
before=(p.Frames,p.CommandsAccepted,p.Replies)
r.SetReset(False,100000);r.SetReset(False,100010)
check('held-denies-traffic',str(p.State)=='Exhausted' and p.ReadyLevel==-1 and not p.CanBegin(2))
r.SetReset(True,100100)
check('qualified-new-generation',p.ControllerGeneration==1 and str(p.State)=='Queued' and p.ReadyLevel==1)
check('fresh-counters',p.Frames==p.CommandsAccepted==p.Replies==p.RuntimeEventsConsumed==p.ReadvertisingCommands==p.ReadvertisingRepliesDropped==0)
check('previous-generation-record',str(p.ControllerGenerationHistory).startswith('0:'+':'.join(str(int(x)) for x in before)+':4:1:0:1:'))
check('repeated-low-preserves-epoch',r.AssertedAt==100000 and r.ReleasedAt==100100)
check('fresh-handshake',readframe()==[4,255,1,1])
cs(False);p.BeginTransaction(2);p.Transmit(0x42);p.Transmit(0);p.FinishTransmission()
prop=p.GetType().GetProperty('CurrentCommand',BindingFlags.Instance|BindingFlags.NonPublic)
first=[int(x) for x in prop.GetValue(p,None)]
check('first-startup-command',first==[1,1,253,5,136,75,240,0,8])
check('bad-first-command-rejected',not p.CanExchange(first[0]^1,1))
cs(True)
# Reset the whole mock machine before independent invalid-state cases.
g.Reset();prime();p.QualifiedRelease(True)
check('release-without-assertion-rejected',p.ControllerGeneration==0 and str(p.State)=='Exhausted' and str(p.ResetGenerationRejection)=='missing-assertion')
g.Reset();prime();r.SetReset(False,200);r.SetReset(True,200)
check('short-pulse-rejected',not r.Released and p.ControllerGeneration==0 and str(p.State)=='Exhausted' and str(p.ResetGenerationRejection)=='short-pulse')
g.Reset();prime();cs(False);r.SetReset(False,300);cs(True);r.SetReset(True,400)
check('selected-at-assertion-rejected',p.ControllerGeneration==0 and str(p.State)=='Exhausted' and str(p.ResetGenerationRejection)=='unfinished-or-selected-transport')
g.Reset();prime();r.SetReset(False,500);cs(False);r.SetReset(True,600)
check('selected-at-release-rejected',p.ControllerGeneration==0 and str(p.State)=='Exhausted' and str(p.ResetGenerationRejection)=='selected-at-release')
g.Reset();cfg(149,0x183);cs(True);p.QualifiedRelease(True);readframe();r.SetReset(False,700);r.SetReset(True,800)
check('unfinished-startup-rejected',p.ControllerGeneration==0 and str(p.State)=='Exhausted')
g.Reset();prime();check('pending-runtime-event-enqueued',p.TryQueueRuntimeConnection());r.SetReset(False,810);r.SetReset(True,850)
check('pending-event-rejected',p.ControllerGeneration==0 and str(p.State)=='Exhausted')
g.Reset();prime();r.SetReset(False,900);r.SetReset(True,1000);prime()
check('second-generation-startup-strict',p.ControllerGeneration==1 and p.CommandsAccepted==baseline[0] and p.Replies==baseline[1] and str(p.State)=='Complete')
r.SetReset(False,1100);r.SetReset(True,1200)
check('generation-limit-rejected',p.ControllerGeneration==1 and str(p.State)=='Exhausted' and str(p.ResetGenerationRejection)=='generation-limit')
g.Reset()
# PARTIAL_WORKFLOW
data=list(bytearray.fromhex(commands[1]))
cs(False);p.BeginTransaction(2);p.Transmit(0x42);capacity=int(p.Transmit(0));p.FinishTransmission();p.BeginTransaction(capacity)
for value in data[:capacity]:p.Transmit(value)
p.FinishTransmission();cs(True)
check('partial-runtime-write-fixture',str(p.State)=='Complete' and p.ReadvertisingCommands==0 and not p.RuntimeEventPending)
r.SetReset(False,1300);r.SetReset(True,1400)
check('partial-runtime-write-rejected',p.ControllerGeneration==0 and str(p.State)=='Exhausted')
g.Reset();prime();r.SetReset(False,1500);r.SetReset(True,1600);p.QualifiedRelease(True)
check('empty-new-generation-needs-assertion',str(p.State)=='Exhausted' and str(p.ResetGenerationRejection)=='missing-assertion')
g.Reset();prime();r.SetReset(False,1700);r.SetReset(True,1800);r.SetReset(False,1900);r.SetReset(True,2000)
check('empty-new-generation-still-bounded',p.ControllerGeneration==1 and str(p.State)=='Exhausted' and str(p.ResetGenerationRejection)=='generation-limit')
g.Reset();check('machine-reset-clears-history',p.ControllerGeneration==0 and str(p.ControllerGenerationHistory)=='' and str(p.ResetGenerationRejection)=='')
for limit in (-1,5):
 try:BlackwallEm9305EventPeer('04ff0101',controllerResetLimit=limit)
 except Exception:check('invalid-limit-'+str(limit),True)
 else:raise ValueError('Invalid limit accepted')
try:BlackwallEm9305EventPeer('04ff0101',controllerResetLimit=1)
except Exception:check('missing-runtime-profile-rejected',True)
else:raise ValueError('No runtime profile accepted')
Console.WriteLine('BLACKWALL_RUNTIME_ATT_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_firmware_executed=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--disabled',action='store_true');a=p.parse_args()
    ref=a.simulator/'hci-response-loss-unit-01';manifest=json.loads((a.simulator/'hci-response-loss-research-01/manifest.json').read_text())
    a.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    for n in ('strict.cs','board.repl','probe.resc','test.py'):
        pin=manifest['files'][str((ref/n).relative_to(a.simulator))]
        if sha(ref/n)!=pin['sha256']:raise ValueError('Changed unit reference')
        shutil.copyfile(ref/n,a.output/n)
    p=a.output/'strict.cs';p.write_text(compose(p.read_text()))
    if not a.disabled:
        p=a.output/'board.repl';p.write_text(p.read_text().replace('    runtimeReadvertise: true\n','    runtimeReadvertise: true\n    controllerResetLimit: 1\n'))
        p=a.output/'test.py';prefix=p.read_text().replace(' p.QualifiedRelease(True);readframe()'," if str(p.State)=='Unreleased':p.QualifiedRelease(True)\n readframe()").split("g.Reset();check('loss-reset'")[0]
        workflow=prefix[prefix.index('prime();baseline='):prefix.index('dropped=[]')]
        p.write_text(prefix+EXTRA.replace('# PARTIAL_WORKFLOW',workflow))
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=90)
    rows=[json.loads(l.split('BLACKWALL_RUNTIME_ATT_UNIT ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_RUNTIME_ATT_UNIT ')]
    if len(rows)!=1:raise ValueError(log[-2200:])
    (a.output/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],checks=rows[0]['count'])))

if __name__=='__main__':main()
