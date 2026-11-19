"""Check the explicit GAF field-read profile, not physical ROM defaults or fusion."""
import json
from pathlib import Path
import verify_imu_powersave as powersave
harness=powersave.harness
PROFILE=json.loads((Path(__file__).resolve().parents[1]/'docs/data/imu-gaf-default-profile.json').read_text())
FIELDS=[(x['address'],x['length']) for x in PROFILE['fields']]
FIXTURE=''.join(x['bytes_le'] for x in PROFILE['fields'])
EXTRA='''
import System
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuGafParameters
fields=__FIELDS__
fixture=__FIXTURE__
raw=[int(fixture[k:k+2],16) for k in range(0,len(fixture),2)]
for bad in ['',fixture[:-2],'g'*306]:
    try:BlackwallImuGafParameters(own,alt,bad);check('gaf-invalid-fixture',False)
    except System.ArgumentException:check('gaf-invalid-fixture',True)
q=BlackwallImuGafParameters(own,alt,fixture)
check('gaf-not-selected',q.ProfileApplications==0 and q.ReadBytes==0 and not q.Complete)
check('gaf-invalid-first-preserves',not q.BeginRead(fields[1][0]) and q.ProfileApplications==0)
time_before=[own.RamByte(0x40+k) for k in range(4)]
ram_before=[own.RamByte(k) for k in range(8192)]
allowed=set(address+k for address,length in fields for k in range(length))
offset=0
for index,(address,length) in enumerate(fields):
    check('gaf-field-order',q.BeginRead(address) and q.FieldsStarted==index+1 and q.ReadRemaining==length)
    check('gaf-no-overlap-read',not q.BeginRead(address) and q.FieldsStarted==index+1)
    actual=[q.ReadNext() for _ in range(length)]
    check('gaf-original-field-width',actual==raw[offset:offset+length] and q.ReadRemaining==0)
    check('gaf-stored-field',actual==[own.RamByte(address+k) for k in range(length)])
    offset+=length
check('gaf-complete',q.Complete and q.ReadBytes==153 and q.FieldsStarted==41 and q.ProfileApplications==1)
check('gaf-time-preserved',time_before==[own.RamByte(0x40+k) for k in range(4)])
check('gaf-all-other-ram-preserved',all(own.RamByte(k)==ram_before[k] for k in range(8192) if k not in allowed))
check('gaf-no-extra-read',not q.BeginRead(fields[0][0]) and q.ReadBytes==153)
try:q.ReadNext();check('gaf-no-overread',False)
except System.InvalidOperationException:check('gaf-no-overread',True)
q.Reset();check('gaf-reset',not q.Complete and q.ReadBytes==q.FieldsStarted==q.ProfileApplications==0)
for value in [0,0xff,0x5a]:
    a=BlackwallImuGafParameters(own,alt,'%02x'%value*153)
    for address,length in fields:
        check('gaf-alternate-select',a.BeginRead(address))
        check('gaf-alternate-value',[a.ReadNext() for _ in range(length)]==[value]*length)
    check('gaf-alternate-complete',a.Complete and a.ReadBytes==153)
alt.Reset()
check('gaf-prerequisite',not q.BeginRead(fields[0][0]) and q.ProfileApplications==0)
'''.replace('__FIELDS__',repr(FIELDS)).replace('__FIXTURE__',repr(FIXTURE))
harness.DRIVER=harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ",EXTRA+"Console.WriteLine('BLACKWALL_IMU_UNIT ")
if __name__=='__main__':harness.main()
