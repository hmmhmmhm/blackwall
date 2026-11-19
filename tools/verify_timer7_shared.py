"""Exercise Timer7 PWM lifecycle through the shared strict bus owner and native virtual time."""
import argparse,json,struct
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_timer14 import models,board
from timer14_engine_source import load_engine

SETUP='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];t=g.Timer14;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def w(o,v):b.WriteDoubleWord(0x40008000+o,v)
def state():return (t.Timer7Control,t.Timer7Counter,t.Timer7Compare0,t.Timer7Compare1,t.Timer7Mode,t.Timer7OutputConfig,t.GlobalEnable,t.Enable,t.Status,t.Timer7IRQ.IsSet,t.Reads,t.Writes)
def blocked(n,fn):
    old=state();count=g.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount==count+1)
check('reset',t.Timer7Enabled and t.Timer7Control==t.Timer7Counter==t.Timer7Compare0==t.Timer7Compare1==0 and t.Timer7OutputConfig==0x3f3f3f3f)
blocked('unconfigured-start',lambda:w(0x2e0,0x41))
blocked('unknown-clock',lambda:w(0x2e0,0x140))
blocked('unknown-function',lambda:w(0x2e0,0x20))
blocked('other-pad',lambda:w(0x110,0x3f3f0e0e))
blocked('unknown-route',lambda:w(0x110,0x3f3f0f3f))
blocked('other-channel',lambda:b.ReadDoubleWord(0x40008220))
blocked('other-irq',lambda:w(0x60,4))
blocked('other-global',lambda:w(0x10,0xfffd))
w(0x2e0,0x40);w(0x2f0,0x100);w(0x2e8,0xffffffff);w(0x2ec,0xffffffff);w(0x2e0,0x42)
w(0x110,0x3f3f0e3f);w(0x2e8,24000);w(0x2ec,16800)
check('source-config',t.Timer7Control==0x42 and t.Timer7Counter==0 and t.Timer7Pad145Selector==14 and not t.Timer7Running)
'''
PHASES=[
 (500,"check('clear-held',t.Timer7Counter==0)\nw(0x2e0,0x40);w(0x2e0,0x41)\n"),
 (500,"check('24MHz-low-phase',t.Timer7Counter==12000 and not t.Timer7Output0 and t.Timer7Output1 and t.Timer7Frequency==24000000)\n"),
 (250,"check('secondary-no-reload-high-phase',17976<=t.Timer7Counter<=18000 and t.Timer7Output0 and not t.Timer7Output1 and t.Status&0x8000 and not t.Timer7IRQ.IsSet)\n"),
 (251,"check('primary-reloads-low',0<=t.Timer7Counter<=48 and not t.Timer7Output0 and t.Status&0xc000==0xc000)\nw(0x60,0x3000c003)\ncheck('irq74',t.Timer7IRQ.IsSet and b.ReadDoubleWord(0xe000e208)&(1<<10))\nw(0x6c,0x20000001)\ncheck('three-channel-pending',t.Timer0IRQ.IsSet and t.Timer7IRQ.IsSet and t.IRQ.IsSet)\nw(0x68,0x4000)\ncheck('primary-clear-preserves-secondary',t.Timer7IRQ.IsSet and t.Status&0xc000==0x8000)\nw(0x68,0x8000)\ncheck('clear7-independent',not t.Timer7IRQ.IsSet and t.Timer0IRQ.IsSet and t.IRQ.IsSet)\nw(0x68,0x20000001)\nw(0x2e0,0x40);held=t.Timer7Counter\n"),
 (500,"check('disabled-holds',t.Timer7Counter==held)\nw(0x2e0,0x41);w(0x10,0xff7f);held=t.Timer7Counter\n"),
 (500,"check('global-gate-holds',t.Timer7Counter==held)\nw(0x10,0xffff)\n"),
 (100,"check('global-gate-resumes',t.Timer7Counter>held)\nblocked('running-counter-write',lambda:w(0x2e4,0))\nblocked('running-period-change',lambda:w(0x2e8,12000))\nblocked('running-duty-change',lambda:w(0x2ec,8000))\nblocked('byte-access',lambda:b.ReadByte(0x400082e0))\nw(0x2e0,0x43)\n"),
 (100,"check('clear-stops-zero-preserves-comparators',t.Timer7Counter==0 and not t.Timer7Running and t.Timer7Compare0==24000 and t.Timer7Compare1==16800)\nw(0x2e0,0x40);w(0x2e0,0x41)\n"),
 (750,"check('restart-high-phase',t.Timer7Output0 and 17976<=t.Timer7Counter<=18000)\nw(0x10,0xff7f);w(0x2e0,0x40);w(0x2e8,0);blocked('invalid-start-period',lambda:w(0x2e0,0x41))\nw(0x2e8,24000);w(0x2ec,24000);blocked('invalid-start-duty',lambda:w(0x2e0,0x41))\nw(0x2ec,16800);w(0x2f0,0);blocked('invalid-start-mode',lambda:w(0x2e0,0x41))\nw(0x2f0,0x100);w(0x2e0,0x41);w(0x2e0,0x40);w(0x2e8,0);w(0x2e0,0x42)\ng.Reset()\ncheck('reset-all',t.Timer7Control==t.Timer7Counter==t.Timer7Compare0==t.Timer7Compare1==t.Timer0Control==t.Control==t.Enable==t.Status==t.Reads==t.Writes==0 and t.Timer7OutputConfig==0x3f3f3f3f and not t.Timer7IRQ.IsSet and t.GlobalEnable==0xffff)\n")]
PHASES[-1]=(PHASES[-1][0],PHASES[-1][1]+'''
w(0x2e0,0x40);w(0x2f0,0x100);w(0x2e8,24000);w(0x2ec,16800);w(0x2e4,24000)
blocked('counter-past-period-start',lambda:w(0x2e0,0x41))
w(0x2e4,0);w(0x2e0,0x41);w(0x10,0xff7f);w(0x2e8,0)
blocked('global-resume-invalid-period',lambda:w(0x10,0xffff))
w(0x2e8,24000);w(0x2ec,0);blocked('global-resume-invalid-duty',lambda:w(0x10,0xffff))
w(0x2ec,16800);w(0x2f0,0);blocked('global-resume-invalid-mode',lambda:w(0x10,0xffff))
w(0x2f0,0x100);w(0x10,0xffff)
check('repaired-global-resume',t.Timer7Running)
''')
PHASES.append((100,"check('reset-clock-restored',t.Timer7Counter==2400)\ng.Reset()\n"))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--candidate',action='store_true');a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
 base='cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    PerformanceInMips: 1\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    -> cpu@0\nflash: Memory.MappedMemory @ sysbus 0x10000\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x1000\nguard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40001000\n    baseAddress: 0x40001000\n    size: 0x23000\n'
 text=board(base).replace('    profile: "nominal-xt-lfrc"\n','    profile: "nominal-xt-lfrc"\n    timer0Profile: "nominal-hfrc96-upcount"\n    timer7Profile: "nominal-hfrc96-pwm"\n    Timer0IRQ -> nvic@67\n    Timer7IRQ -> nvic@74\n')
 model=models(s)
 if a.candidate:
  old=load_engine(s).encode();new=load_engine(s,timer7_pwm=True).encode()
  if model.count(old)!=1:raise ValueError('Engine replacement not unique')
  model=model.replace(old,new)
 (o/'board.repl').write_text(text);(o/'strict.cs').write_bytes(model);(o/'setup.py').write_text(SETUP);(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'))
 resc='include @/work/strict.cs\nmach create "timer7-shared"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 for n,(us,phase) in enumerate(PHASES):
  (o/f'phase-{n}.py').write_text(phase);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'result.py').write_text("Console.WriteLine('BLACKWALL_TIMER7_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='nominal HFRC96/4 PWM count/phase and IRQ74; no pad electrical output or physical timing')))\n");(o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
 rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_TIMER7_UNIT ')]
 if len(rows)!=1 or '[Error]' in log:raise ValueError('Timer7 unit failed; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))

if __name__=='__main__':main()
