"""Verify exact later-generation commands using captured original sender buffers."""
import argparse
import json
from pathlib import Path
import shutil
from post_reset_advertising_model import compose
from verify_kv_persistence_cycle import validate_capture
from run_runtime_connection_m55 import sha
from run_renode_m55_probe import execute
from native_replay import IMAGE

EXTRA='''
r=g.Em9305Reset;r.SetReset(False,10000);r.SetReset(True,10100)
check('new-generation',p.ControllerGeneration==1 and str(p.State)=='Queued')
check('fresh-active-event',readframe()==[4,255,1,1])
history=str(p.ControllerGenerationHistory).split(':')[8].split(',')
def send_checked(data):
 offset=0
 while offset<len(data):
  cs(False);p.BeginTransaction(2);p.Transmit(0x42);capacity=int(p.Transmit(0));p.FinishTransmission();n=min(capacity,len(data)-offset);p.BeginTransaction(n)
  for value in data[offset:offset+n]:
   check('exact-byte-'+str(len(checks)),p.CanExchange(value,1))
   check('wrong-byte-'+str(len(checks)),not p.CanExchange(value^1,1))
   p.Transmit(value)
  p.FinishTransmission();cs(True);offset+=n
for index in range(54):
 send_checked(list(bytearray.fromhex(history[index])))
 while str(p.State)=='ReplyQueued':readframe()
check('retained-startup-prefix',p.CommandsAccepted==54 and p.Replies==55)
for n,index in enumerate(order):
 send_checked(list(bytearray.fromhex(history[54+index])))
 expected=list(bytearray.fromhex('040e0401'+history[54+index][2:6]+'00'))
 check('exact-reordered-reply-'+str(n),readframe()==expected)
check('five-exact-commands',p.CommandsAccepted==59 and p.Replies==60 and p.AdvertisingCommandsAccepted==p.AdvertisingRepliesConsumed==5 and str(p.State)=='Complete')
cs(False);check('no-extra-startup',not p.CanBegin(2));cs(True)
try:BlackwallEm9305EventPeer('04ff0101',postResetAdvertisingDataFirst=True)
except Exception:check('missing-generations-denied',True)
else:raise ValueError('Invalid post-reset option accepted')
Console.WriteLine('BLACKWALL_RUNTIME_ATT_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_firmware_executed=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--disabled',action='store_true');a=p.parse_args()
    s=a.simulator;ref=s/'controller-reset-generations-unit-05';pins=json.loads((s/'controller-reset-generations-research-01/manifest.json').read_text())['files'];capture=s/'post-reset-advertising-native-01';validate_capture(capture)
    v=json.loads((capture/'exports/hci-emission.json').read_text());packets=[p for row,p in zip(v['rows'],v['packets']) if row[6]==1 and int.from_bytes(bytes.fromhex(p[:4]),'little') in (0x2005,0x2006,0x2008,0x2009,0x200a)]
    if [p[:4] for p in packets]!=['0520','0820','0920','0620','0a20']:raise ValueError('Changed observed order')
    a.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    for n in ('strict.cs','board.repl','probe.resc','test.py'):
        if sha(ref/n)!=pins[str((ref/n).relative_to(s))]['sha256']:raise ValueError('Changed retained unit')
        shutil.copyfile(ref/n,a.output/n)
    p=a.output/'strict.cs';p.write_text(compose(p.read_text()))
    p=a.output/'board.repl';p.write_text(p.read_text().replace('    controllerResetLimit: 1\n','    controllerResetLimit: 1\n    postResetAdvertisingDataFirst: '+str(not a.disabled).lower()+'\n'))
    p=a.output/'test.py';prefix=p.read_text().split('r=g.Em9305Reset')[0];order=[0,1,2,3,4] if a.disabled else [0,2,3,1,4]
    # The observed full buffers are the oracle for the new order, independent of the model selector.
    check_oracle="\nobserved="+repr(packets)+"\ncheck('captured-advertising-payloads',[history[54+i][2:] for i in [0,2,3,1,4]]==observed)\n"
    code=prefix+'\norder='+repr(order)+'\n'+EXTRA.replace("def send_checked(data):",check_oracle+'\ndef send_checked(data):');compile(code,'test','exec');p.write_text(code)
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=90)
    rows=[json.loads(line.split('BLACKWALL_RUNTIME_ATT_UNIT ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_RUNTIME_ATT_UNIT ')]
    if len(rows)!=1:raise ValueError(log[-1800:])
    (a.output/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,checks=rows[0]['count'],enabled=not a.disabled)))

if __name__=='__main__':main()
