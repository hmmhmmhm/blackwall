"""Run a synthetic ARM guest to verify read-only PC hooks, counters, and bounded event history."""
import argparse, json, subprocess
from pathlib import Path
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path)
    a=p.parse_args();o=a.output.resolve();o.mkdir(mode=0o700)
    (o/'observer.cs').write_bytes((ROOT/'tools/renode-execution-observer.cs').read_bytes())
    (o/'guest.s').write_bytes((ROOT/'tests/fixtures/observation-smoke.s').read_bytes())
    (o/'guest.ld').write_text('ENTRY(reset)\nSECTIONS { . = 0x10000; .vectors : { *(.vectors) } .text : { *(.text*) } }\n')
    command=['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-nostdlib','-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-T,'+str(o/'guest.ld'),str(o/'guest.s'),'-o',str(o/'guest.elf')]
    execute(command,o,'compiler')
    result=subprocess.run(['/opt/homebrew/opt/llvm@21/bin/llvm-nm',str(o/'guest.elf')],capture_output=True,text=True,check=True)
    symbols={line.split()[2]:int(line.split()[0],16)&~1 for line in result.stdout.splitlines() if len(line.split())==3}
    (o/'symbols.json').write_text(json.dumps(symbols,indent=2)+'\n')
    (o/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    PerformanceInMips: 1\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    -> cpu@0\nflash: Memory.MappedMemory @ sysbus 0x10000\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x1000\n')
    setup='''import clr,json
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallExecutionObserver').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallExecutionObserver
m=monitor.Machine
observer=BlackwallExecutionObserver(m['sysbus.cpu'],2)
'''
    for name in ('reset','loop','store_result','after_store'):setup+=f"observer.AddPoint('{name}',{symbols[name]})\n"
    setup+="observer.CaptureSram(m,'after_store',0x20000000,1)\n"
    setup+='''rejected=0
for label,address in [('duplicate',__RESET__),('reset',0x100f0),('unaligned',0x100f1)]:
    try:observer.AddPoint(label,address)
    except Exception:rejected+=1
    else:raise Exception('invalid observation point accepted')
for label,address,words in [('unknown',0x20000000,1),('reset',0x40000000,1),('reset',0x20000001,1),('reset',0x20000000,17),('after_store',0x20000000,1)]:
    try:observer.CaptureSram(m,label,address,words)
    except Exception:rejected+=1
    else:raise Exception('invalid snapshot accepted')
'''.replace('__RESET__',str(symbols['reset']))
    (o/'setup.py').write_text(setup)
    report='''from System import Console
counts={str(p.Label):int(p.Hits) for p in observer.Points}
events=[dict(sequence=int(e.Sequence),label=str(e.Label),address=int(e.Address),pc=int(e.PC),r0=int(e.R0),r2=int(e.R2)) for e in observer.Events]
assert counts=={'reset':1,'loop':3,'store_result':1,'after_store':1}
assert int(observer.Sequence)==6 and int(observer.DroppedEvents)==4 and len(events)==2
assert [e['sequence'] for e in events]==[5,6]
assert [e['label'] for e in events]==['store_result','after_store']
assert all(e['pc']==e['address'] for e in events)
assert [e['r2'] for e in events]==[0x20000000,0x20000000]
assert [e['r0'] for e in events]==[0,0]
snap=next(p.Snapshot for p in observer.Points if str(p.Label)=='after_store')
assert list(snap.Words)==[42] and snap.Address==0x20000000 and snap.Sequence==6
assert int(m.SystemBus.ReadDoubleWord(0x20000000))==42 and rejected==8
Console.WriteLine('BLACKWALL_OBSERVER_UNIT '+json.dumps(dict(passed=True,counts=counts,events=events,dropped=4,invalid_points_rejected=rejected,snapshot_words=[int(x) for x in snap.Words],guest_result=42,scope='synthetic CPU hook/snapshot verification, not original firmware boot')))
'''
    (o/'report.py').write_text(report)
    compile(setup,'setup.py','exec');compile(report,'report.py','exec')
    (o/'probe.resc').write_text('include @/work/observer.cs\nmach create "observer-unit"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/guest.elf\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\nemulation RunFor "00:00:00.001"\ninclude @/work/report.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','blackwall-renode:1.17.0-local','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(x.split('BLACKWALL_OBSERVER_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_OBSERVER_UNIT ')]
    if len(rows)!=1:raise ValueError('Missing observer guest result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))

if __name__=='__main__':main()
