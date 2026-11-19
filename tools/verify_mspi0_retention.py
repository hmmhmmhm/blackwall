"""Check bounded MSPI0 retention flags and disabled-controller power lifecycle."""
import verify_mspi0_config as harness

harness.DRIVER = '''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMspi1ConfigStorage,BlackwallMspi0RetentionConfig,BlackwallMspi1Interrupts,BlackwallPeripheralPower
m=monitor.Machine;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
p=BlackwallPeripheralPower(0x4000,1,0);irq=BlackwallMspi1Interrupts('source-reset')
c=BlackwallMspi0RetentionConfig(m,p,irq,0x4e92dc)
check('matching-owner',c.RetentionPower==p and c.Mspi0RetentionReadPc==0x4e92dc)
check('power-start',p.TryWrite(0x4000,True) and p.ReadStatus()==0x4000)
for o,v in [(0x2a0,2),(0x2b4,0x400080),(0x200,0x1a80)]:check('setup-'+str(o),c.TryWrite(0x40060000+o,v,True))
check('off-needs-retention-read',not p.CanShutdown())
for pc,base in [(0x4e92de,0x40060000),(0x4e92dc,0x40061000)]:
    before=(c.CqReads,c.CqFlagReads,c.LastCqFlags)
    check('wrong-reader-'+str(pc)+'-'+str(base),tuple(c.TryReadMspi0RetentionFlags(pc,base))==(False,0) and before==(c.CqReads,c.CqFlagReads,c.LastCqFlags))
check('host-read-is-not-guest',tuple(c.TryRead(0x400602b0,True))==(False,0))
check('exact-reader',tuple(c.TryReadMspi0RetentionFlags(0x4e92dc,0x40060000))==(True,0x80) and c.CqFlagReads==1)
check('off-needs-irq-disabled',not p.CanShutdown())
check('irq-disable',c.TryWrite(0x40060200,0,True) and p.CanShutdown())
check('off-request',p.TryWrite(0,True,p.CanShutdown()) and p.Phase=='off-requested' and c.ControllerPowerDowns==0)
check('off-response-reset',p.ReadStatus()==0 and p.Phase=='powered-off' and p.PowerCycles==1 and c.ControllerPowerDowns==1 and c.CqValues[0x2a0]==c.CqValues[0x2b0]==0 and irq.Status==irq.Enable==0)
check('off-domain-read',tuple(c.TryRead(0x400602a0,False))==(False,0))
check('new-cycle-needs-read',not p.CanShutdown())
check('wake-request',p.TryWrite(0x4000,True) and p.ReadStatus()==0x4000)
for o,v in [(0x2a0,3),(0x100,1),(0,1)]:check('engine-refused-'+str(o),not c.TryWrite(0x40060000+o,v,True))
check('no-general-status',tuple(c.TryRead(0x400602ac,True))==(False,0))
for kwargs in [dict(mspi0RetentionReadPc=0x4e92dc),dict(mspi0RetentionPower=p),dict(mspi0RetentionReadPc=0x4e92dd,mspi0RetentionPower=p)]:
    try:BlackwallMspi1ConfigStorage('source-reset-config',baseAddress=0x40060000,commandQueueInit=True,interrupts=irq,mspi0Initialization=True,machine=m,**kwargs)
    except Exception as error:check('invalid-dependencies-'+str(kwargs),'MSPI0 retention requires' in str(error))
    else:raise Exception('Invalid retention accepted')
Console.WriteLine('BLACKWALL_MSPI0_CONFIG_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False)))
'''

if __name__ == '__main__':
    harness.main()
