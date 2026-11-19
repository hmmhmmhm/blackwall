"""Check bounded GAF SRAM storage; no on-demand service/fusion."""
import verify_imu_gaf_parameters as gaf
harness=gaf.harness
EXTRA='''
ps=BlackwallImuPowerSave(own,'78563412')
check('store-bootstrap-time',ps.BeginRead(0x40))
for _ in range(4):ps.ReadNext()
ps.ReadControl();v=ps.ReadControl();check('store-bootstrap-control',ps.TryWriteControl(v&~4))
for k,v in enumerate([0x78,0x56,0x34,0x12]):check('store-bootstrap-write',ps.TryWriteTime(0x40+k,v))
q=BlackwallImuGafParameters(own,ps,fixture,True)
check('store-before-getter',not q.TryWrite(0x774,Array[Byte]([1])) and q.WrittenBytes==0)
for address,length in fields:
    check('store-select',q.BeginRead(address))
    for _ in range(length):q.ReadNext()
check('store-enabled',q.ConfigurationEnabled and q.Complete)
initial=[own.RamByte(k) for k in range(8192)]
ranges=fields+[(0x774,12),(0x974,12),(0x770,4),(0x76c,4),(0x780,12),(0x78c,12),(0x288,4),(0x290,4),(0x28c,4),(0x818,4)]
expected=list(initial);total=0
for index,(address,length) in enumerate(ranges):
    values=[(index*17+k)&255 for k in range(length)]
    check('store-span',q.TryWrite(address,Array[Byte](values)))
    expected[address:address+length]=values;total+=length
check('store-all-ram',expected==[own.RamByte(k) for k in range(8192)] and q.WrittenBytes==total and q.WriteTransactions==len(ranges))
check('store-cross-known-fields',q.TryWrite(0x77f,Array[Byte]([0x12,0x34])))
expected[0x77f:0x781]=[0x12,0x34];total+=2
check('store-cross-values',expected==[own.RamByte(k) for k in range(8192)])
for address,values in [(0x76b,[0,0]),(0x797,[1,2]),(0x2000,[1]),(-1,[1]),(0x774,[]),(4,[2])]:
    before=(q.WrittenBytes,q.WriteTransactions,q.History)
    check('store-reject-atomic',not q.TryWrite(address,Array[Byte](values)) and before==(q.WrittenBytes,q.WriteTransactions,q.History) and expected==[own.RamByte(k) for k in range(8192)])
check('store-clock-register-unsupported',not q.TryWrite(0xa2a2,Array[Byte]([0xa5])) and q.WrittenBytes==total)
q.Reset();check('store-reset',q.WrittenBytes==q.WriteTransactions==0 and q.History=='' and not q.Complete)
check('store-after-reset',not q.TryWrite(0x774,Array[Byte]([1])))
r=BlackwallImuGafParameters(own,ps,fixture)
for address,length in fields:
    r.BeginRead(address)
    for _ in range(length):r.ReadNext()
check('store-default-disabled',r.Complete and not r.ConfigurationEnabled and not r.TryWrite(0x774,Array[Byte]([1])))
'''
harness.DRIVER=harness.DRIVER.replace("Console.WriteLine('BLACKWALL_IMU_UNIT ",EXTRA+"Console.WriteLine('BLACKWALL_IMU_UNIT ")
if __name__=='__main__':harness.main()
