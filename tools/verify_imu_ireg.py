"""Check one explicit SREG_CTRL indirect-read fixture with virtual access time."""
import verify_imu_reset as reset

EXTRA = '''
blocked('ireg-disabled-in-reset-profile',lambda:write(q,[0x7c,0xa2,0x67]),'peer-write')
ir=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,0xa5,0x5a,1000,True,2,4)
blocked('ireg-before-reset',lambda:write(ir,[0x7c,0xa2,0x67]),'peer-write')
write(ir,[0x7f,2]);advance(1001);write(ir,[0x32,0x5a]);write(ir,[0x2d,0xa5]);read(ir,0x19)
for data in [[0x7c,0xa2,0x68],[0x7c,0xa2],[0x7c,0xa2,0x67,2],[0x7e,2]]:
    blocked('unknown-indirect-'+str(data),lambda data=data:write(ir,data),'peer-write')
blocked('no-invented-ready-register',lambda:write(ir,[0x7f]),'peer-write')
blocked('no-data-before-address',lambda:read(ir,0x7e),'peer-write')
write(ir,[0x7c,0xa2,0x67])
check('address-pending',ir.IregAddress==0xa267 and ir.IregPending and not ir.IregReady and ir.IregStarts==1)
blocked('overlapping-address',lambda:write(ir,[0x7c,0xa2,0x67]),'peer-write')
write(ir,[0x7e])
blocked('data-not-ready',lambda:ir.Read(1),'peer-read')
advance(3)
check('ireg-not-early',ir.IregPending and not ir.IregReady and ir.IregCompletions==0)
advance(2)
check('ireg-ready',not ir.IregPending and ir.IregReady and ir.IregCompletions==1)
blocked('ireg-wrong-length',lambda:ir.Read(2),'peer-read')
check('sreg-data',list(ir.Read(1))==[2] and ir.IregReads==1 and not ir.IregReady)
blocked('ireg-no-unselected-repeat',lambda:ir.Read(1),'peer-read')
blocked('ireg-no-assumed-next-byte',lambda:read(ir,0x7e),'peer-write')
write(ir,[0x7c,0xa2,0x67]);i.ResetThroughInterface();advance(5)
check('ireg-controller-reset-independent',ir.IregReady and ir.IregCompletions==2 and read(ir,0x7e)==2)
write(ir,[0x7c,0xa2,0x67]);advance(1);ir.Reset();advance(8)
check('ireg-reset-cancels',ir.IregStarts==ir.IregCompletions==ir.IregReads==0 and not ir.IregPending and not ir.IregReady and ir.IregAddress==-1)
'''

EXTRA += """
import System
initial=BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,0xa5,0x5a,1000,True,2,4,initialIregReady=True)
check('initial-ireg-declared',initial.InitialIregReady and initial.ResetRequests==0)
write(initial,[0x7c,0xa2,0x67]);advance(3)
check('initial-ireg-not-early',initial.IregPending and not initial.IregReady)
advance(2)
check('initial-ireg-byte',read(initial,0x7e)==2 and initial.ResetRequests==0 and initial.DriveRestores==initial.InterfaceRestores==0)
write(initial,[0x7f,2])
blocked('initial-ireg-no-soft-reset-bypass',lambda:write(initial,[0x7c,0xa2,0x67]),'peer-write')
advance(1001)
blocked('initial-ireg-no-unrestored-interface',lambda:write(initial,[0x7c,0xa2,0x67]),'peer-write')
write(initial,[0x32,0x5a])
blocked('initial-ireg-no-partial-restore',lambda:write(initial,[0x7c,0xa2,0x67]),'peer-write')
write(initial,[0x2d,0xa5]);write(initial,[0x7c,0xa2,0x67]);advance(5)
check('initial-ireg-post-reset',read(initial,0x7e)==2 and initial.ResetRequests==1)
initial.Reset();write(initial,[0x7c,0xa2,0x67]);advance(5)
check('initial-ireg-host-reset-restores-profile',read(initial,0x7e)==2 and initial.ResetRequests==0)
try:BlackwallImuIdentity(i,'icm45608-reset-lifecycle',129,m,0xa5,0x5a,initialIregReady=True);check('initial-ireg-requires-fixture',False)
except System.ArgumentException:check('initial-ireg-requires-fixture',True)
"""

reset.harness.DRIVER = reset.harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ", EXTRA + "Console.WriteLine('BLACKWALL_IMU_UNIT ")

if __name__ == '__main__':
    reset.harness.main()
