"""Check source-bounded pad setup and interrupt enable packing."""
import verify_imu_power as power

EXTRA='''
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuAuxiliarySetup
a=BlackwallImuAuxiliarySetup('a5b6d7')
check('aux-initial',a.PadValue==0xa5 and a.Interrupt0==0xb6 and a.Interrupt1==0xd7)
check('aux-pad-read-lease',not a.TryWritePad(0xb5) and a.PadWrites==0)
check('aux-pad-mask',a.ReadPad()==0xa5 and not a.TryWritePad(0xb4) and a.PadValue==0xa5)
check('aux-pad-write',a.TryWritePad(0xb5) and a.PadValue==0xb5 and a.PadWrites==1)
check('aux-int-read-lease',not a.TryWriteInterrupt(0xb6,0x77))
check('aux-int-pair',list(a.ReadInterrupt())==[0xb6,0xd7])
check('aux-int-other-bits-rejected',not a.TryWriteInterrupt(0xb7,0x77) and not a.TryWriteInterrupt(0xb6,0x76))
check('aux-int-reserved-must-clear',not a.TryWriteInterrupt(0xb6,0xf7))
check('aux-int-enable-and-clear-reserved',a.TryWriteInterrupt(0xb6,0x77) and a.Interrupt1==0x77 and a.InterruptWrites==1)
check('aux-int-lease-consumed',not a.TryWriteInterrupt(0xb6,0x57))
check('aux-int-disable',list(a.ReadInterrupt())==[0xb6,0x77] and a.TryWriteInterrupt(0xb6,0x57))
a.Reset();check('aux-reset',a.PadValue==0xa5 and a.Interrupt0==0xb6 and a.Interrupt1==0xd7 and a.PadWrites==a.InterruptWrites==a.PadReads==a.InterruptReads==0)
parent=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,0xa5,0x5a,1000,True,0,4,0,0xa6,'ffff',100,True,'af2500000000',100,True,'a5b6d7')
write(parent,[0x7f,2]);advance(1001);write(parent,[0x32,0x5a]);write(parent,[0x2d,0xa5]);read(parent,0x19)
write(parent,[0x7c,0xa2,0x67]);advance(5);read(parent,0x7e);read(parent,0x24);read(parent,0x18);write(parent,[0x18,0xa1])
read(parent,0x2a);write(parent,[0x2a,0xbf]);advance(101)
read(parent,0x10);write(parent,[0x10,0xac]);read(parent,0x10);write(parent,[0x10,0xa0]);read(parent,0x20);write(parent,[0x20,0xa5]);advance(101)
blocked('aux-before-status-snapshots',lambda:write(parent,[0x30]),'peer-write')
write(parent,[0x19]);parent.Read(2);write(parent,[0x3b]);parent.Read(2)
check('parent-aux-pad',read(parent,0x30)==0xa5)
write(parent,[0x30,0xb5]);check('parent-aux-pad-write',parent.Auxiliary.PadValue==0xb5)
write(parent,[0x16]);check('parent-aux-interrupt',list(parent.Read(2))==[0xb6,0xd7])
write(parent,[0x16,0xb6,0x77]);check('parent-aux-interrupt-write',parent.Auxiliary.Interrupt1==0x77)
blocked('aux-master-configuration-unsupported',lambda:write(parent,[0x7c,0xa2,0x0f]),'peer-write')
'''
harness=power.edmp.configuration.tags.ireg.reset.harness
harness.DRIVER=harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ",EXTRA+"Console.WriteLine('BLACKWALL_IMU_UNIT ")

if __name__=='__main__':harness.main()
