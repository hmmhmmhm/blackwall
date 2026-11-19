"""Check explicit diagnostic RX fixture, timed FIFO/data lifetime and noncompletion."""
import verify_mspi0_tx as tx

tx.harness.DRIVER = '''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMspi0Tx,BlackwallMspi1ClockStorage,BlackwallMspi1Interrupts,BlackwallPeripheralPower
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
m=monitor.Machine;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def advance(us):EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(us))
def create(payload='12345678',complete=True):
    p=BlackwallPeripheralPower(0x4000,1,0);k=BlackwallMspi1ClockStorage('source-reset-storage',True);i=BlackwallMspi1Interrupts('source-reset',True)
    q=BlackwallMspi0Tx(m,'tx-capture',p,k,i,True,payload,complete)
    check('power-'+str(complete),p.TryWrite(0x4000,True) and p.ReadStatus()==0x4000 and k.TryWrite(0xa4215))
    return p,k,i,q
p,k,i,q=create()
check('selected-fixture',q.DiagnosticRxHex=='12345678' and q.RxStarts==0)
check('empty-fifo-no-data',tuple(q.TryRead(0x1c))==(True,0) and tuple(q.TryRead(0x14))==(False,0))
before=(q.Starts,q.RxStarts,q.RxCompletions)
for value,opcode in [(0x40441,0x05),(0x30441,0x9f),(0x404c1,0x9f)]:
    check('unsupported-'+str(value)+'-'+str(opcode),not q.TryWrite(value,opcode,0x2040141,0,0,0) and before==(q.Starts,q.RxStarts,q.RxCompletions))
check('rx-start',q.TryWrite(0x40441,0x9f,0x2040141,0,0,0) and q.Busy and q.RxStarts==1 and q.Starts==0)
check('no-instant-data',tuple(q.TryRead(0x1c))==(True,0) and tuple(q.TryRead(0x14))==(False,0) and not q.CommandComplete)
check('no-tx-in-rx',not q.TryWriteTx(0xdeadbeef))
advance(2)
check('received',q.RxCompletions==1 and not q.Busy and q.CommandComplete and tuple(q.TryRead(0x1c))==(True,1) and i.Status==1)
check('unread-cannot-discard',not q.CanPowerDown and not q.TryWrite(0xc1,0x66,0x2040141,0,0,0))
check('little-endian-read',tuple(q.TryRead(0x14))==(True,0x78563412) and q.RxReads==1 and q.RxBytesDelivered==4)
check('consumed-once',tuple(q.TryRead(0x1c))==(True,0) and tuple(q.TryRead(0x14))==(False,0) and q.RxReads==1)
check('separate-history',q.ReceiveFrames.Count==1 and q.ReceiveFrames[0].PayloadHex=='12345678' and q.ReceiveFrames[0].Instruction==0x9f and q.Frames.Count==0 and q.Completions==0)
check('tx-after-drain',q.TryWrite(0xc1,0x66,0x2040141,0,0,0));advance(2)
check('tx-independent',q.Starts==q.Completions==1 and q.RxStarts==q.RxCompletions==1)
check('powerdown-clears-fifo',q.CanPowerDown);q.PowerDownController()
check('history-survives-domain-loss',q.Control==0 and q.ReceiveFrames.Count==1 and q.RxCompletions==1)
p2,k2,i2,q2=create(complete=False)
check('pending-start',q2.TryWrite(0x40441,0x9f,0x2040141,0,0,0));advance(5)
check('pending-data-not-completion',q2.Busy and not q2.CommandComplete and q2.RxCompletions==0 and q2.ReceiveFrames.Count==0 and i2.Status==0)
check('pending-data-delivered',tuple(q2.TryRead(0x14))==(True,0x78563412) and q2.RxBytesDelivered==4 and not q2.CanPowerDown)
check('clock-off',k2.TryWrite(k2.Value&~1))
check('pending-aborted',not q2.Busy and q2.RxAborted==1 and q2.Aborted==0 and q2.RxCompletions==0)
p3,k3,i3,q3=create('')
check('default-rx-refused',not q3.TryWrite(0x40441,0x9f,0x2040141,0,0,0) and q3.RxStarts==0)
for value in ['00','1234567890','zz345678']:
    try:BlackwallMspi0Tx(m,'tx-capture',p3,k3,i3,True,value)
    except Exception as error:check('bad-fixture-'+value,'diagnostic RX' in str(error))
    else:raise Exception('Malformed fixture accepted')
q.Reset()
check('global-reset-history',q.RxStarts==q.RxCompletions==q.RxReads==q.RxBytesDelivered==0 and q.ReceiveFrames.Count==0)
# Explicit JBD status replies are independent of the 4-byte identity fixture.
try:q4=BlackwallMspi0Tx(m,'tx-capture',p3,k3,i3,True,'12345678',True,'5a01')
except Exception as error:q4=None
check('explicit-jbd-status-profile-supported',q4 is not None)
check('status-profile-declared',q4.JbdStatusHex=='5a01')
check('default-status-still-refused',not q3.TryWrite(0x10441,5,0x2040141,0,0,0))
for control,opcode,configuration in [(0x40441,5,0x2040141),(0x10441,6,0x2040141),(0x104c1,5,0x2040141),(0x10441,5,0x2040140)]:
    before=(q4.RxStarts,q4.RxCompletions,q4.RxBytesDelivered)
    check('status-outside-contract-'+str(control)+'-'+str(opcode)+'-'+str(configuration),not q4.TryWrite(control,opcode,configuration,0,0,0) and before==(q4.RxStarts,q4.RxCompletions,q4.RxBytesDelivered))
for opcode,reply in [(5,0x5a),(0x35,1)]:
    check('status-start-'+str(opcode),q4.TryWrite(0x10441,opcode,0x2040141,0,0,0) and q4.Busy)
    check('status-not-instant-'+str(opcode),tuple(q4.TryRead(0x1c))==(True,0) and not q4.CommandComplete)
    check('status-overlap-'+str(opcode),not q4.TryWrite(0x10441,opcode,0x2040141,0,0,0) and not q4.TryWriteTx(0xdeadbeef))
    advance(2)
    check('status-completion-'+str(opcode),not q4.Busy and q4.CommandComplete and tuple(q4.TryRead(0x1c))==(True,1) and i3.Status==1)
    check('status-unread-preserved-'+str(opcode),not q4.CanPowerDown and not q4.TryWrite(0x10441,opcode,0x2040141,0,0,0))
    check('status-byte-'+str(opcode),tuple(q4.TryRead(0x14))==(True,reply) and tuple(q4.TryRead(0x14))==(False,0))
check('status-payload-lengths',q4.RxBytesDelivered==2 and q4.ReceiveFrames.Count==2 and q4.ReceiveFrames[0].PayloadHex=='5a' and q4.ReceiveFrames[1].PayloadHex=='01')
check('identity-retained-with-status',q4.TryWrite(0x40441,0x9f,0x2040141,0,0,0));advance(2)
check('identity-word-retained',tuple(q4.TryRead(0x14))==(True,0x78563412) and q4.RxBytesDelivered==6)
q4.PowerDownController();check('status-history-retained',q4.ReceiveFrames.Count==3 and q4.RxCompletions==3)
q5=BlackwallMspi0Tx(m,'tx-capture',p3,k3,i3,True,'',False,'9000')
check('status-incomplete-start',q5.TryWrite(0x10441,5,0x2040141,0,0,0));advance(3)
check('status-not-forced-complete',q5.Busy and not q5.CommandComplete and q5.RxCompletions==0 and q5.ReceiveFrames.Count==0)
check('status-incomplete-one-byte',tuple(q5.TryRead(0x14))==(True,0x90) and q5.RxBytesDelivered==1)
check('status-clock-off',k3.TryWrite(k3.Value&~1));check('status-aborted',not q5.Busy and q5.RxAborted==1 and q5.RxCompletions==0)
for value in ['0','123456','zz01']:
    try:BlackwallMspi0Tx(m,'tx-capture',p3,k3,i3,True,'',True,value)
    except Exception as error:check('bad-status-fixture-'+value,'JBD status' in str(error))
    else:raise Exception('Malformed status fixture accepted')
check('restore-clock-for-zero',k3.TryWrite(k3.Value|1))
q6=BlackwallMspi0Tx(m,'tx-capture',p3,k3,i3,True,'',True,'9000')
for opcode,value in [(5,0x90),(0x35,0)]:
    check('abnormal-byte-start-'+str(opcode),q6.TryWrite(0x10441,opcode,0x2040141,0,0,0));advance(2)
    check('abnormal-byte-not-masked-'+str(opcode),tuple(q6.TryRead(0x14))==(True,value))
check('zero-byte-counted',q6.RxBytesDelivered==2 and q6.ReceiveFrames[1].PayloadHex=='00')
q4.Reset();check('status-reset-clears-runtime',q4.RxStarts==q4.RxCompletions==q4.RxBytesDelivered==0 and q4.ReceiveFrames.Count==0 and q4.JbdStatusHex=='5a01')
Console.WriteLine('BLACKWALL_MSPI0_CONFIG_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False,scope='synthetic spin and declared RX bytes; no device identity or native main')))
'''

if __name__ == '__main__':
    tx.harness.main()
