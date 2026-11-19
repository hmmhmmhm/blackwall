"""Check the bounded EDMP register bank and time-based idle handshake."""
import verify_imu_configuration as configuration

EXTRA = '''
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuEdmpQuiesce
e=BlackwallImuEdmpQuiesce(m,'ffff',100,True)
check('edmp-initial',e.Enable0==e.Enable1==255 and not e.Idle and not e.Pending)
check('edmp-read-before-write',not e.TryWriteRegister(0x2a,0xef) and e.Writes==0)
check('edmp-read-full-byte',e.ReadRegister(0x2a)==255)
check('edmp-no-setting-bits',not e.TryWriteRegister(0x2a,0xff^0x80))
check('edmp-gaf-clear',e.TryWriteRegister(0x2a,0xef) and e.Enable1==0xef and e.Writes==1)
check('edmp-read-lease',not e.TryWriteRegister(0x2a,0xcf))
check('edmp-feature-clear',e.ReadRegister(0x2a)==0xef and e.TryWriteRegister(0x2a,0xcf))
check('edmp-core-clear',e.ReadRegister(0x2a)==0xcf and e.TryWriteRegister(0x2a,0x8f) and e.Pending and not e.Idle and e.DisableRequests==1)
check('edmp-busy-byte',e.ReadIdleByte()==0 and e.IdleReads==1)
advance(99)
check('edmp-not-early',e.Pending and not e.Idle and e.IdleCompletions==0)
advance(2)
check('edmp-idle-byte',not e.Pending and e.Idle and e.ReadIdleByte()==2 and e.IdleCompletions==1)
check('edmp-no-extra-clears',e.ReadRegister(0x29)==255 and not e.TryWriteRegister(0x29,0xdf) and e.Enable0==255)
for mask in [4,8,1]:
    old=e.ReadRegister(0x29);check('edmp-source-mask-'+str(mask),e.TryWriteRegister(0x29,old&~mask))
check('edmp-en0-final',e.Enable0==0xf2)
old=e.ReadRegister(0x29);check('edmp-idempotent',e.TryWriteRegister(0x29,old))
check('edmp-forbidden-set',e.ReadRegister(0x2a)==0x8f and not e.TryWriteRegister(0x2a,0xcf) and e.Enable1==0x8f)
e.Reset();e.ReadRegister(0x2a);e.TryWriteRegister(0x2a,0xbf);advance(50);e.Reset();advance(100)
check('edmp-reset-cancels',e.DisableRequests==e.IdleCompletions==0 and e.Enable1==255 and not e.Idle and not e.Pending)
missing=BlackwallImuEdmpQuiesce(m,'007f',100,False)
missing.ReadRegister(0x2a);missing.TryWriteRegister(0x2a,0x3f);advance(101)
check('edmp-missing-idle',not missing.Idle and not missing.Pending and missing.IdleCompletions==0 and missing.ReadIdleByte()==0)
disabled=BlackwallImuEdmpQuiesce(m,'0000',100,True)
check('edmp-already-disabled',disabled.Idle and disabled.ReadIdleByte()==2)
check('edmp-idempotent-disable-no-new-timer',disabled.ReadRegister(0x2a)==0 and disabled.TryWriteRegister(0x2a,0) and disabled.DisableRequests==0 and disabled.Idle)
parent=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,0xa5,0x5a,1000,True,0,4,0,0xa6,'ffff',100,True)
write(parent,[0x7f,2]);advance(1001);write(parent,[0x32,0x5a]);write(parent,[0x2d,0xa5]);read(parent,0x19)
write(parent,[0x7c,0xa2,0x67]);advance(5);read(parent,0x7e);read(parent,0x24);read(parent,0x18);write(parent,[0x18,0xa1])
blocked('empty-edmp-write',lambda:write(parent,[]),'peer-write')
check('parent-edmp-byte',read(parent,0x2a)==255)
write(parent,[0x2a,0xef])
check('parent-edmp-latch',parent.Edmp.Enable1==0xef and parent.Edmp.Writes==1)
'''
configuration.tags.ireg.reset.harness.DRIVER = configuration.tags.ireg.reset.harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ", EXTRA + "Console.WriteLine('BLACKWALL_IMU_UNIT ")

if __name__ == '__main__':
    configuration.tags.ireg.reset.harness.main()
