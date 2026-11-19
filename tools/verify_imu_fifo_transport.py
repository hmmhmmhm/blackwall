"""Run the optional FIFO adapter through the real Renode IOM backend."""
import argparse
import json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_iom4_imu import DRIVER as LEGACY

ROOT=Path(__file__).resolve().parents[1]
EXTRA='''
import clr
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallImuFifoTransport').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuFifoTransport
q=t.RawFifo
w(0x118,1);w(0x11c,0x10);w(0x2c0,0x23040);w(0x2c4,0x69);w(0x200,1)
def frame(seed):return Array[Byte]([0x68]+[(seed+k)&255 for k in range(15)])
def select(address):
    w(0x208,0x7fff);w(0x10c,address);w(0x120,0x101)
def receive(n,cont=False):
    w(0x208,0x7fff);w(0x120,(n<<8)|2|(0x80 if cont else 0));result=[]
    for offset in range(0,n,4):
        value=r(0x108)
        result += [(value>>(8*k))&255 for k in range(min(4,n-offset))]
    return result
def fail(name,action):
    access=i.AccessCount;queued=q.PacketCount;consumed=q.PacketsConsumed
    try:action()
    except Exception as e:
        if 'Blackwall unsupported IOM' not in str(e):raise
    else:raise Exception(name+' accepted')
    check(name,i.AccessCount==access+1 and q.PacketCount==queued and q.PacketsConsumed==consumed)
check('fifo-opt-in',t.FifoEnabled and q.Enabled and q.PacketCount==0)
check('enqueue-two',q.TryEnqueueFrame(frame(1)) and q.TryEnqueueFrame(frame(20)))
startup_writes=p.WriteAttempts
fail('queued-register-flush-unsupported',lambda:t.Write(Array[Byte]([0x20,0x80])))
check('queued-flush-not-forwarded',p.WriteAttempts==startup_writes)
for unused in range(2):
    select(0x12);data=receive(2)
    check('actual-count-endianness',data==([0,2] if q.BigEndian else [2,0]))
    check('actual-count-nondestructive',q.PacketCount==2 and not q.ReadActive)
expected=list(frame(1))+list(frame(20));before=t.ChunksRead;completed=t.TransactionsCompleted
select(0x14);data=receive(32)
check('actual-fifo-bytes',data==expected)
check('actual-four-byte-chunks',t.ChunksRead-before==8)
check('actual-finish-consumes',q.PacketCount==0 and q.PacketsConsumed==2 and not q.ReadActive and t.TransactionsCompleted==completed+1)
check('identity-after-fifo',p.Pointer==0x72)
select(0x72);check('delegated-identity',receive(1)==[0x81])
for n in range(128):check('fill-2k',q.TryEnqueueFrame(frame(n)))
select(0x14);before=t.ChunksRead;data=receive(2048)
check('actual-2k-drain',data==sum([list(frame(n)) for n in range(128)],[]) and q.PacketCount==0 and t.ChunksRead-before==512)
check('partial-test-fill',all(q.TryEnqueueFrame(frame(n)) for n in range(20)))
select(0x14);w(0x208,0x7fff);w(0x120,(320<<8)|2)
check('iom-backpressure-keeps-lease',q.ReadActive and q.ReadRemaining>0 and q.PacketCount==20)
consumed=q.PacketsConsumed;i.ResetThroughInterface()
check('controller-reset-not-device-reset',q.ReadActive and q.PacketCount==20 and q.PacketsConsumed==consumed)
fail('partial-finish-rejected',lambda:t.FinishTransmission())
fail('partial-reselect-rejected',lambda:t.Write(Array[Byte]([0x12])))
t.Reset()
check('peer-reset-discards-lease',not q.ReadActive and q.PacketCount==0 and p.Pointer==-1 and t.Selections==0)
w(0x118,1);w(0x11c,0x10);w(0x2c0,0x23040);w(0x2c4,0x69);w(0x200,1)
check('invalid-length-input',q.TryEnqueueFrame(frame(50)))
select(0x14);fail('unaligned-read-rejected',lambda:receive(17))
check('unaligned-no-reservation',not q.ReadActive)
i.ResetThroughInterface();t.Reset();w(0x118,1);w(0x11c,0x10);w(0x2c0,0x23040);w(0x2c4,0x69);w(0x200,1)
q.TryEnqueueFrame(frame(50));select(0x14);fail('continued-read-unsupported',lambda:receive(16,True))
check('continued-no-reservation',not q.ReadActive)
i.ResetThroughInterface();t.Reset()
default=BlackwallImuFifoTransport(i,p)
default.Write(Array[Byte]([0x72]));check('default-pass-through',not default.FifoEnabled and list(default.Read(1))==[0x81])
try:default.Write(Array[Byte]([0x12]))
except Exception as e:check('default-fifo-unsupported','Blackwall unsupported IOM' in str(e))
else:raise Exception('Default FIFO enabled')
Console.WriteLine('BLACKWALL_FIFO_TRANSPORT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,big_endian=bool(q.BigEndian),original_firmware_executed=False,real_iom_backend=True,normal_gaf_supported=False)))
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--big-endian',action='store_true')
    args=parser.parse_args();out=args.output.resolve()
    if out.exists() or not out.is_relative_to(args.simulator.resolve()) or out.is_relative_to(ROOT):parser.error('New private simulator output required')
    out.mkdir(parents=True,mode=0o700)
    source=(args.simulator/'mspi0-rx-main-01/stock24/strict.cs').read_text()
    for name in ['renode-imu-identity.cs','renode-imu-raw-fifo.cs','renode-imu-fifo-threshold.cs','renode-imu-fifo-transport.cs']:source+='\n'+(ROOT/'tools'/name).read_text()
    (out/'strict.cs').write_text(source)
    (out/'board.repl').write_text('power: Miscellaneous.BlackwallPeripheralPower\n    mask: 32\n    profile: 1\n    offProfile: 0\niom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40054000\n    power: power\n    module: 4\nstartup: Miscellaneous.BlackwallImuIdentity @ none\n    owner: iom\n    profile: "icm45608-whoami-only"\nraw_fifo: Miscellaneous.BlackwallImuRawFifo @ none\n    enabled: true\n    bigEndian: '+str(args.big_endian).lower()+'\nfifo_transport: Miscellaneous.BlackwallImuFifoTransport @ iom 0x69\n    owner: iom\n    startupPeer: startup\n    rawFifo: raw_fifo\n')
    driver=LEGACY.replace("p=m['sysbus.iom.peer']","t=m['sysbus.iom.fifo_transport'];p=t.StartupPeer")
    driver=driver[:driver.index("Console.WriteLine('BLACKWALL_IMU_UNIT ")]+EXTRA
    (out/'test.py').write_text(driver)
    (out/'probe.resc').write_text('include @/work/strict.cs\nmach create "fifo-transport"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode',timeout=90)
    rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_FIFO_TRANSPORT ')]
    if len(rows)!=1:raise ValueError('Transport suite did not complete; inspect preserved log')
    (out/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps({'passed':rows[0]['passed'],'count':rows[0]['count'],'big_endian':args.big_endian}))

if __name__=='__main__':main()
