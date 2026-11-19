"""Check explicit unknown-ROM time fixture, pass-through write and control bit preservation."""
import verify_imu_wom as wom
harness=wom.harness
EXTRA='''
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuPowerSave
own=ready_service()
check('ps-restore',own.TryWrite(0x29,Array[Byte]([0xf2])) and own.TryWrite(0x2a,Array[Byte]([0x8f])))
ps=BlackwallImuPowerSave(own,'78563412')
check('ps-no-unselected-write',not ps.TryWriteTime(0x40,0x78) and ps.ProfileApplications==0)
check('ps-invalid-read-no-seed',not ps.BeginRead(0x3f) and ps.ProfileApplications==0)
check('ps-explicit-profile',ps.BeginRead(0x40) and ps.ProfileApplications==1 and ps.ReadRemaining==4)
check('ps-time-read',[ps.ReadNext() for _ in range(4)]==[0x78,0x56,0x34,0x12] and ps.ReadBytes==4)
check('ps-getter-control',ps.ReadControl()==0x8f)
check('ps-no-early-control-write',not ps.TryWriteControl(0x8b))
check('ps-setter-control',ps.ReadControl()==0x8f)
check('ps-no-other-bits',not ps.TryWriteControl(0x0b) and not ps.TryWriteControl(0x8f))
check('ps-disable-bit2',ps.TryWriteControl(0x8b) and ps.ControlWrites==1)
check('ps-no-time-value-change',not ps.TryWriteTime(0x40,0) and ps.WriteBytes==0 and own.RamByte(0x40)==0x78)
check('ps-no-time-skip',not ps.TryWriteTime(0x41,0x56))
for k,v in enumerate([0x78,0x56,0x34,0x12]):check('ps-time-passthrough',ps.TryWriteTime(0x40+k,v))
check('ps-done',ps.Complete and ps.ValuesHex=='78563412' and ps.ControlReads==2 and ps.WriteBytes==4)
check('ps-neighbors',own.RamByte(0x3f)==0 and own.RamByte(0x44)==0)
check('ps-no-overrun',not ps.TryWriteTime(0x44,0) and not ps.BeginRead(0x40))
ps.Reset();check('ps-reset',not ps.Active and ps.ReadBytes==ps.WriteBytes==ps.ProfileApplications==0)
for fixture,expected in [('00000000',[0]*4),('ffffffff',[255]*4),('f0debc9a',[0xf0,0xde,0xbc,0x9a])]:
    alt=BlackwallImuPowerSave(own,fixture)
    check('ps-alternate-read',alt.BeginRead(0x40) and [alt.ReadNext() for _ in range(4)]==expected)
    alt.ReadControl();value=alt.ReadControl()
    check('ps-idempotent-disable',alt.TryWriteControl(value&~4))
    for k,v in enumerate(expected):check('ps-alternate-pass',alt.TryWriteTime(0x40+k,v))
    check('ps-alternate-complete',alt.Complete and alt.ValuesHex==fixture)
'''
harness.DRIVER=harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ",EXTRA+"Console.WriteLine('BLACKWALL_IMU_UNIT ")
if __name__=='__main__':harness.main()
