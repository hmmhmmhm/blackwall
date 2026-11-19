"""Verify one-time retained NOR image loading before a window is used."""
import argparse
import json
from pathlib import Path

from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models

DRIVER = '''import clr,json
from System import Console,Array,Byte,Object,UInt32
from System.Reflection import BindingFlags
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallNorReadWindow').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallNorReadWindow
checks=[]
def check(name,value):
    if not value:raise Exception(name)
    checks.append(name)
check('managed-bytearray-equality',bytearray(Array[Byte]([0,165,255]))==bytearray(Array[Byte]([0,165,255])))
check('managed-bytearray-difference',bytearray(Array[Byte]([0,165,255]))!=bytearray(Array[Byte]([0,166,255])))
def read(w):
    ok,data=w.TryRead(w.Start,w.Length)
    check('read-success',ok)
    return [int(x) for x in data]
def call(w,name,*args):
    return w.GetType().GetMethod(name,BindingFlags.Instance|BindingFlags.NonPublic).Invoke(w,Array[Object](args))
def denied(name,fn):
    try:fn()
    except Exception:checks.append(name)
    else:raise Exception('accepted '+name)
w=BlackwallNorReadWindow('erased-range',0x1000,16,True,True)
data=Array[Byte](range(16))
w.LoadCommittedImage(data)
data[0]=99
check('loaded-owned-copy',w.SnapshotLoaded and read(w)==list(range(16)))
denied('second-load',lambda:w.LoadCommittedImage(Array[Byte]([0]*16)))
w.Reset()
check('reset-retains-image-and-origin',w.SnapshotLoaded and read(w)==list(range(16)))
denied('reset-not-import-permission',lambda:w.LoadCommittedImage(Array[Byte]([0]*16)))
for data in [None,Array[Byte]([]),Array[Byte]([0]*15),Array[Byte]([0]*17)]:
    n=BlackwallNorReadWindow('erased-range',0x1000,16)
    denied('invalid-extent',lambda:n.LoadCommittedImage(data))
    check('invalid-unchanged',not n.SnapshotLoaded and read(n)==[255]*16)
n=BlackwallNorReadWindow('erased-range',0x1000,16)
read(n)
denied('read-before-load',lambda:n.LoadCommittedImage(Array[Byte]([0]*16)))
n=BlackwallNorReadWindow('erased-range',0x1000,4096,True,True)
check('program-seed',call(n,'TryProgramPage',UInt32(0x1000),Array[Byte]([3])))
denied('program-before-load',lambda:n.LoadCommittedImage(Array[Byte]([0]*4096)))
check('program-preserved',read(n)[0]==3)
n=BlackwallNorReadWindow('erased-range',0x1000,4096,True,True)
check('erase-seed',call(n,'TryEraseSector',UInt32(0x1000)))
denied('erase-before-load',lambda:n.LoadCommittedImage(Array[Byte]([0]*4096)))
check('erase-preserved',read(n)==[255]*4096)
n=BlackwallNorReadWindow('erased-range',0x1000,16)
check('invalid-read-denied',not n.TryRead(0x2000,1)[0])
check('invalid-program-denied',not call(n,'TryProgramPage',UInt32(0x1000),Array[Byte]([0])))
n.LoadCommittedImage(Array[Byte]([7]*16))
check('denied-ops-dont-consume-load',read(n)==[7]*16)
child=BlackwallNorReadWindow('erased-range',0x3000,16)
parent=BlackwallNorReadWindow('erased-range',0x1000,16,False,False,child)
parent.LoadCommittedImage(Array[Byte]([1]*16));child.LoadCommittedImage(Array[Byte]([2]*16))
check('separate-window-images',read(parent)==[1]*16 and read(child)==[2]*16)
Console.WriteLine('BLACKWALL_NOR_SNAPSHOT_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False)))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (args.output/'strict.cs').write_bytes(models(args.simulator))
    (args.output/'run.py').write_text(DRIVER)
    (args.output/'probe.resc').write_text('include @/work/strict.cs\nmach create "NOR-snapshot"\ninclude @/work/run.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1',
                 '--cap-drop','ALL','--security-opt','no-new-privileges','--mount',
                 f'type=bind,source={args.output},target=/work,readonly',IMAGE,
                 '--disable-gui','--console','-p','-e','quit','/work/probe.resc'],args.output,'renode')
    rows=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_NOR_SNAPSHOT_UNIT ')]
    if len(rows)!=1:raise ValueError('Missing snapshot unit result; inspect retained log')
    (args.output/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n')
    print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
