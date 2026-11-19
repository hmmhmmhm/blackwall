"""Verify nominal Timer14 counter clocks using Renode virtual time and a synthetic spin guest."""
import argparse,json,struct
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def models(s):
 old=(s/'timer14-research-01/base-core.cs').read_bytes();frozen=(s/'mspi1-interrupts-main-01/stock24/strict.cs').read_bytes()
 if not frozen.startswith(old):raise ValueError('Frozen core differs')
 data=(ROOT/'tools/renode-strict-mmio.cs').read_bytes()+frozen[len(old):]
 if (ROOT/'tools/timer14_engine_source.py').exists():
  from timer14_engine_source import load_engine
  data+=b'\n'+load_engine(s).encode()
 addon=ROOT/'tools/renode-timer14.cs'
 if addon.exists():data+=b'\n'+addon.read_bytes()
 return data
def board(text):
 needle='    baseAddress: 0x40001000\n'
 if text.count(needle)!=1:raise ValueError('Unexpected owner')
 return text.replace(needle,needle+'    timer14: timer14\n')+'\ntimer14: Miscellaneous.BlackwallTimer14 @ none\n    profile: "nominal-xt-lfrc"\n    IRQ -> nvic@81\n'
SETUP='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];t=g.Timer14;checks=[]
def check(n,v):
    if not v:raise Exception(n+' state='+repr(state()))
    checks.append(n)
def state():return (t.Control,t.Counter,t.Compare0,t.Compare1,t.GlobalEnable,t.Enable,t.Status,t.Reads,t.Writes)
def blocked(n,fn):
    old=state();count=g.AccessCount
    try:fn()
    except Exception as e:
        if 'BLACKWALL unsupported' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,state()==old and g.AccessCount==count+1)
check('source-reset',t.Control==t.Counter==t.Compare0==t.Compare1==t.Enable==t.Status==0 and t.GlobalEnable==0xffff)
blocked('unconfigured-enable',lambda:g.WriteDoubleWord(0x73c0,0xa11))
blocked('other-timer',lambda:g.ReadDoubleWord(0x7200))
blocked('other-global-domain',lambda:g.WriteDoubleWord(0x7010,0xfffe))
blocked('other-interrupt',lambda:g.WriteDoubleWord(0x7060,1))
blocked('unsupported-function',lambda:g.WriteDoubleWord(0x73c0,0xa40))
blocked('unsupported-clock',lambda:g.WriteDoubleWord(0x73c0,0x110))
blocked('trigger-config',lambda:g.WriteDoubleWord(0x73d0,0x100))
blocked('clear-alias-read',lambda:g.ReadDoubleWord(0x7068))
g.WriteDoubleWord(0x73c8,0xffffffff);g.WriteDoubleWord(0x73cc,0xffffffff);g.WriteDoubleWord(0x73c0,0xa13)
check('clear-held',t.Counter==0 and t.Control==0xa13)
'''
# Event phases include 1us margin: upstream drops sub-tick residue at compare/wrap.
PHASES=[(31250,"check('clear-holds-over-time',t.Counter==0)\ng.WriteDoubleWord(0x73c0,0xa11)\n"),
 (31250,"check('XT-1024-ticks',t.Counter==1024 and t.Frequency==32768)\nold=t.Counter\nfor n in range(10):g.ReadDoubleWord(0x73c4)\ncheck('reads-do-not-increment',t.Counter==old)\nblocked('running-counter-write',lambda:g.WriteDoubleWord(0x73c4,5))\ng.WriteDoubleWord(0x73c0,0xa10)\n"),
 (31250,"check('disabled-holds-count',t.Counter==1024)\ng.WriteDoubleWord(0x73c0,0xa11)\n"),
 (31250,"check('resume-preserves-count',t.Counter==2048)\ng.WriteDoubleWord(0x7010,0xbfff)\n"),
 (31250,"check('global-gate-holds',t.Counter==2048)\ng.WriteDoubleWord(0x7010,0xffff)\n"),
 (31250,"check('global-gate-resumes',t.Counter==3072)\ng.WriteDoubleWord(0x73c0,0x612)\ng.WriteDoubleWord(0x73c0,0x611)\n"),
 (10000,"check('nominal-LFRC-nine-ticks',t.Counter==9 and t.Frequency==900)\ng.WriteDoubleWord(0x73c0,0x610)\ng.WriteDoubleWord(0x73c4,0xfffffffe)\ng.WriteDoubleWord(0x73c0,0x611)\n"),
 (10001,"check('32bit-wrap',t.Counter==7)\ncheck('masked-compare-latches',t.Status==0x30000000 and not t.IRQ.IsSet)\ng.WriteDoubleWord(0x7060,0x30000000)\ncheck('compare-NVIC81',t.IRQ.IsSet and (b.ReadDoubleWord(0xe000e208)&(1<<17))!=0)\ng.WriteDoubleWord(0x7068,0x30000000)\ncheck('clear-status',t.Status==0 and not t.IRQ.IsSet)\nb.WriteDoubleWord(0xe000e288,1<<17)\ng.WriteDoubleWord(0x73c0,0x610)\ng.WriteDoubleWord(0x73c4,0)\ng.WriteDoubleWord(0x73cc,4)\ng.WriteDoubleWord(0x7060,0x20000000)\ng.WriteDoubleWord(0x73c0,0x611)\n"),
 (10001,"check('secondary-compare',t.Counter==9 and t.Status==0x20000000 and t.IRQ.IsSet)\ng.WriteDoubleWord(0x7068,0x20000000)\nblocked('byte-width',lambda:g.ReadByte(0x73c0))\nblocked('status-write',lambda:g.WriteDoubleWord(0x7064,0))\ng.Reset()\ncheck('owner-reset',t.Control==t.Counter==t.Compare0==t.Compare1==t.Enable==t.Status==t.Reads==t.Writes==0 and t.GlobalEnable==0xffff and not t.IRQ.IsSet)\n")]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700)
 (o/'strict.cs').write_bytes(models(s));base='cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    PerformanceInMips: 1\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    -> cpu@0\nflash: Memory.MappedMemory @ sysbus 0x10000\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x1000\nguard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40001000\n    baseAddress: 0x40001000\n    size: 0x23000\n';(o/'board.repl').write_text(board(base));(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'));(o/'setup.py').write_text(SETUP)
 resc='include @/work/strict.cs\nmach create "timer14-unit"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 for n,(us,phase) in enumerate(PHASES):
  (o/f'phase-{n}.py').write_text(phase);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'report.py').write_text("Console.WriteLine('BLACKWALL_TIMER14_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='nominal virtual XT/LFRC, max primary continuous counter, secondary compare/NVIC81; spin guest, no physical or original ISR proof')))\n");(o/'probe.resc').write_text(resc+'include @/work/report.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(z.split('BLACKWALL_TIMER14_UNIT ',1)[1]) for z in log.splitlines() if z.startswith('BLACKWALL_TIMER14_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing Timer14 result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
