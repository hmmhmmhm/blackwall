"""Check bounded INT1 pin configuration latching and preservation of other bits."""
import verify_imu_tags as tags

EXTRA = '''
blocked('int1-disabled-by-default',lambda:write(tag,[0x18]),'peer-write')
pin=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,0xa5,0x5a,1000,True,0,4,0,0xa6)
check('int1-before-fsync-explicit-fixture',read(pin,0x18)==0xa6 and pin.FsyncReads==0 and pin.ResetRequests==0)
pin.Reset()
write(pin,[0x7f,2]);advance(1001);write(pin,[0x32,0x5a]);write(pin,[0x2d,0xa5]);read(pin,0x19)
write(pin,[0x7c,0xa2,0x67]);advance(5);read(pin,0x7e);read(pin,0x24)
blocked('int1-write-before-read',lambda:write(pin,[0x18,0xa1]),'peer-write')
write(pin,[0x18])
blocked('int1-wrong-read-length',lambda:pin.Read(2),'peer-read')
check('int1-read-full-byte',list(pin.Read(1))==[0xa6] and pin.Int1Reads==1)
blocked('int1-unselected-repeat',lambda:pin.Read(1),'peer-read')
blocked('int1-preserve-upper-bits',lambda:write(pin,[0x18,1]),'peer-write')
check('int1-rejected-write-state',pin.Int1Config2Value==0xa6 and pin.Int1Writes==0)
write(pin,[0x18,0xa1])
check('int1-latched',pin.Int1Config2Value==0xa1 and pin.Int1Writes==1 and read(pin,0x18)==0xa1)
for value in range(8):write(pin,[0x18,0xa0|value])
check('int1-only-three-config-bits',pin.Int1Config2Value==0xa7 and pin.Int1Writes==9)
blocked('int2-not-in-profile',lambda:write(pin,[0x58]),'peer-write')
pin.Reset()
check('int1-reset-restores-fixture',pin.Int1Config2Value==0xa6 and pin.Int1Reads==pin.Int1Writes==0)
check('int1-after-host-reset-explicit-fixture',read(pin,0x18)==0xa6 and pin.FsyncReads==0)
write(pin,[0x7f,2])
blocked('int1-during-soft-reset-unknown',lambda:read(pin,0x18),'peer-write')
advance(1001)
for initial in range(256):
    early=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',0,m,0xa5,0x5a,1000,True,0,4,0,initial)
    blocked('int1-independent-write-before-read',lambda:write(early,[0x18,initial]),'peer-write')
    check('int1-independent-byte',read(early,0x18)==initial and early.FsyncReads==early.ResetRequests==0)
    changed=(initial&0xf8)|((initial+1)&7)
    write(early,[0x18,changed])
    check('int1-independent-rmw',read(early,0x18)==changed and early.Int1Writes==1)
    early.Reset()
    check('int1-independent-reset-fixture',read(early,0x18)==initial)

'''
tags.ireg.reset.harness.DRIVER = tags.ireg.reset.harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ", EXTRA + "Console.WriteLine('BLACKWALL_IMU_UNIT ")

if __name__ == '__main__':
    tags.ireg.reset.harness.main()
