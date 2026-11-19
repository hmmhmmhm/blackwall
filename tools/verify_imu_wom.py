"""Check ordered threshold storage and source-bounded WOM control RMW."""
import verify_imu_b2s_parameters as b2s
harness=b2s.harness
EXTRA='''
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuWomConfiguration
wom=BlackwallImuWomConfiguration('a5b6c7c3')
check('wom-no-skipped-threshold',not wom.TryWriteThreshold(0xa27f,2) and wom.ThresholdWrites==0)
check('wom-no-early-control',not wom.TryWriteControl(0xc9))
for k in range(3):check('wom-threshold-byte',wom.TryWriteThreshold(0xa27e+k,2))
check('wom-three-only',not wom.TryWriteThreshold(0xa281,2) and wom.ThresholdWrites==3)
check('wom-control-read',wom.ReadControl()==0xc3)
check('wom-upper-preserved',not wom.TryWriteControl(0x49) and wom.Control==0xc3)
check('wom-cfg-bit-required',not wom.TryWriteControl(0xc1))
check('wom-config',wom.TryWriteControl(0xc9) and wom.ControlWrites==1)
check('wom-read-lease',not wom.TryWriteControl(0xd9))
check('wom-enable-bit-only',wom.ReadControl()==0xc9 and not wom.TryWriteControl(0xdb) and wom.TryWriteControl(0xd9))
check('wom-final',wom.ValuesHex=='020202d9' and wom.ControlWrites==2 and wom.ControlReads==2)
check('wom-no-extra-phase',wom.ReadControl()==0xd9 and not wom.TryWriteControl(0xd9))
wom.Reset();check('wom-reset',wom.ValuesHex=='a5b6c7c3' and wom.ThresholdWrites==wom.ControlWrites==wom.ControlReads==0)
for previous in [0,0xff,0xa5,0x5a]:
    for mode in [0,1]:
        for duration in range(4):
            q=BlackwallImuWomConfiguration('000000'+'%02x'%previous)
            for k in range(3):q.TryWriteThreshold(0xa27e+k,2)
            q.ReadControl();value=((previous|8)&~7)|(mode<<2)|duration
            check('wom-field-preserves',q.TryWriteControl(value) and q.ReadControl()==value and q.TryWriteControl(value|0x10))
'''
harness.DRIVER=harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ",EXTRA+"Console.WriteLine('BLACKWALL_IMU_UNIT ")
if __name__=='__main__':harness.main()
