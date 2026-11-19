"""Check disjoint NOR windows and independent read/program/erase permissions in RAM."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute

DRIVER='''import clr,json
from System import Console,Array,Byte,Object,UInt32
from System.Reflection import BindingFlags
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallNorReadWindow').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallNorReadWindow
checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def call(w,name,*args):
    method=w.GetType().GetMethod(name,BindingFlags.Instance|BindingFlags.NonPublic)
    return method.Invoke(w,Array[Object](args))
def read(w,addr,size):
    ok,data=w.TryRead(addr,size)
    return ok,None if data is None else [int(x) for x in data]
volume=BlackwallNorReadWindow('erased-range',0x1400000,0xbc0000)
root=BlackwallNorReadWindow('erased-range',0x1fc0000,0x40000,True,True,volume)
check('same-additional-owner',root.AdditionalWindow==volume)
for addr in [0x1400000,0x1fbfff0,0x1fc0000,0x1fffff0]:check('in-range-'+str(addr),read(root,addr,16)==(True,[255]*16))
for addr,size in [(0x13fffff,1),(0x1fbfff8,16),(0x1ffffff,2),(0xffffffff,2),(0x1400000,0)]:check('out-or-cross-range-'+str(addr),read(root,addr,size)==(False,None))
check('volume-program-denied',not call(root,'TryProgramPage',UInt32(0x1400000),Array[Byte]([1,2,3])))
check('volume-erase-denied',not call(root,'TryEraseSector',UInt32(0x1400000)))
check('volume-unchanged',read(root,0x1400000,4)==(True,[255]*4))
check('primary-program-allowed',call(root,'TryProgramPage',UInt32(0x1fc00ff),Array[Byte]([1,2,3])))
check('primary-wrap-within-page',read(root,0x1fc0000,2)==(True,[2,3]) and read(root,0x1fc00ff,1)==(True,[1]))
root.Reset();volume.Reset();check('reset-preserves-bytes',read(root,0x1fc0000,2)==(True,[2,3]))
check('primary-erase-allowed',call(root,'TryEraseSector',UInt32(0x1fc0000)))
check('primary-erased',read(root,0x1fc0000,4)==(True,[255]*4))
check('outside-program-denied',not call(root,'TryProgramPage',UInt32(0x13fffff),Array[Byte]([0])))
small=BlackwallNorReadWindow('erased-range',0x1000,0x1000,True,True)
readOnlyRoot=BlackwallNorReadWindow('erased-range',0x3000,0x1000,False,False,small)
check('child-own-program-permission',call(readOnlyRoot,'TryProgramPage',UInt32(0x1000),Array[Byte]([7])))
check('child-readback',read(readOnlyRoot,0x1000,1)==(True,[7]))
check('child-own-erase-permission',call(readOnlyRoot,'TryEraseSector',UInt32(0x1000)))
check('parent-permission-not-inherited',not call(readOnlyRoot,'TryProgramPage',UInt32(0x3000),Array[Byte]([7])))
edge=BlackwallNorReadWindow('erased-range',0x1000,2,True,True)
split=BlackwallNorReadWindow('erased-range',0x1002,0xffe,True,True,edge)
check('split-page-program-denied',not call(split,'TryProgramPage',UInt32(0x1000),Array[Byte]([0,0,0])))
check('split-program-no-partial-change',read(split,0x1000,2)==(True,[255]*2) and read(split,0x1002,2)==(True,[255]*2))
check('split-erase-seeds',call(split,'TryProgramPage',UInt32(0x1000),Array[Byte]([17])) and call(split,'TryProgramPage',UInt32(0x1002),Array[Byte]([34])))
check('split-sector-erase-denied',not call(split,'TryEraseSector',UInt32(0x1000)))
check('split-erase-no-partial-change',read(split,0x1000,2)==(True,[17,255]) and read(split,0x1002,2)==(True,[34,255]))
for child in [BlackwallNorReadWindow('erased-range',0x1fc0000,0x1000),BlackwallNorReadWindow('erased-range',0x1fbf000,0x2000),readOnlyRoot]:
    try:BlackwallNorReadWindow('erased-range',0x1fc0000,0x40000,True,True,child)
    except Exception as e:check('invalid-overlap-or-chain','disjoint single additional' in str(e))
    else:raise Exception('invalid window graph accepted')
Console.WriteLine('BLACKWALL_NOR_ADDITIONAL_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='disjoint RAM windows only; no hardware or filesystem mount')))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    (o/'strict.cs').write_bytes(models(s));(o/'test.py').write_text(DRIVER)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "NOR-windows"\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_NOR_ADDITIONAL_UNIT ')]
    if len(rows)!=1:raise ValueError('Missing window result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
