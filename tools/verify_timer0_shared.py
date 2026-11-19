"""Verify nominal Timer0 config/reload/IRQ and Timer14 shared state on a spin guest."""
import argparse,json,struct
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_timer14 import models,board

SETUP='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];t=g.Timer14;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def state():return (t.Timer0Control,t.Timer0Counter,t.Timer0Compare0,t.Timer0Compare1,t.Timer0Mode,t.Control,t.Counter,t.Compare0,t.Compare1,t.GlobalEnable,t.Enable,t.Status,t.Timer0IRQ.IsSet,t.IRQ.IsSet,t.Reads,t.Writes)
def blocked(n,fn):
    old=state();count=g.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount==count+1)
def w(offset,value):b.WriteDoubleWord(0x40008000+offset,value)
check('timer0-reset',t.Timer0Enabled and t.Timer0Control==t.Timer0Counter==t.Timer0Compare0==t.Timer0Compare1==0)
blocked('unconfigured-start',lambda:w(0x200,0x121))
blocked('other-channel',lambda:b.ReadDoubleWord(0x40008220))
blocked('other-global-bit',lambda:w(0x10,0xfffd))
blocked('other-interrupt-bit',lambda:w(0x60,4))
blocked('unknown-clock',lambda:w(0x200,0x220))
blocked('unknown-function',lambda:w(0x200,0x110))
blocked('unknown-trigger',lambda:w(0x210,0x200))
blocked('unknown-period',lambda:w(0x208,5))
w(0x200,0x120);w(0x210,0x100);w(0x208,6000);w(0x20c,0xffffffff);w(0x200,0x122)
check('source-config-clear-held',t.Timer0Control==0x122 and t.Timer0Counter==0 and not t.Timer0Running)
'''
PHASES=[(100,"check('clear-held-over-time',t.Timer0Counter==0)\nw(0x200,0x120);w(0x200,0x121)\n"),
 (250,"check('nominal-6MHz-1500ticks',t.Timer0Counter==1500 and t.Timer0Frequency==6000000)\n"),
 (751,"check('nominal-reload',0<=t.Timer0Counter<=12 and t.Status&1 and not t.Timer0IRQ.IsSet)\nw(0x60,0x20000001)\ncheck('channel0-IRQ',t.Timer0IRQ.IsSet and not t.IRQ.IsSet and b.ReadDoubleWord(0xe000e208)&8)\nw(0x6c,0x20000000)\ncheck('shared-pending-both',t.Timer0IRQ.IsSet and t.IRQ.IsSet and t.Status==0x20000001)\nw(0x68,1)\ncheck('clear0-preserves14',not t.Timer0IRQ.IsSet and t.IRQ.IsSet and t.Status==0x20000000)\nw(0x68,0x20000000)\ncheck('clear14-independent',not t.IRQ.IsSet and t.Status==0)\nw(0x200,0x120);held=t.Timer0Counter\n"),
 (500,"check('disable-preserves-count',t.Timer0Counter==held)\nw(0x200,0x121);w(0x10,0xfffe);held=t.Timer0Counter\n"),
 (500,"check('global0-gate-holds',t.Timer0Counter==held)\nw(0x10,0xffff)\n"),
 (100,"check('global0-gate-resumes',t.Timer0Counter>held)\nblocked('running-counter-write',lambda:w(0x204,0))\nw(0x200,0x123)\n"),
 (100,"check('clear-stops-and-zeroes',t.Timer0Counter==0 and not t.Timer0Running)\nw(0x200,0x120)\nw(0x3c8,0xffffffff);w(0x3cc,0xffffffff);w(0x3c0,0x611)\n"),
 (10000,"check('channel14-still-nominal',t.Counter==9 and t.Frequency==900 and t.Timer0Counter==0)\nblocked('byte-read',lambda:b.ReadByte(0x40008200))\nblocked('status-write',lambda:w(0x64,0))\nblocked('clear-register-read',lambda:b.ReadDoubleWord(0x40008068))\ng.Reset()\ncheck('shared-reset',t.Timer0Control==t.Timer0Counter==t.Control==t.Counter==t.Enable==t.Status==t.Reads==t.Writes==0 and t.GlobalEnable==0xffff and not t.Timer0IRQ.IsSet and not t.IRQ.IsSet)\n")]
PHASES[-1]=(PHASES[-1][0],PHASES[-1][1]+'''
w(0x200,0x120);w(0x210,0x100);w(0x208,6000);w(0x20c,0xffffffff);w(0x200,0x121);w(0x10,0xfffe)
w(0x208,0);blocked('global-resume-rejects-bad-primary',lambda:w(0x10,0xffff))
w(0x208,6000);w(0x20c,0);blocked('global-resume-rejects-bad-secondary',lambda:w(0x10,0xffff))
w(0x20c,0xffffffff);w(0x210,0);blocked('global-resume-rejects-bad-mode',lambda:w(0x10,0xffff))
w(0x210,0x100);w(0x10,0xffff);check('global-resume-after-repair',t.Timer0Running)
g.Reset();w(0x3c8,0xffffffff);w(0x3cc,100);w(0x3c0,0xa11);w(0x10,0xbfff)
w(0x3c8,0);blocked('global14-resume-rejects-bad-primary',lambda:w(0x10,0xffff))
w(0x3c8,0xffffffff);w(0x3cc,0);blocked('global14-resume-rejects-bad-secondary',lambda:w(0x10,0xffff))
w(0x3cc,100);w(0x10,0xffff);check('global14-resume-after-repair',t.Running)
g.Reset()
''')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    base='cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    PerformanceInMips: 1\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    -> cpu@0\nflash: Memory.MappedMemory @ sysbus 0x10000\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x1000\nguard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40001000\n    baseAddress: 0x40001000\n    size: 0x23000\n'
    text=board(base).replace('    profile: "nominal-xt-lfrc"\n','    profile: "nominal-xt-lfrc"\n    timer0Profile: "nominal-hfrc96-upcount"\n    Timer0IRQ -> nvic@67\n')
    (o/'board.repl').write_text(text);(o/'strict.cs').write_bytes(models(s));(o/'setup.py').write_text(SETUP);(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'))
    resc='include @/work/strict.cs\nmach create "timer0-shared"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
    for n,(us,phase) in enumerate(PHASES):
        (o/f'phase-{n}.py').write_text(phase);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
    (o/'result.py').write_text("Console.WriteLine('BLACKWALL_TIMER0_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='nominal HFRC96/16, virtual reload and shared IRQ only; not original ISR or silicon timing')))\n");(o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_TIMER0_UNIT ')]
    if len(rows)!=1:raise ValueError('Missing Timer0 result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
