"""Check explicitly selected SW_PLL1_TRIM bytes; unknown is never a zero default."""
import verify_imu_gaf_storage as storage
harness = storage.harness
EXTRA = '''
for value in [-2,256]:
    try:BlackwallImuGafParameters(own,ps,fixture,True,value);check('clock-invalid-byte',False)
    except System.ArgumentException:check('clock-invalid-byte',True)
try:BlackwallImuGafParameters(own,ps,fixture,False,0);check('clock-requires-config',False)
except System.ArgumentException:check('clock-requires-config',True)
check('clock-default-unknown',r.ClockVariationByte==-1 and not r.BeginClockRead() and r.ClockReads==0)
for value in range(256):
    c=BlackwallImuGafParameters(own,ps,fixture,True,value)
    check('clock-before-getter',not c.BeginClockRead() and c.ClockSelections==0)
    for address,length in fields:
        if not c.BeginRead(address):raise Exception('getter prerequisite failed')
        for _ in range(length):c.ReadNext()
    check('clock-selected',c.BeginClockRead() and c.ReadRemaining==1 and c.ClockSelections==1)
    check('clock-no-overlap',not c.BeginClockRead() and not c.TryWrite(0x774,Array[Byte]([1])))
    check('clock-byte-pass-through',c.ReadNext()==value and c.ReadRemaining==0 and c.ClockReads==1 and c.ReadBytes==153 and c.Complete)
    try:c.ReadNext();check('clock-no-overread',False)
    except System.InvalidOperationException:check('clock-no-overread',True)
    check('clock-reread',c.BeginClockRead() and c.ReadNext()==value and c.ClockReads==2)
    c.Reset();check('clock-reset',c.ClockReads==c.ClockSelections==c.ReadRemaining==0 and not c.BeginClockRead())
'''
harness.DRIVER = harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ", EXTRA + "Console.WriteLine('BLACKWALL_IMU_UNIT ")
if __name__ == '__main__':
    harness.main()
