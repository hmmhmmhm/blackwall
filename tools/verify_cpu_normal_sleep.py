"""Exercise finite normal-sleep storage and exact-PC flush qualification."""
import verify_mspi0_config as harness

harness.DRIVER = '''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallCpuNormalSleep
m=monitor.Machine;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
c=BlackwallCpuNormalSleep(m,'normal-sleep-storage',0x44e16e)
def state():return (c.PowerControlReads,c.CpdReads,c.CpdWrites,c.FlushReads,c.CpdValue)
check('default-unselected',m['sysbus.guard'].CpuNormalSleep is None)
check('initial-cpd',tuple(c.TryRead(0xe001e300))==(True,0))
check('flush-needs-setup',tuple(c.TryReadFlush(0x44e16e,0x47ff0000))==(False,0))
check('normal-write-needs-control',not c.TryWrite(0xe001e300,0x11))
check('power-source-reset',tuple(c.TryRead(0x40021050))==(True,0))
for address,value in [(0x40021050,0),(0x47ff0000,0),(0xe001e300,0x21),(0xe001e300,0x22),(0xe001e300,0x311),(0xe001e300,1),(0xe001e304,0)]:
    before=state();check('unsupported-'+str(address)+'-'+str(value),not c.TryWrite(address,value) and before==state())
check('original-cpd-write',c.TryWrite(0xe001e300,0x11) and tuple(c.TryRead(0xe001e300))==(True,0x11))
for pc,base in [(0x44e170,0x47ff0000),(0x44e16e,0x47ff0004)]:
    before=state();check('wrong-flush-'+str(pc)+'-'+str(base),tuple(c.TryReadFlush(pc,base))==(False,0) and before==state())
check('host-flush-not-guest',tuple(c.TryRead(0x47ff0000))==(False,0))
check('exact-flush',tuple(c.TryReadFlush(0x44e16e,0x47ff0000))==(True,0) and c.FlushReads==1)
check('repeat-needs-next-cycle',tuple(c.TryReadFlush(0x44e16e,0x47ff0000))==(False,0))
check('next-cycle',tuple(c.TryRead(0x40021050))==(True,0) and c.TryWrite(0xe001e300,0x11) and tuple(c.TryReadFlush(0x44e16e,0x47ff0000))==(True,0))
c.Reset();check('reset',state()==(0,0,0,0,0))
for pc in [0,0x44e16f,0x800000]:
    try:BlackwallCpuNormalSleep(m,'normal-sleep-storage',pc)
    except Exception as error:check('invalid-pc-'+str(pc),'Explicit normal sleep' in str(error))
    else:raise Exception('Invalid PC accepted')
Console.WriteLine('BLACKWALL_MSPI0_CONFIG_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False)))
'''

if __name__ == '__main__':
    harness.main()
