"""Exercise captured startup-runtime HCI packets through the actual SPI/GPIO peer."""
import argparse
import json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_runtime_local_version import constant, REPLY


TEST = '''
prime();baseline=(int(p.CommandsAccepted),int(p.Replies))
check('startup-and-no-injected-events',baseline==(59,60) and p.RuntimeEventsConsumed==p.RuntimeRemoteRepliesConsumed==0)
def send_checked(data):
 offset=0
 while offset<len(data):
  cs(False);check('write-header-'+str(len(checks)),p.CanBegin(2))
  p.BeginTransaction(2);p.Transmit(0x42);capacity=int(p.Transmit(0));p.FinishTransmission()
  n=min(capacity,len(data)-offset)
  check('captured-payload-supported-'+str(len(data))+'-'+str(offset),p.CanBegin(n))
  check('oversize-chunk-denied-'+str(len(checks)),not p.CanBegin(capacity+1))
  p.BeginTransaction(n)
  if n>=4:
   word=sum(data[offset+i]<<(8*i) for i in range(4))
   check('word-write-supported-'+str(len(checks)),p.CanExchange(word,4))
   check('wrong-word-denied-'+str(len(checks)),not p.CanExchange(word^0x100,4))
  for value in data[offset:offset+n]:
   check('wrong-byte-denied-'+str(len(checks)),not p.CanExchange(value^1,1))
   p.Transmit(value)
  p.FinishTransmission();cs(True);offset+=n
def reply(expected):
 check('reply-queued-'+str(len(checks)),p.RuntimeEventPending and p.ReadyLevel==1)
 cs(False);p.BeginTransaction(2)
 check('write-while-reply-pending-denied-'+str(len(checks)),not p.CanExchange(0x42,1))
 p.Transmit(0x81);cs(True)
 check('aborted-reply-header-retained-'+str(len(checks)),p.RuntimeEventPending)
 check('reply-exact-'+str(len(checks)),drain()==list(bytearray.fromhex(expected)))
 check('reply-consumed-'+str(len(checks)),not p.RuntimeEventPending and p.ReadyLevel==0 and not q.IRQ.IsSet)
send_checked(list(bytearray.fromhex('01011000')));reply(VERSION_REPLY)
if DISABLED:
 cs(False);p.BeginTransaction(2);p.Transmit(0x42);p.Transmit(0);p.FinishTransmission()
 check('advertising-default-off',not p.CanBegin(5));cs(True)
else:
 send_checked(list(bytearray.fromhex(CAPTURED_STOP)));reply('040e04010a2000')
 check('stopped-advertising-rejects-connection',not p.TryQueueRuntimeConnection())
 send_checked(list(bytearray.fromhex('01011000')));reply(VERSION_REPLY)
 check('separate-opcode-counters',p.LocalVersionCommands==p.LocalVersionReplies==2 and p.AdvertisingDisableCommands==p.AdvertisingDisableReplies==1)
 check('startup-counter-preserved',baseline==(int(p.CommandsAccepted),int(p.Replies)))
 check('no-fake-connection',p.RuntimeEventsConsumed==p.RuntimeRemoteRepliesConsumed==0)
 cs(False);check('all-budgets-exhausted',not p.CanBegin(2));cs(True)
p.Reset();check('reset-clears-pending',not p.RuntimeEventPending and p.LocalVersionCommands==p.LocalVersionReplies==0)
check('reset-clears-advertising',p.AdvertisingDisableCommands==p.AdvertisingDisableReplies==0 and not p.AdvertisingStopped)
for limit in (-1,1,33):
 try:BlackwallEm9305EventPeer('04ff0101',startupAdvertisingDisableLimit=limit)
 except Exception as error:check('invalid-advertising-profile-'+str(limit),'Advertising disable requires' in str(error))
 else:raise Exception('Invalid advertising profile accepted')
Console.WriteLine('BLACKWALL_STARTUP_COMMANDS_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_firmware_executed=False,startup_primer_uses_same_class_command_getter=True)))
'''


def main():
    q = argparse.ArgumentParser(description=__doc__)
    q.add_argument('simulator', type=Path)
    q.add_argument('output', type=Path)
    q.add_argument('--baseline', action='store_true')
    q.add_argument('--disabled', action='store_true')
    q.add_argument('--split-chunks', action='store_true')
    a = q.parse_args();s, out = a.simulator, a.output
    if out.exists() or not out.resolve().is_relative_to(s.resolve()):
        raise ValueError('Fresh private output required')
    proof = json.loads((s / 'sustained-hci-stop-source-01/report.json').read_text())
    if not proof['passed'] or proof['original_packet'] != '010a200100':
        raise ValueError('Captured original advertising-stop command required')
    ref = s / 'sustained-uart-history-native-01/stock24'
    model, board = (ref / 'strict.cs').read_text(), (ref / 'board.repl').read_text()
    if not a.baseline:
        from startup_hci_commands_model import compose
        model = compose(model)
        if not a.disabled:
            anchor = '    runtimeLocalVersionHex:'
            if board.count(anchor) != 1:raise ValueError('One controller profile required')
            board = board.replace(anchor, '    startupAdvertisingDisableLimit: 1\n' + anchor, 1)
    board = board.replace('    runtimeLocalVersionLimit: 32\n', '    runtimeLocalVersionLimit: 2\n')
    if a.split_chunks:
        if board.count('    writeCapacity: 9\n') != 1:raise ValueError('Unknown transport capacity')
        board = board.replace('    writeCapacity: 9\n', '    writeCapacity: 2\n')
    root = Path(__file__).parent
    prefix = constant('SCRIPT', root / 'verify_runtime_event_gpio.py').split("check('runtime-opt-in'")[0]
    prefix = prefix.replace(' p.BeginReceive(n);data=', " if p.RuntimeEventPending:\n  check('short-reply-denied-'+str(len(checks)),not p.CanReceive(n-1))\n  check('long-reply-denied-'+str(len(checks)),not p.CanReceive(n+1))\n p.BeginReceive(n);data=")
    definitions = constant('TEST', root / 'verify_runtime_att_workflow.py').split('prime();baseline=')[0]
    code = prefix + definitions + TEST.replace('VERSION_REPLY', repr(REPLY)).replace('CAPTURED_STOP', repr(proof['original_packet'])).replace('DISABLED', repr(a.disabled))
    compile(code, 'startup-command-unit.py', 'exec')
    out.mkdir(mode=0o700)
    for name, text in [('strict.cs', model), ('board.repl', board), ('test.py', code)]:
        (out / name).write_text(text)
    (out / 'probe.resc').write_text('include @/work/strict.cs\nmach create "startup-commands"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={out},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], out, 'renode', timeout=120)
    rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_STARTUP_COMMANDS_UNIT ')]
    if len(rows) != 1:raise ValueError('Missing startup command result; inspect saved log')
    (out / 'report.json').write_text(json.dumps(rows[0], indent=2) + '\n')
    print(json.dumps(dict(passed=True, checks=rows[0]['count'])))


if __name__ == '__main__':main()
