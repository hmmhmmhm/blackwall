"""Test virtual-time STIMER counting, relative compare and NVIC pending with a synthetic spin guest."""
import argparse,json,struct
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
SETUP='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];s=g.Stimer;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def read(a):return g.ReadDoubleWord(a-0x40001000)
def write(a,v):g.WriteDoubleWord(a-0x40001000,v)
def blocked(n,fn):
    before=(s.Config,s.Counter,s.Reads,s.Writes);count=g.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,before==(s.Config,s.Counter,s.Reads,s.Writes) and g.AccessCount==count+1)
check('reset-frozen-no-clock',read(0x40008800)==0x80000000 and read(0x40008804)==0)
for v in [7,8,9,0x10]:blocked('unsupported-clock-'+str(v),lambda:write(0x40008800,v))
write(0x40008800,0x40000001);check('clear-held',s.Counter==0)
'''
PHASES=[(10,"check('clear-holds-across-time',s.Counter==0);write(0x40008800,1)"),(1,"""
check('six-mhz-six-ticks',read(0x40008804)==6)
write(0x40008800,0x80000001);frozen=s.Counter
"""),(10,"""
check('freeze-preserves',s.Counter==frozen)
write(0x40008804,100);check('frozen-counter-load',s.Counter==100)
write(0x40008800,1)
blocked('running-counter-write-denied',lambda:write(0x40008804,4))
write(0x40008800,0);stopped=s.Counter
"""),(10,"""
check('no-clock-stops-after-running',s.Counter==stopped and s.Frequency==0)
write(0x40008800,0x40000002);write(0x40008800,2)
"""),(8,"""
check('375khz-three-ticks',s.Counter==3 and s.Frequency==375000)
write(0x40008800,0x40000003);write(0x40008800,3)
"""),(1000000,"""
check('crystal-exact-32768',s.Counter==32768 and s.Frequency==32768)
write(0x40008800,0x40000004);write(0x40008800,4)
"""),(1000000,"""
check('crystal-exact-16384',s.Counter==16384 and s.Frequency==16384)
write(0x40008800,0x40000005);write(0x40008800,5)
"""),(1000000,"""
check('crystal-exact-1024',s.Counter==1024 and s.Frequency==1024)
write(0x40008800,0x40000006);write(0x40008800,6)
"""),(1000000,"""
check('lfrc-declared-nominal-900',s.Counter==900 and s.Frequency==900)
g.Reset();write(0x40008900,1);write(0x40008800,0x101);before=s.Counter;write(0x40008820,10)
check('compare-write-does-not-force-time',s.Counter==before and read(0x40008820)==before+10)
"""),(1,"""
check('compare-not-early',s.Counter==6 and s.Status==0 and not s.IRQA.IsSet)
"""),(1,"""
check('compare-latched-at-deadline',s.Counter==12 and s.Status==1 and s.IRQA.IsSet)
check('nvic32-pending',b.ReadDoubleWord(0xe000e204)&1==1)
write(0x40008908,1);check('compare-clear-deasserts-line',s.Status==0 and not s.IRQA.IsSet)
g.Reset();check('owner-reset',s.Config==0x80000000 and s.Counter==s.Enable==s.Status==s.Reads==s.Writes==0)
write(0x40008804,0xfffffffd);write(0x40008900,0x100);write(0x40008800,1)
"""),(1,"""
check('uint32-wrap-period',s.Counter==3 and s.Status==0x100)
check('overflow-nvic40',s.IRQI.IsSet and b.ReadDoubleWord(0xe000e204)&0x100==0x100)
write(0x40008800,0x80000001)
for a in [0x40008808,0x40008840,0x40008908]:blocked('unmodeled-read-'+str(a),lambda:read(a))
blocked('reserved-interrupt',lambda:write(0x40008900,0x2000))
blocked('byte-access',lambda:g.ReadByte(0x7800))
g.Reset()
write(0x40008804,0xfffffffd);write(0x40008900,0x101);write(0x40008800,0x80000101);write(0x40008820,5)
check('relative-compare-wrap-readback',read(0x40008820)==2)
b.WriteDoubleWord(0xe000e284,0xffffffff);write(0x40008800,0x101)
"""),(1,"""
check('relative-compare-across-wrap',s.Counter==3 and s.Status==0x101 and s.IRQA.IsSet and s.IRQI.IsSet)
check('fresh-nvic-lines-across-wrap',b.ReadDoubleWord(0xe000e204)&0x101==0x101)
g.Reset()
""")]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence output required')
 frozen=(a.simulator/'stimer-interrupt-main-03/stock24/strict.cs').read_bytes();strict=frozen
 if (ROOT/'tools/stimer_engine_source.py').exists():
  from stimer_engine_source import load_engine
  strict+=b'\n'+load_engine(a.simulator).encode()
 addon=ROOT/'tools/renode-stimer-clock-probe.cs'
 if addon.exists():strict+=b'\n'+addon.read_bytes()
 o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(strict);(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'))
 board='cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    PerformanceInMips: 1\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    -> cpu@0\nflash: Memory.MappedMemory @ sysbus 0x10000\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x1000\nstimer: Miscellaneous.BlackwallStimerClockCounter @ none\n    profile: "nominal-source-clocks"\n'
 for n,c in enumerate('ABCDEFGHI'):board+='    IRQ'+c+' -> nvic@'+str(32+n)+'\n'
 board+='guard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40001000\n    baseAddress: 0x40001000\n    size: 0x23000\n    stimer: stimer\n';(o/'board.repl').write_text(board);(o/'setup.py').write_text(SETUP);compile(SETUP,'setup.py','exec');resc='include @/work/strict.cs\nmach create "stimer-clock"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 for n,(us,script) in enumerate(PHASES):
  (o/f'phase-{n}.py').write_text(script);compile(script,'phase.py','exec');(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'report.py').write_text("Console.WriteLine('BLACKWALL_STIMER_CLOCK_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='nominal virtual clocks, immediate relative-compare model, NVIC pending with spin guest; no physical/ISR/main proof')))\n");(o/'probe.resc').write_text(resc+'include @/work/report.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_STIMER_CLOCK_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_STIMER_CLOCK_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing clock unit marker; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
