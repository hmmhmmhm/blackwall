"""Exercise the optional read-only chip-info fixture, never real device identifiers."""
import argparse,json
from pathlib import Path
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import json
from System import Console
m=monitor.Machine;g=m['sysbus.guard'];unknown=m['sysbus.unknown'];checks=[]
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
def state():return [(int(a),int(g.ChipInfo.GetValue(a)),int(g.ChipInfo.GetReads(a))) for a in g.ChipInfo.Addresses]
def blocked(name,action,owner=None):
    before=state();owner=owner or g;count=int(owner.AccessCount)
    try:action()
    except Exception:pass
    else:raise Exception(name+' accepted')
    check(name,state()==before and int(owner.AccessCount)==count+1)
expected=[0x10320080,0,0,0x23,0,0x2d480f]
for index,address in enumerate(g.ChipInfo.Addresses):
    check('read-'+str(index),g.ReadDoubleWord(int(address)-0x40000000)==expected[index] and g.ChipInfo.GetReads(address)==1)
    blocked('readonly-'+str(index),lambda:g.WriteDoubleWord(int(address)-0x40000000,expected[index]))
check('shared-revision-accounting',g.ChipRevision==0x23 and g.ChipRevisionReads==g.ChipInfo.GetReads(0x4002000c)==1)
for offset in (0x1fffc,0x20018,0x20001):blocked('adjacent-'+str(offset),lambda:g.ReadDoubleWord(offset))
blocked('byte-width',lambda:g.ReadByte(0x20000))
blocked('word-width',lambda:g.WriteWord(0x20000,0))
blocked('quad-width',lambda:g.ReadQuadWord(0x20000))
blocked('default-unknown',lambda:unknown.ReadDoubleWord(0x20000),unknown)
check('default-revision-still-supported',unknown.ReadDoubleWord(0x2000c)==0x23)
g.Reset()
check('reset-counts',g.ChipRevisionReads==0 and all(g.ChipInfo.GetReads(a)==0 for a in g.ChipInfo.Addresses))
check('reset-values',state()==[(0x40020000+4*i,expected[i],0) for i in range(6)])
Console.WriteLine('BLACKWALL_CHIP_INFO '+json.dumps(dict(passed=True,checks=checks,assertion_count=len(checks),unique_ids='synthetic-zero-not-device-data',hardware_validated=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
    if o.exists():raise ValueError('Use a fresh evidence directory')
    o.mkdir(mode=0o700);(o/'strict.cs').write_bytes((ROOT/'tools/renode-strict-mmio.cs').read_bytes())
    (o/'test.py').write_text(DRIVER);compile(DRIVER,'test.py','exec')
    (o/'board.repl').write_text('guard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40000000\n    baseAddress: 0x40000000\n    size: 0x30000\n    chipRevision: 0x23\n    chipInfo: true\nunknown: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x60000000\n    baseAddress: 0x40000000\n    size: 0x30000\n    chipRevision: 0x23\n')
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "chip-info-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(x.split('BLACKWALL_CHIP_INFO ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_CHIP_INFO ')]
    if len(rows)!=1:raise ValueError('Missing chip fixture result; inspect saved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))

if __name__=='__main__':main()
