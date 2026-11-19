"""Check explicit FSYNC configuration query after bounded reset/indirect setup."""
import verify_imu_ireg as ireg

EXTRA = '''
blocked('fsync-disabled-by-default',lambda:write(ir,[0x24]),'peer-write')
tag=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,0xa5,0x5a,1000,True,0,4,0xe5)
blocked('fsync-before-reset',lambda:write(tag,[0x24]),'peer-write')
write(tag,[0x7f,2]);advance(1001);write(tag,[0x32,0x5a]);write(tag,[0x2d,0xa5]);read(tag,0x19)
blocked('fsync-before-indirect-read',lambda:write(tag,[0x24]),'peer-write')
write(tag,[0x7c,0xa2,0x67]);advance(5);read(tag,0x7e)
write(tag,[0x24])
blocked('fsync-wrong-length',lambda:tag.Read(2),'peer-read')
check('fsync-original-byte-not-premasked',list(tag.Read(1))==[0xe5] and tag.FsyncReads==1)
blocked('fsync-one-consumption',lambda:tag.Read(1),'peer-read')
blocked('fsync-no-configuration-write',lambda:write(tag,[0x24,0]),'peer-write')
check('fsync-reselect-stable',read(tag,0x24)==0xe5 and tag.FsyncReads==2)
tag.Reset()
check('fsync-global-reset',tag.FsyncReads==0 and tag.FsyncConfig==0xe5)
blocked('fsync-reset-requires-bootstrap',lambda:write(tag,[0x24]),'peer-write')
'''
ireg.reset.harness.DRIVER = ireg.reset.harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ", EXTRA + "Console.WriteLine('BLACKWALL_IMU_UNIT ")

if __name__ == '__main__':
    ireg.reset.harness.main()
