"""Test timed TX capture, logical payload, backpressure, clock and power lifetime."""
import struct
import verify_mspi0_config as harness

harness.DRIVER = '''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMspi0Tx,BlackwallMspi0RetentionConfig,BlackwallMspi1ClockStorage,BlackwallMspi1Interrupts,BlackwallPeripheralPower
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
m=monitor.Machine;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def advance(us):EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(us))
p=BlackwallPeripheralPower(0x4000,1,0);k=BlackwallMspi1ClockStorage('source-reset-storage',True);i=BlackwallMspi1Interrupts('source-reset',True)
q=BlackwallMspi0Tx(m,'tx-capture',p,k,i)
c=BlackwallMspi0RetentionConfig(m,p,i,0x4e92dc,q)
check('unpowered-start-refused',not q.TryWrite(0xc1,0x66,0x2040141,0,0,0) and q.Starts==0)
check('power-clock',p.TryWrite(0x4000,True) and p.ReadStatus()==0x4000 and k.TryWrite(0xa4215))
check('retention-read',c.TryWrite(0x400602b4,0x400080,True) and tuple(c.TryReadMspi0RetentionFlags(0x4e92dc,0x40060000))==(True,0x80))
check('start',q.TryWrite(0xc1,0x66,0x2040141,0,0,0) and q.Busy and not q.CommandComplete)
check('no-off-during-command',not p.CanShutdown())
before=(q.Starts,q.FifoWrites,q.Completions)
check('overlap-refused',not q.TryWrite(0xc1,0x99,0x2040141,0,0,0) and before==(q.Starts,q.FifoWrites,q.Completions))
check('other-clock-change',k.TryWrite(k.Value^0x20))
advance(2)
check('instruction-completed',not q.Busy and q.Completions==1 and q.Frames.Count==1 and q.Frames[0].Instruction==0x66 and q.Frames[0].PayloadHex=='' and q.Aborted==0 and i.Status==1)
for value,instruction in [(0x41,0x9f),(0xc0,0x66),(0xc1,0x100),(0x100c1|0x200,1)]:
    before=(q.Starts,q.FifoWrites,q.Completions)
    check('unsupported-'+str(value)+'-'+str(instruction),not q.TryWrite(value,instruction,0x2040141,0,0,0) and before==(q.Starts,q.FifoWrites,q.Completions))
check('data-start',q.TryWrite(0x100c1,1,0x2040141,0,0,0))
check('one-byte-word',q.TryWriteTx(0xa5a5a510) and q.TxEntries==1)
check('excess-word-refused',not q.TryWriteTx(0))
advance(2)
check('padding-not-payload',q.Frames.Count==2 and q.Frames[1].PayloadHex=='10' and q.BytesShifted==1)
check('long-start',q.TryWrite(0x4100c1,2,0x2040141,0,0,0))
for n in range(16):check('fifo-word-'+str(n),q.TryWriteTx(0x04030201))
check('fifo-full-refused',q.TxEntries==16 and not q.TryWriteTx(0xee))
advance(20)
check('no-early-complete',q.Busy and q.Completions==2 and q.TxEntries==0)
check('last-byte',q.TryWriteTx(0xa5a5a5ee))
advance(2)
check('exact-long-payload',q.Frames.Count==3 and q.Frames[2].PayloadHex=='01020304'*16+'ee' and q.BytesShifted==66)
check('clock-abort-start',q.TryWrite(0xc1,0x99,0x2040141,0,0,0))
check('clock-gate-off',k.TryWrite(k.Value&~1))
advance(2)
check('clock-abort-no-completion',not q.Busy and q.Aborted==1 and q.Completions==3 and q.Frames.Count==3)
check('power-off-ready',p.CanShutdown() and p.TryWrite(0,True,p.CanShutdown()) and p.ReadStatus()==0 and q.Control==0 and q.Frames.Count==3)
check('no-unpowered-data',not q.TryWriteTx(0))
p2=BlackwallPeripheralPower(0x4000,1);i2=BlackwallMspi1Interrupts('source-reset',True);q2=BlackwallMspi0Tx(m,'tx-capture',p2,k,i2,False)
check('fault-power',p2.TryWrite(0x4000,True) and p2.ReadStatus()==0x4000 and k.TryWrite(k.Value|1))
check('stuck-start',q2.TryWrite(0xc1,0x66,0x2040141,0,0,0))
advance(5)
check('stuck-no-fake-completion',q2.Busy and q2.Completions==0 and q2.Frames.Count==0 and not q2.CanPowerDown)
Console.WriteLine('BLACKWALL_MSPI0_CONFIG_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False,scope='synthetic spin/timed transport; not real firmware or slave effects')))
'''

base_execute = harness.execute


def execute(command, output, name, **kwargs):
    (output / 'spin.bin').write_bytes(struct.pack('<II', 0x20001000, 0x10009) + bytes.fromhex('fee7'))
    p = output / 'probe.resc'
    text = p.read_text()
    anchor = 'include @/work/test.py\n'
    if text.count(anchor) != 1:
        raise ValueError('Different unit driver anchor')
    p.write_text(text.replace(anchor, 'sysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\n' + anchor))
    return base_execute(command, output, name, **kwargs)


harness.execute = execute

if __name__ == '__main__':
    harness.main()
