"""Check bounded ODR/filter/FSR field storage with reserved-bit preservation."""
import verify_imu_i2cm as master
harness=master.harness
EXTRA='''
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuOdrConfiguration
b=BlackwallImuOdrConfiguration('a5b6c7c8e9faab9c')
check('odr-read-lease',not b.TryWrite(0x27,0xa2) and b.Writes==0)
check('odr-apex-read',b.Read(0x27)==0xa5)
check('odr-apex-preserves-upper',not b.TryWrite(0x27,0x22) and b.TryWrite(0x27,0xa2))
check('odr-accel-field',b.Read(0x1b)==0xb6 and b.TryWrite(0x1b,0xb9))
check('odr-fsr-separate-field',b.Read(0x1b)==0xb9 and not b.TryWrite(0x1b,0xa8) and b.TryWrite(0x1b,0xa9))
check('odr-accel-reserved',b.Read(0x1b)==0xa9 and not b.TryWrite(0x1b,0x29))
check('odr-gyro-field',b.Read(0x1c)==0xc7 and b.TryWrite(0x1c,0xc9))
check('odr-gyro-fsr-field',b.Read(0x1c)==0xc9 and b.TryWrite(0x1c,0x39))
check('odr-lp-clock-bit',b.Read(0xa258)==0xc8 and b.TryWrite(0xa258,0xd8))
for reg,value in [(0xa581,0xe2),(0xa583,0xfb),(0xa4aa,0xa3),(0xa4ac,0x9e)]:
    b.Read(reg);check('odr-filter-'+str(reg),b.TryWrite(reg,value))
check('odr-no-unknown',not b.Contains(0xa2a7) and not b.TryWrite(0xa2a7,0))
b.Reset();check('odr-reset',b.ValuesHex=='a5b6c7c8e9faab9c' and b.Reads==b.Writes==0 and b.History=='')
'''
harness.DRIVER=harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ",EXTRA+"Console.WriteLine('BLACKWALL_IMU_UNIT ")
if __name__=='__main__':harness.main()
