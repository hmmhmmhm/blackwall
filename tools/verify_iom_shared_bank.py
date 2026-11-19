"""Verify IOM2 shared power isolation and the actual mapped guard boundaries."""
import argparse,json
from pathlib import Path
from iom_main_adapter import connect_ioms
from run_renode_m55_probe import execute
from iom_engine_source import load_engine
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import json
from System import Console
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];i=m['sysbus.iom2'];h=m['sysbus.guard_high'];t=m['sysbus.guard_iom2_tail'];p=i.Power
extra=[node for n in g.IomPowers.Keys if n!=2 for node in (m['sysbus.iom'+str(n)],m['sysbus.guard_iom'+str(n)+'_tail'])]
checks=[]
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
def state():
    return (str(p.Phase),int(p.RequestWord),int(p.StatusWord),int(p.Requests),int(p.Responses),int(p.OffRequests),int(p.PowerCycles),int(i.Writes),int(i.Commands),int(i.PowerDowns),int(i.ClockConfiguration),int(i.FifoControl),int(i.SubmoduleControl),bool(i.IRQ.IsSet),int(g.DevicePowerWrites),tuple((int(n),str(g.UartPowers[n].Phase),int(g.UartPowers[n].RequestWord),int(g.UartPowers[n].StatusWord),int(g.Uarts[n].Writes)) for n in g.UartPowers.Keys),int(g.GpuPower.RequestWord),int(g.AdcPower.RequestWord),tuple((int(n),str(g.IomPowers[n].Phase),int(g.IomPowers[n].RequestWord),int(g.IomPowers[n].StatusWord),int(g.IomPowers[n].Requests),int(g.IomPowers[n].Responses),int(g.IomPowers[n].OffRequests),int(g.IomPowers[n].PowerCycles),int(m['sysbus.iom'+str(n)].Writes),int(m['sysbus.iom'+str(n)].ClockConfiguration),bool(m['sysbus.iom'+str(n)].IRQ.IsSet),int(m['sysbus.iom'+str(n)].CommandQueue.SoftwareFlags)) for n in g.IomPowers.Keys))
def blocks():return sum(int(x.AccessCount) for x in [g,h,t,i]+extra)
def blocked(name,action):
    before=state();count=blocks()
    try:action()
    except Exception:pass
    else:raise Exception(name+' accepted')
    check(name,state()==before and blocks()==count+1)
check('same-power-owner',g.IomPowers[2]==p)
g.GpuPower.TryWrite(0x40000,True);g.GpuPower.ReadStatus()
g.AdcPower.TryWrite(0x2000,True);g.AdcPower.TryReadStatus(True)
g.UartPowers[1].TryWrite(0x400,True);g.UartPowers[1].ReadStatus()
p.TryWrite(8,True);p.ReadStatus()
check('combined-read-enable',g.ReadDoubleWord(0x20004)==0x42408)
check('combined-read-status',g.ReadDoubleWord(0x20008)==0x42408)
blocked('two-domain-change',lambda:g.WriteDoubleWord(0x20004,0x42000))
blocked('unknown-domain-bit',lambda:g.WriteDoubleWord(0x20004,0x42409))
b.WriteDoubleWord(0x4005211c,0x10)
blocked('active-iom-off',lambda:g.WriteDoubleWord(0x20004,0x42400))
b.WriteDoubleWord(0x4005211c,0)
g.WriteDoubleWord(0x20004,0x42400)
check('off-request-preserve-others',p.Phase=='off-requested' and p.StatusWord==8 and g.UartPowers[1].RequestWord==0x400 and g.GpuPower.RequestWord==0x40000 and g.AdcPower.RequestWord==0x2000)
blocked('requested-mmio',lambda:b.ReadDoubleWord(0x40052118))
check('shared-off-status-callback',g.ReadDoubleWord(0x20008)==0x42400 and i.PowerDowns==1 and p.PowerCycles==1)
g.ReadDoubleWord(0x20008)
check('off-callback-single',i.PowerDowns==1 and p.Responses==2)
blocked('powered-off-mmio',lambda:b.WriteDoubleWord(0x40052118,1))
g.WriteDoubleWord(0x20004,0x42408)
check('cold-rail-reenable',p.Phase=='requested' and p.RequestWord==8 and p.StatusWord==0)
check('cold-rail-status',g.ReadDoubleWord(0x20008)==0x42408 and p.Phase=='on' and i.PowerDowns==1)
for address in (0x40051ffc,0x400523fc,0x40052400,0x5ffffffc):
    blocked('guard-boundary-'+hex(address),lambda:b.WriteDoubleWord(address,0))
g.Reset();i.ResetThroughInterface();p.TryWrite(8,True);g.UartPowers[1].TryWrite(0x400,True)
g.WriteDoubleWord(0x20004,8)
check('cancel-uart-preserve-iom',g.UartPowers[1].Phase=='cancelled' and p.RequestWord==8 and p.Phase=='requested')
g.WriteDoubleWord(0x20004,0)
check('cancel-iom',p.Phase=='cancelled' and p.RequestWord==0)
__MULTI_IOM_CHECKS__
__STARTUP_IOM_CHECKS__
Console.WriteLine('BLACKWALL_IOM_SHARED '+json.dumps(dict(passed=True,checks=checks,assertion_count=len(checks),scope='isolated shared-bank and mapped strict guards; no physical power or original main execution')))
'''
MULTI="i4=m['sysbus.iom4'];p4=i4.Power\ng.Reset();i.ResetThroughInterface();i4.ResetThroughInterface()\ncheck('iom4-power-owner',g.IomPowers[4]==p4 and p4.Mask==0x20 and i4.Module==4 and i4.BaseAddress==0x40054000)\np.TryWrite(8,True);p4.TryWrite(0x20,True)\nblocked('two-iom-cancel-change',lambda:g.WriteDoubleWord(0x20004,0))\ncheck('two-iom-status',g.ReadDoubleWord(0x20008)==0x28 and p.Phase=='on' and p4.Phase=='on')\nb.WriteDoubleWord(0x40052118,1);b.WriteDoubleWord(0x40054118,0x2001)\ncheck('iom-config-isolation',i.ClockConfiguration==1 and i4.ClockConfiguration==0x2001)\nblocked('unselected-iom3-power',lambda:g.WriteDoubleWord(0x20004,0x38))\nb.WriteDoubleWord(0x40054200,1);b.WriteDoubleWord(0x4005420c,1)\ncheck('iom4-irq10-wired',i4.IRQ.IsSet and not i.IRQ.IsSet and b.ReadDoubleWord(0xe000e200)&(1<<10)!=0)\nb.WriteDoubleWord(0x40054208,0x7fff);b.WriteDoubleWord(0xe000e280,1<<10)\ncheck('iom4-irq-clear',not i4.IRQ.IsSet and b.ReadDoubleWord(0xe000e200)&(1<<10)==0)\ng.WriteDoubleWord(0x20004,8)\ncheck('iom4-off-preserves-iom2',p4.Phase=='off-requested' and p.Phase=='on' and p.RequestWord==8 and i.ClockConfiguration==1)\ncheck('iom4-off-status',g.ReadDoubleWord(0x20008)==8 and i4.PowerDowns==1 and i.PowerDowns==0 and i4.ClockConfiguration==0 and i.ClockConfiguration==1)\nblocked('iom4-off-mmio',lambda:b.WriteDoubleWord(0x40054118,1))\nfor address in (0x40053ffc,0x400543fc,0x40054400,0x40055118,0x5ffffffc):\n    blocked('multi-guard-boundary-'+hex(address),lambda:b.WriteDoubleWord(address,0))\n"

STARTUP="if g.IomPowers.ContainsKey(5) and g.IomPowers.ContainsKey(7):\n    g.Reset()\n    for n in g.IomPowers.Keys:\n        w=m['sysbus.iom'+str(n)];w.ResetThroughInterface();w.Power.TryWrite(w.Power.Mask,True)\n    check('startup-all-on',g.ReadDoubleWord(0x20008)==0x168)\n    for n in (2,4,5,7):\n        w=m['sysbus.iom'+str(n)];b.WriteDoubleWord(w.BaseAddress+0x118,(n<<8)|1)\n        check('owner-'+str(n),w.Power==g.IomPowers[n] and w.Power.Mask==(1<<(n+1)))\n    for n in (5,7):\n        w=m['sysbus.iom'+str(n)];bit=1<<(6+n)\n        b.WriteDoubleWord(w.BaseAddress+0x200,1);b.WriteDoubleWord(w.BaseAddress+0x20c,1)\n        check('irq-route-'+str(n),w.IRQ.IsSet and b.ReadDoubleWord(0xe000e200)&bit!=0 and all(not m['sysbus.iom'+str(other)].IRQ.IsSet for other in (2,4,5,7) if other!=n))\n        b.WriteDoubleWord(w.BaseAddress+0x208,0x7fff);b.WriteDoubleWord(0xe000e280,bit)\n        check('irq-clear-'+str(n),not w.IRQ.IsSet and b.ReadDoubleWord(0xe000e200)&bit==0)\n    b.WriteDoubleWord(0x40055238,1);b.WriteDoubleWord(0x40057238,2)\n    check('cq-flags-isolated',m['sysbus.iom5'].CommandQueue.SoftwareFlags==1 and m['sysbus.iom7'].CommandQueue.SoftwareFlags==2 and i.CommandQueue.SoftwareFlags==0 and i4.CommandQueue.SoftwareFlags==0)\n    g.WriteDoubleWord(0x20004,0x128)\n    check('iom5-off-status',g.ReadDoubleWord(0x20008)==0x128 and m['sysbus.iom5'].PowerDowns==1)\n    check('iom5-off-preserves-others',m['sysbus.iom5'].ClockConfiguration==0 and m['sysbus.iom5'].CommandQueue.SoftwareFlags==0 and m['sysbus.iom7'].ClockConfiguration==0x701 and m['sysbus.iom7'].CommandQueue.SoftwareFlags==2 and i.ClockConfiguration==0x201 and i4.ClockConfiguration==0x401)\n    blocked('startup-two-domain-change',lambda:g.WriteDoubleWord(0x20004,0x20))\n    blocked('unselected-iom6-power',lambda:g.WriteDoubleWord(0x20004,0x1a8))\n    for address in (0x400553fc,0x40055400,0x40056ffc,0x400573fc,0x40057400):\n        blocked('startup-boundary-'+hex(address),lambda:b.WriteDoubleWord(address,0))\n"

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('board',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--with-iom4',action='store_true');p.add_argument('--modules')
    a=p.parse_args()
    modules=tuple(int(n) for n in a.modules.split(',')) if a.modules else ((2,4) if a.with_iom4 else (2,))
    if 2 not in modules or ((5 in modules or 7 in modules) and 4 not in modules) or (a.with_iom4 and 4 not in modules):
        raise ValueError('Shared fixture requires2, plus4 for extended startup')
    o=a.output.resolve();o.mkdir(mode=0o700)
    sources=['renode-strict-mmio.cs','renode-memory-policy.cs','renode-system-control.cs','renode-reset-controller.cs','renode-watchdog.cs']
    (o/'strict.cs').write_text('\n'.join((ROOT/'tools'/f).read_text() for f in sources)+'\n'+load_engine()+'\n'+(ROOT/'tools/renode-iom-command-queue.cs').read_text()+'\n'+(ROOT/'tools/renode-iom.cs').read_text());(o/'board.repl').write_text(connect_ioms(a.board.read_text(),'active','off',modules));(o/'test.py').write_text(DRIVER.replace('__MULTI_IOM_CHECKS__',MULTI if 4 in modules else '').replace('__STARTUP_IOM_CHECKS__',STARTUP))
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "iom-shared"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','blackwall-renode:1.17.0-local','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(x.split('BLACKWALL_IOM_SHARED ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_IOM_SHARED ')];assert len(rows)==1
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))
if __name__=='__main__':main()
