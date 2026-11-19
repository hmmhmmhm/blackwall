"""Check model RAM marker stream, exact payloads, partial writes and reset."""
import verify_imu_edmp_service as service
harness=service.harness
EXTRA='''
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuPatchRam
def ready_service():
    bank=BlackwallImuEdmpQuiesce(m,'f28f',100,True)
    owner=BlackwallImuEdmpService(m,bank,'a5b6c7d8e9',0xa5,100,True)
    first_request(owner);advance(101)
    def setbyte(reg,v):check('ready-write',owner.TryWrite(reg,Array[Byte]([v])))
    setbyte(0x29,0xf2);setbyte(0x2a,0x8f)
    for reg in [0xa271,0xa272,0xa273]:setbyte(reg,0x3f)
    owner.Read(0xa272);setbyte(0xa272,0x1f)
    setbyte(0x29,0);setbyte(0x2a,0x42);owner.Read(0x73);setbyte(0x73,0xe9);advance(101)
    return owner
owner=ready_service()
dispatch=bytes(bytearray(range(25)));feature=bytes(bytearray(i%256 for i in range(375)))
dhex=''.join('%02x'%v for v in bytearray(dispatch));fhex=''.join('%02x'%v for v in bytearray(feature))
p=BlackwallImuPatchRam(owner,dhex,fhex,-1)
check('patch-no-write-before-read',not p.TryWrite(0x1580,0) and p.WrittenBytes==0)
check('patch-begin-marker',p.BeginRead(0x48) and p.ReadRemaining==4)
check('patch-no-restart-read',not p.BeginRead(0x48))
check('patch-marker-zero',[p.ReadNext() for _ in range(4)]==[0]*4 and p.ReadRemaining==0)
check('patch-no-unknown',not p.BeginRead(0x47) and not p.TryWrite(0x1581,1))
check('patch-partial',p.TryWrite(0x1580,0) and p.DispatcherBytes==1 and owner.RamByte(0x1580)==0)
check('patch-bad-byte-no-effect',not p.TryWrite(0x1581,0xff) and p.DispatcherBytes==1 and owner.RamByte(0x1581)==0)
check('patch-no-premature-key',not p.TryWrite(0x48,0xf1) and p.KeyBytes==0)
for k,v in enumerate(bytearray(dispatch)[1:]):check('patch-dispatch-byte',p.TryWrite(0x1581+k,v))
for k,v in enumerate([0xf1,0x70,0x15,0x80]):check('patch-key-byte',p.TryWrite(0x48+k,v))
for k,v in enumerate(bytearray(feature)):check('patch-feature-byte',p.TryWrite(0x1600+k,v))
check('patch-complete',p.Loaded and p.WrittenBytes==404 and p.FeatureBytes==375 and p.KeyBytes==4 and p.DispatcherBytes==25)
check('patch-range-preserved',owner.RamByte(0x157f)==0 and owner.RamByte(0x1599)==0 and owner.RamByte(0x1777)==0)
check('patch-no-overrun',not p.TryWrite(0x1777,1) and p.WrittenBytes==404)
check('patch-stored-feature-read',p.BeginRead(0x1618) and [p.ReadNext() for _ in range(4)]==[24,25,26,27])
check('patch-read-address-reselect',p.BeginRead(0x161c) and [p.ReadNext() for _ in range(4)]==[28,29,30,31])
check('patch-read-end-bound',p.BeginRead(0x1776) and p.ReadNext()==118 and p.ReadRemaining==0 and not p.BeginRead(0x1777))
for marker in [0x801570f1,1]:
    q=BlackwallImuPatchRam(owner,dhex,fhex,marker)
    check('patch-seed-read',q.BeginRead(0x48))
    check('patch-seed-value',sum(q.ReadNext()<<(8*k) for k in range(4))==marker)
    check('patch-no-dispatch-for-existing',not q.TryWrite(0x1580,0))
    for k,v in enumerate(bytearray(feature)):check('patch-existing-feature',q.TryWrite(0x1600+k,v))
    check('patch-existing-status',q.FeatureBytes==375 and q.Loaded==(marker==0x801570f1))
owner.Reset();p.Reset();check('patch-reset',p.WrittenBytes==p.ReadRemaining==0 and not p.Loaded and not p.BeginRead(0x48))
'''
harness.DRIVER=harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ",EXTRA+"Console.WriteLine('BLACKWALL_IMU_UNIT ")
if __name__=='__main__':harness.main()
