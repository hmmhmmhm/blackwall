"""Check declared IMU reset lifecycle against real Renode virtual time."""
import verify_iom4_imu as harness

EXTRA = '''
import clr
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallImuIdentity').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuIdentity
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
def advance(us):EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(us))
def write(q,data):q.Write(Array[Byte](data))
def read(q,reg):write(q,[reg]);return list(q.Read(1))[0]
q=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,0xa5,0x5a,1000,True)
check('explicit-initial-values',q.InterfaceValue==0xa5 and q.DriveValue==0x5a and not q.ResetPending and not q.ResetDone)
check('save-interface-and-drive',read(q,0x2d)==0xa5 and read(q,0x32)==0x5a)
blocked('reset-status-not-assumed-at-powerup',lambda:write(q,[0x19]),'peer-write')
write(q,[0x7f,2])
check('reset-start',q.ResetPending and not q.ResetElapsed and not q.ResetDone and q.ResetRequests==1 and q.ResetCompletions==0 and q.InterfaceValue==q.DriveValue==-1)
check('pending-status',read(q,0x19)==0 and q.StatusReads==1)
blocked('pending-register-not-fabricated',lambda:write(q,[0x2d]),'peer-write')
blocked('premature-restore',lambda:write(q,[0x32,0x5a]),'peer-write')
blocked('overlapping-reset',lambda:write(q,[0x7f,2]),'peer-write')
advance(999)
check('not-early',q.ResetPending and not q.ResetElapsed and not q.ResetDone and q.ResetCompletions==0)
advance(2)
check('timed-completion',not q.ResetPending and q.ResetElapsed and q.ResetDone and q.ResetCompletions==1)
blocked('interface-before-drive',lambda:write(q,[0x2d,0xa5]),'peer-write')
blocked('wrong-restore-value',lambda:write(q,[0x32,0]),'peer-write')
write(q,[0x32,0x5a]);write(q,[0x2d,0xa5])
check('restored-values',q.DriveValue==0x5a and q.InterfaceValue==0xa5 and q.DriveRestores==q.InterfaceRestores==1)
check('restored-readback',read(q,0x32)==0x5a and read(q,0x2d)==0xa5)
check('done-read-clear',read(q,0x19)==0x80 and not q.ResetDone and read(q,0x19)==0 and q.StatusReads==3)
blocked('unknown-configuration',lambda:write(q,[0x23,1]),'peer-write')
q.Reset();write(q,[0x7f,2]);advance(500);q.Reset();advance(1500)
check('global-reset-cancels-timer',q.ResetRequests==q.ResetCompletions==0 and not q.ResetDone and not q.ResetPending and q.InterfaceValue==0xa5)
write(q,[0x7f,2]);i.ResetThroughInterface();advance(1001)
check('controller-reset-independent',q.ResetRequests==q.ResetCompletions==1 and q.ResetDone)
q.Reset()
stuck=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,0x12,0x34,1000,False)
write(stuck,[0x7f,2]);advance(1001)
check('elapsed-without-done',stuck.ResetElapsed and not stuck.ResetPending and not stuck.ResetDone and stuck.ResetCompletions==0)
write(stuck,[0x32,0x34]);write(stuck,[0x2d,0x12])
check('missing-done-does-not-prevent-restore-fixture',stuck.DriveRestores==stuck.InterfaceRestores==1 and read(stuck,0x19)==0)
for args in [(None,0,0), (m,-1,0), (m,0,256)]:
    try:BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,args[0],args[1],args[2],1000,True)
    except Exception as e:check('invalid-lifecycle-fixture-'+str(args[1:]),'reset fixture' in str(e))
    else:raise Exception('Invalid lifecycle fixture accepted')
'''
harness.DRIVER = harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ", EXTRA + "Console.WriteLine('BLACKWALL_IMU_UNIT ")

if __name__ == '__main__':
    harness.main()
