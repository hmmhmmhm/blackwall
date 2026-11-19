"""Declared controller/phone workflow and exact host packets in Renode, no original guest."""
import argparse,json
from pathlib import Path
from verify_runtime_event_gpio import build,SCRIPT
from run_runtime_connection_m55 import att_packets
from run_renode_m55_probe import execute
from native_replay import IMAGE

TEST='''
def send(data):
 offset=0
 while offset<len(data):
  cs(False);p.BeginTransaction(2);p.Transmit(0x42);capacity=int(p.Transmit(0));p.FinishTransmission()
  n=min(capacity,len(data)-offset);p.BeginTransaction(n)
  for value in data[offset:offset+n]:p.Transmit(value)
  p.FinishTransmission();cs(True);offset+=n
def drain():
 b.WriteDoubleWord(0x40010568,1<<21)
 return readframe()
prime();baseline=(int(p.CommandsAccepted),int(p.Replies))
check('no-att-before-connection',not p.TryQueueRuntimeAtt(0))
check('connection-enqueued',p.TryQueueRuntimeConnection())
check('connection-exact',drain()==list(bytearray.fromhex('043e1301004000010011223344556618000000c80000')))
check('no-mtu-before-host-request',not p.TryQueueRuntimeAtt(0) and not p.TryQueueRuntimeAtt(1))
send(list(bytearray.fromhex('01182000')))
check('rand-command-exact',p.RuntimeRandCommandsAccepted==1)
check('rand-return-parameters',drain()==list(bytearray.fromhex('040e0c011820000102030405060708')))
check('rand-completed',p.RuntimeRandRepliesConsumed==1)
send(list(bytearray.fromhex('02400007000300040002f700')))
check('host-mtu-request-complete',p.RuntimeHostAclConsumed==1 and p.RuntimeEventPending)
check('mtu-response-exact',drain()==list(bytearray.fromhex(packets[0])))
check('time-follows-response',p.RuntimeEventsConsumed==2 and p.RuntimeEventPending)
check('time-h4-acl-exact',drain()==list(bytearray.fromhex(packets[1])))
check('three-runtime-inputs',p.RuntimeEventsConsumed==3 and not p.RuntimeEventPending)
send(list(bytearray.fromhex('010514024000')))
check('rssi-command-exact',p.RuntimeRssiCommandsAccepted==1)
check('rssi-handle-signed-value',drain()==list(bytearray.fromhex('040e07010514004000d6')))
send(list(bytearray.fromhex('011620024000')))
check('remote-command-exact',p.RuntimeRemoteCommandsAccepted==1)
check('remote-command-status',drain()==list(bytearray.fromhex('040f0400011620')))
check('remote-still-pending',p.RuntimeRemoteRepliesConsumed==1 and p.RuntimeEventPending)
check('remote-async-completion',drain()==list(bytearray.fromhex('043e0c040040000100000000000000')))
check('remote-completion-count',p.RuntimeRemoteRepliesConsumed==2 and not p.RuntimeEventPending)
check('startup-counts-unchanged',(int(p.CommandsAccepted),int(p.Replies))==baseline)
check('seven-ready-edges',q.RisingEdges==7)
check('no-replay',not p.TryQueueRuntimeAtt(0) and not p.TryQueueRuntimeAtt(1) and not p.TryQueueRuntimeConnection())
cs(False);check('unknown-next-command-denied',not p.CanBegin(2));cs(True)
g.Reset();check('reset-runtime-counters',p.RuntimeEventsConsumed==p.RuntimeHostAclConsumed==p.RuntimeRandCommandsAccepted==p.RuntimeRandRepliesConsumed==p.RuntimeRssiCommandsAccepted==p.RuntimeRssiRepliesConsumed==p.RuntimeRemoteCommandsAccepted==p.RuntimeRemoteRepliesConsumed==0)
Console.WriteLine('BLACKWALL_RUNTIME_ATT_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_firmware_executed=False,startup_primer_uses_same_class_command_getter=True)))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--disconnect',action='store_true');a=p.parse_args()
    assert a.output.resolve().is_relative_to(a.simulator.resolve())
    build(a.simulator,a.output)
    path=a.output/'board.repl';t=path.read_text();anchor='    runtimeConnectionEventHex:';assert t.count(anchor)==1
    t=t.replace(anchor,'    runtimeAttPacketsHex: "'+';'.join(att_packets())+'"\n    runtimeHostAclHex: "02400007000300040002f700"\n    runtimeRandHex: "0102030405060708"\n    runtimeRssi: -42\n    runtimeRemoteFeaturesHex: "0100000000000000"\n'+anchor);path.write_text(t)
    if a.disconnect:
        path.write_text(path.read_text().replace('    runtimeConnectionEventHex:', '    runtimeDisconnectEventHex: \"04050400400013\"\n    runtimeConnectionEventHex:'))
    prefix=SCRIPT.split("check('runtime-opt-in'")[0]
    test=TEST
    if a.disconnect:
        test=test.replace("prime();baseline=","check('disconnect-before-start-denied',not p.TryQueueRuntimeDisconnect())\nprime();baseline=")
        test=test.replace("check('three-runtime-inputs',","check('disconnect-before-features-denied',not p.TryQueueRuntimeDisconnect())\ncheck('three-runtime-inputs',")
        test=test.replace("check('no-replay',","check('disconnect-enqueued',p.TryQueueRuntimeDisconnect())\ncheck('disconnect-duplicate-denied',not p.TryQueueRuntimeDisconnect())\ncheck('disconnect-exact',drain()==list(bytearray.fromhex('04050400400013')))\ncheck('disconnect-consumed-clean',p.RuntimeEventsConsumed==4 and not p.RuntimeEventPending and q.RisingEdges==8)\ncheck('disconnect-no-replay',not p.TryQueueRuntimeDisconnect())\ncheck('no-replay',")
    code=prefix+'packets='+repr(att_packets())+'\n'+test;compile(code,'test','exec');(a.output/'test.py').write_text(code)
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=90)
    rows=[json.loads(x.split('BLACKWALL_RUNTIME_ATT_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RUNTIME_ATT_UNIT ')]
    assert len(rows)==1,log[-1800:]
    (a.output/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))


if __name__=='__main__':main()
