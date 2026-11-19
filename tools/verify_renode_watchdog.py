"""Exercise the bounded Apollo510 watchdog model and an upstream counter control."""
import argparse
import json
from pathlib import Path
import subprocess

from run_renode_m55_probe import execute

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--image', default='blackwall-renode:1.17.0-local')
    parser.add_argument('--case', action='append', dest='selected_cases', help='Run selected named cases; repeatable')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    image_id = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', args.image],
                                       text=True, timeout=15).strip()
    # Each assertion below checks runtime state, not a reconstructed Python timer.
    cases = [
        ('interrupt-delivery', 1, '', 'emulation RunFor "00:00:00.200"',
         {'mailbox': [0x600d,17,1,2,1,0,0,0], 'events': 1, 'pending': False, 'irq': False, 'count': 3}),
        ('counter-only', 0, 'wdt WriteDoubleWord 0 0x02000001', 'emulation RunFor "00:00:00.200"', {'count': 3}),
        ('clock-off', 0, 'wdt WriteDoubleWord 0 1', 'emulation RunFor "00:00:00.200"', {'count': 0}),
        ('lfrc-div8', 0, 'wdt WriteDoubleWord 0 0x01000001', 'emulation RunFor "00:00:00.200"', {'count': 25}),
        ('lfrc-div1k', 0, 'wdt WriteDoubleWord 0 0x03000001', 'emulation RunFor "00:00:01.200"', {'count': 1}),
        ('lfrc-div16k', 0, 'wdt WriteDoubleWord 0 0x04000001', 'emulation RunFor "00:00:17.000"', {'count': 1}),
        ('counter-wrap', 0, 'wdt WriteDoubleWord 0 0x02000001', 'emulation RunFor "00:00:16.100"', {'count': 1}),
        ('restart', 0, 'wdt WriteDoubleWord 0 0x02000001',
         'emulation RunFor "00:00:00.100"\ninclude @/work/before.py\nwdt WriteDoubleWord 4 0xb2\n'
         'include @/work/after.py\nemulation RunFor "00:00:00.100"', {'count': 1, 'restarts': 1, 'before': 1, 'after': 0}),
        ('pending-mask-restart', 0, 'wdt WriteDoubleWord 0 0x02020a03',
         'emulation RunFor "00:00:00.150"\ninclude @/work/pending.py\nwdt WriteDoubleWord 4 0xb2\n'
         'wdt WriteDoubleWord 0x200 1\ninclude @/work/line.py\nwdt WriteDoubleWord 0x208 1',
         {'pending_before': True, 'line_before_clear': True, 'pending': False, 'irq': False, 'restarts': 1}),
        ('software-pending', 0, 'wdt WriteDoubleWord 0x200 1\nwdt WriteDoubleWord 0x20c 1',
         'emulation RunFor "00:00:00.010"\ninclude @/work/line.py\nwdt WriteDoubleWord 0x208 1',
         {'line_before_clear': True, 'pending': False, 'irq': False}),
        ('reset-request-boundary', 0, 'wdt WriteDoubleWord 0 0x02000305',
         'start\npython "import time; time.sleep(0.5)"\npause',
         {'reset_due': True, 'count': 3, 'mailbox': [0x11112222,0,0,0,0,0,0,0]}),
        ('unsupported-xtal', 2, '', 'start\npython "import time; time.sleep(0.2)"\npause',
         {'accesses': 1, 'address': 0x40024000, 'width': 4, 'cfg': 0, 'mailbox': [0x11112222,0,0,0,0,0,0,0]}),
        ('partial-access', 3, '', 'start\npython "import time; time.sleep(0.2)"\npause',
         {'accesses': 1, 'address': 0x4002400c, 'width': 2, 'mailbox': [0x11112222,0,0,0,0,0,0,0]}),
        ('invalid-restart', 4, '', 'start\npython "import time; time.sleep(0.2)"\npause',
         {'accesses': 1, 'address': 0x40024004, 'restarts': 0, 'mailbox': [0x11112222,0,0,0,0,0,0,0]}),
        ('upstream-counter-control', 0, 'wdt WriteDoubleWord 0 0x02000001',
         'emulation RunFor "00:00:00.200"', {'count': 0, 'irq_available': False}),
    ]
    gates = {'gate-disabled':0, 'gate-brownout-only':1, 'gate-watchdog':2, 'gate-both':3}
    for name, cfg in gates.items():
        cases.append((name,0,f'rstgen WriteDoubleWord 0 {cfg}\nwdt WriteDoubleWord 0 0x02000305',
            'start\npython "import time; time.sleep(0.5)"\npause',
            {'reset_due':True,'gating_evaluated':True,'allowed_by_gate':bool(cfg&2),'rstgen_cfg':cfg,'count':3}))
    for name,mode,address,width in [('rstgen-reserved-bit',5,0x40000000,4),
                                    ('rstgen-software-reset',6,0x40000004,4),
                                    ('rstgen-partial',7,0x40000000,2)]:
        cases.append((name,mode,'','start\npython "import time; time.sleep(0.2)"\npause',
            {'rstgen_accesses':1,'rstgen_address':address,'rstgen_width':width,'rstgen_cfg':0,
             'mailbox':[0x11112222,0,0,0,0,0,0,0]}))
    cases.append(('rstgen-roundtrip',0,'rstgen WriteDoubleWord 0 0\nrstgen WriteDoubleWord 0 1\n'
                  'rstgen WriteDoubleWord 0 2\nrstgen WriteDoubleWord 0 3','emulation RunFor "00:00:00.010"',
                  {'rstgen_cfg':3,'rstgen_writes':4,'wdren':True,'rstgen_accesses':0}))
    if args.selected_cases:
        if set(args.selected_cases)-{case[0] for case in cases}:
            parser.error('Unknown watchdog case')
        cases = [case for case in cases if case[0] in args.selected_cases]
    results = {}
    for name, mode, setup, run, expected in cases:
        directory = output/name
        directory.mkdir(mode=0o700)
        (directory/'strict.cs').write_text((ROOT/'tools/renode-strict-mmio.cs').read_text()+'\n'
                                          +(ROOT/'tools/renode-reset-controller.cs').read_text()+'\n'
                                          +(ROOT/'tools/renode-watchdog.cs').read_text())
        model = 'Timers.AmbiqApollo4_Watchdog' if name.startswith('upstream-') else 'Miscellaneous.BlackwallApollo510Watchdog'
        board = (ROOT/'tests/fixtures/m55-minimal.repl').read_text()+f'\nwdt: {model} @ sysbus 0x40024000\n'
        if not name.startswith('upstream-'):
            if name in gates or name.startswith('rstgen-'):
                board += '    resetController: rstgen\n'
            board += '    -> nvic@1\n'
        if name in gates or name.startswith('rstgen-'):
            board += '\nrstgen: Miscellaneous.BlackwallResetController @ sysbus 0x40000000\n'
        (directory/'board.repl').write_text(board)
        execute(['/opt/homebrew/opt/llvm@21/bin/clang', '--target=arm-none-eabi', '-mcpu=cortex-m55',
                 '-mthumb', '-O1', '-ffreestanding', '-fno-builtin', '-nostdlib', '-DPROBE_MODE='+str(mode),
                 '-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld', '-Wl,-T,'+str(ROOT/'tests/fixtures/m55-exceptions-smoke.ld'),
                 str(ROOT/'tests/fixtures/renode-watchdog-probe.c'), '-o', str(directory/'probe.elf')], directory, 'compiler')
        for filename, expression in {'before':'int(w.ReadDoubleWord(12))','after':'int(w.ReadDoubleWord(12))',
                                      'pending':'bool(w.InterruptPending)','line':'bool(w.IRQ.IsSet)'}.items():
            (directory/(filename+'.py')).write_text("from System import Console\nw = monitor.Machine['sysbus.wdt']\nConsole.WriteLine('BLACKWALL_"+filename.upper()+" '+str("+expression+"))\n")
        (directory/'result.py').write_text('''import json
from System import Console
m = monitor.Machine
w = m['sysbus.wdt']
def attr(name):
    value = getattr(w,name,None)
    if value is None: return None
    if name in ('ResetDue','InterruptPending','ResetGatingEvaluated','ResetAllowedByGate'): return bool(value)
    return int(value)
rst = {}
if __RSTGEN_PRESENT__:
    r = m['sysbus.rstgen']
    rst = dict(rstgen_cfg=int(r.Configuration),rstgen_writes=int(r.ConfigurationWrites),
        wdren=bool(r.WatchdogResetEnabled),rstgen_accesses=int(r.AccessCount),
        rstgen_address=int(r.LastAddress),rstgen_width=int(r.LastWidth))
Console.WriteLine('BLACKWALL_WDT '+json.dumps(dict(count=int(w.ReadDoubleWord(12)),
    cfg=int(w.ReadDoubleWord(0)),irq_available=hasattr(w,'IRQ'),irq=bool(w.IRQ.IsSet) if hasattr(w,'IRQ') else None,
    reset_due=attr('ResetDue'),pending=attr('InterruptPending'),events=attr('InterruptEvents'),
    gating_evaluated=attr('ResetGatingEvaluated'),allowed_by_gate=attr('ResetAllowedByGate'),
    restarts=attr('Restarts'),accesses=attr('AccessCount'),address=attr('LastAddress'),width=attr('LastWidth'),
    mailbox=[int(m.SystemBus.ReadDoubleWord(0x20000000+4*i)) for i in range(8)],**rst)))
'''.replace('__RSTGEN_PRESENT__', 'True' if name in gates or name.startswith('rstgen-') else 'False'))
        (directory/'probe.resc').write_text('include @/work/strict.cs\nmach create "blackwall-watchdog-probe"\n'
            'machine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/probe.elf\n'
            +setup+'\n'+run+'\ninclude @/work/result.py\nquit\n')
        log = execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1',
            '--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',
            f'type=bind,source={directory},target=/work,readonly',image_id,'--disable-gui','--hide-monitor','-p','/work/probe.resc'],
            directory,'renode',timeout=45)
        lines = [line.partition('BLACKWALL_WDT ')[2] for line in log.splitlines() if line.startswith('BLACKWALL_WDT ')]
        if len(lines) != 1:
            raise ValueError('Missing watchdog result: '+name)
        observed = json.loads(lines[0])
        for prefix, key in [('BEFORE','before'),('AFTER','after'),('PENDING','pending_before'),('LINE','line_before_clear')]:
            rows=[line.partition('BLACKWALL_'+prefix+' ')[2] for line in log.splitlines() if line.startswith('BLACKWALL_'+prefix+' ')]
            if rows: observed[key]={'True':True,'False':False}.get(rows[0],rows[0]) if rows[0] in ('True','False') else int(rows[0])
        passed = all(observed[k] == value for k,value in expected.items())
        results[name] = {'passed': passed, 'expected': expected, 'observed': observed}
        print(name, 'passed' if passed else 'FAILED '+str(observed), flush=True)
    report = {'image_id':image_id,'scope':'synthetic LFRC watchdog contract, not physical G2 validation',
              'passed':all(r['passed'] for r in results.values()),'cases':results,'hardware_validated':False}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['passed']:raise SystemExit(1)


if __name__ == '__main__':
    main()
