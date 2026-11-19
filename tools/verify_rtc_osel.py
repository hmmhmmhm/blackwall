"""Exercise an explicit OCTRL request latch in Renode; no physical clocks or firmware."""
import argparse, json, shutil
from pathlib import Path
from run_renode_m55_probe import execute

ROOT = Path(__file__).resolve().parents[1]
DRIVER = '''import json
from System import Console
m=monitor.Machine
checks=[]
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
def blocked(name,g,action):
    r=g.RtcOsel
    before=(int(r.Value),int(r.Reads),int(r.Writes)) if r is not None else None
    count=int(g.AccessCount)
    try:action()
    except Exception:pass
    else:raise Exception(name+' accepted')
    after=(int(r.Value),int(r.Reads),int(r.Writes)) if r is not None else None
    check(name,before==after and int(g.AccessCount)==count+1)
for name,initial in [('xt',0),('lfrc',128)]:
    g=m['sysbus.'+name]
    check(name+'-initial',g.RtcOsel.InitialValue==initial and g.ReadDoubleWord(12)==initial)
    for value in (128,0,128,128,0):
        g.WriteDoubleWord(12,value)
        check(name+'-readback-'+str(g.RtcOsel.Writes),g.ReadDoubleWord(12)==value)
    for value in (1,129,0xffffffff):
        blocked(name+'-reserved-'+str(value),g,lambda:g.WriteDoubleWord(12,value))
    for offset in (8,13,16):
        blocked(name+'-neighbor-'+str(offset),g,lambda:g.ReadDoubleWord(offset))
    blocked(name+'-byte-read',g,lambda:g.ReadByte(12))
    blocked(name+'-word-write',g,lambda:g.WriteWord(12,128))
    blocked(name+'-quad-read',g,lambda:g.ReadQuadWord(12))
    check(name+'-counts',g.RtcOsel.Reads==6 and g.RtcOsel.Writes==5)
    g.Reset()
    check(name+'-reset',g.RtcOsel.Value==initial and g.RtcOsel.Reads==0 and g.RtcOsel.Writes==0 and g.AccessCount==0)
g=m['sysbus.unknown']
check('default-unmodeled',g.RtcOsel is None)
blocked('default-read',g,lambda:g.ReadDoubleWord(12))
blocked('default-write',g,lambda:g.WriteDoubleWord(12,0))
check('independent-initial-state',m['sysbus.xt'].RtcOsel.Value==0 and m['sysbus.lfrc'].RtcOsel.Value==128)
Console.WriteLine('BLACKWALL_RTC_OSEL '+json.dumps(dict(passed=True,checks=checks,assertion_count=len(checks),effective_source=None,hardware_validated=False,scope='explicit request latch; no oscillator, RTC time, or silicon readback validation')))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    a=p.parse_args();o=a.output.resolve();o.mkdir(mode=0o700)
    shutil.copy2(ROOT/'tools/renode-strict-mmio.cs',o/'strict.cs')
    (o/'test.py').write_text(DRIVER)
    board=''
    for name,address,initial in [('xt',0x40000000,0),('lfrc',0x60000000,1),('unknown',0x80000000,None)]:
        board+=f'{name}: Miscellaneous.BlackwallG2StartupFixture @ sysbus {hex(address)}\n    baseAddress: 0x40004000\n    size: 0x1000\n'
        if initial is not None:board+=f'    rtcOselInitial: {initial}\n'
        board+='\n'
    (o/'board.repl').write_text(board)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "rtc-osel-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','blackwall-renode:1.17.0-local','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(x.split('BLACKWALL_RTC_OSEL ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RTC_OSEL ')]
    if len(rows)!=1:raise ValueError('Missing RTC latch verification result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n')
    print(json.dumps(rows[0]))

if __name__=='__main__':main()
