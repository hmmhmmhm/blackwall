"""Exercise disabled MSPI0 queue/IRQ state and refusal of engine/status synthesis."""
import verify_mspi0_config as harness

harness.DRIVER = '''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMspi1ConfigStorage,BlackwallMspi1Interrupts
checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
irq=BlackwallMspi1Interrupts('source-reset')
c=BlackwallMspi1ConfigStorage('source-reset-config',baseAddress=0x40060000,commandQueueInit=True,interrupts=irq,mspi0Initialization=True)
old=monitor.Machine['sysbus.guard'].Mspi1Config
before_old=(old.Reads,old.Writes,list(old.Values),list(old.CqValues))
def read(o,ready=True):return tuple(c.TryRead(0x40060000+o,ready))
for offset,value in [(0x2c0,0),(0x2c4,0),(0x2b8,0x4000),(0x2a8,0x2035c460),(0x2a0,2),(0x2b4,0x400080)]:
    check('original-write-'+str(offset),c.TryWrite(0x40060000+offset,value,True))
check('queue-disabled',read(0x2a0)==(True,2))
check('software-flags',c.CqValues[0x2b0]==0x80)
check('pause',read(0x2b8)==(True,0x4000))
for offset in [0x2b0,0x2ac,0x18,0,0x10]:check('unknown-read-'+str(offset),read(offset)==(False,0))
for offset,value in [(0x2a0,3),(0x2a0,1),(0x2a8,3),(0x2c0,256),(0x2b0,0),(0x2ac,1),(0x100,1),(0,1)]:
    before=(c.Writes,c.CqWrites,list(c.Values),list(c.CqValues),irq.Status,irq.Enable)
    check('unsupported-no-change-'+str(offset)+'-'+str(value),not c.TryWrite(0x40060000+offset,value,True) and before==(c.Writes,c.CqWrites,list(c.Values),list(c.CqValues),irq.Status,irq.Enable))
check('off-domain-read',read(0x2a0,False)==(False,0))
check('off-domain-write',not c.TryWrite(0x400602c0,1,False) and read(0x2c0)==(True,0))
check('other-instance-refused',not c.TryWrite(0x400612a0,2,True))
check('irq-enable',c.TryWrite(0x40060200,0x1a80,True) and irq.Enable==0x1a80 and not irq.IRQ.IsSet)
irq.SetPending(0x80)
check('synthetic-event-asserts',irq.IRQ.IsSet)
check('irq-clear',c.TryWrite(0x40060208,0x1a80,True) and irq.Status==0 and not irq.IRQ.IsSet)
check('mspi1-independent',before_old==(old.Reads,old.Writes,list(old.Values),list(old.CqValues)))
for kwargs in [dict(baseAddress=0x40061000,commandQueueInit=True,interrupts=irq),dict(baseAddress=0x40060000,interrupts=irq),dict(baseAddress=0x40060000,commandQueueInit=True)]:
    try:BlackwallMspi1ConfigStorage('source-reset-config',mspi0Initialization=True,**kwargs)
    except Exception as error:check('missing-dependency-'+str(kwargs),'MSPI0 initialization requires' in str(error))
    else:raise Exception('Invalid initialization accepted')
c.Reset()
check('reset-clears',c.CqReads==c.CqWrites==0 and c.CqValues[0x2a0]==c.CqValues[0x2b0]==0 and irq.Enable==irq.Status==0 and not irq.IRQ.IsSet)
Console.WriteLine('BLACKWALL_MSPI0_CONFIG_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False)))
'''

if __name__ == '__main__':
    harness.main()
