"""Exercise the explicit raw FIFO component in Renode; no firmware or hardware."""
import argparse
import json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = '''import clr,json
from System import Array,Byte,Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallImuRawFifo').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuRawFifo
checks=[]
def check(name,value):
    if not value:raise Exception(name)
    checks.append(name)
def frame(seed):return Array[Byte]([0x68]+[(seed+k)&255 for k in range(15)])
def read(q,n):
    data=q.ReadChunk(n)
    return None if data is None else [int(x) for x in data]
def count(q,expected):
    check('count-begin',q.TryBeginRead(0x12,2))
    expected_bytes=[0,expected] if q.BigEndian else [expected,0]
    check('count-snapshot',read(q,2)==expected_bytes)
    check('count-finish',q.TryFinishRead() and q.PacketCount==expected)
default=BlackwallImuRawFifo()
check('default-off',not default.Enabled and not default.TryEnqueueFrame(frame(1)) and not default.TryBeginRead(0x12,2))
for cap in [0,129]:
    try:BlackwallImuRawFifo(True,False,cap)
    except System.ArgumentException:check('invalid-capacity',True)
    else:raise Exception('capacity accepted')
for endian in [False,True]:
    q=BlackwallImuRawFifo(True,endian,2)
    for bad in [None,Array[Byte]([]),Array[Byte]([0]*16),Array[Byte]([0x68]*15),Array[Byte]([0x68]*17)]:
        check('invalid-frame-preserves',not q.TryEnqueueFrame(bad) and q.PacketCount==0 and q.PacketsEnqueued==0)
    a=frame(10);expected_a=[int(x) for x in a]
    check('enqueue-one',q.TryEnqueueFrame(a));a[1]=255
    count(q,1);count(q,1)
    for address,length in [(0x11,2),(0x13,2),(0x12,1),(0x12,3),(0x14,0),(0x14,1),(0x14,17),(0x14,32)]:
        check('invalid-select-preserves',not q.TryBeginRead(address,length) and not q.ReadActive and q.PacketCount==1)
    check('data-begin',q.TryBeginRead(0x14,16))
    check('active-reselect-rejected',not q.TryBeginRead(0x12,2))
    check('active-flush-rejected',not q.TryFlush())
    check('early-finish-rejected',not q.TryFinishRead() and q.PacketCount==1)
    check('bad-chunk-preserves',read(q,0) is None and read(q,17) is None and q.ReadBytes==4)
    first=q.ReadChunk(4);check('chunk-copy',list(first)==expected_a[:4]);first[0]=0
    b=frame(40);expected_b=[int(x) for x in b]
    check('append-during-read',q.TryEnqueueFrame(b) and q.PacketCount==2)
    check('capacity-bound',not q.TryEnqueueFrame(frame(60)) and q.PacketCount==2)
    check('count-not-consumed-by-chunk',q.PacketCount==2 and q.PacketsConsumed==0)
    check('rest-in-order',read(q,12)==expected_a[4:])
    check('read-overrun-rejected',read(q,1) is None)
    check('commit-only-prefix',q.TryFinishRead() and q.PacketCount==1 and q.PacketsConsumed==1)
    count(q,1)
    check('next-frame-begin',q.TryBeginRead(0x14,16))
    received=[]
    for n in [1,2,3,4,6]:received+=read(q,n)
    check('split-chunks-exact',received==expected_b and q.PacketCount==1)
    check('commit-second',q.TryFinishRead() and q.PacketCount==0 and q.PacketsConsumed==2)
    check('empty-data-rejected',not q.TryBeginRead(0x14,16))
    check('no-extra-finish',not q.TryFinishRead())
    check('flush-input',q.TryEnqueueFrame(frame(80)))
    check('flush-preserves-config',q.TryFlush() and q.PacketCount==0 and q.BigEndian==endian and q.CapacityPackets==2 and q.PacketsConsumed==2 and q.Flushes==1)
    check('abort-input',q.TryEnqueueFrame(frame(90)) and q.TryBeginRead(0x14,16) and read(q,3) is not None)
    check('partial-finish-unsupported',not q.TryFinishRead() and q.ReadActive and q.PacketCount==1)
    q.Reset()
    check('reset-discards-state',not q.ReadActive and q.PacketCount==q.PacketsEnqueued==q.PacketsConsumed==q.ReadBytes==q.Flushes==0 and q.Enabled and q.BigEndian==endian)
q=BlackwallImuRawFifo(True,False,128)
expected=[]
for n in range(128):
    value=frame(n);expected+=list(value);check('fill-to-2k',q.TryEnqueueFrame(value))
check('2k-full',not q.TryEnqueueFrame(frame(1)) and q.PacketCount==128)
count(q,128)
check('full-drain-begin',q.TryBeginRead(0x14,2048));actual=[]
for unused in range(512):actual+=read(q,4)
check('full-drain-bytes',actual==expected and q.PacketCount==128)
check('full-drain-commit',q.TryFinishRead() and q.PacketCount==0 and q.PacketsConsumed==128)
Console.WriteLine('BLACKWALL_RAW_FIFO_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,original_firmware_executed=False,bus_integration=False,normal_gaf_supported=False)))
'''.replace('from System import Array,Byte,Console', 'import System\nfrom System import Array,Byte,Console')

SCRIPT_32 = """import clr,json,System
from System import Array,Byte,Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallImuRawFifo').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuRawFifo
checks=[]
def check(n,v):
 if not v:raise Exception(n)
 checks.append(n)
def frame(seed=0,header=0xe0,header2=0x1f):return Array[Byte]([header,header2]+[(seed+k)&255 for k in range(30)])
for endian in [False,True]:
 q=BlackwallImuRawFifo(True,endian,64,32)
 check('32byte-2k-profile',q.FrameBytes==32 and q.CapacityPackets==64)
 for bad in [Array[Byte]([0x68]*16),Array[Byte]([0xe0]*31),Array[Byte]([0xe0]*33),frame(header=0x60),frame(header=0xf0),frame(header2=0x0f),frame(header2=0x3f)]:
  check('invalid-frame-rejected',not q.TryEnqueueFrame(bad) and q.PacketCount==0)
 for valid in [0,4,8,12]:
  check('valid-es-mask',q.TryEnqueueFrame(frame(header2=0x13|valid)))
 for header in [0xe4,0xe8,0xef]:check('retained-low-header-flags',q.TryEnqueueFrame(frame(header=header)))
 check('flush-preserves-frame-size',q.TryFlush() and q.PacketCount==0 and q.FrameBytes==32)
 values=[frame(n) for n in range(64)];expected=sum([list(v) for v in values],[])
 check('fill-2k',all(q.TryEnqueueFrame(v) for v in values) and not q.TryEnqueueFrame(frame(100)) and q.PacketCount==64)
 check('packet-count-begin',q.TryBeginRead(0x12,2))
 check('packet-count-not-byte-count',list(q.ReadChunk(2))==([0,64] if endian else [64,0]) and q.TryFinishRead() and q.PacketCount==64)
 for n in [0,1,16,31,33,2049]:check('bad-read-length',not q.TryBeginRead(0x14,n) and not q.ReadActive)
 check('full-drain-begin',q.TryBeginRead(0x14,2048));actual=[]
 for n in range(512):actual+=list(q.ReadChunk(4))
 check('2k-exact-chunks',actual==expected and q.PacketCount==64)
 check('complete-64-packets',q.TryFinishRead() and q.PacketCount==0 and q.PacketsConsumed==64)
 check('partial-fill',q.TryEnqueueFrame(frame(1)) and q.TryEnqueueFrame(frame(2)) and q.TryBeginRead(0x14,64))
 check('partial-no-consume',list(q.ReadChunk(4))==list(frame(1))[:4] and not q.TryFinishRead() and q.PacketCount==2)
 check('append-during-read',q.TryEnqueueFrame(frame(3)))
 check('finish-prefix-only',len(q.ReadChunk(60))==60 and q.TryFinishRead() and q.PacketCount==1)
 q.Reset();check('reset-keeps-profile',q.PacketCount==0 and q.FrameBytes==32 and q.BigEndian==endian)
for size,cap in [(8,64),(20,64),(64,32),(32,65)]:
 try:BlackwallImuRawFifo(True,False,cap,size)
 except System.ArgumentException:check('unsupported-profile-rejected',True)
 else:raise Exception('Unsupported FIFO profile accepted')
Console.WriteLine('BLACKWALL_RAW_FIFO_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,frame_bytes=32,original_firmware_executed=False,bus_integration=False,normal_gaf_supported=False)))
"""

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--frame-bytes',type=int,choices=[16,32],default=16)
    args=parser.parse_args()
    out=args.output.resolve()
    if out.exists() or out.is_relative_to(ROOT):parser.error('New output outside repository required')
    source=(ROOT/'tools/renode-imu-raw-fifo.cs').read_bytes()
    out.mkdir(parents=True,mode=0o700)
    (out/'fifo.cs').write_bytes(source)
    (out/'test.py').write_text(SCRIPT_32 if args.frame_bytes==32 else SCRIPT)
    (out/'probe.resc').write_text('mach create "raw-fifo-unit"\ninclude @/work/fifo.cs\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode',timeout=90)
    rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RAW_FIFO_UNIT ')]
    if len(rows)!=1:raise ValueError('Raw FIFO suite did not complete; inspect saved Renode log')
    (out/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n')
    print(json.dumps({'passed':rows[0]['passed'],'count':rows[0]['count']}))

if __name__=='__main__':main()
