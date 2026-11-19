"""Verify captured stop/parameters and retained enable in the runtime SPI state machine."""
import argparse
import json
from pathlib import Path
from verify_runtime_local_version import constant, REPLY
from verify_startup_hci_commands import TEST
from run_renode_m55_probe import execute
from native_replay import IMAGE


PARAMETERS = '0106200f400640060001000000000000000700'


def main():
    q = argparse.ArgumentParser(description=__doc__)
    q.add_argument('simulator', type=Path);q.add_argument('output', type=Path)
    q.add_argument('--baseline', action='store_true');q.add_argument('--legacy', action='store_true')
    q.add_argument('--split-chunks', action='store_true');q.add_argument('--version-limit', type=int, choices=[2, 3], default=3)
    a = q.parse_args();s, out = a.simulator, a.output
    if out.exists() or not out.resolve().is_relative_to(s.resolve()):raise ValueError('Fresh private output required')
    proof = json.loads((s / 'sustained-hci-parameters-source-01/report.json').read_text())
    if not proof['passed'] or proof['packet'] != PARAMETERS:raise ValueError('Captured original parameters required')
    ref = s / 'sustained-hci-stop-native-01/stock24'
    model, board = (ref / 'strict.cs').read_text(), (ref / 'board.repl').read_text()
    if not a.baseline:
        from startup_advertising_procedure_model import compose
        model = compose(model)
        if not a.legacy:
            anchor = '    runtimeLocalVersionHex:'
            if board.count(anchor) != 1:raise ValueError('One identity profile required')
            board = board.replace(anchor, '    startupAdvertisingParametersHex: "' + PARAMETERS + '"\n' + anchor)
    limit = 2 if a.legacy else a.version_limit
    board = board.replace('    runtimeLocalVersionLimit: 32\n', '    runtimeLocalVersionLimit: ' + str(limit) + '\n')
    if a.split_chunks:
        if board.count('    writeCapacity: 9\n') != 1:raise ValueError('Unknown capacity')
        board = board.replace('    writeCapacity: 9\n', '    writeCapacity: 2\n')
    test = TEST
    if not a.legacy:
        anchor = " send_checked(list(bytearray.fromhex('01011000')));reply(VERSION_REPLY)\n"
        if test.count(anchor) != 1:raise ValueError('Unknown interleaved version boundary')
        extra = " send_checked(list(bytearray.fromhex('" + PARAMETERS + "')));reply('040e0401062000')\n"
        extra += " check('parameters-consumed-while-stopped',p.AdvertisingStopped and p.AdvertisingProcedureStep==2 and p.AdvertisingParameterCommands==p.AdvertisingParameterReplies==1)\n"
        extra += " check('no-connection-before-reenable',not p.TryQueueRuntimeConnection())\n"
        extra += " send_checked(list(bytearray.fromhex('010a200101')));reply('040e04010a2000')\n"
        extra += " check('procedure-reenabled',not p.AdvertisingStopped and p.AdvertisingProcedureStep==3 and p.AdvertisingEnableCommands==p.AdvertisingEnableReplies==1)\n"
        if limit == 3:
            extra += anchor
            test = test.replace('p.LocalVersionCommands==p.LocalVersionReplies==2', 'p.LocalVersionCommands==p.LocalVersionReplies==3')
        test = test.replace(anchor, anchor + extra, 1)
        test += "check('procedure-reset',p.AdvertisingProcedureStep==p.AdvertisingParameterCommands==p.AdvertisingParameterReplies==p.AdvertisingEnableCommands==p.AdvertisingEnableReplies==0)\n"
    root = Path(__file__).parent
    prefix = constant('SCRIPT', root / 'verify_runtime_event_gpio.py').split("check('runtime-opt-in'")[0]
    prefix = prefix.replace(' p.BeginReceive(n);data=', " if p.RuntimeEventPending:\n  check('short-reply-denied-'+str(len(checks)),not p.CanReceive(n-1))\n  check('long-reply-denied-'+str(len(checks)),not p.CanReceive(n+1))\n p.BeginReceive(n);data=")
    definitions = constant('TEST', root / 'verify_runtime_att_workflow.py').split('prime();baseline=')[0]
    test = test.replace('VERSION_REPLY', repr(REPLY)).replace('CAPTURED_STOP', repr('010a200100')).replace('DISABLED', 'False')
    test = test.replace("Console.WriteLine('BLACKWALL_STARTUP_COMMANDS_UNIT '", "Console.WriteLine('BLACKWALL_ADVERTISING_PROCEDURE_UNIT '")
    # The report must follow the extra reset assertion.
    lines = test.splitlines();report = next(line for line in lines if line.startswith('Console.WriteLine('))
    lines.remove(report);test = '\n'.join(lines) + '\n' + report + '\n'
    code = prefix + definitions + test;compile(code, 'procedure-unit.py', 'exec')
    out.mkdir(mode=0o700)
    for name, value in [('strict.cs', model), ('board.repl', board), ('test.py', code)]: (out / name).write_text(value)
    (out / 'probe.resc').write_text('include @/work/strict.cs\nmach create "advertising-procedure"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log = execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode',timeout=120)
    rows = [json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_ADVERTISING_PROCEDURE_UNIT ')]
    if len(rows) != 1:raise ValueError('Missing procedure result; inspect saved log')
    (out / 'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,checks=rows[0]['count'])))


if __name__ == '__main__':main()
