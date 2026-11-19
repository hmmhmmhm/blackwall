"""Test actual SRAM queue fetch, DMA consumption, completion ordering and noncompletion."""
import verify_mspi0_tx as tx

tx.harness.DRIVER = '''import clr,json
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
def setup(complete=True):
    p=BlackwallPeripheralPower(0x4000,1,0);k=BlackwallMspi1ClockStorage('source-reset-storage',True);i=BlackwallMspi1Interrupts('source-reset',True)
    q=BlackwallMspi0Tx(m,'tx-capture',p,k,i)
    c=BlackwallMspi0RetentionConfig(m,p,i,0x4e92dc,q,True,complete)
    check('power-'+str(complete),p.TryWrite(0x4000,True) and p.ReadStatus()==0x4000 and k.TryWrite(0xa4215))
    return p,k,i,q,c
def write(c,o,v):return c.TryWrite(0x40060000+o,v,True)
def prepare(c,length,source=0x20081000,queue=0x20080000):
    pairs=[(0x400602b8,0x4080),(0x400602b8,0x4000),(0x40060108,source),(0x4006010c,0),(0x40060110,length),(0x40060100,0x17),(0x40060100,0),(0x400602b4,0),(0x400602c1,1)]
    for n,(a,v) in enumerate(pairs):m.SystemBus.WriteDoubleWord(queue+8*n,a);m.SystemBus.WriteDoubleWord(queue+8*n+4,v)
    for o,v in [(0x84,0x2040141),(0x88,0),(4,0),(0x2a8,queue),(0x2c0,0),(0x2c4,1),(0x2b8,0x4000),(0x2b4,0x80),(0x200,0x1a80)]:
        check('prepare-'+str(o)+'-'+str(length),write(c,o,v))
    return pairs
p,k,i,q,c=setup();pairs=prepare(c,65)
for n in range(65):m.SystemBus.WriteByte(0x20081000+n,n)
check('selected',c.QueueDma is not None and not c.QueueDma.Enabled)
check('start',write(c,0x2a0,3) and c.QueueDma.Enabled and c.QueueDma.Frames.Count==0)
check('no-poweroff-queue',not p.CanShutdown())
check('no-pio-during-queue',not write(c,0,0xc1))
check('no-active-rebase',not write(c,0x2a8,0x20080008))
advance(5)
check('not-instant',c.QueueDma.Completions==0 and c.CqValues[0x2c0]==0 and c.QueueDma.Frames.Count==0)
advance(100)
d=c.QueueDma
check('actual-fetch-nine',d.Descriptors==9 and d.Fault=='' and d.Paused)
check('one-dma',d.Starts==d.Completions==1 and d.BytesConsumed==65 and d.Frames.Count==1)
check('logical-payload',d.Frames[0].PayloadHex==''.join('%02x'%n for n in range(65)))
check('index-after-data',c.CqValues[0x2c0]==1 and c.CqValues[0x2a8]==0x20080048)
check('irq-status',i.Status==0x640 and i.IRQ.IsSet)
check('paused-status',tuple(c.TryRead(0x400602ac,True))==(True,9))
check('guest-ack-disable',write(c,0x208,0x640) and write(c,0x2a0,2) and not d.Enabled and not i.IRQ.IsSet)
check('retention-saved',tuple(c.TryReadMspi0RetentionFlags(0x4e92dc,0x40060000))==(True,0x80) and write(c,0x200,0))
check('off',p.TryWrite(0,True,p.CanShutdown()) and p.ReadStatus()==0 and d.Frames.Count==1 and d.Descriptors==9)
p2,k2,i2,q2,c2=setup(False);prepare(c2,513,0x20082000,0x20080100)
check('stuck-start',write(c2,0x2a0,3));advance(100)
check('stuck-at-dma',c2.QueueDma.DmaActive and c2.QueueDma.Descriptors==6 and c2.QueueDma.Starts==1 and c2.QueueDma.Completions==0 and c2.QueueDma.Frames.Count==0 and c2.CqValues[0x2c0]==0 and i2.Status==0)
check('stuck-cannot-disable',not write(c2,0x2a0,2) and not p2.CanShutdown())
check('clock-abort',k2.TryWrite(k2.Value&~1));advance(3)
check('abort-no-success',c2.QueueDma.Aborted==1 and c2.QueueDma.Completions==0 and c2.QueueDma.Fault!='' and i2.Status==0)
p3,k3,i3,q3,c3=setup();prepare(c3,65,0x40010000,0x20080200)
check('invalid-dma-start',write(c3,0x2a0,3));advance(100)
check('reject-nonram-source',c3.QueueDma.Fault!='' and c3.QueueDma.Starts==0 and c3.QueueDma.Completions==0 and c3.CqValues[0x2c0]==0 and i3.Status==0)
p4,k4,i4,q4,c4=setup();prepare(c4,1,0x20081000,0x20080300)
m.SystemBus.WriteDoubleWord(0x20080300,0x40010000)
check('invalid-destination-start',write(c4,0x2a0,3));advance(100)
check('reject-foreign-mmio',c4.QueueDma.Fault!='' and c4.QueueDma.Descriptors==0 and i4.Status==0)
p5,k5,i5,q5,c5=setup();prepare(c5,1,0x20081000,0x20080400)
check('mixed-d4-config',write(c5,4,5) and write(c5,0x90,0x45ec) and write(c5,0x94,0x630062))
check('mixed-d4-start',write(c5,0x2a0,3));advance(100)
check('mixed-d4-logical-byte',c5.QueueDma.Frames.Count==1 and c5.QueueDma.Frames[0].PayloadHex=='00' and c5.QueueDma.Fault=='')
Console.WriteLine('BLACKWALL_MSPI0_CONFIG_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False,scope='synthetic spin/SRAM queue and logical DMA; not original main or physical SPI timing')))
'''

if __name__ == '__main__':
    tx.harness.main()
