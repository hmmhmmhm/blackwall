"""Check power-field preservation, FIFO flush timing and explicit status pairs."""
import verify_imu_edmp as edmp

EXTRA = '''
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuPowerConfiguration
q=BlackwallImuPowerConfiguration(m,'af25a55a1234',100,True)
check('power-fixtures',q.PowerValue==0xaf and q.FifoValue==0x25 and not q.FlushDone)
check('power-read-lease',not q.TryWriteRegister(0x10,0xac) and q.PowerWrites==0)
check('power-accel-field',q.ReadRegister(0x10)==0xaf and q.TryWriteRegister(0x10,0xac) and q.PowerValue==0xac)
check('power-gyro-field',q.ReadRegister(0x10)==0xac and q.TryWriteRegister(0x10,0xa0) and q.PowerValue==0xa0)
check('power-upper-preserved',q.ReadRegister(0x10)==0xa0 and not q.TryWriteRegister(0x10,0x90) and q.PowerValue==0xa0)
check('power-both-fields-rejected',not q.TryWriteRegister(0x10,0xaf) and q.PowerWrites==2)
check('power-single-mode-enable',q.TryWriteRegister(0x10,0xa3) and q.PowerValue==0xa3)
check('fifo-command-lease',not q.TryWriteRegister(0x20,0xa5))
check('fifo-lower-preserved',q.ReadRegister(0x20)==0x25 and not q.TryWriteRegister(0x20,0xa4))
check('fifo-flush-request',q.TryWriteRegister(0x20,0xa5) and q.FlushPending and q.FlushRequests==1 and q.FifoValue==0xa5)
advance(99)
check('fifo-flush-not-early',q.ReadRegister(0x20)==0xa5 and not q.FlushDone)
advance(2)
check('fifo-flush-finished',not q.FlushPending and q.FlushDone and q.ReadRegister(0x20)==0x25 and q.FlushCompletions==1)
check('status-pair0',list(q.ReadStatusPair(0x19))==[0xa5,0x5a] and q.Status0Reads==1)
check('status-apex-pair',list(q.ReadStatusPair(0x3b))==[0x12,0x34] and q.StatusApexReads==1)
check('fifo-extra-command-rejected',not q.TryWriteRegister(0x20,0xa5) and q.FlushRequests==1)
q.Reset();q.ReadRegister(0x20);q.TryWriteRegister(0x20,0xa5);advance(50);q.Reset();advance(100)
check('fifo-reset-cancels',q.PowerValue==0xaf and q.FifoValue==0x25 and q.FlushRequests==q.FlushCompletions==0 and not q.FlushDone and not q.FlushPending)
missing=BlackwallImuPowerConfiguration(m,'0f2500000000',100,False)
missing.ReadRegister(0x20);missing.TryWriteRegister(0x20,0xa5);advance(101)
check('fifo-missing-completion',missing.FifoValue==0xa5 and not missing.FlushDone and not missing.FlushPending and missing.FlushCompletions==0)
parent=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,0xa5,0x5a,1000,True,0,4,0,0xa6,'ffff',100,True,'af2500000000',100,True)
write(parent,[0x7f,2]);advance(1001);write(parent,[0x32,0x5a]);write(parent,[0x2d,0xa5]);read(parent,0x19)
write(parent,[0x7c,0xa2,0x67]);advance(5);read(parent,0x7e);read(parent,0x24);read(parent,0x18);write(parent,[0x18,0xa1])
blocked('power-before-edmp-idle',lambda:write(parent,[0x10]),'peer-write')
read(parent,0x2a);write(parent,[0x2a,0xbf]);advance(101)
check('parent-power-read',read(parent,0x10)==0xaf)
write(parent,[0x10,0xac]);check('parent-power-write',parent.Configuration.PowerValue==0xac)
read(parent,0x20);write(parent,[0x20,0xa5]);advance(101)
write(parent,[0x19]);pair=parent.Read(2)
check('parent-status-pair',list(pair)==[0,0] and parent.Configuration.Status0Reads==1)
blocked('power-odr-unsupported',lambda:write(parent,[0x1b]),'peer-write')
'''
edmp.configuration.tags.ireg.reset.harness.DRIVER = edmp.configuration.tags.ireg.reset.harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ", EXTRA + "Console.WriteLine('BLACKWALL_IMU_UNIT ")

if __name__ == '__main__':
    edmp.configuration.tags.ireg.reset.harness.main()
