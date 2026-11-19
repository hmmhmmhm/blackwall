"""Exercise the strict RTC adapter through the mapped startup fixture under virtual time."""
import argparse,json,struct
from pathlib import Path
from rtc_engine_source import load_engine
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]

SETUP='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];a=g.Rtc;denied=m['sysbus.denied_guard'].Rtc;unknown=m['sysbus.unknown']
checks=[]
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
def state(x):return (str(x.VirtualDate),int(x.Control),bool(x.WritePending),bool(x.PairPending),int(x.Reads),int(x.Writes),int(x.Commits),bool(x.IRQ.IsSet))
def blocked(name,x,action,owner=None):
    before=state(x);owner=owner or x;count=int(owner.AccessCount)
    try:action()
    except Exception:pass
    else:raise Exception(name+' accepted')
    check(name,state(x)==before and owner.AccessCount==count+1)
def readpair():return (g.ReadDoubleWord(0x4820),g.ReadDoubleWord(0x4824))
def setdate(low,upper):
    g.WriteDoubleWord(0x4800,1);g.WriteDoubleWord(0x4820,low);g.WriteDoubleWord(0x4824,upper);g.WriteDoubleWord(0x4800,0)
check('fixture-owner',g.Rtc==a and a.Control==0)
blocked('upper-without-low',a,lambda:g.ReadDoubleWord(0x4824))
denied.WriteDoubleWord(0,1)
blocked('write-profile-required',denied,lambda:denied.WriteDoubleWord(0x20,0))
blocked('wrtc-required',a,lambda:g.WriteDoubleWord(0x4820,0))
g.WriteDoubleWord(0x4800,1)
for low in (0xff,0x24000000,0x00600000,0x00006000,0x80000000):blocked('bad-low-'+str(low),a,lambda:g.WriteDoubleWord(0x4820,low))
g.WriteDoubleWord(0x4820,0x23595999)
check('staged-busy',a.WritePending and g.ReadDoubleWord(0x4804)==1 and a.Commits==0 and str(a.VirtualDate).startswith('2000-01-01T00:00:00'))
blocked('pending-read',a,lambda:g.ReadDoubleWord(0x4820))
blocked('unfinished-wrtc-clear',a,lambda:g.WriteDoubleWord(0x4800,0))
for upper in (0x14240230,0x04240229,0x34240229,0x15240229):blocked('bad-upper-'+str(upper),a,lambda:g.WriteDoubleWord(0x4824,upper))
g.WriteDoubleWord(0x4824,0x14240229);g.WriteDoubleWord(0x4800,0)
check('valid-commit',a.Commits==1 and not a.WritePending and g.ReadDoubleWord(0x4804)==0)
check('century-encoded-2000s',readpair()==(0x23595999,0x14240229))
'''
PHASES=[('020','rollover','''check('leap-day-rollover',readpair()==(1,0x15240301))
setdate(0x23595999,0x16000101)
check('split-low-value',g.ReadDoubleWord(0x4820)==0x23595999)
'''),('005','early','''check('early-upper-no-error',g.ReadDoubleWord(0x4824)==0x16000101)
setdate(0x23595999,0x16000101)
g.ReadDoubleWord(0x4820)
'''),('020','late','''check('late-upper-held-and-error',g.ReadDoubleWord(0x4824)==0x96000101 and a.LateReads==1)
frozen=readpair();g.WriteDoubleWord(0x4800,16)
'''),('050','stopped','''check('stop-freezes-counter',readpair()==frozen and a.Control&16!=0)
g.WriteDoubleWord(0x4800,0)
'''),('020','resumed','''after=readpair()
check('resume-advances-counter',after!=frozen and after[1]==frozen[1])
g.WriteDoubleWord(0x4a0c,1)
check('software-mask',not a.IRQ.IsSet and g.ReadDoubleWord(0x4a04)==1)
g.WriteDoubleWord(0x4a00,1)
check('irq2-pending',a.IRQ.IsSet and b.ReadDoubleWord(0xe000e200)&4!=0)
g.WriteDoubleWord(0x4a08,1)
check('software-clear',not a.IRQ.IsSet)
g.Reset();check('fixture-reset',a.Commits==0 and a.Reads==0 and a.Writes==0 and not a.IRQ.IsSet and str(a.VirtualDate)=='2000-01-01T00:00:00.00')
b.WriteDoubleWord(0xe000e280,4)
g.WriteDoubleWord(0x4830,0x50);g.WriteDoubleWord(0x4834,0);g.WriteDoubleWord(0x4a00,1);g.WriteDoubleWord(0x4800,14)
'''),('490','before-alarm','''check('alarm-not-early',not a.IRQ.IsSet)
'''),('010','alarm','''check('alarm-at-half-second',a.IRQ.IsSet and g.ReadDoubleWord(0x4a04)==1)
g.WriteDoubleWord(0x4a08,1)
'''),('1000','final','''check('alarm-repeats-one-second',a.IRQ.IsSet)
for value in (32,64,6):blocked('control-unmodeled-'+str(value),a,lambda:g.WriteDoubleWord(0x4800,value))
blocked('subsecond-alarm-unmodeled',a,lambda:g.WriteDoubleWord(0x4830,255))
blocked('invalid-alarm-date',a,lambda:g.WriteDoubleWord(0x4834,0x71f3f))
blocked('irq-reserved',a,lambda:g.WriteDoubleWord(0x4a00,2))
blocked('status-write',a,lambda:g.WriteDoubleWord(0x4804,0))
blocked('interrupt-action-read',a,lambda:g.ReadDoubleWord(0x4a08))
blocked('unknown-register',a,lambda:g.ReadDoubleWord(0x4810))
blocked('byte-through-fixture',a,lambda:g.ReadByte(0x4800),g)
blocked('word-through-fixture',a,lambda:g.WriteWord(0x4800,0),g)
blocked('quad-direct',a,lambda:a.ReadQuadWord(0))
blocked('default-unmodeled',a,lambda:unknown.ReadDoubleWord(0x4800),unknown)
Console.WriteLine('BLACKWALL_RTC_ADAPTER '+json.dumps(dict(passed=True,checks=checks,assertion_count=len(checks),scope='mapped functional adapter with virtual epoch/100Hz/optional HAL-order assumptions, no physical clock or original main',date=str(a.VirtualDate))))
''')]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
    if o.exists():raise ValueError('Use a fresh evidence directory')
    o.mkdir(mode=0o700)
    (o/'strict.cs').write_text((ROOT/'tools/renode-strict-mmio.cs').read_text()+'\n'+load_engine()+'\n'+(ROOT/'tools/renode-rtc.cs').read_text())
    (o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'))
    (o/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    PerformanceInMips: 1\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    -> cpu@0\nflash: Memory.MappedMemory @ sysbus 0x10000\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x1000\nrtc: Miscellaneous.BlackwallRtcAdapter @ none\n    halLowUpperWrites: true\n    -> nvic@2\ndenied: Miscellaneous.BlackwallRtcAdapter @ none\nguard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40000000\n    baseAddress: 0x40000000\n    size: 0x10000\n    rtc: rtc\ndenied_guard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x60010000\n    baseAddress: 0x40000000\n    size: 0x10000\n    rtc: denied\nunknown: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x60000000\n    baseAddress: 0x40000000\n    size: 0x10000\n')
    compile(SETUP,'setup','exec');(o/'setup.py').write_text(SETUP)
    resc='include @/work/strict.cs\nmach create "rtc-adapter"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
    for milliseconds,name,code in PHASES:
        compile(code,name,'exec');(o/(name+'.py')).write_text(code)
        duration=f'{int(milliseconds)//1000:02}.{int(milliseconds)%1000:03}'
        resc+='emulation RunFor "00:00:'+duration+'"\ninclude @/work/'+name+'.py\n'
    (o/'probe.resc').write_text(resc+'quit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(x.split('BLACKWALL_RTC_ADAPTER ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RTC_ADAPTER ')]
    if len(rows)!=1:raise ValueError('Missing RTC adapter result; inspect saved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))

if __name__=='__main__':main()
